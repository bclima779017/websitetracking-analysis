"""
Report generation module — Stage 6 of the diagnostic pipeline.

Assembles the final diagnostic report from all pipeline stages.
Generates PT-BR comments, evidence items, and recommendations.
Pure function with no side effects.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ..shared.config import (
    AttributionResult,
    DataLayerResult,
    DiagnosticReport,
    FunnelDataLayerResult,
    ModuleScore,
    SSTResult,
    TagIdentification,
)


def generate_report(
    url: str,
    tag_data: TagIdentification,
    attribution_data: AttributionResult,
    sst_data: SSTResult,
    datalayer_data: DataLayerResult,
    scores: list[ModuleScore],
    overall: dict[str, Any],
    funnel_datalayer: FunnelDataLayerResult | None = None,
) -> DiagnosticReport:
    """
    Generate final diagnostic report from all pipeline outputs.

    Assembles JSON payload with:
    - Module scores and data
    - Evidence items per module (pass/fail checks with details)
    - Top 3 critical issues ranked by severity
    - Recommendations grouped by effort level (quick_wins, medium_effort, high_effort)

    Args:
        url: Domain analyzed (e.g., example.com)
        tag_data: TagIdentification from Stage 2
        attribution_data: AttributionResult from Stage 3
        sst_data: SSTResult from Stage 4
        datalayer_data: DataLayerResult from Stage 5
        scores: List of ModuleScore from Stage 6
        overall: Overall maturity dict from scorer
        funnel_datalayer: Optional per-page funnel DataLayer analysis

    Returns:
        DiagnosticReport matching sample-diagnostic.json contract
    """
    # Extract domain from URL if needed
    if url.startswith("http"):
        from urllib.parse import urlparse
        domain = urlparse(url).netloc
    else:
        domain = url

    # Build modules dict with evidence and data
    modules = {}

    # Find scores by module name for easy lookup
    score_map = {s.module_name: s for s in scores}

    # === TRACKING INFRASTRUCTURE ===
    ti_score = score_map.get("tracking_infrastructure", scores[0])
    modules["tracking_infrastructure"] = {
        "module_name": "tracking_infrastructure",
        "rating": ti_score.rating,
        "score": ti_score.score,
        "max_score": ti_score.max_score,
        "comment": ti_score.comment,
        "data": {
            "gtm_installed": bool(tag_data.gtm_ids),
            "gtm_ids": tag_data.gtm_ids,
            "ga4_installed": bool(tag_data.ga4_ids),
            "ga4_ids": tag_data.ga4_ids,
            "meta_pixel_installed": bool(tag_data.meta_pixel_ids),
            "meta_pixel_ids": tag_data.meta_pixel_ids,
            "meta_advanced_matching": tag_data.meta_advanced_matching,
            "linkedin_insight_installed": bool(tag_data.linkedin_ids),
            "tags_with_errors": tag_data.tags_with_errors,
            "duplicate_tags": tag_data.duplicate_tags,
        },
        "evidence": _generate_tracking_infrastructure_evidence(tag_data),
        "scoring_breakdown": ti_score.scoring_breakdown,
    }

    # === ATTRIBUTION HEALTH ===
    ah_score = score_map.get("attribution_health", scores[1] if len(scores) > 1 else scores[0])
    modules["attribution_health"] = {
        "module_name": "attribution_health",
        "rating": ah_score.rating,
        "score": ah_score.score,
        "max_score": ah_score.max_score,
        "comment": ah_score.comment,
        "data": {
            "utm_persistence_on_redirect": attribution_data.utm_persistence_on_redirect,
            "redirect_strips_params": attribution_data.redirect_strips_params,
            "redirect_type": attribution_data.redirect_type,
            "google_click_id_cookie_dropped": attribution_data.google_click_id_cookie_dropped,
            "meta_click_id_cookie_dropped": attribution_data.meta_click_id_cookie_dropped,
            "localstorage_utm_saved": attribution_data.localstorage_utm_saved,
            "cookies_found": attribution_data.cookies_found,
            "cookies_missing": attribution_data.cookies_missing,
        },
        "evidence": _generate_attribution_evidence(attribution_data),
        "scoring_breakdown": ah_score.scoring_breakdown,
    }

    # === SERVER SIDE TRACKING ===
    sst_score = score_map.get("server_side_tracking", scores[2] if len(scores) > 2 else scores[0])
    modules["server_side_tracking"] = {
        "module_name": "server_side_tracking",
        "rating": sst_score.rating,
        "score": sst_score.score,
        "max_score": sst_score.max_score,
        "comment": sst_score.comment,
        "data": {
            "sst_detected": sst_data.sst_detected,
            "sgtm_subdomain": sst_data.sgtm_subdomain,
            "sgtm_endpoints": sst_data.sgtm_endpoints,
            "meta_capi_proxy": sst_data.meta_capi_proxy,
            "httponly_tracking_cookies": sst_data.httponly_tracking_cookies,
            "itp_bypass_functional": sst_data.itp_bypass_functional,
        },
        "evidence": _generate_sst_evidence(sst_data),
        "scoring_breakdown": sst_score.scoring_breakdown,
    }

    # === DATALAYER DEPTH ===
    dl_score = score_map.get("datalayer_depth", scores[3] if len(scores) > 3 else scores[0])

    if funnel_datalayer and funnel_datalayer.pages:
        dl_evidence = _generate_funnel_datalayer_evidence(funnel_datalayer)
        dl_module_data = {
            "datalayer_exists": datalayer_data.datalayer_exists,
            "datalayer_events_count": datalayer_data.datalayer_events_count,
            "standard_events_detected": datalayer_data.standard_events_detected,
            "interaction_tracking_active": datalayer_data.interaction_tracking_active,
            "ga4_schema_compliant": datalayer_data.ga4_schema_compliant,
            "ecommerce_items_array": datalayer_data.ecommerce_items_array,
            "required_fields_present": datalayer_data.required_fields_present,
            "missing_recommended_fields": datalayer_data.missing_recommended_fields,
            "funnel_analysis": funnel_datalayer.model_dump(),
        }
    else:
        dl_evidence = _generate_datalayer_evidence(datalayer_data)
        dl_module_data = {
            "datalayer_exists": datalayer_data.datalayer_exists,
            "datalayer_events_count": datalayer_data.datalayer_events_count,
            "standard_events_detected": datalayer_data.standard_events_detected,
            "interaction_tracking_active": datalayer_data.interaction_tracking_active,
            "ga4_schema_compliant": datalayer_data.ga4_schema_compliant,
            "ecommerce_items_array": datalayer_data.ecommerce_items_array,
            "required_fields_present": datalayer_data.required_fields_present,
            "missing_recommended_fields": datalayer_data.missing_recommended_fields,
        }

    modules["datalayer_depth"] = {
        "module_name": "datalayer_depth",
        "rating": dl_score.rating,
        "score": dl_score.score,
        "max_score": dl_score.max_score,
        "comment": dl_score.comment,
        "data": dl_module_data,
        "evidence": dl_evidence,
        "scoring_breakdown": dl_score.scoring_breakdown,
    }

    # Generate top issues
    top_issues = _generate_top_issues(modules)

    # Generate recommendations (pass funnel data for per-page recs)
    recommendations = _generate_recommendations(modules, funnel_datalayer=funnel_datalayer)

    return DiagnosticReport(
        domain=domain,
        audit_timestamp=datetime.utcnow().isoformat() + "Z",
        modules=modules,
        overall_maturity=overall,
        top_issues=top_issues,
        recommendations_summary=recommendations,
        funnel_analysis=funnel_datalayer,
    )


def _generate_tracking_infrastructure_evidence(tag_data: TagIdentification) -> list[dict[str, Any]]:
    """Generate evidence items for tracking infrastructure module."""
    evidence = []

    # GTM check
    if tag_data.gtm_ids:
        evidence.append({
            "check": "Google Tag Manager (GTM)",
            "result": "pass" if tag_data.gtm_status == 200 else "fail",
            "score_impact": "+1",
            "detail": f"Container(s) {tag_data.gtm_ids} detectado(s) com status {tag_data.gtm_status}",
            "source": "Network request interceptado ao carregar a página",
            "url_captured": f"googletagmanager.com/gtm.js?id={tag_data.gtm_ids[0]}" if tag_data.gtm_ids else None,
        })
    else:
        evidence.append({
            "check": "Google Tag Manager (GTM)",
            "result": "fail",
            "score_impact": "0",
            "detail": "GTM não detectado",
            "source": "Nenhuma requisição para googletagmanager.com encontrada",
            "url_captured": None,
        })

    # GA4 check
    if tag_data.ga4_ids:
        evidence.append({
            "check": "Google Analytics 4 (GA4)",
            "result": "pass" if tag_data.ga4_status == 200 else "fail",
            "score_impact": "+1",
            "detail": f"Medição(ões) {tag_data.ga4_ids} com status {tag_data.ga4_status}",
            "source": "Request de coleta GA4 interceptado",
            "url_captured": f"google-analytics.com/g/collect?tid={tag_data.ga4_ids[0]}" if tag_data.ga4_ids else None,
        })
    else:
        evidence.append({
            "check": "Google Analytics 4 (GA4)",
            "result": "fail",
            "score_impact": "0",
            "detail": "GA4 não detectado",
            "source": "Nenhuma requisição para google-analytics.com encontrada",
            "url_captured": None,
        })

    # Meta Pixel check
    if tag_data.meta_pixel_ids:
        evidence.append({
            "check": "Meta Pixel",
            "result": "pass" if tag_data.meta_pixel_status == 200 else "fail",
            "score_impact": "+1",
            "detail": f"Pixel ID(s) {tag_data.meta_pixel_ids} com status {tag_data.meta_pixel_status}",
            "source": "fbevents.js carregado",
            "url_captured": "connect.facebook.net/en_US/fbevents.js",
        })
    else:
        evidence.append({
            "check": "Meta Pixel",
            "result": "fail",
            "score_impact": "0",
            "detail": "Meta Pixel não detectado",
            "source": "Nenhuma requisição para facebook.net ou facebook.com",
            "url_captured": None,
        })

    # Meta Advanced Matching
    if tag_data.meta_pixel_ids:
        evidence.append({
            "check": "Meta Advanced Matching",
            "result": "pass" if tag_data.meta_advanced_matching else "fail",
            "score_impact": "+1 se presente" if tag_data.meta_advanced_matching else "0",
            "detail": "Advanced Matching detectado" if tag_data.meta_advanced_matching else "Advanced Matching não detectado",
            "source": "Análise de parâmetros fbq('init')",
            "url_captured": None,
        })

    # Duplicates check
    evidence.append({
        "check": "Tags duplicadas",
        "result": "fail" if tag_data.duplicate_tags else "pass",
        "score_impact": "-1" if tag_data.duplicate_tags else "+1",
        "detail": "Duplicatas detectadas" if tag_data.duplicate_tags else "Nenhuma duplicação detectada",
        "source": "Contagem de IDs únicos nos requests de rede",
        "url_captured": None,
    })

    return evidence


def _generate_attribution_evidence(attr_data: AttributionResult) -> list[dict[str, Any]]:
    """Generate evidence items for attribution health module."""
    evidence = []

    # UTM persistence
    evidence.append({
        "check": "Persistência de UTMs no redirect",
        "result": "pass" if attr_data.utm_persistence_on_redirect else "fail",
        "score_impact": "+1" if attr_data.utm_persistence_on_redirect else "-2",
        "detail": "UTMs preservados" if attr_data.utm_persistence_on_redirect else "UTMs perdidos no redirect",
        "source": "Simulação de acesso com UTMs",
        "test_input": "?utm_source=google&utm_medium=cpc&utm_campaign=test",
        "test_output": "UTMs presentes" if attr_data.utm_persistence_on_redirect else "UTMs removidos",
    })

    # Google click ID cookie
    evidence.append({
        "check": "Cookie _gcl_aw (Google Ads)",
        "result": "pass" if attr_data.google_click_id_cookie_dropped else "fail",
        "score_impact": "+1" if attr_data.google_click_id_cookie_dropped else "-1",
        "detail": "Cookie presente" if attr_data.google_click_id_cookie_dropped else "Cookie não encontrado",
        "source": "Inspeção de document.cookie após navegação",
        "cookies_snapshot": {
            "expected": "_gcl_aw=GCL.*",
            "found": "_gcl_aw" if attr_data.google_click_id_cookie_dropped else "não encontrado",
        },
    })

    # Meta click ID cookie
    evidence.append({
        "check": "Cookie _fbc (Meta)",
        "result": "pass" if attr_data.meta_click_id_cookie_dropped else "fail",
        "score_impact": "+1" if attr_data.meta_click_id_cookie_dropped else "0",
        "detail": "Cookie presente" if attr_data.meta_click_id_cookie_dropped else "Cookie não encontrado",
        "source": "Inspeção de document.cookie",
        "cookies_snapshot": {
            "expected": "_fbc=fb.*",
            "found": "_fbc" if attr_data.meta_click_id_cookie_dropped else "não encontrado",
        },
    })

    # localStorage check
    evidence.append({
        "check": "Backup de UTMs em localStorage",
        "result": "pass" if attr_data.localstorage_utm_saved else "fail",
        "score_impact": "0",
        "detail": "UTMs em localStorage" if attr_data.localstorage_utm_saved else "Sem fallback de UTMs",
        "source": "Inspeção de localStorage",
        "test_output": attr_data.localStorage_keys if attr_data.localStorage_keys else "null",
    })

    return evidence


def _generate_sst_evidence(sst_data: SSTResult) -> list[dict[str, Any]]:
    """Generate evidence items for server-side tracking module."""
    evidence = []

    # sGTM check
    evidence.append({
        "check": "Subdomínio sGTM",
        "result": "pass" if sst_data.sgtm_subdomain else "fail",
        "score_impact": "+2" if sst_data.sgtm_subdomain else "0",
        "detail": f"Detectado: {sst_data.sgtm_subdomain}" if sst_data.sgtm_subdomain else "Não encontrado",
        "source": "DNS lookup de subdomínios comuns",
        "subdomains_tested": sst_data.subdomains_checked[:4],
    })

    # Meta CAPI check
    evidence.append({
        "check": "Meta Conversions API (CAPI)",
        "result": "pass" if sst_data.meta_capi_proxy else "fail",
        "score_impact": "+1" if sst_data.meta_capi_proxy else "0",
        "detail": f"Detectado: {sst_data.meta_capi_endpoint}" if sst_data.meta_capi_endpoint else "Não detectado",
        "source": "Análise de requests para endpoints de proxy",
        "url_captured": sst_data.meta_capi_endpoint,
    })

    # HttpOnly cookies check
    evidence.append({
        "check": "Cookies HttpOnly de tracking",
        "result": "pass" if sst_data.httponly_tracking_cookies else "fail",
        "score_impact": "+1" if sst_data.httponly_tracking_cookies else "0",
        "detail": f"Encontrados: {sst_data.httponly_cookies_list}" if sst_data.httponly_cookies_list else "Nenhum detectado",
        "source": "Análise de Set-Cookie headers",
        "cookies_analyzed": sst_data.httponly_cookies_list,
    })

    return evidence


def _generate_datalayer_evidence(dl_data: DataLayerResult) -> list[dict[str, Any]]:
    """Generate evidence items for datalayer depth module."""
    evidence = []

    # DataLayer presence
    evidence.append({
        "check": "DataLayer presente",
        "result": "pass" if dl_data.datalayer_exists else "fail",
        "score_impact": "+1" if dl_data.datalayer_exists else "0",
        "detail": f"{dl_data.datalayer_events_count} eventos encontrados" if dl_data.datalayer_exists else "Não encontrado",
        "source": "Execução de window.dataLayer no console",
        "test_output": f"window.dataLayer.length = {dl_data.datalayer_events_count}" if dl_data.datalayer_exists else "undefined",
    })

    # Standard events
    if dl_data.standard_events_detected:
        evidence.append({
            "check": "Eventos GA4 padrão",
            "result": "pass",
            "score_impact": "+1",
            "detail": f"{len(dl_data.standard_events_detected)} eventos: {', '.join(dl_data.standard_events_detected[:3])}",
            "source": "Filtragem de window.dataLayer por event name",
            "events_found": dl_data.standard_events_detected[:3],
        })

    # Required fields
    if dl_data.ecommerce_items_array:
        evidence.append({
            "check": "Schema GA4 — campos obrigatórios",
            "result": "pass" if dl_data.required_fields_present else "fail",
            "score_impact": "+1" if dl_data.required_fields_present else "0",
            "detail": f"Presentes: {', '.join(dl_data.required_fields_present)}" if dl_data.required_fields_present else "Faltam campos",
            "source": "Validação do array items[]",
            "fields_present": dl_data.required_fields_present,
        })

    # Recommended fields
    if dl_data.ecommerce_items_array:
        percent_present = (
            100 * (7 - len(dl_data.missing_recommended_fields)) / 7
            if dl_data.missing_recommended_fields
            else 100
        )
        evidence.append({
            "check": "Schema GA4 — campos recomendados",
            "result": "pass" if len(dl_data.missing_recommended_fields) < 3 else "partial",
            "score_impact": "+1" if len(dl_data.missing_recommended_fields) < 3 else "+0.5",
            "detail": f"{percent_present:.0f}% dos campos recomendados presentes",
            "source": "Comparação com schema GA4",
            "fields_missing": dl_data.missing_recommended_fields,
        })

    return evidence


def _generate_funnel_datalayer_evidence(funnel_dl: FunnelDataLayerResult) -> list[dict[str, Any]]:
    """Generate evidence items for per-page funnel DataLayer analysis."""
    evidence = []

    stage_labels = {
        "home": "Home", "category": "Categoria", "product": "Produto",
        "cart": "Carrinho", "checkout": "Checkout",
    }

    for stage, page_data in funnel_dl.pages.items():
        label = stage_labels.get(stage, stage)

        if not page_data.accessible:
            evidence.append({
                "check": f"DataLayer — {label}",
                "result": "info",
                "score_impact": "skip",
                "detail": f"Página inacessível (login/redirect): {page_data.url}",
                "source": "Navegação com Playwright",
                "url_captured": page_data.url,
            })
            continue

        if not page_data.datalayer_exists:
            evidence.append({
                "check": f"DataLayer — {label}",
                "result": "fail",
                "score_impact": "0",
                "detail": f"window.dataLayer não encontrado em {label}",
                "source": f"Execução de window.dataLayer em {page_data.url}",
                "url_captured": page_data.url,
            })
            continue

        # Load events check
        if page_data.missing_load_events:
            evidence.append({
                "check": f"Eventos de carregamento — {label}",
                "result": "fail",
                "score_impact": f"-{len(page_data.missing_load_events)} eventos",
                "detail": f"Eventos faltando em {label}: {', '.join(page_data.missing_load_events)}",
                "source": f"Comparação com funnel-event-map para {stage}",
                "url_captured": page_data.url,
                "matched_events": page_data.matched_events,
                "missing_events": page_data.missing_load_events,
            })
        else:
            evidence.append({
                "check": f"Eventos de carregamento — {label}",
                "result": "pass",
                "score_impact": f"+{len(page_data.matched_events)} eventos",
                "detail": f"Todos eventos de carregamento presentes em {label}: {', '.join(page_data.matched_events)}",
                "source": f"Comparação com funnel-event-map para {stage}",
                "url_captured": page_data.url,
                "matched_events": page_data.matched_events,
            })

        # Interaction events (informational)
        if page_data.missing_interaction_events:
            evidence.append({
                "check": f"Eventos de interação — {label}",
                "result": "info",
                "score_impact": "informativo",
                "detail": f"Eventos de interação não detectados em {label}: {', '.join(page_data.missing_interaction_events)}",
                "source": "Eventos de interação requerem ação do usuário — não penalizam",
                "url_captured": page_data.url,
            })

        # Ecommerce schema (for product/cart/checkout)
        if stage in ("product", "cart", "checkout"):
            if page_data.ecommerce_items_array:
                evidence.append({
                    "check": f"Schema e-commerce — {label}",
                    "result": "pass" if page_data.ga4_schema_compliant else "partial",
                    "score_impact": "+1" if page_data.ga4_schema_compliant else "+0.5",
                    "detail": f"Schema GA4 {'compliant' if page_data.ga4_schema_compliant else 'parcial'} em {label}",
                    "source": "Validação do array ecommerce.items[]",
                    "fields_present": page_data.required_fields_present,
                    "fields_missing": page_data.missing_required_fields,
                })

    # Overall coverage
    evidence.append({
        "check": "Cobertura do funil",
        "result": "pass" if funnel_dl.funnel_coverage >= 0.8 else "partial" if funnel_dl.funnel_coverage >= 0.5 else "fail",
        "score_impact": f"Score agregado: {funnel_dl.aggregate_score:.1f}/5",
        "detail": f"{int(funnel_dl.funnel_coverage * 100)}% das etapas do funil analisadas, "
                  f"{funnel_dl.total_matched_load_events}/{funnel_dl.total_expected_load_events} eventos de carregamento detectados",
        "source": "Análise agregada por página do funil",
    })

    return evidence


def _generate_top_issues(modules: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Generate top 3 issues ranked by severity."""
    issues = []

    # Collect all potential issues
    all_issues = []

    # Attribution issues
    if modules["attribution_health"]["data"]["redirect_strips_params"]:
        all_issues.append({
            "severity": "critical",
            "module": "attribution_health",
            "title": "Redirecionamentos limpam UTMs",
            "score_impact": -2,
        })

    if not modules["attribution_health"]["data"]["google_click_id_cookie_dropped"]:
        all_issues.append({
            "severity": "critical",
            "module": "attribution_health",
            "title": "Cookie _gcl_aw não é criado",
            "score_impact": -1,
        })

    # SST issues
    if not modules["server_side_tracking"]["data"]["sst_detected"]:
        all_issues.append({
            "severity": "critical",
            "module": "server_side_tracking",
            "title": "Sem infraestrutura Server-Side",
            "score_impact": 0,
        })

    # Tracking infrastructure issues
    if not modules["tracking_infrastructure"]["data"]["gtm_installed"]:
        all_issues.append({
            "severity": "warning",
            "module": "tracking_infrastructure",
            "title": "GTM não instalado",
            "score_impact": -1,
        })

    if modules["tracking_infrastructure"]["data"]["duplicate_tags"]:
        all_issues.append({
            "severity": "warning",
            "module": "tracking_infrastructure",
            "title": "Tags duplicadas detectadas",
            "score_impact": -1,
        })

    if not modules["tracking_infrastructure"]["data"]["meta_advanced_matching"]:
        all_issues.append({
            "severity": "warning",
            "module": "tracking_infrastructure",
            "title": "Meta Pixel sem Advanced Matching",
            "score_impact": 0,
        })

    # Sort by severity (critical first) and take top 3
    severity_order = {"critical": 0, "high": 1, "warning": 2, "info": 3}
    all_issues.sort(key=lambda x: (severity_order.get(x["severity"], 4), x["score_impact"]))

    for rank, issue in enumerate(all_issues[:3], 1):
        top_issue = {
            "rank": rank,
            "severity": issue["severity"],
            "module": issue["module"],
            "title": issue["title"],
            "description": f"{issue['title']} foi detectado durante a análise.",
            "business_impact": _get_business_impact(issue["module"], issue["title"]),
            "recommendation": _get_recommendation(issue["module"], issue["title"]),
        }
        issues.append(top_issue)

    return issues


