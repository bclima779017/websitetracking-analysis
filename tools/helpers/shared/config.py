"""
Configuration, constants, and Pydantic models for the Blind Analytics pipeline.

This module provides:
- TYPE DEFINITIONS: Pydantic models for all pipeline output types
- CONSTANTS: User agents, timeouts, default parameters
- LOADERS: Functions to load JSON assets (regex patterns, GA4 taxonomy)
"""

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field


# ============================================================================
# CONSTANTS
# ============================================================================

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
]

NETWORK_IDLE_TIMEOUT = 10000  # milliseconds

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

COMMON_SGTM_SUBDOMAINS = [
    "sgtm",
    "data",
    "tag",
    "collect",
    "tracking",
    "events",
]

# Page discovery constants
SPIDER_MAX_DEPTH = 3
SPIDER_MAX_PAGES = 50
SITEMAP_TIMEOUT = 15  # seconds per sitemap HTTP request


# ============================================================================
# ENUMS
# ============================================================================


class FunnelStage(str, Enum):
    """E-commerce conversion funnel stages for page classification."""

    HOME = "home"
    CATEGORY = "category"
    PRODUCT = "product"
    CART = "cart"
    CHECKOUT = "checkout"
    OTHER = "other"


# ============================================================================
# PYDANTIC MODELS — Pipeline Output Types
# ============================================================================


class DiscoveredUrl(BaseModel):
    """A URL discovered during sitemap parsing or spidering."""

    url: str = Field(..., description="Absolute URL")
    source: str = Field(..., description="How discovered: 'sitemap' or 'spider'")
    sitemap_priority: Optional[float] = Field(default=None, description="Priority from sitemap (0.0-1.0)")
    sitemap_lastmod: Optional[str] = Field(default=None, description="Last modification date from sitemap")
    depth: int = Field(default=0, description="Spider depth from homepage (0 = homepage)")


class ClassifiedUrl(BaseModel):
    """A URL classified into a funnel stage."""

    url: str = Field(..., description="Absolute URL")
    stage: FunnelStage = Field(..., description="Classified funnel stage")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Classification confidence 0-1")
    source: str = Field(default="spider", description="Discovery source: 'sitemap' or 'spider'")
    sitemap_priority: Optional[float] = Field(default=None, description="Sitemap priority if available")
    classification_signals: list[str] = Field(
        default_factory=list,
        description="Signals that drove classification (e.g., 'url:/product/', 'content:og:type=product')",
    )


class FunnelSelection(BaseModel):
    """Final selected pages for funnel analysis."""

    pages: dict[str, Optional[ClassifiedUrl]] = Field(
        ...,
        description="Map of FunnelStage value -> best selected URL (None if no candidate found)",
    )
    total_discovered: int = Field(default=0, description="Total URLs found by sitemap + spider")
    total_classified: int = Field(default=0, description="URLs that matched a funnel stage (not OTHER)")
    gaps: list[str] = Field(
        default_factory=list,
        description="Funnel stages with no candidates found",
    )
    discovery_stats: dict[str, int] = Field(
        default_factory=dict,
        description="Stats: sitemap_urls, spider_urls, spider_depth_reached, etc.",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Non-fatal issues during discovery (e.g., 'sitemap.xml returned 404')",
    )


class UrlValidationResult(BaseModel):
    """Result of URL validation (Stage 1)."""

    url: str = Field(..., description="Original URL provided")
    final_url: str = Field(..., description="Final URL after all redirects")
    is_accessible: bool = Field(..., description="True if URL responds with 2xx status")
    status_code: int = Field(..., description="Final HTTP status code")
    redirect_chain: list[str] = Field(default_factory=list, description="List of URLs in redirect chain")
    is_https: bool = Field(..., description="True if final URL uses HTTPS")
    dns_resolves: bool = Field(..., description="True if domain DNS resolves")
    error: Optional[str] = Field(default=None, description="Error message if validation failed")


class NetworkRequest(BaseModel):
    """Represents a single network request intercepted during page load."""

    url: str = Field(..., description="Full request URL")
    method: str = Field(default="GET", description="HTTP method (GET, POST, etc)")
    status: int = Field(..., description="HTTP response status code")
    headers: dict[str, str] = Field(default_factory=dict, description="Response headers (lowercase keys)")
    resource_type: str = Field(default="xhr", description="Type: xhr, fetch, script, image, stylesheet, etc")
    timestamp: float = Field(..., description="Request timestamp (seconds since epoch)")


