"""
Standalone subprocess: runs all browser-dependent pipeline stages in one process.

Completely isolates Playwright from Streamlit's event loop / greenlet conflicts.
Single Chromium launch, single navigation, CDP capture, stealth, scroll.

Usage:
    # Legacy single-page mode
    python run_browser_pipeline.py <url> <domain>

    # Multi-page mode (per-page DataLayer analysis)
    python run_browser_pipeline.py <url> <domain> --pages '{"home":"url1","product":"url2"}'

Output:
    JSON dict with keys: requests, dl_data, attr_data, per_page_dl
    Printed to stdout. Errors to stderr.
"""

import sys
import json
import time
import random
import asyncio
from pathlib import Path
from urllib.parse import urlparse, urlunparse

# Add project root to sys.path so tools.helpers.* imports work
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
]

DEFAULT_UTM_PARAMS = {
    "utm_source": "google",
    "utm_medium": "cpc",
    "utm_campaign": "test_campaign",
    "utm_content": "test_content",
    "utm_term": "test_keyword",
}

DEFAULT_CLICK_IDS = {
    "gclid": "test_gclid_123456789",
    "fbclid": "test_fbclid_123456789",
}

STEALTH_JS = """
    Object.defineProperty(navigator, 'webdriver', { get: () => false });
    window.chrome = { runtime: {} };
    const origQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (params) =>
        params.name === 'notifications'
            ? Promise.resolve({ state: Notification.permission })
            : origQuery(params);
    Object.defineProperty(navigator, 'plugins', {
        get: () => [1, 2, 3, 4, 5],
    });
    Object.defineProperty(navigator, 'languages', {
        get: () => ['pt-BR', 'pt', 'en-US', 'en'],
    });
"""

SCROLL_JS = """
async () => {
    const delay = ms => new Promise(r => setTimeout(r, ms));
    const height = document.body.scrollHeight;
    for (const pct of [0.25, 0.5, 0.75, 1.0]) {
        window.scrollTo({ top: height * pct, behavior: 'smooth' });
        await delay(800 + Math.random() * 400);
    }
    window.scrollTo({ top: 0, behavior: 'smooth' });
    await delay(500);
}
"""


# ---------------------------------------------------------------------------
# Stealth helper
# ---------------------------------------------------------------------------

async def apply_stealth(page):
    try:
        from playwright_stealth import stealth_async
        await stealth_async(page)
    except ImportError:
        await page.add_init_script(STEALTH_JS)


# ---------------------------------------------------------------------------
# Stage 2: Network interception via CDP
# ---------------------------------------------------------------------------

async def intercept_network(page, cdp_session, url):
    """Navigate, scroll, capture all network traffic via CDP. Returns list[dict]."""
    captured = []
    pending = {}

    def on_request(params):
        rid = params.get("requestId", "")
        req = params.get("request", {})
        pending[rid] = {
            "url": req.get("url", ""),
            "method": req.get("method", "GET"),
            "resource_type": params.get("type", "Other").lower(),
            "timestamp": time.time(),
        }

    def on_response(params):
        rid = params.get("requestId", "")
        info = pending.pop(rid, None)
        if not info:
            return
        resp = params.get("response", {})
        hdrs = {k.lower(): v for k, v in resp.get("headers", {}).items()}
        captured.append({
            "url": info["url"],
            "method": info["method"],
            "status": resp.get("status", 0),
            "headers": hdrs,
            "resource_type": info["resource_type"],
            "timestamp": info["timestamp"],
        })

    def on_failed(params):
        rid = params.get("requestId", "")
        info = pending.pop(rid, None)
        if not info:
            return
        captured.append({
            "url": info["url"],
            "method": info["method"],
            "status": 0,
            "headers": {},
            "resource_type": info["resource_type"],
            "timestamp": info["timestamp"],
        })

    cdp_session.on("Network.requestWillBeSent", on_request)
    cdp_session.on("Network.responseReceived", on_response)
    cdp_session.on("Network.loadingFailed", on_failed)

    await cdp_session.send("Network.enable")

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
    except Exception:
        pass

    await asyncio.sleep(3)

    try:
        await page.evaluate(SCROLL_JS)
    except Exception:
        pass

    await asyncio.sleep(4)

    return captured


