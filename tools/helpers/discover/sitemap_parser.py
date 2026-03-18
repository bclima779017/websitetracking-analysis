"""
Sitemap parser — fetches and parses sitemap.xml for URL discovery.

Handles sitemap index files (recursive), gzipped sitemaps, and robots.txt
Sitemap: directives. Uses httpx for async HTTP (no browser needed).
"""

from __future__ import annotations

import asyncio
import gzip
import re
import xml.etree.ElementTree as ET
from urllib.parse import urljoin, urlparse

import httpx

from tools.helpers.shared.config import (
    SITEMAP_TIMEOUT,
    DiscoveredUrl,
    load_funnel_heuristics,
)


async def fetch_sitemap(
    base_url: str,
    timeout: int = SITEMAP_TIMEOUT,
) -> list[DiscoveredUrl]:
    """
    Fetch and parse sitemap.xml for the given domain.

    Tries multiple sitemap locations (from funnel-heuristics.json),
    falls back to robots.txt Sitemap: directives. Handles sitemap
    index files recursively and gzipped sitemaps.

    Args:
        base_url: Base URL of the site (e.g., https://example.com)
        timeout: HTTP timeout in seconds per request

    Returns:
        List of DiscoveredUrl objects sorted by priority descending.
        Returns empty list if no sitemap is found (non-fatal).
    """
    if not base_url.startswith(("http://", "https://")):
        base_url = "https://" + base_url

    parsed = urlparse(base_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"

    heuristics = load_funnel_heuristics()
    sitemap_paths = heuristics.get("sitemap_paths", ["/sitemap.xml"])
    robots_path = heuristics.get("robots_txt_path", "/robots.txt")

    discovered: list[DiscoveredUrl] = []

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(float(timeout)),
        follow_redirects=True,
        verify=False,
        headers={"User-Agent": "Mozilla/5.0 (compatible; BlindAnalytics/1.0)"},
    ) as client:
        # Try standard sitemap paths first
        sitemap_urls_to_try: list[str] = [origin + p for p in sitemap_paths]

        # Also check robots.txt for Sitemap: directives
        robots_sitemaps = await _find_sitemap_in_robots(client, origin + robots_path)
        sitemap_urls_to_try.extend(robots_sitemaps)

        # Deduplicate while preserving order
        seen: set[str] = set()
        unique_urls: list[str] = []
        for u in sitemap_urls_to_try:
            if u not in seen:
                seen.add(u)
                unique_urls.append(u)

        for sitemap_url in unique_urls:
            urls = await _fetch_and_parse(client, sitemap_url, origin, depth=0)
            if urls:
                discovered.extend(urls)
                break  # Use first successful sitemap

    # Sort by priority descending (highest priority first)
    discovered.sort(key=lambda u: u.sitemap_priority or 0.0, reverse=True)
    return discovered


