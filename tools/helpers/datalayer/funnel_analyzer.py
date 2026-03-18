"""
Funnel DataLayer analyzer — cross-references detected events per page against
the expected event map to produce per-page and aggregate scores.

Pure function with no side effects.
"""

from __future__ import annotations

from typing import Any

from ..shared.config import FunnelDataLayerResult, PageDataLayerResult


def build_funnel_datalayer_result(
    raw_per_page: dict[str, dict],
    event_map: dict[str, Any],
) -> FunnelDataLayerResult:
    """
    Build a FunnelDataLayerResult from raw subprocess data and the event map.

    Args:
        raw_per_page: stage -> dict with keys: url, accessible, datalayer_exists,
                      events_detected, ecommerce_items_array, ga4_schema_compliant,
                      required_fields_present, missing_required_fields, sample_events
        event_map: Loaded funnel-event-map.json with stage_weights and stages

    Returns:
        FunnelDataLayerResult with per-page scores and weighted aggregate
    """
    stage_weights = event_map.get("stage_weights", {})
    stages_def = event_map.get("stages", {})

    pages: dict[str, PageDataLayerResult] = {}
    total_events = 0
    total_expected_load = 0
    total_matched_load = 0

    weighted_score_sum = 0.0
    weight_sum = 0.0

    for stage, raw in raw_per_page.items():
        expected_events = stages_def.get(stage, {}).get("expected_events", [])
        events_detected = set(raw.get("events_detected", []))
        accessible = raw.get("accessible", True)
        datalayer_exists = raw.get("datalayer_exists", False)

        matched = []
        missing_load = []
        missing_interaction = []

        load_expected_count = 0
        load_matched_count = 0

        for ev_def in expected_events:
            ev_name = ev_def["event"]
            ev_type = ev_def.get("type", "load")

            if ev_name in events_detected:
                matched.append(ev_name)
                if ev_type == "load":
                    load_matched_count += 1
            else:
                if ev_type == "load":
                    missing_load.append(ev_name)
                else:
                    missing_interaction.append(ev_name)

            if ev_type == "load":
                load_expected_count += 1

        # Calculate page score
        page_score = _calculate_page_score(
            accessible=accessible,
            datalayer_exists=datalayer_exists,
            load_matched=load_matched_count,
            load_expected=load_expected_count,
            ecommerce_items=raw.get("ecommerce_items_array", False),
            ga4_schema_compliant=raw.get("ga4_schema_compliant", False),
            required_fields=raw.get("required_fields_present", []),
            stage=stage,
        )

        page_result = PageDataLayerResult(
            stage=stage,
            url=raw.get("url", ""),
            accessible=accessible,
            datalayer_exists=datalayer_exists,
            events_detected=list(events_detected),
            expected_events=expected_events,
            matched_events=matched,
            missing_load_events=missing_load,
            missing_interaction_events=missing_interaction,
            ecommerce_items_array=raw.get("ecommerce_items_array", False),
            ga4_schema_compliant=raw.get("ga4_schema_compliant", False),
            required_fields_present=raw.get("required_fields_present", []),
            missing_required_fields=raw.get("missing_required_fields", []),
            page_score=page_score,
            sample_events=raw.get("sample_events", [])[:5],
        )
        pages[stage] = page_result

        total_events += len(events_detected)
        total_expected_load += load_expected_count
        total_matched_load += load_matched_count

        # Weighted aggregate (skip inaccessible pages)
        if accessible:
            w = stage_weights.get(stage, 0.1)
            weighted_score_sum += page_score * w
            weight_sum += w

    # Aggregate score
    aggregate_score = 0.0
    if weight_sum > 0:
        aggregate_score = min(weighted_score_sum / weight_sum, 5.0)

    accessible_count = sum(1 for p in pages.values() if p.accessible)
    total_stages = len(pages)
    funnel_coverage = accessible_count / total_stages if total_stages > 0 else 0.0

    return FunnelDataLayerResult(
        pages=pages,
        aggregate_score=round(aggregate_score, 2),
        funnel_coverage=round(funnel_coverage, 2),
        total_events_detected=total_events,
        total_expected_load_events=total_expected_load,
        total_matched_load_events=total_matched_load,
    )


def _calculate_page_score(
    accessible: bool,
    datalayer_exists: bool,
    load_matched: int,
    load_expected: int,
    ecommerce_items: bool,
    ga4_schema_compliant: bool,
    required_fields: list[str],
    stage: str,
) -> float:
    """
    Calculate score for a single funnel page (0-5).

    Breakdown:
    - Coverage of load events: up to 3.0 points
    - Ecommerce schema compliance (product/cart/checkout only): +1.0
    - Required fields coverage >= 75%: +1.0
    """
    if not accessible:
        return 0.0

    if not datalayer_exists:
        return 0.0

    score = 0.0

    # Coverage of load events (up to 3.0)
    if load_expected > 0:
        coverage = load_matched / load_expected
        score += coverage * 3.0
    else:
        score += 3.0  # No load events expected = full marks

    # Ecommerce schema bonus (only relevant for product, cart, checkout)
    ecommerce_stages = {"product", "cart", "checkout"}
    if stage in ecommerce_stages:
        if ecommerce_items and ga4_schema_compliant:
            score += 1.0

        # Required fields coverage
        required_total = 4  # item_id, item_name, price, quantity
        if required_fields and len(required_fields) / required_total >= 0.75:
            score += 1.0
    else:
        # Non-ecommerce stages get the 2 bonus points automatically
        score += 2.0

    return min(score, 5.0)