# ---------------------------------------------------------------------------
# Stage 5: DataLayer (reuses same page — no re-navigation)
# ---------------------------------------------------------------------------

async def inspect_datalayer(page):
    """Extract dataLayer from the already-rendered page. Returns dict."""
    result = {
        "datalayer_exists": False,
        "datalayer_events_count": 0,
        "standard_events_detected": [],
        "interaction_tracking_active": False,
        "ga4_schema_compliant": False,
        "ecommerce_items_array": False,
        "required_fields_present": [],
        "missing_required_fields": [],
        "missing_recommended_fields": [],
        "sample_events": [],
    }

    try:
        events = await page.evaluate("() => window.dataLayer || []")
    except Exception:
        return result

    if not events:
        return result

    result["datalayer_exists"] = True
    result["datalayer_events_count"] = len(events)

    standard_ga4 = [
        "page_view", "view_item", "view_item_list", "select_item",
        "add_to_cart", "remove_from_cart", "view_cart", "begin_checkout",
        "add_payment_info", "add_shipping_info", "purchase", "refund",
        "login", "sign_up", "search", "select_content", "share",
        "generate_lead", "select_promotion", "view_promotion",
    ]
    required_fields = ["item_id", "item_name", "price", "quantity"]
    recommended_fields = [
        "item_brand", "item_category", "item_category2",
        "item_variant", "discount", "coupon", "index",
    ]

    all_names = set()
    interaction = False
    ecommerce = False
    samples = []

    for ev in events[:10]:
        if not isinstance(ev, dict):
            continue
        name = ev.get("event")
        if name:
            all_names.add(name)
            if name in standard_ga4 and name not in result["standard_events_detected"]:
                result["standard_events_detected"].append(name)
            if name in ("click", "scroll", "form_start", "form_submit"):
                interaction = True
            if "ecommerce" in ev or "items" in ev:
                ecommerce = True
        if len(samples) < 5:
            samples.append(ev)

    result["interaction_tracking_active"] = interaction
    result["ecommerce_items_array"] = ecommerce
    result["sample_events"] = samples

    # Try add-to-cart interaction
    selectors = [
        "button:has-text('Add to Cart')",
        "button:has-text('add to cart')",
        "button:has-text('Adicionar ao Carrinho')",
        "button:has-text('adicionar ao carrinho')",
        "button:has-text('Comprar')",
        "[data-action='add-to-cart']",
        "[class*='add-to-cart']",
        "[class*='buy-button']",
    ]
    for sel in selectors:
        try:
            el = page.locator(sel).first
            if await el.is_visible(timeout=1000):
                await el.click(timeout=1000)
                await asyncio.sleep(2)
                updated = await page.evaluate("() => window.dataLayer || []")
                if len(updated) > len(events):
                    result["datalayer_events_count"] = len(updated)
                    for ev in updated[len(events):]:
                        if isinstance(ev, dict):
                            name = ev.get("event")
                            if name and name not in all_names:
                                all_names.add(name)
                                result["standard_events_detected"].append(name)
                break
        except Exception:
            continue

    # Validate e-commerce schema
    if ecommerce or "ecommerce" in str(events):
        for ev in samples:
            if not isinstance(ev, dict):
                continue
            items = ev.get("ecommerce", {}).get("items", [])
            if items and isinstance(items, list) and isinstance(items[0], dict):
                first = items[0]
                for f in required_fields:
                    if f in first and f not in result["required_fields_present"]:
                        result["required_fields_present"].append(f)
                for f in recommended_fields:
                    if f not in first and f not in result["missing_recommended_fields"]:
                        result["missing_recommended_fields"].append(f)

        missing_req = [f for f in required_fields if f not in result["required_fields_present"]]
        result["missing_required_fields"] = missing_req
        if len(result["required_fields_present"]) >= len(required_fields):
            result["ga4_schema_compliant"] = True

    return result


# ---------------------------------------------------------------------------
# Per-page DataLayer inspection (new context per page)
# ---------------------------------------------------------------------------