def fetch_sitemap_sync(
    base_url: str,
    timeout: int = SITEMAP_TIMEOUT,
) -> list[DiscoveredUrl]:
    """
    Sync wrapper for fetch_sitemap. For Streamlit compatibility.

    Args:
        base_url: Base URL of the site
        timeout: HTTP timeout in seconds

    Returns:
        List of DiscoveredUrl objects sorted by priority descending.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(
                    asyncio.run, fetch_sitemap(base_url, timeout)
                ).result()
        return loop.run_until_complete(fetch_sitemap(base_url, timeout))
    except RuntimeError:
        return asyncio.run(fetch_sitemap(base_url, timeout))


async def _fetch_and_parse(
    client: httpx.AsyncClient,
    sitemap_url: str,
    origin: str,
    depth: int = 0,
    max_depth: int = 2,
) -> list[DiscoveredUrl]:
    """
    Fetch a sitemap URL and parse its content recursively.

    Handles both <urlset> (leaf) and <sitemapindex> (index) formats.
    Follows child sitemaps up to max_depth levels.

    Args:
        client: httpx async client
        sitemap_url: URL of the sitemap to fetch
        origin: Site origin for domain filtering
        depth: Current recursion depth
        max_depth: Maximum recursion depth for sitemap indexes

    Returns:
        List of DiscoveredUrl objects from this sitemap (and children).
    """
    if depth > max_depth:
        return []

    try:
        response = await client.get(sitemap_url)
        if response.status_code != 200:
            return []
    except (httpx.RequestError, httpx.TimeoutException):
        return []

    content = response.content

    # Handle gzipped sitemaps
    if sitemap_url.endswith(".gz") or response.headers.get("content-type", "").startswith("application/x-gzip"):
        try:
            content = gzip.decompress(content)
        except (gzip.BadGzipFile, OSError):
            return []

    # Parse XML
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return []

    # Strip namespace for easier parsing
    ns = ""
    tag = root.tag
    if tag.startswith("{"):
        ns = tag[: tag.index("}") + 1]

    # Check if this is a sitemap index — recurse into child sitemaps
    sitemap_entries = root.findall(f"{ns}sitemap")
    if sitemap_entries:
        child_urls: list[str] = []
        for entry in sitemap_entries:
            loc = entry.find(f"{ns}loc")
            if loc is not None and loc.text:
                child_urls.append(loc.text.strip())

        discovered: list[DiscoveredUrl] = []
        for child_url in child_urls[:10]:  # Limit to 10 child sitemaps
            child_results = await _fetch_and_parse(
                client, child_url, origin, depth + 1, max_depth,
            )
            discovered.extend(child_results)
        return discovered

    # This is a urlset — extract URLs
    return _parse_urlset(root, ns, origin)


def _parse_urlset(
    root: ET.Element,
    ns: str,
    origin: str,
) -> list[DiscoveredUrl]:
    """
    Parse a <urlset> XML element into DiscoveredUrl objects.

    Args:
        root: Parsed XML root element
        ns: XML namespace prefix (e.g., '{http://...}')
        origin: Site origin for resolving relative URLs and domain filtering

    Returns:
        List of DiscoveredUrl objects.
    """
    discovered: list[DiscoveredUrl] = []
    url_entries = root.findall(f"{ns}url")
    parsed_origin = urlparse(origin)

    for entry in url_entries:
        loc = entry.find(f"{ns}loc")
        if loc is None or not loc.text:
            continue

        url = loc.text.strip()

        # Only include URLs from the same domain
        parsed_url = urlparse(url)
        if parsed_url.netloc and parsed_url.netloc != parsed_origin.netloc:
            continue

        # Resolve relative URLs
        if not url.startswith(("http://", "https://")):
            url = urljoin(origin, url)

        # Extract optional metadata
        priority_el = entry.find(f"{ns}priority")
        priority = None
        if priority_el is not None and priority_el.text:
            try:
                priority = float(priority_el.text.strip())
            except ValueError:
                pass

        lastmod_el = entry.find(f"{ns}lastmod")
        lastmod = None
        if lastmod_el is not None and lastmod_el.text:
            lastmod = lastmod_el.text.strip()

        discovered.append(
            DiscoveredUrl(
                url=url,
                source="sitemap",
                sitemap_priority=priority,
                sitemap_lastmod=lastmod,
                depth=0,
            )
        )

    return discovered


async def _find_sitemap_in_robots(
    client: httpx.AsyncClient,
    robots_url: str,
) -> list[str]:
    """
    Parse robots.txt to find Sitemap: directives.

    Args:
        client: httpx async client
        robots_url: Full URL to robots.txt

    Returns:
        List of sitemap URLs found in robots.txt. Empty if absent.
    """
    try:
        response = await client.get(robots_url)
        if response.status_code != 200:
            return []
    except (httpx.RequestError, httpx.TimeoutException):
        return []

    sitemaps: list[str] = []
    for line in response.text.splitlines():
        line = line.strip()
        match = re.match(r"^Sitemap:\s*(.+)$", line, re.IGNORECASE)
        if match:
            sitemaps.append(match.group(1).strip())

    return sitemaps
