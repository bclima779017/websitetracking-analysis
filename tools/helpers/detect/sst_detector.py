"""
Server-Side Tracking (SST) detection module — Stage 4 of the diagnostic pipeline.

Pure function that analyzes network requests to detect:
- sGTM (Google Tag Manager Server-Side) subdomains
- Meta Conversions API (CAPI) proxy endpoints
- HttpOnly tracking cookies
"""

from __future__ import annotations

from urllib.parse import urlparse

from ..shared.config import COMMON_SGTM_SUBDOMAINS, NetworkRequest, SSTResult


def detect_sst(requests: list[NetworkRequest], domain: str) -> SSTResult:
    """
    Detect Server-Side Tracking infrastructure.

    Analyzes network requests to find:
    1. First-party sGTM subdomains (e.g., sgtm.example.com, data.example.com)
    2. Meta CAPI proxy endpoints (Meta Conversions API)
    3. HttpOnly cookies in Set-Cookie headers
    4. Determines if ITP (Safari tracking prevention) bypass is functional

    Args:
        requests: List of NetworkRequest objects from network interception
        domain: Base domain being analyzed (e.g., example.com)

    Returns:
        SSTResult with SST infrastructure details
    """
    sst_detected = False
    sgtm_subdomain: str | None = None
    sgtm_endpoints: list[str] = []
    meta_capi_proxy = False
    meta_capi_endpoint: str | None = None
    httponly_tracking_cookies: bool = False
    httponly_cookies_list: list[str] = []
    subdomains_checked: list[str] = []

    # Normalize domain (remove www, get base domain)
    domain_parts = domain.replace("www.", "").split(".")
    if len(domain_parts) > 2:
        # Handle subdomains: extract last 2 parts
        base_domain = ".".join(domain_parts[-2:])
    else:
        base_domain = domain.replace("www.", "")

    # Check for sGTM subdomains in requests
    sgtm_candidates: set[str] = set()

    for req in requests:
        parsed = urlparse(req.url)
        req_domain = parsed.netloc.lower()

        # Check if request is from a first-party subdomain
        for sgtm_prefix in COMMON_SGTM_SUBDOMAINS:
            # Build possible sGTM subdomain
            sgtm_test = f"{sgtm_prefix}.{base_domain}"
            subdomains_checked.append(sgtm_test)

            if sgtm_test in req_domain:
                sgtm_detected = True
                if sgtm_subdomain is None:
                    sgtm_subdomain = sgtm_test
                sgtm_candidates.add(sgtm_test)

                # Look for sGTM endpoints (typically /gtag/js or /g/collect patterns)
                if "/gtag/" in req.url or "/g/collect" in req.url or "/events" in req.url:
                    if req.url not in sgtm_endpoints:
                        sgtm_endpoints.append(req.url)

    # Check for Meta CAPI proxy endpoints
    for req in requests:
        # Meta CAPI typically sends to first-party domain with /api/meta or similar
        if ("/api/meta" in req.url or "/conversions" in req.url or "/capi" in req.url):
            if base_domain in req.url:
                meta_capi_proxy = True
                meta_capi_endpoint = req.url
                sst_detected = True

        # Also check for obvious Meta CAPI headers or patterns
        if "conversions-api" in req.url.lower() or "graph.facebook.com" in req.url:
            if req.method == "POST":
                meta_capi_proxy = True
                if not meta_capi_endpoint:
                    meta_capi_endpoint = req.url
                sst_detected = True

    # Check for HttpOnly cookies in response headers
    for req in requests:
        headers = req.headers
        set_cookie = headers.get("set-cookie", "") or headers.get("Set-Cookie", "")

        if set_cookie:
            # Check if HttpOnly flag is present
            if "httponly" in set_cookie.lower():
                httponly_tracking_cookies = True

                # Extract cookie name
                cookie_parts = set_cookie.split(";")
                if cookie_parts:
                    cookie_name = cookie_parts[0].split("=")[0].strip()
                    # Look for tracking-related cookies
                    if any(track in cookie_name.lower() for track in ["_ga", "_fbc", "_fbp", "_gclid", "fbp", "gclid"]):
                        if cookie_name not in httponly_cookies_list:
                            httponly_cookies_list.append(cookie_name)

    # Determine ITP bypass functionality
    # ITP bypass works if: sGTM present OR HttpOnly cookies present
    itp_bypass_functional = httponly_tracking_cookies or bool(sgtm_subdomain)

    # Remove duplicates and deduplicate subdomains checked
    subdomains_checked = list(set(subdomains_checked))

    return SSTResult(
        sst_detected=sst_detected,
        sgtm_subdomain=sgtm_subdomain,
        sgtm_endpoints=sgtm_endpoints,
        meta_capi_proxy=meta_capi_proxy,
        meta_capi_endpoint=meta_capi_endpoint,
        httponly_tracking_cookies=httponly_tracking_cookies,
        httponly_cookies_list=httponly_cookies_list,
        itp_bypass_functional=itp_bypass_functional,
        subdomains_checked=subdomains_checked,
    )
