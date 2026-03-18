"""
Standalone subprocess: runs all browser-dependent pipeline stages in one process.

Completely isolates Playwright from Streamlit's event loop / greenlet conflicts.
Single Chromium launch, single navigation, CDP capture, stealth, scroll.

Usage:
    python run_browser_pipeline.py <url> <domain>

Output:
    JSON dict with keys: requests, dl_data, attr_data
    Printed to stdout. Errors to stderr.
"""

import sys
import json
import time
import random
import asyncio
from urllib.parse import urlparse, urlunparse


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
# Main: single browser, all stages, JSON output
# ---------------------------------------------------------------------------

async def run_all(url: str, domain: str) -> dict:
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

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

        # Stage 5: DataLayer (same page, no re-navigation)
        dl_data = await inspect_datalayer(page)

        await context.close()

        # Stage 3: Attribution (separate context)
        attr_data = await test_attribution(browser, url)

        await browser.close()

    return {
        "requests": requests,
        "dl_data": dl_data,
        "attr_data": attr_data,
    }


def main():
    if len(sys.argv) < 3:
        print(json.dumps({"requests": [], "dl_data": {}, "attr_data": {}}))
        return

    url = sys.argv[1]
    domain = sys.argv[2]

    try:
        result = asyncio.run(run_all(url, domain))
    except Exception as e:
        print(f"Pipeline error: {type(e).__name__}: {e}", file=sys.stderr)
        result = {"requests": [], "dl_data": {}, "attr_data": {}}

    print(json.dumps(result))


if __name__ == "__main__":
    main()