DATALAYER_EXTRACT_JS = """
() => {
    const dl = window.dataLayer || [];
    const events = [];
    const eventNames = [];
    let ecommerce = false;
    const requiredFields = ['item_id', 'item_name', 'price', 'quantity'];
    const foundRequired = new Set();
    let ga4Compliant = false;

    for (const ev of dl) {
        if (typeof ev !== 'object' || ev === null) continue;
        const name = ev.event;
        if (name) eventNames.push(name);
        if (ev.ecommerce || ev.items) {
            ecommerce = true;
            const items = (ev.ecommerce && ev.ecommerce.items) || ev.items || [];
            if (Array.isArray(items) && items.length > 0 && typeof items[0] === 'object') {
                const first = items[0];
                for (const f of requiredFields) {
                    if (f in first) foundRequired.add(f);
                }
            }
        }
        if (events.length < 5) events.push(ev);
    }

    if (foundRequired.size >= requiredFields.length) ga4Compliant = true;

    return {
        datalayer_exists: dl.length > 0,
        events_count: dl.length,
        event_names: eventNames,
        ecommerce_items_array: ecommerce,
        ga4_schema_compliant: ga4Compliant,
        required_fields_present: Array.from(foundRequired),
        missing_required_fields: requiredFields.filter(f => !foundRequired.has(f)),
        sample_events: events,
    };
}
"""


async def inspect_page_datalayer(browser, url):
    """Navigate to a page, extract dataLayer, return dict with analysis.

    Creates a fresh browser context for isolation. Handles inaccessible pages
    (login walls, errors) gracefully by returning accessible=False.
    """
    result = {
        "url": url,
        "accessible": False,
        "datalayer_exists": False,
        "events_detected": [],
        "ecommerce_items_array": False,
        "ga4_schema_compliant": False,
        "required_fields_present": [],
        "missing_required_fields": [],
        "sample_events": [],
    }

    context = await browser.new_context(
        user_agent=random.choice(USER_AGENTS),
        viewport={"width": 1920, "height": 1080},
        ignore_https_errors=True,
        locale="pt-BR",
    )

    try:
        page = await context.new_page()
        await apply_stealth(page)

        response = None
        try:
            response = await page.goto(url, wait_until="domcontentloaded", timeout=15000)
        except Exception:
            return result

        if response and response.status >= 400:
            return result

        result["accessible"] = True

        # Wait for dynamic content + scroll
        await asyncio.sleep(3)
        try:
            await page.evaluate(SCROLL_JS)
        except Exception:
            pass
        await asyncio.sleep(2)

        # Extract dataLayer
        try:
            dl_info = await page.evaluate(DATALAYER_EXTRACT_JS)
        except Exception:
            return result

        result["datalayer_exists"] = dl_info.get("datalayer_exists", False)
        result["events_detected"] = dl_info.get("event_names", [])
        result["ecommerce_items_array"] = dl_info.get("ecommerce_items_array", False)
        result["ga4_schema_compliant"] = dl_info.get("ga4_schema_compliant", False)
        result["required_fields_present"] = dl_info.get("required_fields_present", [])
        result["missing_required_fields"] = dl_info.get("missing_required_fields", [])
        result["sample_events"] = dl_info.get("sample_events", [])

    finally:
        await context.close()

    return result


# ---------------------------------------------------------------------------
# Stage 3: Attribution (separate context, same browser)
# ---------------------------------------------------------------------------

