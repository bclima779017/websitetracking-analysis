"""
Attribution testing module — Stage 3 of the diagnostic pipeline.

Tests URL parameter persistence (UTMs), click ID cookies (_gcl_aw, _fbc),
and localStorage preservation across redirects.
Uses Playwright with stealth patches for reliable browser automation.
"""

from __future__ import annotations

import random
from urllib.parse import urlparse, urlunparse

from ..shared.config import AttributionResult, DEFAULT_CLICK_IDS, DEFAULT_UTM_PARAMS, USER_AGENTS


def _apply_stealth(page) -> None:
    """Apply stealth patches to mask headless browser fingerprint."""
    try:
        from playwright_stealth import stealth_sync
        stealth_sync(page)
    except ImportError:
        page.add_init_script("""
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


async def _apply_stealth_async(page) -> None:
    """Apply stealth patches (async version)."""
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


def _build_test_url(url: str) -> str:
    """Build test URL with UTM params and click IDs."""
    parsed = urlparse(url)
    base_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path or "/", "", "", ""))
    params = "&".join([f"{k}={v}" for k, v in DEFAULT_UTM_PARAMS.items()])
    params += "&gclid=" + DEFAULT_CLICK_IDS["gclid"]
    params += "&fbclid=" + DEFAULT_CLICK_IDS["fbclid"]
    return base_url + "?" + params


def _extract_attribution(page, test_url: str, response) -> AttributionResult:
    """Extract attribution data from page state (works for both sync contexts)."""
    result = AttributionResult()
    final_url = page.url

    # Check redirect behavior
    result.redirect_strips_params = not any(
        param in final_url for param in ["utm_source", "gclid", "fbclid"]
    )

    # Detect redirect type
    if response:
        status = response.status
        if status in (301, 302, 303, 307, 308):
            result.redirect_type = f"{status}"

    result.utm_persistence_on_redirect = test_url == final_url

    # Extract cookies
    cookies = page.context.cookies()
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

    for cookie_name in ["_fbp", "_ga", "_gat", "_gcl_au"]:
        if cookie_name in cookie_dict and cookie_name not in result.cookies_found:
            result.cookies_found.append(cookie_name)

    # Check localStorage for UTM values
    try:
        local_storage = page.evaluate("() => Object.entries(localStorage)")
        for key, value in local_storage:
            if "utm_" in key.lower():
                result.localstorage_utm_saved = True
                result.localStorage_keys.append(key)
    except Exception:
        pass

    return result


def test_attribution_sync(url: str) -> AttributionResult:
    """
    Test attribution mechanisms (UTMs, cookies, localStorage) — synchronous version.

    Simulates a user clicking a Google Ads link with UTM parameters and click ID,
    then checks parameter persistence, cookie creation, and localStorage state.

    Args:
        url: Base URL to test (e.g., https://example.com)

    Returns:
        AttributionResult with cookies found, redirect behavior, localStorage status
    """
    from playwright.sync_api import sync_playwright

    result = AttributionResult()

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
            _apply_stealth(page)

            test_url = _build_test_url(url)

            # Navigate and capture redirect chain
            response = None
            try:
                response = page.goto(test_url, wait_until="domcontentloaded", timeout=15000)
            except Exception:
                pass

            # Wait for cookies/scripts to settle
            page.wait_for_timeout(3000)

            result = _extract_attribution(page, test_url, response)

            context.close()
            browser.close()

    except Exception as e:
        print(f"Attribution test error: {e}")

    return result


async def test_attribution(url: str) -> AttributionResult:
    """
    Test attribution mechanisms (UTMs, cookies, localStorage) — async version.

    Args:
        url: Base URL to test (e.g., https://example.com)

    Returns:
        AttributionResult with cookies found, redirect behavior, localStorage status
    """
    import asyncio
    from playwright.async_api import async_playwright

    result = AttributionResult()

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
            await _apply_stealth_async(page)

            test_url = _build_test_url(url)

            response = None
            try:
                response = await page.goto(test_url, wait_until="domcontentloaded", timeout=15000)
            except Exception:
                pass

            await asyncio.sleep(3)

            # Extract attribution data — async version needs manual extraction
            # because _extract_attribution uses sync page.evaluate
            final_url = page.url

            result.redirect_strips_params = not any(
                param in final_url for param in ["utm_source", "gclid", "fbclid"]
            )

            if response:
                status = response.status
                if status in (301, 302, 303, 307, 308):
                    result.redirect_type = f"{status}"

            result.utm_persistence_on_redirect = test_url == final_url

            cookies = await page.context.cookies()
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

            for cookie_name in ["_fbp", "_ga", "_gat", "_gcl_au"]:
                if cookie_name in cookie_dict and cookie_name not in result.cookies_found:
                    result.cookies_found.append(cookie_name)

            try:
                local_storage = await page.evaluate("() => Object.entries(localStorage)")
                for key, value in local_storage:
                    if "utm_" in key.lower():
                        result.localstorage_utm_saved = True
                        result.localStorage_keys.append(key)
            except Exception:
                pass

            await context.close()
            await browser.close()

    except Exception as e:
        print(f"Attribution test error: {e}")

    return result
