"""
Network traffic interception module — Stage 2 of the diagnostic pipeline.

Captures all network requests during page load using Playwright + CDP
(Chrome DevTools Protocol) for complete network visibility, including
sendBeacon, preflight CORS, and internal redirects.

Uses playwright-stealth to bypass bot detection and deadline-based
collection with realistic page interaction (scroll) instead of
fragile networkidle waits.

Provides both async and sync versions for compatibility with different runners
(async for direct use, sync for Streamlit via ThreadPoolExecutor).
"""

from __future__ import annotations

import random
import time
from typing import Any

from ..shared.config import NetworkRequest, USER_AGENTS


# ---------------------------------------------------------------------------
# Shared interaction helpers
# ---------------------------------------------------------------------------

_SCROLL_STEPS_JS = """
async () => {
    const delay = ms => new Promise(r => setTimeout(r, ms));
    const height = document.body.scrollHeight;
    const steps = [0.25, 0.5, 0.75, 1.0];
    for (const pct of steps) {
        window.scrollTo({ top: height * pct, behavior: 'smooth' });
        await delay(800 + Math.random() * 400);
    }
    // Scroll back to top (some tags fire on scroll-up)
    window.scrollTo({ top: 0, behavior: 'smooth' });
    await delay(500);
}
"""


def _apply_stealth(page: Any) -> None:
    """Apply stealth patches to mask headless browser fingerprint."""
    try:
        from playwright_stealth import stealth_sync
        stealth_sync(page)
    except ImportError:
        # Fallback: apply minimal stealth patches via JS
        page.add_init_script("""
            // Override navigator.webdriver
            Object.defineProperty(navigator, 'webdriver', { get: () => false });
            // Override chrome runtime
            window.chrome = { runtime: {} };
            // Override permissions query
            const origQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (params) =>
                params.name === 'notifications'
                    ? Promise.resolve({ state: Notification.permission })
                    : origQuery(params);
            // Override plugins length
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });
            // Override languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['pt-BR', 'pt', 'en-US', 'en'],
            });
        """)


async def _apply_stealth_async(page: Any) -> None:
    """Apply stealth patches to mask headless browser fingerprint (async)."""
    try:
        from playwright_stealth import stealth_async
        await stealth_async(page)
    except ImportError:
        await page.add_init_script("""
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
        """)


# ---------------------------------------------------------------------------
# Sync version (used from Streamlit via ThreadPoolExecutor)
# ---------------------------------------------------------------------------

def intercept_network_traffic_sync(url: str) -> list[NetworkRequest]:
    """
    Synchronous network interception using Playwright sync API + CDP.

    Uses CDP Network.enable for complete request capture (including beacons,
    preflight CORS, redirects). Applies stealth patches and performs
    realistic page interaction (scroll) to trigger lazy-loaded tags.

    Args:
        url: Full URL to navigate to (e.g., https://example.com)

    Returns:
        List of NetworkRequest objects with URL, method, status, headers, resource_type
    """
    from playwright.sync_api import sync_playwright

    captured: list[NetworkRequest] = []
    # Track request IDs for pairing requests with responses
    pending_requests: dict[str, dict[str, Any]] = {}

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)

            context = browser.new_context(
                user_agent=random.choice(USER_AGENTS),
                viewport={"width": 1920, "height": 1080},
                ignore_https_errors=True,
                locale="pt-BR",
            )

            page = context.new_page()

            # Apply stealth patches before navigation
            _apply_stealth(page)

            # --- CDP Network interception ---
            cdp = context.new_cdp_session(page)
            cdp.send("Network.enable")

            def on_request_will_be_sent(params: dict) -> None:
                """Track outgoing requests."""
                request_id = params.get("requestId", "")
                request_data = params.get("request", {})
                pending_requests[request_id] = {
                    "url": request_data.get("url", ""),
                    "method": request_data.get("method", "GET"),
                    "resource_type": params.get("type", "Other").lower(),
                    "timestamp": time.time(),
                }

            def on_response_received(params: dict) -> None:
                """Pair response with its request and capture."""
                request_id = params.get("requestId", "")
                req_info = pending_requests.pop(request_id, None)
                if not req_info:
                    return

                response = params.get("response", {})
                headers = response.get("headers", {})
                # Normalize header keys to lowercase
                headers_lower = {k.lower(): v for k, v in headers.items()}

                try:
                    captured.append(NetworkRequest(
                        url=req_info["url"],
                        method=req_info["method"],
                        status=response.get("status", 0),
                        headers=headers_lower,
                        resource_type=req_info["resource_type"],
                        timestamp=req_info["timestamp"],
                    ))
                except Exception:
                    pass

            def on_loading_failed(params: dict) -> None:
                """Capture failed requests (blocked, CORS, timeout)."""
                request_id = params.get("requestId", "")
                req_info = pending_requests.pop(request_id, None)
                if not req_info:
                    return

                try:
                    captured.append(NetworkRequest(
                        url=req_info["url"],
                        method=req_info["method"],
                        status=0,  # 0 = failed/blocked
                        headers={},
                        resource_type=req_info["resource_type"],
                        timestamp=req_info["timestamp"],
                    ))
                except Exception:
                    pass

            cdp.on("Network.requestWillBeSent", on_request_will_be_sent)
            cdp.on("Network.responseReceived", on_response_received)
            cdp.on("Network.loadingFailed", on_loading_failed)

            # --- Navigate with domcontentloaded (not networkidle) ---
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
            except Exception:
                pass  # Continue even if navigation times out

            # Wait for initial scripts/tags to fire
            page.wait_for_timeout(3000)

            # --- Realistic interaction: progressive scroll ---
            try:
                page.evaluate(_SCROLL_STEPS_JS)
            except Exception:
                pass

            # --- Final collection window for late-firing tags ---
            page.wait_for_timeout(4000)

            # Also capture via Playwright listener for Set-Cookie headers
            # that CDP may report differently
            cookies = context.cookies()
            # Cookies are used by other pipeline stages via the context

            cdp.detach()
            context.close()
            browser.close()

    except Exception as e:
        print(f"Network interception error: {e}")
        raise

    return captured