def _generate_recommendations(
    modules: dict[str, dict[str, Any]],
    funnel_datalayer: FunnelDataLayerResult | None = None,
) -> dict[str, list[str]]:
    """Generate recommendations grouped by effort level."""
    recommendations = {
        "quick_wins": [],
        "medium_effort": [],
        "high_effort": [],
    }

    # Check each module and generate recommendations
    if not modules["tracking_infrastructure"]["data"]["meta_advanced_matching"]:
        recommendations["quick_wins"].append("Ativar Meta Advanced Matching no painel do Meta")

    if not modules["tracking_infrastructure"]["data"]["linkedin_insight_installed"]:
        recommendations["quick_wins"].append("Instalar LinkedIn Insight Tag se investir em LinkedIn Ads")

    if modules["attribution_health"]["data"]["redirect_strips_params"]:
        recommendations["medium_effort"].append("Corrigir redirecionamentos para preservar UTMs")

    if not modules["attribution_health"]["data"]["google_click_id_cookie_dropped"]:
        recommendations["medium_effort"].append("Garantir geração do cookie _gcl_aw do Google Ads")

    if not modules["server_side_tracking"]["data"]["sst_detected"]:
        recommendations["high_effort"].append("Implementar Google Tag Manager Server-Side (sGTM)")

    if not modules["server_side_tracking"]["data"]["httponly_tracking_cookies"]:
        recommendations["high_effort"].append("Configurar cookies HttpOnly para bypass de ITP")

    if not modules["server_side_tracking"]["data"]["meta_capi_proxy"]:
        recommendations["high_effort"].append("Implementar Meta Conversions API (CAPI) via proxy first-party")

    # Funnel-specific DataLayer recommendations
    if funnel_datalayer and funnel_datalayer.pages:
        stage_recs = {
            "product": ("view_item", "Implementar evento view_item na página de produto"),
            "cart": ("view_cart", "Implementar evento view_cart na página de carrinho"),
            "checkout": ("begin_checkout", "Implementar evento begin_checkout na página de checkout"),
            "category": ("view_item_list", "Implementar evento view_item_list na página de categoria"),
        }

        no_datalayer_pages = []
        for stage, page_data in funnel_datalayer.pages.items():
            if not page_data.accessible:
                continue

            if not page_data.datalayer_exists:
                stage_labels = {"home": "Home", "category": "Categoria", "product": "Produto",
                                "cart": "Carrinho", "checkout": "Checkout"}
                no_datalayer_pages.append(stage_labels.get(stage, stage))
                continue

            if stage in stage_recs:
                event_name, rec_text = stage_recs[stage]
                if event_name in page_data.missing_load_events:
                    recommendations["quick_wins"].append(rec_text)

        if no_datalayer_pages:
            recommendations["high_effort"].append(
                f"Implementar window.dataLayer em: {', '.join(no_datalayer_pages)}"
            )

    return recommendations


