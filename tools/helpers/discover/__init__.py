"""
Page discovery module — discovers and selects e-commerce funnel pages.

Exports:
    select_funnel_pages: Sync orchestrator (sitemap + spider + selection)
    select_funnel_pages_async: Async orchestrator
    classify_url: Pure URL-pattern classification function
    fetch_sitemap: Async sitemap parser
    fetch_sitemap_sync: Sync sitemap parser wrapper
"""

from tools.helpers.discover.page_selector import (
    classify_url,
    select_funnel_pages,
    select_funnel_pages_async,
)
from tools.helpers.discover.sitemap_parser import (
    fetch_sitemap,
    fetch_sitemap_sync,
)

__all__ = [
    "classify_url",
    "select_funnel_pages",
    "select_funnel_pages_async",
    "fetch_sitemap",
    "fetch_sitemap_sync",
]