# ---------------------------------------------------------------------------
# Async version (used from FastAPI / direct script)
# ---------------------------------------------------------------------------

async def intercept_network_traffic(url: str) -> list[NetworkRequest]:
    """
    Async network interception using Playwright async API + CDP.

    Uses CDP Network.enable for complete request capture. Applies stealth
    patches and performs realistic page interaction.

    Args:
        url: Full URL to navigate to (e.g., https://example.com)

    Returns:
        List of NetworkRequest objects with URL, method, status, headers, resource_type
    """
    import asyncio
    from playwright.async_api import async_playwright

    captured: list[NetworkRequest] = []
    pending_requests: dict[str, dict[str, Any]] = {}

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)

            context = await browser.new_context(
                user_agent=random.choice(USER_AGENTS),
                viewport={"width": 1920, "height": 1080},
                ignore_https_errors=True,
                locale="pt-BR",
            )

            page = await context.new_page()

            # Apply stealth patches before navigation
            await _apply_stealth_async(page)

            # --- CDP Network interception ---
            cdp = await context.new_cdp_session(page)
            await cdp.send("Network.enable")

            def on_request_will_be_sent(params: dict) -> None:
                request_id = params.get("requestId", "")
                request_data = params.get("request", {})
                pending_requests[request_id] = {
                    "url": request_data.get("url", ""),
                    "method": request_data.get("method", "GET"),
                    "resource_type": params.get("type", "Other").lower(),
                    "timestamp": time.time(),
                }

            def on_response_received(params: dict) -> None:
                request_id = params.get("requestId", "")
                req_info = pending_requests.pop(request_id, None)
                if not req_info:
                    return

                response = params.get("response", {})
                headers = response.get("headers", {})
                headers_lower = {k.lower(): v for k, v in headers.items()}

                try:
                    captured.append(NetworkRequest(
                        url=req_info["url"],
                        method=req_info["method"],
                        status=response.get("status", 0),
                        headers=headers_lower,
                        resource_type=req_info["resource_type"],
                        timestamp=req_info["timestamp"],
                    ))
                except Exception:
                    pass

            def on_loading_failed(params: dict) -> None:
                request_id = params.get("requestId", "")
                req_info = pending_requests.pop(request_id, None)
                if not req_info:
                    return

                try:
                    captured.append(NetworkRequest(
                        url=req_info["url"],
                        method=req_info["method"],
                        status=0,
                        headers={},
                        resource_type=req_info["resource_type"],
                        timestamp=req_info["timestamp"],
                    ))
                except Exception:
                    pass

            cdp.on("Network.requestWillBeSent", on_request_will_be_sent)
            cdp.on("Network.responseReceived", on_response_received)
            cdp.on("Network.loadingFailed", on_loading_failed)

            # Navigate with domcontentloaded
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            except Exception:
                pass

            await asyncio.sleep(3)

            # Realistic interaction: progressive scroll
            try:
                await page.evaluate(_SCROLL_STEPS_JS)
            except Exception:
                pass

            # Final collection window
            await asyncio.sleep(4)

            await cdp.detach()
            await context.close()
            await browser.close()

    except Exception as e:
        print(f"Network interception error: {e}")
        raise

    return captured