class TagIdentification(BaseModel):
    """Result of tag identification from network requests (Stage 2)."""

    gtm_ids: list[str] = Field(default_factory=list, description="GTM container IDs found (GTM-*)")
    gtm_status: Optional[int] = Field(default=None, description="HTTP status of GTM script load")
    ga4_ids: list[str] = Field(default_factory=list, description="GA4 measurement IDs found (G-*)")
    ga4_status: Optional[int] = Field(default=None, description="HTTP status of GA4 script load")
    meta_pixel_ids: list[str] = Field(default_factory=list, description="Meta Pixel IDs found")
    meta_pixel_status: Optional[int] = Field(default=None, description="HTTP status of Meta Pixel script")
    meta_advanced_matching: bool = Field(default=False, description="True if Meta AM detected (em/ph params)")
    linkedin_ids: list[str] = Field(default_factory=list, description="LinkedIn Partner IDs found")
    linkedin_status: Optional[int] = Field(default=None, description="HTTP status of LinkedIn script")
    duplicate_tags: bool = Field(default=False, description="True if duplicates detected (2+ same tag)")
    tags_with_errors: list[dict[str, Any]] = Field(
        default_factory=list,
        description="List of tags with HTTP errors (status != 200)",
    )
    total_requests_analyzed: int = Field(..., description="Total number of requests analyzed")


class AttributionResult(BaseModel):
    """Result of attribution testing (Stage 3)."""

    utm_persistence_on_redirect: bool = Field(
        default=False,
        description="True if UTM params survive redirects",
    )
    redirect_strips_params: bool = Field(default=False, description="True if redirect removes query params")
    redirect_type: Optional[str] = Field(default=None, description="HTTP redirect type if detected (301, 302, etc)")
    google_click_id_cookie_dropped: bool = Field(
        default=False,
        description="True if _gcl_aw cookie found",
    )
    meta_click_id_cookie_dropped: bool = Field(default=False, description="True if _fbc cookie found")
    localstorage_utm_saved: bool = Field(
        default=False,
        description="True if any utm_* key found in localStorage",
    )
    cookies_found: list[str] = Field(default_factory=list, description="Names of tracking cookies found")
    cookies_missing: list[str] = Field(
        default_factory=list,
        description="Expected cookies that were not found",
    )
    localStorage_keys: list[str] = Field(default_factory=list, description="UTM-related keys in localStorage")


class SSTResult(BaseModel):
    """Result of Server-Side Tracking detection (Stage 4)."""

    sst_detected: bool = Field(default=False, description="True if any SST infrastructure detected")
    sgtm_subdomain: Optional[str] = Field(
        default=None,
        description="Detected sGTM subdomain (e.g., sgtm.example.com)",
    )
    sgtm_endpoints: list[str] = Field(default_factory=list, description="Detected sGTM proxy endpoints")
    meta_capi_proxy: bool = Field(default=False, description="True if Meta CAPI proxy detected")
    meta_capi_endpoint: Optional[str] = Field(
        default=None,
        description="URL of detected Meta CAPI endpoint",
    )
    httponly_tracking_cookies: bool = Field(
        default=False,
        description="True if HttpOnly tracking cookies found",
    )
    httponly_cookies_list: list[str] = Field(
        default_factory=list,
        description="Names of HttpOnly cookies detected",
    )
    itp_bypass_functional: bool = Field(
        default=False,
        description="True if sGTM or HttpOnly cookies enable ITP bypass",
    )
    subdomains_checked: list[str] = Field(default_factory=list, description="Subdomains tested for SST")


