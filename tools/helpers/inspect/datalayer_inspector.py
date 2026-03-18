"""
DataLayer inspection module — Stage 5 of the diagnostic pipeline.

Inspects window.dataLayer for GA4 events, validates schema compliance,
checks for e-commerce tracking, and simulates user interactions.
Uses Playwright with stealth patches and realistic scroll interaction
to capture dynamically-pushed dataLayer events.
"""

from __future__ import annotations

import random
from typing import Any

from ..shared.config import DataLayerResult, USER_AGENTS, load_ga4_taxonomy


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


def _analyze_events(
    events: list[dict],
    standard_events: list[str],
    required_fields: list[str],
    recommended_fields: list[str],
    result: DataLayerResult,
) -> tuple[set[str], bool, bool, list[dict]]:
    """Analyze dataLayer events and populate result fields. Returns tracking state."""
    all_event_names: set[str] = set()
    interaction_found = False
    has_ecommerce_items = False
    sample_events: list[dict[str, Any]] = []

    for event in events[:10]:
        if not isinstance(event, dict):
            continue

        event_name = event.get("event")
        if event_name:
            all_event_names.add(event_name)

            if event_name in standard_events:
                if event_name not in result.standard_events_detected:
                    result.standard_events_detected.append(event_name)

            if event_name in ["click", "scroll", "form_start", "form_submit"]:
                interaction_found = True

            if "ecommerce" in event or "items" in event:
                has_ecommerce_items = True

        if len(sample_events) < 5:
            sample_events.append(event)

    return all_event_names, interaction_found, has_ecommerce_items, sample_events


def _validate_ecommerce(
    events: list[dict],
    required_fields: list[str],
    recommended_fields: list[str],
    result: DataLayerResult,
) -> None:
    """Validate e-commerce schema in dataLayer events."""
    for event in events:
        if not isinstance(event, dict):
            continue
        items = event.get("ecommerce", {}).get("items", [])
        if items and isinstance(items, list):
            first_item = items[0]
            if isinstance(first_item, dict):
                for field in required_fields:
                    if field in first_item and field not in result.required_fields_present:
                        result.required_fields_present.append(field)
                for field in recommended_fields:
                    if field not in first_item and field not in result.missing_recommended_fields:
                        result.missing_recommended_fields.append(field)

    if len(result.required_fields_present) >= len(required_fields):
        result.ga4_schema_compliant = True


