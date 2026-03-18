"""
Standalone subprocess: discovers and selects e-commerce funnel pages.

Isolates Playwright from Streamlit's event loop / greenlet conflicts.
Runs sitemap parsing + BFS spider in a single process.

Usage:
    python run_page_discovery.py <base_url>
    python run_page_discovery.py <base_url> --no-spider
    python run_page_discovery.py <base_url> --no-sitemap

Output:
    JSON dict with FunnelSelection fields.
    Printed to stdout. Errors to stderr.
"""

import sys
import json
import asyncio


async def run_discovery(base_url: str, use_spider: bool = True, use_sitemap: bool = True) -> dict:
    """
    Run page discovery pipeline.

    Args:
        base_url: Homepage URL to discover pages from
        use_spider: Whether to use BFS spider
        use_sitemap: Whether to parse sitemaps

    Returns:
        Dict representation of FunnelSelection.
    """
    # Import locally to avoid greenlet conflicts at module level
    from tools.helpers.discover.page_selector import select_funnel_pages_async

    result = await select_funnel_pages_async(
        base_url=base_url,
        browser=None,  # Will launch its own browser if spider is needed
        use_spider=use_spider,
        use_sitemap=use_sitemap,
    )

    return result.model_dump()


def main():
    if len(sys.argv) < 2:
        print(json.dumps({
            "pages": {},
            "total_discovered": 0,
            "total_classified": 0,
            "gaps": ["home", "category", "product", "cart", "checkout"],
            "discovery_stats": {},
            "warnings": ["No URL provided"],
        }))
        return

    base_url = sys.argv[1]
    use_spider = "--no-spider" not in sys.argv
    use_sitemap = "--no-sitemap" not in sys.argv

    try:
        result = asyncio.run(run_discovery(base_url, use_spider, use_sitemap))
    except Exception as e:
        print(f"Discovery error: {type(e).__name__}: {e}", file=sys.stderr)
        result = {
            "pages": {},
            "total_discovered": 0,
            "total_classified": 0,
            "gaps": ["home", "category", "product", "cart", "checkout"],
            "discovery_stats": {},
            "warnings": [f"Pipeline error: {e}"],
        }

    print(json.dumps(result, default=str))


if __name__ == "__main__":
    main()
