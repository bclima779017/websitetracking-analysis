"""
Shared browser session for the diagnostic pipeline.

Opens a single Chromium instance and exposes helpers to run multiple
pipeline stages without relaunching the browser. This eliminates ~6-8s
of repeated browser startup and ~10s of redundant page navigation.

Architecture:
    browser (1 instance)
    ├── context_main   → network interception + dataLayer extraction (same page)
    └── context_attr   → attribution testing (separate context with UTM URL)

All Playwright calls run in the same thread (greenlet constraint).
Speed gains come from shared browser + page reuse, not thread parallelism.
"""

from __future__ import annotations

import random
import time
from typing import Any

from playwright.sync_api import sync_playwright, Playwright, Browser, BrowserContext, Page

from .config import NetworkRequest, DataLayerResult, AttributionResult
from .config import USER_AGENTS, DEFAULT_UTM_PARAMS, DEFAULT_CLICK_IDS, load_ga4_taxonomy


# ---------------------------------------------------------------------------
# Stealth
# ---------------------------------------------------------------------------

_STEALTH_JS = """
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

_SCROLL_STEPS_JS = """
async () => {
    const delay = ms => new Promise(r => setTimeout(r, ms));
    const height = document.body.scrollHeight;
    const steps = [0.25, 0.5, 0.75, 1.0];
    for (const pct of steps) {
        window.scrollTo({ top: height * pct, behavior: 'smooth' });
        await delay(800 + Math.random() * 400);
    }
    window.scrollTo({ top: 0, behavior: 'smooth' });
    await delay(500);
}
"""


def _apply_stealth(page: Page) -> None:
    try:
        from playwright_stealth import stealth_sync
        stealth_sync(page)
    except ImportError:
        page.add_init_script(_STEALTH_JS)


def _new_context(browser: Browser) -> BrowserContext:
    return browser.new_context(
        user_agent=random.choice(USER_AGENTS),
        viewport={"width": 1920, "height": 1080},
        ignore_https_errors=True,
        locale="pt-BR",
    )


# ---------------------------------------------------------------------------
# Pipeline session — single browser, multiple stages
# ---------------------------------------------------------------------------

class PipelineSession:
    """
    Manages a shared Chromium browser for the full diagnostic pipeline.

    Usage (sync, from ThreadPoolExecutor):
        session = PipelineSession()
        session.open()
        requests = session.intercept_network(url)   # stage 2
        dl_data  = session.inspect_datalayer()       # stage 5 (same page!)
        attr     = session.test_attribution(url)     # stage 3 (new context)
        session.close()
    """

    def __init__(self) -> None:
        self._pw: Playwright | None = None
        self._browser: Browser | None = None
        self._main_ctx: BrowserContext | None = None
        self._main_page: Page | None = None

    # -- lifecycle ----------------------------------------------------------

    def open(self) -> None:
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=True)

    def close(self) -> None:
        if self._main_ctx:
            try:
                self._main_ctx.close()
            except Exception:
                pass
        if self._browser:
            try:
                self._browser.close()
            except Exception:
                pass
        if self._pw:
            try:
                self._pw.stop()
            except Exception:
                pass

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *exc):
        self.close()

    # -- stage 2: network interception (CDP) --------------------------------

    def intercept_network(self, url: str) -> list[NetworkRequest]:
        """Navigate to *url*, capture all network traffic via CDP, scroll, return requests."""
        captured: list[NetworkRequest] = []
        pending: dict[str, dict[str, Any]] = {}

        self._main_ctx = _new_context(self._browser)
        self._main_page = self._main_ctx.new_page()
        _apply_stealth(self._main_page)

        page = self._main_page

        # CDP
        cdp = self._main_ctx.new_cdp_session(page)
        cdp.send("Network.enable")

        def on_request(params: dict) -> None:
            rid = params.get("requestId", "")
            req = params.get("request", {})
            pending[rid] = {
                "url": req.get("url", ""),
                "method": req.get("method", "GET"),
                "resource_type": params.get("type", "Other").lower(),
                "timestamp": time.time(),
            }

        def on_response(params: dict) -> None:
            rid = params.get("requestId", "")
            info = pending.pop(rid, None)
            if not info:
                return
            resp = params.get("response", {})
            hdrs = {k.lower(): v for k, v in resp.get("headers", {}).items()}
            try:
                captured.append(NetworkRequest(
                    url=info["url"], method=info["method"],
                    status=resp.get("status", 0), headers=hdrs,
                    resource_type=info["resource_type"], timestamp=info["timestamp"],
                ))
            except Exception:
                pass

        def on_failed(params: dict) -> None:
            rid = params.get("requestId", "")
            info = pending.pop(rid, None)
            if not info:
                return
            try:
                captured.append(NetworkRequest(
                    url=info["url"], method=info["method"],
                    status=0, headers={},
                    resource_type=info["resource_type"], timestamp=info["timestamp"],
                ))
            except Exception:
                pass

        cdp.on("Network.requestWillBeSent", on_request)
        cdp.on("Network.responseReceived", on_response)
        cdp.on("Network.loadingFailed", on_failed)

        # Navigate
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
        except Exception:
            pass

        page.wait_for_timeout(3000)

        # Scroll
        try:
            page.evaluate(_SCROLL_STEPS_JS)
        except Exception:
            pass

        # Final collection window
        page.wait_for_timeout(4000)

        cdp.detach()
        return captured

    # -- stage 5: dataLayer (reuses already-rendered page) ------------------

    def inspect_datalayer(self) -> DataLayerResult:
        """Extract dataLayer from the page already loaded by intercept_network()."""
        result = DataLayerResult(datalayer_exists=False)
        page = self._main_page
        if not page:
            return result

        taxonomy = load_ga4_taxonomy()
        standard_events = list(taxonomy.get("standard_events", {}).keys())
        required_fields = taxonomy.get("ecommerce_fields", {}).get("required", [])
        recommended_fields = taxonomy.get("ecommerce_fields", {}).get("recommended", [])

        # Extract dataLayer (page is already rendered + scrolled)
        try:
            events = page.evaluate("() => window.dataLayer || []")
        except Exception:
            return result

        if not events:
            return result

        result.datalayer_exists = True
        result.datalayer_events_count = len(events)

        all_names: set[str] = set()
        interaction = False
        ecommerce = False
        samples: list[dict] = []

        for ev in events[:10]:
            if not isinstance(ev, dict):
                continue
            name = ev.get("event")
            if name:
                all_names.add(name)
                if name in standard_events and name not in result.standard_events_detected:
                    result.standard_events_detected.append(name)
                if name in ("click", "scroll", "form_start", "form_submit"):
                    interaction = True
                if "ecommerce" in ev or "items" in ev:
                    ecommerce = True
            if len(samples) < 5:
                samples.append(ev)

        result.interaction_tracking_active = interaction
        result.ecommerce_items_array = ecommerce
        result.sample_events = samples

        # Try add-to-cart interaction
        try:
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
            clicked = False
            for sel in selectors:
                try:
                    el = page.locator(sel).first
                    if el.is_visible(timeout=1000):
                        el.click(timeout=1000)
                        clicked = True
                        break
                except Exception:
                    continue

            if clicked:
                page.wait_for_timeout(2000)
                try:
                    updated = page.evaluate("() => window.dataLayer || []")
                    if len(updated) > len(events):
                        result.datalayer_events_count = len(updated)
                        for ev in updated[len(events):]:
                            if isinstance(ev, dict):
                                name = ev.get("event")
                                if name and name not in all_names:
                                    all_names.add(name)
                                    result.standard_events_detected.append(name)
                except Exception:
                    pass
        except Exception:
            pass

        # Validate e-commerce schema
        if ecommerce or "ecommerce" in str(events):
            for ev in samples:
                if not isinstance(ev, dict):
                    continue
                items = ev.get("ecommerce", {}).get("items", [])
                if items and isinstance(items, list):
                    first = items[0]
                    if isinstance(first, dict):
                        for f in required_fields:
                            if f in first and f not in result.required_fields_present:
                                result.required_fields_present.append(f)
                        for f in recommended_fields:
                            if f not in first and f not in result.missing_recommended_fields:
                                result.missing_recommended_fields.append(f)

            if len(result.required_fields_present) >= len(required_fields):
                result.ga4_schema_compliant = True

        return result

    # -- stage 3: attribution (separate context, parallel-safe) -------------

    def test_attribution(self, url: str) -> AttributionResult:
        """Test attribution in a fresh context (can run parallel to inspect_datalayer)."""
        from urllib.parse import urlparse, urlunparse

        result = AttributionResult()
        ctx = _new_context(self._browser)
        page = ctx.new_page()
        _apply_stealth(page)

        # Build test URL
        parsed = urlparse(url)
        base = urlunparse((parsed.scheme, parsed.netloc, parsed.path or "/", "", "", ""))
        params = "&".join(f"{k}={v}" for k, v in DEFAULT_UTM_PARAMS.items())
        params += "&gclid=" + DEFAULT_CLICK_IDS["gclid"]
        params += "&fbclid=" + DEFAULT_CLICK_IDS["fbclid"]
        test_url = base + "?" + params

        response = None
        try:
            response = page.goto(test_url, wait_until="domcontentloaded", timeout=15000)
        except Exception:
            pass

        page.wait_for_timeout(3000)

        final_url = page.url

        result.redirect_strips_params = not any(
            p in final_url for p in ["utm_source", "gclid", "fbclid"]
        )
        if response:
            status = response.status
            if status in (301, 302, 303, 307, 308):
                result.redirect_type = f"{status}"

        result.utm_persistence_on_redirect = test_url == final_url

        cookies = ctx.cookies()
        cookie_dict = {c["name"]: c for c in cookies}

        if "_gcl_aw" in cookie_dict:
            result.google_click_id_cookie_dropped = True
            result.cookies_found.append("_gcl_aw")
        else:
            result.cookies_missing.append("_gcl_aw")

        if "_fbc" in cookie_dict:
            result.meta_click_id_cookie_dropped = True
            result.cookies_found.append("_fbc")
        else:
            result.cookies_missing.append("_fbc")

        for name in ["_fbp", "_ga", "_gat", "_gcl_au"]:
            if name in cookie_dict and name not in result.cookies_found:
                result.cookies_found.append(name)

        try:
            ls = page.evaluate("() => Object.entries(localStorage)")
            for key, _ in ls:
                if "utm_" in key.lower():
                    result.localstorage_utm_saved = True
                    result.localStorage_keys.append(key)
        except Exception:
            pass

        ctx.close()
        return result