def inspect_datalayer_sync(url: str) -> DataLayerResult:
    """
    Inspect DataLayer events and GA4 schema compliance — synchronous version.

    Navigates to URL with stealth patches, performs scroll interaction to
    trigger lazy-pushed events, extracts window.dataLayer, validates against
    GA4 schema, and checks for e-commerce fields.

    Args:
        url: Full URL to inspect (e.g., https://example.com)

    Returns:
        DataLayerResult with event list, schema compliance, and field validation
    """
    from playwright.sync_api import sync_playwright

    result = DataLayerResult(datalayer_exists=False)

    try:
        taxonomy = load_ga4_taxonomy()
        standard_events = list(taxonomy.get("standard_events", {}).keys())
        required_fields = taxonomy.get("ecommerce_fields", {}).get("required", [])
        recommended_fields = taxonomy.get("ecommerce_fields", {}).get("recommended", [])

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

            # Navigate
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=15000)
            except Exception:
                pass

            # Wait for initial scripts
            page.wait_for_timeout(3000)

            # Scroll to trigger lazy-loaded dataLayer pushes
            try:
                page.evaluate(_SCROLL_STEPS_JS)
            except Exception:
                pass

            # Wait for scroll-triggered events to settle
            page.wait_for_timeout(2000)

            # Extract dataLayer
            try:
                initial_events = page.evaluate("() => window.dataLayer || []")
            except Exception:
                initial_events = []

            if not initial_events:
                result.datalayer_exists = False
                context.close()
                browser.close()
                return result

            result.datalayer_exists = True
            result.datalayer_events_count = len(initial_events)

            all_event_names, interaction_found, has_ecommerce_items, sample_events = _analyze_events(
                initial_events, standard_events, required_fields, recommended_fields, result,
            )

            result.interaction_tracking_active = interaction_found
            result.ecommerce_items_array = has_ecommerce_items
            result.sample_events = sample_events

            # Try to interact with page to trigger more events
            try:
                add_to_cart_selectors = [
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
                for selector in add_to_cart_selectors:
                    try:
                        element = page.locator(selector).first
                        if element.is_visible(timeout=1000):
                            element.click(timeout=1000)
                            clicked = True
                            break
                    except Exception:
                        continue

                if clicked:
                    page.wait_for_timeout(2000)
                    try:
                        updated_events = page.evaluate("() => window.dataLayer || []")
                        if len(updated_events) > len(initial_events):
                            result.datalayer_events_count = len(updated_events)
                            for event in updated_events[len(initial_events):]:
                                if isinstance(event, dict):
                                    event_name = event.get("event")
                                    if event_name and event_name not in all_event_names:
                                        all_event_names.add(event_name)
                                        result.standard_events_detected.append(event_name)
                    except Exception:
                        pass
            except Exception:
                pass

            # Validate e-commerce schema
            if has_ecommerce_items or "ecommerce" in str(initial_events):
                _validate_ecommerce(sample_events, required_fields, recommended_fields, result)

            context.close()
            browser.close()

    except Exception as e:
        print(f"DataLayer inspection error: {e}")

    return result


async def inspect_datalayer(url: str) -> DataLayerResult:
    """
    Inspect DataLayer events and GA4 schema compliance — async version.

    Args:
        url: Full URL to inspect (e.g., https://example.com)

    Returns:
        DataLayerResult with event list, schema compliance, and field validation
    """
    import asyncio
    from playwright.async_api import async_playwright

    result = DataLayerResult(datalayer_exists=False)

    try:
        taxonomy = load_ga4_taxonomy()
        standard_events = list(taxonomy.get("standard_events", {}).keys())
        required_fields = taxonomy.get("ecommerce_fields", {}).get("required", [])
        recommended_fields = taxonomy.get("ecommerce_fields", {}).get("recommended", [])

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

            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            except Exception:
                pass

            await asyncio.sleep(3)

            # Scroll to trigger lazy-loaded events
            try:
                await page.evaluate(_SCROLL_STEPS_JS)
            except Exception:
                pass

            await asyncio.sleep(2)

            # Extract dataLayer
            try:
                initial_events = await page.evaluate("() => window.dataLayer || []")
            except Exception:
                initial_events = []

            if not initial_events:
                result.datalayer_exists = False
                await context.close()
                await browser.close()
                return result

            result.datalayer_exists = True
            result.datalayer_events_count = len(initial_events)

            all_event_names, interaction_found, has_ecommerce_items, sample_events = _analyze_events(
                initial_events, standard_events, required_fields, recommended_fields, result,
            )

            result.interaction_tracking_active = interaction_found
            result.ecommerce_items_array = has_ecommerce_items
            result.sample_events = sample_events

            # Try to interact
            try:
                add_to_cart_selectors = [
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
                for selector in add_to_cart_selectors:
                    try:
                        element = page.locator(selector).first
                        if await element.is_visible(timeout=1000):
                            await element.click(timeout=1000)
                            clicked = True
                            break
                    except Exception:
                        continue

                if clicked:
                    await asyncio.sleep(2)
                    try:
                        updated_events = await page.evaluate("() => window.dataLayer || []")
                        if len(updated_events) > len(initial_events):
                            result.datalayer_events_count = len(updated_events)
                            for event in updated_events[len(initial_events):]:
                                if isinstance(event, dict):
                                    event_name = event.get("event")
                                    if event_name and event_name not in all_event_names:
                                        all_event_names.add(event_name)
                                        result.standard_events_detected.append(event_name)
                    except Exception:
                        pass
            except Exception:
                pass

            if has_ecommerce_items or "ecommerce" in str(initial_events):
                _validate_ecommerce(sample_events, required_fields, recommended_fields, result)

            await context.close()
            await browser.close()

    except Exception as e:
        print(f"DataLayer inspection error: {e}")

    return result
