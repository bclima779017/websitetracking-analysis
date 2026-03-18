"""
Page selector — discovers and selects representative e-commerce funnel pages.

Orchestrates sitemap parsing + BFS spider to find pages for each funnel stage
(home, category, product, cart, checkout). Classifies URLs using URL-pattern
heuristics and optional content-based signals via Playwright.
"""

from __future__ import annotations

import asyncio
import re
from collections import defaultdict
from urllib.parse import urljoin, urlparse

from tools.helpers.shared.config import (
    SPIDER_MAX_DEPTH,
    SPIDER_MAX_PAGES,
    ClassifiedUrl,
    FunnelSelection,
    FunnelStage,
    load_funnel_heuristics,
)
from tools.helpers.discover.sitemap_parser import fetch_sitemap, fetch_sitemap_sync


# ============================================================================
# PURE FUNCTIONS — URL classification (no browser, no I/O)
# ============================================================================


def classify_url(url: str, heuristics: dict | None = None) -> ClassifiedUrl:
    """
    Classify a single URL into a funnel stage using URL-pattern heuristics.

    Pure function, no network access. Applies regex and path-contains patterns
    from funnel-heuristics.json against the URL path.

    Args:
        url: Absolute URL to classify
        heuristics: Pre-loaded heuristics dict. Loaded from asset if None.

    Returns:
        ClassifiedUrl with stage, confidence, and signals list.
        Returns stage=OTHER with confidence=0 if no pattern matches.
    """
    if heuristics is None:
        heuristics = load_funnel_heuristics()

    parsed = urlparse(url)
    path = parsed.path.lower().rstrip("/") or "/"
    patterns = heuristics.get("url_patterns", {})

    # HOME — exact match (highest priority, checked first)
    home_patterns = patterns.get("home", {})
    home_exact = home_patterns.get("path_exact", ["/", "/home", "/index"])
    if path in home_exact or path == "":
        return ClassifiedUrl(
            url=url,
            stage=FunnelStage.HOME,
            confidence=home_patterns.get("weight", 0.95),
            classification_signals=[f"url_exact:{path}"],
        )

    # Evaluate remaining stages: CART → CHECKOUT → PRODUCT → CATEGORY
    # Order: most specific first to avoid false positives
    stage_order: list[tuple[str, FunnelStage]] = [
        ("cart", FunnelStage.CART),
        ("checkout", FunnelStage.CHECKOUT),
        ("product", FunnelStage.PRODUCT),
        ("category", FunnelStage.CATEGORY),
    ]

    for stage_key, stage_enum in stage_order:
        stage_patterns = patterns.get(stage_key, {})
        weight = stage_patterns.get("weight", 0.5)

        # Check path_contains patterns
        contains_list = stage_patterns.get("path_contains", [])
        for pattern in contains_list:
            if pattern.lower() in path:
                return ClassifiedUrl(
                    url=url,
                    stage=stage_enum,
                    confidence=weight,
                    classification_signals=[f"url_contains:{pattern}"],
                )

        # Check regex patterns
        path_regex = stage_patterns.get("path_regex")
        if path_regex:
            try:
                if re.search(path_regex, path, re.IGNORECASE):
                    return ClassifiedUrl(
                        url=url,
                        stage=stage_enum,
                        confidence=weight * 0.9,
                        classification_signals=[f"url_regex:{path_regex}"],
                    )
            except re.error:
                pass

    # Product-specific: SKU-like slug detection
    product_patterns = patterns.get("product", {})
    sku_regex = product_patterns.get("sku_regex")
    slug_regex = product_patterns.get("slug_regex")

    if sku_regex:
        try:
            if re.search(sku_regex, parsed.path):
                return ClassifiedUrl(
                    url=url,
                    stage=FunnelStage.PRODUCT,
                    confidence=0.5,
                    classification_signals=[f"url_sku:{sku_regex}"],
                )
        except re.error:
            pass

    if slug_regex:
        try:
            if re.search(slug_regex, parsed.path):
                return ClassifiedUrl(
                    url=url,
                    stage=FunnelStage.PRODUCT,
                    confidence=0.4,
                    classification_signals=[f"url_slug:{slug_regex}"],
                )
        except re.error:
            pass

    # No match
    return ClassifiedUrl(
        url=url,
        stage=FunnelStage.OTHER,
        confidence=0.0,
        classification_signals=[],
    )