async def test_attribution(browser, url):
    """Test UTM persistence, cookies, localStorage. Returns dict."""
    result = {
        "utm_persistence_on_redirect": False,
        "redirect_strips_params": False,
        "redirect_type": None,
        "google_click_id_cookie_dropped": False,
        "meta_click_id_cookie_dropped": False,
        "localstorage_utm_saved": False,
        "cookies_found": [],
        "cookies_missing": [],
        "localStorage_keys": [],
    }

    context = await browser.new_context(
        user_agent=random.choice(USER_AGENTS),
        viewport={"width": 1920, "height": 1080},
        ignore_https_errors=True,
        locale="pt-BR",
    )
    page = await context.new_page()
    await apply_stealth(page)

    parsed = urlparse(url)
    base = urlunparse((parsed.scheme, parsed.netloc, parsed.path or "/", "", "", ""))
    params = "&".join(f"{k}={v}" for k, v in DEFAULT_UTM_PARAMS.items())
    params += "&gclid=" + DEFAULT_CLICK_IDS["gclid"]
    params += "&fbclid=" + DEFAULT_CLICK_IDS["fbclid"]
    test_url = base + "?" + params

    response = None
    try:
        response = await page.goto(test_url, wait_until="domcontentloaded", timeout=15000)
    except Exception:
        pass

    await asyncio.sleep(3)

    final_url = page.url
    result["redirect_strips_params"] = not any(
        p in final_url for p in ["utm_source", "gclid", "fbclid"]
    )
    if response:
        status = response.status
        if status in (301, 302, 303, 307, 308):
            result["redirect_type"] = str(status)

    result["utm_persistence_on_redirect"] = test_url == final_url

    cookies = await context.cookies()
    cookie_dict = {c["name"]: c for c in cookies}

    if "_gcl_aw" in cookie_dict:
        result["google_click_id_cookie_dropped"] = True
        result["cookies_found"].append("_gcl_aw")
    else:
        result["cookies_missing"].append("_gcl_aw")

    if "_fbc" in cookie_dict:
        result["meta_click_id_cookie_dropped"] = True
        result["cookies_found"].append("_fbc")
    else:
        result["cookies_missing"].append("_fbc")

    for name in ["_fbp", "_ga", "_gat", "_gcl_au"]:
        if name in cookie_dict and name not in result["cookies_found"]:
            result["cookies_found"].append(name)

    try:
        ls = await page.evaluate("() => Object.entries(localStorage)")
        for key, _ in ls:
            if "utm_" in key.lower():
                result["localstorage_utm_saved"] = True
                result["localStorage_keys"].append(key)
    except Exception:
        pass

    await context.close()
    return result


# ---------------------------------------------------------------------------
# Spider: fill funnel gaps using existing browser (before other stages)
# ---------------------------------------------------------------------------

async def spider_for_gaps(
    browser,
    base_url: str,
    existing_pages: dict[str, str],
    gaps: list[str],
) -> dict:
    """BFS spider to fill funnel stage gaps, reusing the subprocess browser.

    Imports classification logic from page_selector.py (pure functions +
    async spider). Merges spider discoveries with existing sitemap pages.

    Args:
        browser: Already-launched Playwright Browser instance.
        existing_pages: {stage: url} from sitemap phase.
        gaps: Stage names that still need a candidate page.

    Returns:
        Dict with 'funnel_pages' ({stage: ClassifiedUrl dict}) and
        'spider_stats' ({spider_urls: int}).
    """
    from tools.helpers.discover.page_selector import (
        classify_url,
        _select_best_per_stage,
        _spider_site,
    )
    from tools.helpers.shared.config import (
        ClassifiedUrl,
        FunnelStage,
        load_funnel_heuristics,
    )

    heuristics = load_funnel_heuristics()

    # Rebuild already_classified from existing_pages
    already_classified: dict[FunnelStage, list[ClassifiedUrl]] = {}
    for stage_key, url in existing_pages.items():
        try:
            stage_enum = FunnelStage(stage_key)
        except ValueError:
            continue
        classified = classify_url(url, heuristics)
        classified.source = "sitemap"
        classified.stage = stage_enum
        already_classified.setdefault(stage_enum, []).append(classified)

    # Run BFS spider (async — works here because we're in a real asyncio.run)
    spider_results = await _spider_site(
        base_url, browser, already_classified, heuristics,
    )

    # Merge spider results into candidates
    for classified in spider_results:
        if classified.stage != FunnelStage.OTHER:
            already_classified.setdefault(classified.stage, []).append(classified)

    # Select best per stage
    best = _select_best_per_stage(already_classified)

    # Serialize to plain dicts
    funnel_pages = {}
    for stage_key, cu in best.items():
        if cu is not None:
            funnel_pages[stage_key] = {
                "url": cu.url,
                "stage": cu.stage.value if hasattr(cu.stage, "value") else cu.stage,
                "confidence": cu.confidence,
                "source": cu.source or "spider",
                "signals": cu.classification_signals,
            }

    return {
        "funnel_pages": funnel_pages,
        "spider_stats": {"spider_urls": len(spider_results)},
    }