class DataLayerResult(BaseModel):
    """Result of DataLayer inspection (Stage 5)."""

    datalayer_exists: bool = Field(default=False, description="True if window.dataLayer exists")
    datalayer_events_count: int = Field(default=0, description="Total events in dataLayer")
    standard_events_detected: list[str] = Field(
        default_factory=list,
        description="GA4 standard events found (e.g., view_item, add_to_cart)",
    )
    interaction_tracking_active: bool = Field(
        default=False,
        description="True if interaction events (click, form, etc) detected",
    )
    ga4_schema_compliant: bool = Field(
        default=False,
        description="True if dataLayer events follow GA4 schema",
    )
    ecommerce_items_array: bool = Field(
        default=False,
        description="True if ecommerce.items[] array detected",
    )
    required_fields_present: list[str] = Field(
        default_factory=list,
        description="Required fields found (item_id, item_name, price, quantity)",
    )
    missing_required_fields: list[str] = Field(
        default_factory=list,
        description="Required fields missing from items",
    )
    missing_recommended_fields: list[str] = Field(
        default_factory=list,
        description="Recommended fields not present (item_brand, item_category2, etc)",
    )
    sample_events: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Sample events from dataLayer (first 5)",
    )


class ModuleScore(BaseModel):
    """Score for a single module."""

    module_name: str = Field(..., description="Module name (tracking_infrastructure, etc)")
    score: float = Field(..., ge=0, le=5, description="Score 0-5")
    max_score: float = Field(default=5.0, description="Maximum possible score")
    comment: str = Field(..., description="Module evaluation comment (PT-BR)")
    rating: str = Field(..., description="Rating label (Crítico, Básico, Intermediário, Avançado, Excelente)")
    data: dict[str, Any] = Field(default_factory=dict, description="Module-specific data")
    evidence: list[dict[str, Any]] = Field(default_factory=list, description="Evidence items supporting the score")
    scoring_breakdown: str = Field(
        default="",
        description="Human-readable breakdown of score calculation",
    )


class DiagnosticReport(BaseModel):
    """Complete diagnostic report (Stage 6 output)."""

    domain: str = Field(..., description="Domain analyzed")
    audit_timestamp: str = Field(..., description="ISO 8601 timestamp of audit")
    modules: dict[str, ModuleScore] = Field(..., description="Scores for all 4 modules")
    overall_maturity: dict[str, Any] = Field(..., description="Overall score, rating, and comment")
    top_issues: list[dict[str, Any]] = Field(default_factory=list, description="Top 3 critical issues ranked")
    recommendations_summary: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Grouped recommendations (quick_wins, medium_effort, high_effort)",
    )


# ============================================================================
# ASSET LOADERS
# ============================================================================


def load_regex_patterns() -> dict[str, str]:
    """
    Load regex patterns from tools/assets/protocols/regex-patterns.json.

    Returns:
        Dictionary of pattern_name -> regex_string

    Raises:
        FileNotFoundError: If regex patterns file does not exist
        json.JSONDecodeError: If file is not valid JSON
    """
    assets_path = Path(__file__).parent.parent.parent / "assets" / "protocols" / "regex-patterns.json"
    if not assets_path.exists():
        # Return hardcoded patterns as fallback
        return {
            "gtm_container": r"GTM-[A-Z0-9]{6,}",
            "ga4_measurement": r"G-[A-Z0-9]{10}",
            "meta_pixel": r"fbq\(['\"]init['\"]\s*,\s*['\"](\d{10,})",
            "linkedin_partner": r"_linkedin_partner_id\s*=\s*['\"](\d+)",
            "gclid_param": r"[?&]gclid=([^&]+)",
            "fbclid_param": r"[?&]fbclid=([^&]+)",
        }

    with open(assets_path, encoding="utf-8") as f:
        return json.load(f)


def load_ga4_taxonomy() -> dict[str, Any]:
    """
    Load GA4 events taxonomy from tools/assets/protocols/ga4-events-taxonomy.json.

    Returns:
        Dictionary of event definitions and field schemas

    Raises:
        FileNotFoundError: If GA4 taxonomy file does not exist
        json.JSONDecodeError: If file is not valid JSON
    """
    assets_path = Path(__file__).parent.parent.parent / "assets" / "protocols" / "ga4-events-taxonomy.json"
    if not assets_path.exists():
        # Return minimal schema as fallback
        return {
            "standard_events": {
                "page_view": {"description": "Page view event"},
                "view_item": {"description": "Product view"},
                "add_to_cart": {"description": "Add to cart"},
                "begin_checkout": {"description": "Checkout started"},
                "purchase": {"description": "Purchase completed"},
            },
            "ecommerce_fields": {
                "required": ["item_id", "item_name", "price", "quantity"],
                "recommended": [
                    "item_brand",
                    "item_category",
                    "item_category2",
                    "item_variant",
                    "discount",
                    "coupon",
                    "index",
                ],
            },
        }

    with open(assets_path, encoding="utf-8") as f:
        return json.load(f)