def _select_best_per_stage(
    candidates: dict[FunnelStage, list[ClassifiedUrl]],
) -> dict[str, ClassifiedUrl | None]:
    """
    Select the single best URL for each funnel stage.

    Selection criteria (priority order):
    1. Highest classification confidence
    2. Highest sitemap priority (if available)
    3. Shortest URL path (simpler URLs are usually canonical)

    Args:
        candidates: Map of stage -> list of classified URLs

    Returns:
        Map of stage value -> single best ClassifiedUrl (or None if no candidates).
    """
    result: dict[str, ClassifiedUrl | None] = {}

    for stage in FunnelStage:
        if stage == FunnelStage.OTHER:
            continue

        stage_candidates = candidates.get(stage, [])
        if not stage_candidates:
            result[stage.value] = None
            continue

        # Sort by: confidence desc, sitemap_priority desc, URL length asc
        stage_candidates.sort(
            key=lambda c: (
                c.confidence,
                c.sitemap_priority or 0.0,
                -len(c.url),
            ),
            reverse=True,
        )
        result[stage.value] = stage_candidates[0]

    return result


# ============================================================================
# BROWSER FUNCTIONS — Content classification + Spider
# ============================================================================


async def classify_url_by_content(
    page,
    url: str,
    heuristics: dict | None = None,
) -> ClassifiedUrl:
    """
    Classify a URL by inspecting its rendered page content.

    Uses Playwright Page to check for CSS selectors, meta tags, and
    structured data that indicate the page type. Combines with URL-pattern
    classification for higher confidence.

    Args:
        page: Playwright Page already navigated to the URL
        url: The URL being classified
        heuristics: Pre-loaded heuristics dict

    Returns:
        ClassifiedUrl with stage, confidence, and signals.
    """
    if heuristics is None:
        heuristics = load_funnel_heuristics()

    # Start with URL-pattern classification
    url_result = classify_url(url, heuristics)
    content_signals = heuristics.get("content_signals", {})

    best_stage = url_result.stage
    best_confidence = url_result.confidence
    all_signals = list(url_result.classification_signals)

    # Check content signals for each stage
    stage_order: list[tuple[str, FunnelStage]] = [
        ("product", FunnelStage.PRODUCT),
        ("category", FunnelStage.CATEGORY),
        ("cart", FunnelStage.CART),
        ("checkout", FunnelStage.CHECKOUT),
    ]

    for stage_key, stage_enum in stage_order:
        stage_signals = content_signals.get(stage_key, {})
        selectors = stage_signals.get("selectors", [])

        match_count = 0
        for selector in selectors:
            try:
                count = await page.locator(selector).count()
                if count > 0:
                    match_count += 1
                    all_signals.append(f"content:{selector}")
            except Exception:
                continue

        if match_count > 0:
            content_confidence = min(0.15 * match_count, 0.9)
            if content_confidence > best_confidence:
                best_stage = stage_enum
                best_confidence = content_confidence

        # Check og:type for products
        if stage_key == "product":
            og_type = stage_signals.get("meta_og_type")
            if og_type:
                try:
                    meta_content = await page.locator(
                        f"meta[property='og:type']"
                    ).get_attribute("content", timeout=1000)
                    if meta_content and meta_content.lower() == og_type:
                        all_signals.append(f"content:og:type={og_type}")
                        if 0.85 > best_confidence:
                            best_stage = FunnelStage.PRODUCT
                            best_confidence = 0.85
                except Exception:
                    pass

    return ClassifiedUrl(
        url=url,
        stage=best_stage,
        confidence=best_confidence,
        classification_signals=all_signals,
    )


