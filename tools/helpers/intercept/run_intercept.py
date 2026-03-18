"""
Standalone subprocess script for Playwright network interception.

Called by app.py via subprocess.run() to avoid event loop conflicts
between Streamlit's asyncio and Playwright on Windows.

Uses async Playwright + CDP (Chrome DevTools Protocol) for complete
network capture including beacons, preflight CORS, and redirects.
Applies stealth patches and performs realistic scroll interaction.

Usage:
    python run_intercept.py <url>

Output:
    JSON array of NetworkRequest dicts printed to stdout.
    Errors printed to stderr.
"""

import sys
import json
import time
import random
import asyncio


USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

SCROLL_STEPS_JS = """
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


async def intercept(url: str) -> list[dict]:
    from playwright.async_api import async_playwright

    captured: list[dict] = []
    pending_requests: dict[str, dict] = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            viewport={"width": 1920, "height": 1080},
            ignore_https_errors=True,
            locale="pt-BR",
        )
        page = await context.new_page()

        # Apply stealth patches
        try:
            from playwright_stealth import stealth_async
            await stealth_async(page)
        except ImportError:
            await page.add_init_script(STEALTH_JS)

        # CDP Network interception
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
            captured.append({
                "url": req_info["url"],
                "method": req_info["method"],
                "status": response.get("status", 0),
                "headers": headers_lower,
                "resource_type": req_info["resource_type"],
                "timestamp": req_info["timestamp"],
            })

        def on_loading_failed(params: dict) -> None:
            request_id = params.get("requestId", "")
            req_info = pending_requests.pop(request_id, None)
            if not req_info:
                return
            captured.append({
                "url": req_info["url"],
                "method": req_info["method"],
                "status": 0,
                "headers": {},
                "resource_type": req_info["resource_type"],
                "timestamp": req_info["timestamp"],
            })

        cdp.on("Network.requestWillBeSent", on_request_will_be_sent)
        cdp.on("Network.responseReceived", on_response_received)
        cdp.on("Network.loadingFailed", on_loading_failed)

        # Navigate (domcontentloaded, not networkidle)
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        except Exception:
            pass

        # Wait for initial tags
        await asyncio.sleep(3)

        # Realistic scroll interaction
        try:
            await page.evaluate(SCROLL_STEPS_JS)
        except Exception:
            pass

        # Final collection window
        await asyncio.sleep(4)

        await cdp.detach()
        await context.close()
        await browser.close()

    return captured


def main() -> None:
    if len(sys.argv) < 2:
        print("[]")
        return

    url = sys.argv[1]
    try:
        captured = asyncio.run(intercept(url))
    except Exception as e:
        print(f"Playwright error: {type(e).__name__}: {e}", file=sys.stderr)
        captured = []

    print(json.dumps(captured))


if __name__ == "__main__":
    main()