def load_scoring_rubrics() -> dict[str, dict[str, Any]]:
    """
    Load scoring rubrics from tools/assets/protocols/scoring-rubrics.json.

    Returns:
        Dictionary of module_name -> rubric definition

    Raises:
        FileNotFoundError: If scoring rubrics file does not exist
        json.JSONDecodeError: If file is not valid JSON
    """
    assets_path = Path(__file__).parent.parent.parent / "assets" / "protocols" / "scoring-rubrics.json"
    if not assets_path.exists():
        # Return minimal rubrics as fallback
        return {
            "tracking_infrastructure": {
                0: "Nenhuma tag detectada",
                1: "Tags com erros ou duplicadas",
                3: "Uma plataforma OK (GA4 ou Meta)",
                4: "GTM + GA4 + Meta ok",
                5: "Tudo ok + Meta Advanced Matching",
            },
            "attribution_health": {
                0: "Sem cookies, sem localStorage",
                2: "Alguns cookies, UTMs perdidos",
                4: "Cookies ok, UTMs preservados",
                5: "Completo com localStorage",
            },
            "server_side_tracking": {
                0: "Sem SST",
                2: "Proxy detectado mas incompleto",
                4: "sGTM funcional",
                5: "sGTM + CAPI + HttpOnly",
            },
            "datalayer_depth": {
                0: "Sem dataLayer",
                2: "DataLayer existe, poucos eventos",
                4: "Eventos completos, schema ok",
                5: "Excelente, todos campos presentes",
            },
        }

    with open(assets_path, encoding="utf-8") as f:
        return json.load(f)


def load_funnel_heuristics() -> dict[str, Any]:
    """
    Load funnel classification heuristics from tools/assets/protocols/funnel-heuristics.json.

    Returns:
        Dictionary with url_patterns, content_signals, sitemap_paths, robots_txt_path.

    Raises:
        FileNotFoundError: If heuristics file does not exist
        json.JSONDecodeError: If file is not valid JSON
    """
    assets_path = Path(__file__).parent.parent.parent / "assets" / "protocols" / "funnel-heuristics.json"
    if not assets_path.exists():
        # Return hardcoded fallback patterns
        return {
            "url_patterns": {
                "home": {
                    "path_exact": ["/", "/home", "/index", "/inicio"],
                    "weight": 0.95,
                },
                "category": {
                    "path_contains": [
                        "/category/", "/categories/", "/collections/", "/c/",
                        "/shop/", "/departamento/", "/browse/", "/catalog/",
                        "/loja/", "/produtos/",
                    ],
                    "weight": 0.7,
                },
                "product": {
                    "path_contains": [
                        "/product/", "/products/", "/p/", "/dp/", "/item/",
                        "/produto/", "/pd/", "/sku/",
                    ],
                    "weight": 0.8,
                },
                "cart": {
                    "path_contains": [
                        "/cart", "/carrinho", "/basket", "/bag", "/sacola", "/cesta",
                    ],
                    "weight": 0.9,
                },
                "checkout": {
                    "path_contains": [
                        "/checkout", "/payment", "/finalizar", "/order",
                        "/pagamento", "/pedido",
                    ],
                    "weight": 0.9,
                },
            },
            "content_signals": {
                "product": {
                    "selectors": [
                        "[data-product-id]", "[itemtype*='Product']",
                        ".product-detail", ".pdp", ".product-price",
                    ],
                },
                "category": {
                    "selectors": [
                        ".product-list", ".product-grid",
                        "[class*='product-card']", "[class*='filter']",
                    ],
                },
                "cart": {
                    "selectors": [
                        "[class*='cart-item']", "[class*='cart-product']",
                        "[class*='subtotal']",
                    ],
                },
                "checkout": {
                    "selectors": [
                        "[class*='checkout-step']", "[class*='payment-method']",
                        "[class*='order-summary']",
                    ],
                },
            },
            "sitemap_paths": [
                "/sitemap.xml", "/sitemap_index.xml",
                "/sitemap-index.xml", "/sitemaps.xml",
            ],
            "robots_txt_path": "/robots.txt",
        }

    with open(assets_path, encoding="utf-8") as f:
        return json.load(f)