def _get_business_impact(module: str, title: str) -> str:
    """Get business impact description for an issue."""
    impacts = {
        "attribution_health": "Campanhas de tráfego pago não estão sendo rastreadas corretamente, prejudicando ROI",
        "server_side_tracking": "Perda estimada de 15-30% dos dados de conversão por bloqueadores e ITP",
        "tracking_infrastructure": "Qualidade de targeting e remarketing reduzida",
        "datalayer_depth": "Relatórios de e-commerce e campanhas de catálogo dinâmico comprometidos",
    }
    return impacts.get(module, "Impacto detectado no rastreamento")


def _get_recommendation(module: str, title: str) -> str:
    """Get recommendation description for an issue."""
    recommendations = {
        "redirect_strips_params": "Preservar parâmetros de query string em redirecionamentos",
        "cookie _gcl_aw não é criado": "Instalar corretamente o tag de Google Ads para gerar cookies de click ID",
        "Sem infraestrutura Server-Side": "Implementar Google Tag Manager Server-Side (sGTM) em subdomínio próprio",
        "GTM não instalado": "Instalar Google Tag Manager (GTM) para centralizar configuração de tags",
        "Tags duplicadas": "Consolidar tags duplicadas em uma única instalação",
        "Meta Advanced Matching": "Ativar Advanced Matching para enviar dados hashados (email, telefone)",
        "LinkedIn Insight Tag": "Instalar LinkedIn Insight Tag para rastreamento de conversões",
    }
    return recommendations.get(title, "Revisar configuração deste módulo")