# ---------------------------------------------------------------------------
# Main: single browser, all stages, JSON output
# ---------------------------------------------------------------------------

async def run_all(
    url: str,
    domain: str,
    funnel_pages: dict[str, str] | None = None,
    gaps: list[str] | None = None,
) -> dict:
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        # Spider phase: fill funnel gaps before other stages
        spider_result: dict = {}
        final_funnel_pages = dict(funnel_pages or {})
        if gaps:
            print(f"Spider: filling gaps {gaps}", file=sys.stderr)
            try:
                spider_result = await spider_for_gaps(
                    browser, url, final_funnel_pages, gaps,
                )
                for stage_key, page_info in spider_result.get("funnel_pages", {}).items():
                    if page_info and stage_key not in final_funnel_pages:
                        final_funnel_pages[stage_key] = page_info["url"]
                print(
                    f"Spider: found {spider_result.get('spider_stats', {}).get('spider_urls', 0)} pages",
                    file=sys.stderr,
                )
            except Exception as e:
                print(f"Spider failed: {type(e).__name__}: {e}", file=sys.stderr)

        # Main context for network + dataLayer
        context = await browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            viewport={"width": 1920, "height": 1080},
            ignore_https_errors=True,
            locale="pt-BR",
        )
        page = await context.new_page()
        await apply_stealth(page)

        cdp = await context.new_cdp_session(page)

        # Stage 2: Network interception
        requests = await intercept_network(page, cdp, url)
        await cdp.detach()

        # Stage 5: DataLayer (same page, no re-navigation — legacy single-page)
        dl_data = await inspect_datalayer(page)

        await context.close()

        # Stage 3: Attribution (separate context)
        attr_data = await test_attribution(browser, url)

        # Per-page DataLayer analysis (uses merged pages including spider results)
        per_page_dl = {}
        if final_funnel_pages:
            for stage, page_url in final_funnel_pages.items():
                print(f"Inspecting DataLayer: {stage} -> {page_url}", file=sys.stderr)
                per_page_dl[stage] = await inspect_page_datalayer(browser, page_url)

        await browser.close()

    return {
        "requests": requests,
        "dl_data": dl_data,
        "attr_data": attr_data,
        "per_page_dl": per_page_dl,
        "funnel_pages": spider_result.get("funnel_pages", {}),
        "spider_stats": spider_result.get("spider_stats", {}),
    }


def main():
    if len(sys.argv) < 3:
        print(json.dumps({"requests": [], "dl_data": {}, "attr_data": {}, "per_page_dl": {}}))
        return

    url = sys.argv[1]
    domain = sys.argv[2]

    # Parse optional --pages and --gaps arguments
    funnel_pages = None
    gaps = None
    i = 3
    while i < len(sys.argv):
        if sys.argv[i] == "--pages" and i + 1 < len(sys.argv):
            try:
                funnel_pages = json.loads(sys.argv[i + 1])
            except json.JSONDecodeError as e:
                print(f"Invalid --pages JSON: {e}", file=sys.stderr)
            i += 2
        elif sys.argv[i] == "--gaps" and i + 1 < len(sys.argv):
            try:
                gaps = json.loads(sys.argv[i + 1])
            except json.JSONDecodeError as e:
                print(f"Invalid --gaps JSON: {e}", file=sys.stderr)
            i += 2
        else:
            i += 1

    try:
        result = asyncio.run(run_all(url, domain, funnel_pages=funnel_pages, gaps=gaps))
    except Exception as e:
        print(f"Pipeline error: {type(e).__name__}: {e}", file=sys.stderr)
        result = {"requests": [], "dl_data": {}, "attr_data": {}, "per_page_dl": {}}

    print(json.dumps(result, default=str))


if __name__ == "__main__":
    main()
