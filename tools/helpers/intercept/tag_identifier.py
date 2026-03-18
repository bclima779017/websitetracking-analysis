"""
Tag identification module — Stage 2 of the diagnostic pipeline.

Pure function that applies regex patterns to captured network requests
to identify tracking tags (GTM, GA4, Meta Pixel, LinkedIn).
"""

from __future__ import annotations

import re
from typing import Any

from ..shared.config import NetworkRequest, TagIdentification, load_regex_patterns


def identify_tags(requests: list[NetworkRequest], patterns: dict[str, str] | None = None) -> TagIdentification:
    """
    Identify tracking tags from intercepted network requests.

    Applies regex patterns to request URLs to extract:
    - Google Tag Manager (GTM) container IDs
    - Google Analytics 4 (GA4) measurement IDs
    - Meta Pixel IDs (with Advanced Matching detection)
    - LinkedIn Insight Tag Partner IDs

    Detects:
    - Duplicate tags (2+ of same type)
    - HTTP errors on tag loads (status != 200)
    - Meta Advanced Matching (em, ph params in facebook.com/tr/ payloads)

    Args:
        requests: List of NetworkRequest objects from network interception
        patterns: Optional dict of regex patterns (loaded from assets if None)

    Returns:
        TagIdentification with found IDs, duplicates flag, and error details
    """
    if patterns is None:
        patterns = load_regex_patterns()

    # Extract Google Tag Manager (GTM)
    gtm_ids: list[str] = []
    gtm_status: int | None = None

    for req in requests:
        if "googletagmanager.com/gtm.js" in req.url:
            gtm_status = req.status
            match = re.search(patterns.get("gtm_container", r"GTM-[A-Z0-9]{6,}"), req.url)
            if match:
                gtm_id = match.group(0)
                if gtm_id not in gtm_ids:
                    gtm_ids.append(gtm_id)

    # Extract Google Analytics 4 (GA4)
    # GA4 loads via googletagmanager.com/gtag/js?id=G-* and sends data to
    # analytics.google.com/g/collect — both patterns must be checked
    ga4_ids: list[str] = []
    ga4_status: int | None = None
    ga4_pattern = patterns.get("ga4_measurement", r"G-[A-Z0-9]{6,10}")

    for req in requests:
        is_ga4_url = (
            "google-analytics.com" in req.url
            or "googleanalytics.com" in req.url
            or "analytics.google.com" in req.url
            or ("googletagmanager.com/gtag/js" in req.url and "id=G-" in req.url)
        )
        if is_ga4_url:
            if ga4_status is None:
                ga4_status = req.status
            match = re.search(ga4_pattern, req.url)
            if match:
                ga4_id = match.group(0)
                if ga4_id not in ga4_ids:
                    ga4_ids.append(ga4_id)

    # Extract Meta Pixel
    meta_pixel_ids: list[str] = []
    meta_pixel_status: int | None = None
    meta_advanced_matching = False

    for req in requests:
        # Check for fbevents.js
        if "fbevents.js" in req.url:
            meta_pixel_status = req.status

        # Check for Meta pixel init in requests
        if "facebook.com" in req.url or "facebook.net" in req.url:
            match = re.search(r"(?:id[=:]|pixel[_-]?id[=:]|fid[=:])\s*['\"]?(\d{10,})", req.url)
            if match:
                pixel_id = match.group(1)
                if pixel_id not in meta_pixel_ids:
                    meta_pixel_ids.append(pixel_id)

            # Detect Advanced Matching (em, ph, fn, ln, ct, st, zp, country params)
            if any(param in req.url for param in ["em=", "ph=", "fn=", "ln=", "ct=", "st=", "zp=", "country="]):
                meta_advanced_matching = True

    # Extract LinkedIn Insight Tag
    linkedin_ids: list[str] = []
    linkedin_status: int | None = None

    for req in requests:
        if "snap.licdn.com" in req.url or "licdn.com" in req.url:
            linkedin_status = req.status
            match = re.search(patterns.get("linkedin_partner", r"_linkedin_partner_id['\"]?\s*[=:]\s*['\"]?(\d+)"), req.url)
            if match:
                partner_id = match.group(1)
                if partner_id not in linkedin_ids:
                    linkedin_ids.append(partner_id)

    # Detect duplicates
    duplicate_tags = (
        len(gtm_ids) > 1 or len(ga4_ids) > 1 or len(meta_pixel_ids) > 1 or len(linkedin_ids) > 1
    )

    # Collect tags with HTTP errors
    tags_with_errors: list[dict[str, Any]] = []

    if gtm_status and gtm_status >= 400:
        tags_with_errors.append({
            "tag_type": "GTM",
            "status": gtm_status,
            "ids": gtm_ids,
        })

    if ga4_status and ga4_status >= 400:
        tags_with_errors.append({
            "tag_type": "GA4",
            "status": ga4_status,
            "ids": ga4_ids,
        })

    if meta_pixel_status and meta_pixel_status >= 400:
        tags_with_errors.append({
            "tag_type": "Meta Pixel",
            "status": meta_pixel_status,
            "ids": meta_pixel_ids,
        })

    if linkedin_status and linkedin_status >= 400:
        tags_with_errors.append({
            "tag_type": "LinkedIn",
            "status": linkedin_status,
            "ids": linkedin_ids,
        })

    return TagIdentification(
        gtm_ids=gtm_ids,
        gtm_status=gtm_status,
        ga4_ids=ga4_ids,
        ga4_status=ga4_status,
        meta_pixel_ids=meta_pixel_ids,
        meta_pixel_status=meta_pixel_status,
        meta_advanced_matching=meta_advanced_matching,
        linkedin_ids=linkedin_ids,
        linkedin_status=linkedin_status,
        duplicate_tags=duplicate_tags,
        tags_with_errors=tags_with_errors,
        total_requests_analyzed=len(requests),
    )