async def _spider_site(
    base_url: str,
    browser,
    already_classified: dict[FunnelStage, list[ClassifiedUrl]],
    heuristics: dict,
    max_depth: int = SPIDER_MAX_DEPTH,
    max_pages: int = SPIDER_MAX_PAGES,
) -> list[ClassifiedUrl]:
    """
    BFS spider from homepage, classifying pages as they are discovered.

    Stops early when all funnel stages (excluding OTHER) have at least
    one candidate. Only follows internal links (same domain).

    Args:
        base_url: Starting URL for the spider
        browser: Playwright Browser instance
        already_classified: URLs already classified from sitemap (to skip)
        heuristics: Pre-loaded funnel heuristics
        max_depth: Maximum link depth from homepage
        max_pages: Maximum pages to visit

    Returns:
        List of newly classified URLs found by spidering.
    """
    import random

    from tools.helpers.shared.config import USER_AGENTS

    parsed_base = urlparse(base_url)
    base_domain = parsed_base.netloc.lower()

    # Track visited URLs and which stages still need candidates
    visited: set[str] = set()
    for stage_urls in already_classified.values():
        for cu in stage_urls:
            visited.add(cu.url)

    # BFS queue: (url, depth)
    queue: list[tuple[str, int]] = [(base_url, 0)]
    newly_classified: list[ClassifiedUrl] = []
    pages_visited = 0

    # Determine which stages still need candidates
    def _stages_with_gaps() -> set[FunnelStage]:
        all_candidates = dict(already_classified)
        for cu in newly_classified:
            if cu.stage != FunnelStage.OTHER:
                all_candidates.setdefault(cu.stage, []).append(cu)
        gaps = set()
        for stage in FunnelStage:
            if stage == FunnelStage.OTHER:
                continue
            if not all_candidates.get(stage):
                gaps.add(stage)
        return gaps

    context = await browser.new_context(
        user_agent=random.choice(USER_AGENTS),
        viewport={"width": 1920, "height": 1080},
        ignore_https_errors=True,
        locale="pt-BR",
    )
    page = await context.new_page()

    # Apply stealth
    try:
        from playwright_stealth import stealth_async

        await stealth_async(page)
    except ImportError:
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => false });
            window.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['pt-BR', 'pt', 'en-US', 'en'] });
        """)

    try:
        while queue and pages_visited < max_pages:
            # Check if all stages are covered
            if not _stages_with_gaps():
                break

            url, depth = queue.pop(0)

            if url in visited:
                continue
            visited.add(url)

            if depth > max_depth:
                continue

            pages_visited += 1

            # Navigate to page
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=15000)
                await asyncio.sleep(1)
            except Exception:
                continue

            # Classify by content (only if URL-pattern classification is weak)
            url_classification = classify_url(url, heuristics)
            if url_classification.confidence < 0.5:
                classification = await classify_url_by_content(page, url, heuristics)
            else:
                classification = url_classification

            classification.source = "spider"
            newly_classified.append(classification)

            # Extract internal links for BFS
            if depth < max_depth:
                try:
                    links = await page.evaluate("""
                        () => {
                            const anchors = document.querySelectorAll('a[href]');
                            return Array.from(anchors)
                                .map(a => a.href)
                                .filter(h => h.startsWith('http'));
                        }
                    """)
                except Exception:
                    links = []

                for link in links:
                    parsed_link = urlparse(link)
                    # Same domain only, skip fragments and query-heavy URLs
                    if parsed_link.netloc.lower() == base_domain and link not in visited:
                        # Normalize: remove fragment
                        clean = link.split("#")[0]
                        if clean not in visited:
                            # Pre-classify by URL pattern to prioritize promising links
                            pre_class = classify_url(clean, heuristics)
                            if pre_class.stage != FunnelStage.OTHER:
                                # Promising link — add to front of queue
                                queue.insert(0, (clean, depth + 1))
                            else:
                                queue.append((clean, depth + 1))
    finally:
        await context.close()

    return newly_classified


# ============================================================================
# ORCHESTRATOR — Main entry points
# ============================================================================


async def select_funnel_pages_async(
    base_url: str,
    browser=None,
    use_spider: bool = True,
    use_sitemap: bool = True,
) -> FunnelSelection:
    """
    Discover and select representative pages across the e-commerce funnel.

    Orchestration flow:
    1. Fetch sitemap URLs (async HTTP, no browser needed)
    2. Classify sitemap URLs by funnel stage (URL pattern heuristics)
    3. If gaps remain and use_spider=True, spider the site to fill them
    4. Select the best candidate per stage
    5. Guarantee homepage is always present

    Args:
        base_url: Homepage URL (e.g., https://example.com)
        browser: Optional Playwright Browser instance for spider/content classification.
                 If None and use_spider=True, a browser will be launched.
        use_spider: Whether to spider the site if sitemap doesn't cover all stages
        use_sitemap: Whether to attempt sitemap parsing

    Returns:
        FunnelSelection with best page per funnel stage and discovery stats.
    """
    if not base_url.startswith(("http://", "https://")):
        base_url = "https://" + base_url

    heuristics = load_funnel_heuristics()
    candidates: dict[FunnelStage, list[ClassifiedUrl]] = defaultdict(list)
    warnings: list[str] = []
    stats: dict[str, int] = {"sitemap_urls": 0, "spider_urls": 0}

    # PHASE 1: Sitemap
    if use_sitemap:
        try:
            sitemap_urls = await fetch_sitemap(base_url)
            stats["sitemap_urls"] = len(sitemap_urls)

            for discovered in sitemap_urls:
                classified = classify_url(discovered.url, heuristics)
                classified.source = "sitemap"
                classified.sitemap_priority = discovered.sitemap_priority
                if classified.stage != FunnelStage.OTHER:
                    candidates[classified.stage].append(classified)
        except Exception as e:
            warnings.append(f"Sitemap fetch failed: {type(e).__name__}: {e}")

    # Check coverage
    gaps = [
        stage for stage in FunnelStage
        if stage != FunnelStage.OTHER and not candidates.get(stage)
    ]

    # PHASE 2: Spider (if gaps remain)
    if use_spider and gaps:
        own_browser = False
        if browser is None:
            try:
                from playwright.async_api import async_playwright

                pw = await async_playwright().start()
                browser = await pw.chromium.launch(headless=True)
                own_browser = True
            except Exception as e:
                warnings.append(f"Spider skipped (Playwright unavailable): {e}")
                browser = None

        if browser is not None:
            try:
                spider_results = await _spider_site(
                    base_url, browser, candidates, heuristics,
                )
                stats["spider_urls"] = len(spider_results)

                for classified in spider_results:
                    if classified.stage != FunnelStage.OTHER:
                        candidates[classified.stage].append(classified)
            except Exception as e:
                warnings.append(f"Spider failed: {type(e).__name__}: {e}")
            finally:
                if own_browser:
                    await browser.close()
                    await pw.stop()

    # PHASE 3: Homepage guarantee
    if not candidates.get(FunnelStage.HOME):
        candidates[FunnelStage.HOME].append(
            ClassifiedUrl(
                url=base_url,
                stage=FunnelStage.HOME,
                confidence=1.0,
                source="forced",
                classification_signals=["forced:homepage_guarantee"],
            )
        )

    # PHASE 4: Selection
    pages = _select_best_per_stage(candidates)

    # Identify final gaps
    final_gaps = [
        stage for stage in ["home", "category", "product", "cart", "checkout"]
        if pages.get(stage) is None
    ]

    total_discovered = stats["sitemap_urls"] + stats["spider_urls"]
    total_classified = sum(len(v) for v in candidates.values())

    return FunnelSelection(
        pages=pages,
        total_discovered=total_discovered,
        total_classified=total_classified,
        gaps=final_gaps,
        discovery_stats=stats,
        warnings=warnings,
    )


def select_funnel_pages(
    base_url: str,
    browser=None,
    use_spider: bool = True,
    use_sitemap: bool = True,
) -> FunnelSelection:
    """
    Sync version of select_funnel_pages_async. For Streamlit compatibility.

    Args:
        base_url: Homepage URL
        browser: Optional Playwright Browser (sync API)
        use_spider: Whether to spider the site
        use_sitemap: Whether to attempt sitemap parsing

    Returns:
        FunnelSelection with best page per funnel stage.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(
                    asyncio.run,
                    select_funnel_pages_async(base_url, browser, use_spider, use_sitemap),
                ).result()
        return loop.run_until_complete(
            select_funnel_pages_async(base_url, browser, use_spider, use_sitemap)
        )
    except RuntimeError:
        return asyncio.run(
            select_funnel_pages_async(base_url, browser, use_spider, use_sitemap)
        )
