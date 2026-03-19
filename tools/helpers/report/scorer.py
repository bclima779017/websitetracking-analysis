"""
Scoring module — Stage 6 of the diagnostic pipeline.

Applies rubrics to compute module scores (0-5) and overall maturity rating.
Pure functions with no side effects.
"""

from __future__ import annotations

from typing import Any

from ..shared.config import ModuleScore, load_scoring_rubrics


def score_module(
    module_name: str,
    data: dict[str, Any],
    rubrics: dict[str, dict[int, str]] | None = None,
    funnel_data: dict[str, Any] | None = None,
) -> ModuleScore:
    """
    Calculate score for a single module (0-5) based on diagnostic data.

    Applies module-specific rubrics to determine the score. Rubrics define
    what data characteristics correspond to each score level (0-5).

    Args:
        module_name: One of: tracking_infrastructure, attribution_health,
                     server_side_tracking, datalayer_depth
        data: Dictionary of module-specific diagnostic data
        rubrics: Optional rubric definitions (loaded from assets if None)
        funnel_data: Optional per-page funnel DataLayer data (for datalayer_depth)

    Returns:
        ModuleScore with score, rating, and comment in PT-BR
    """
    if rubrics is None:
        rubrics = load_scoring_rubrics()

    score = 0.0
    rating = "Crítico"
    comment = ""
    breakdown = ""

    if module_name == "tracking_infrastructure":
        score, rating, comment, breakdown = _score_tracking_infrastructure(data)

    elif module_name == "attribution_health":
        score, rating, comment, breakdown = _score_attribution_health(data)

    elif module_name == "server_side_tracking":
        score, rating, comment, breakdown = _score_server_side_tracking(data)

    elif module_name == "datalayer_depth":
        if funnel_data and funnel_data.get("pages"):
            score, rating, comment, breakdown = _score_datalayer_depth_per_page(funnel_data)
        else:
            score, rating, comment, breakdown = _score_datalayer_depth(data)

    return ModuleScore(
        module_name=module_name,
        score=score,
        max_score=5.0,
        comment=comment,
        rating=rating,
        data=data,
        scoring_breakdown=breakdown,
    )


def _score_tracking_infrastructure(data: dict[str, Any]) -> tuple[float, str, str, str]:
    """
    Score Tracking Infrastructure module (0-5).

    Rubric:
    - 0: Nenhuma tag detectada
    - 1-2: Tags com erros HTTP ou duplicadas
    - 3: Uma plataforma ok (GA4 ou Meta)
    - 4: GTM + GA4 + Meta funcionando
    - 5: Tudo ok + Meta Advanced Matching
    """
    score = 0.0
    breakdown = "Base: 0"

    gtm_ids = data.get("gtm_ids", [])
    ga4_ids = data.get("ga4_ids", [])
    meta_pixel_ids = data.get("meta_pixel_ids", [])
    linkedin_ids = data.get("linkedin_ids", [])
    duplicate_tags = data.get("duplicate_tags", False)
    tags_with_errors = data.get("tags_with_errors", [])
    meta_advanced_matching = data.get("meta_advanced_matching", False)

    # Check for errors
    if tags_with_errors or duplicate_tags:
        score = 1.0
        breakdown += " | Tags com erros ou duplicatas: 1"
        return score, "Básico", "Tags presentes mas com problemas de funcionamento.", breakdown

    # Count working platforms
    platforms_ok = 0
    if gtm_ids:
        platforms_ok += 1
        score += 1
        breakdown += " | +1 GTM ok"

    if ga4_ids:
        platforms_ok += 1
        score += 1
        breakdown += " | +1 GA4 ok"

    if meta_pixel_ids:
        platforms_ok += 1
        score += 1
        breakdown += " | +1 Meta Pixel ok"

    if linkedin_ids:
        score += 0.5
        breakdown += " | +0.5 LinkedIn ok"

    if not platforms_ok:
        score = 0
        breakdown = "Base: 0 | Nenhuma tag detectada"
        return score, "Crítico", "Nenhuma tag de tracking detectada.", breakdown

    # Add bonus for Meta Advanced Matching
    if meta_advanced_matching and meta_pixel_ids:
        score += 1
        breakdown += " | +1 Meta Advanced Matching"

    # Cap score at 5
    score = min(score, 5.0)

    # Generate comment
    if score >= 4.5:
        rating = "Excelente"
        comment = f"Todas as tags base presentes ({platforms_ok} plataformas) e Meta Advanced Matching ativo."
    elif score >= 3.5:
        rating = "Avançado"
        comment = f"Infraestrutura completa ({platforms_ok} plataformas) e funcionando."
    elif score >= 2.5:
        rating = "Intermediário"
        comment = f"Múltiplas plataformas detectadas ({platforms_ok}), mas faltam algumas funcionalidades."
    elif score >= 1.5:
        rating = "Básico"
        comment = "Uma ou mais plataformas presentes, mas com limitações."
    else:
        rating = "Crítico"
        comment = "Infraestrutura de tracking mínima ou com problemas graves."

    return score, rating, comment, breakdown


def _score_attribution_health(data: dict[str, Any]) -> tuple[float, str, str, str]:
    """
    Score Attribution Health module (0-5).

    Rubric:
    - 0: Sem cookies e sem localStorage
    - 2: Alguns cookies, mas UTMs perdidos em redirects
    - 4: Cookies ok, UTMs preservados
    - 5: Completo com localStorage + sem redirect stripping
    """
    score = 5.0  # Start at max and deduct
    breakdown = "Base: 5"

    utm_persistence = data.get("utm_persistence_on_redirect", False)
    redirect_strips = data.get("redirect_strips_params", False)
    google_cookie = data.get("google_click_id_cookie_dropped", False)
    meta_cookie = data.get("meta_click_id_cookie_dropped", False)
    localstorage = data.get("localstorage_utm_saved", False)

    # Deduct for redirect stripping (critical issue)
    if redirect_strips:
        score -= 2.0
        breakdown += " | -2 redirect limpa parâmetros (crítico)"

    # Deduct for missing Google cookie
    if not google_cookie:
        score -= 1.0
        breakdown += " | -1 falta cookie _gcl_aw"

    # Deduct for missing Meta cookie
    if not meta_cookie:
        score -= 1.0
        breakdown += " | -1 falta cookie _fbc"

    # Bonus for localStorage (small, it's a workaround)
    if localstorage:
        score += 0.0  # No bonus, but not negative
        breakdown += " | localStorage disponível"

    score = max(0, min(score, 5.0))

    # Generate comment and rating
    if score >= 4:
        rating = "Avançado"
        comment = "Excelente persistência de atribuição com cookies funcionando e preservação de parâmetros."
    elif score >= 3:
        rating = "Intermediário"
        comment = "Atribuição parcial funciona, mas há perda de dados em alguns cenários."
    elif score >= 2:
        rating = "Básico"
        comment = "Alerta: Problemas críticos na persistência de atribuição. Alguns parâmetros ou cookies estão sendo perdidos."
    else:
        rating = "Crítico"
        comment = "Alerta Crítico: Atribuição completamente quebrada. Dados de campanhas não estão sendo rastreados."

    return score, rating, comment, breakdown


def _score_server_side_tracking(data: dict[str, Any]) -> tuple[float, str, str, str]:
    """
    Score Server-Side Tracking module (0-5).

    Rubric:
    - 0: Sem SST
    - 2: Proxy detectado mas incompleto
    - 4: sGTM funcional
    - 5: sGTM + CAPI + HttpOnly
    """
    score = 0.0
    breakdown = "Base: 0"

    sst_detected = data.get("sst_detected", False)
    sgtm_subdomain = data.get("sgtm_subdomain")
    meta_capi = data.get("meta_capi_proxy", False)
    httponly = data.get("httponly_tracking_cookies", False)
    itp_bypass = data.get("itp_bypass_functional", False)

    if not sst_detected:
        score = 0
        breakdown = "Base: 0 | Sem Server-Side Tracking detectado"
        return score, "Crítico", "Nenhuma infraestrutura de Server-Side Tracking detectada. Vulnerável a ad blockers e ITP.", breakdown

    # sGTM detected
    if sgtm_subdomain:
        score += 2.0
        breakdown += " | +2 sGTM detectado"

    # Meta CAPI detected
    if meta_capi:
        score += 1.0
        breakdown += " | +1 Meta CAPI proxy"

    # HttpOnly cookies
    if httponly:
        score += 1.0
        breakdown += " | +1 HttpOnly cookies"

    # ITP bypass functional
    if itp_bypass:
        score += 0.5
        breakdown += " | +0.5 bypass ITP funcional"

    score = min(score, 5.0)

    # Generate comment and rating
    if score >= 4:
        rating = "Avançado"
        comment = "Infraestrutura Server-Side bem implementada. Protegido contra ad blockers e ITP."
    elif score >= 2:
        rating = "Intermediário"
        comment = "Algumas medidas de Server-Side implementadas, mas há gaps de cobertura."
    else:
        rating = "Crítico"
        comment = "Dependência 100% de Client-Side. Altamente vulnerável a bloqueadores e ITP do Safari."

    return score, rating, comment, breakdown


def _score_datalayer_depth(data: dict[str, Any]) -> tuple[float, str, str, str]:
    """
    Score DataLayer Depth module (0-5).

    Rubric:
    - 0: Sem dataLayer
    - 2: DataLayer existe, poucos eventos
    - 4: Eventos completos, schema GA4 ok
    - 5: Excelente, todos campos presentes
    """
    score = 0.0
    breakdown = "Base: 0"

    datalayer_exists = data.get("datalayer_exists", False)
    events_count = data.get("datalayer_events_count", 0)
    standard_events = data.get("standard_events_detected", [])
    ga4_schema = data.get("ga4_schema_compliant", False)
    required_fields = data.get("required_fields_present", [])
    missing_fields = data.get("missing_recommended_fields", [])

    if not datalayer_exists:
        score = 0
        breakdown = "Base: 0 | window.dataLayer não encontrado"
        return score, "Crítico", "Sem DataLayer. Rastreamento de eventos não configurado.", breakdown

    score = 1.0
    breakdown += " | +1 dataLayer presente"

    # Events detected
    if events_count > 5:
        score += 1.0
        breakdown += " | +1 múltiplos eventos"

    # Standard GA4 events
    if len(standard_events) >= 3:  # view_item, add_to_cart, etc
        score += 1.0
        breakdown += f" | +1 {len(standard_events)} eventos GA4 standard"

    # GA4 schema compliance
    if ga4_schema and len(required_fields) >= 4:
        score += 1.0
        breakdown += " | +1 schema GA4 compliant"

    # Recommended fields present
    if len(missing_fields) < 3:  # Most recommended fields present
        score += 1.0
        breakdown += " | +1 campos recomendados >60%"

    score = min(score, 5.0)

    # Generate comment and rating
    if score >= 4:
        rating = "Excelente"
        comment = "Excelente configuração de DataLayer com eventos de funil e schema GA4 e-commerce completo."
    elif score >= 3:
        rating = "Avançado"
        comment = "DataLayer bem configurado com bom coverage de eventos e schema GA4."
    elif score >= 2:
        rating = "Intermediário"
        comment = "DataLayer existe mas faltam eventos ou compliance com schema GA4."
    else:
        rating = "Básico"
        comment = "DataLayer mínimo. Poucos eventos e dados limitados para análise."

    return score, rating, comment, breakdown


def _score_datalayer_depth_per_page(funnel_data: dict[str, Any]) -> tuple[float, str, str, str]:
    """
    Score DataLayer Depth using per-page funnel analysis (0-5).

    Uses the aggregate_score from FunnelDataLayerResult and generates
    a breakdown from individual page results.
    """
    aggregate_score = funnel_data.get("aggregate_score", 0.0)
    pages = funnel_data.get("pages", {})
    total_matched = funnel_data.get("total_matched_load_events", 0)
    total_expected = funnel_data.get("total_expected_load_events", 0)
    coverage = funnel_data.get("funnel_coverage", 0.0)

    score = min(aggregate_score, 5.0)

    breakdown = f"Agregado por página: {score:.1f}"

    # Per-page breakdown
    stage_labels = {
        "home": "Home", "category": "Categoria", "product": "Produto",
        "cart": "Carrinho", "checkout": "Checkout",
    }
    for stage, page_data in pages.items():
        label = stage_labels.get(stage, stage)
        if isinstance(page_data, dict):
            ps = page_data.get("page_score", 0)
            accessible = page_data.get("accessible", False)
        else:
            ps = page_data.page_score
            accessible = page_data.accessible
        if not accessible:
            breakdown += f" | {label}: inacessível"
        else:
            breakdown += f" | {label}: {ps:.1f}/5"

    if total_expected > 0:
        pct = int(total_matched / total_expected * 100)
        breakdown += f" | Cobertura eventos load: {pct}%"

    # Rating and comment
    if score >= 4:
        rating = "Excelente"
        comment = f"DataLayer bem configurado em {int(coverage * 100)}% das páginas do funil com eventos GA4 corretos por etapa."
    elif score >= 3:
        rating = "Avançado"
        comment = f"DataLayer presente nas principais páginas do funil, mas alguns eventos de carregamento estão faltando."
    elif score >= 2:
        rating = "Intermediário"
        comment = f"DataLayer parcial — eventos de funil ausentes em páginas críticas. Coverage: {int(coverage * 100)}%."
    elif score >= 1:
        rating = "Básico"
        comment = "DataLayer mínimo nas páginas do funil. Eventos essenciais ausentes em múltiplas etapas."
    else:
        rating = "Crítico"
        comment = "DataLayer ausente ou inacessível nas páginas do funil. Rastreamento de eventos de conversão inexistente."

    return score, rating, comment, breakdown


def calculate_overall(scores: list[ModuleScore]) -> dict[str, Any]:
    """
    Calculate overall maturity score from module scores.

    Computes weighted average of evaluated modules only. Modules marked as
    not evaluated (e.g., browser unavailable) are excluded from the average.

    Args:
        scores: List of ModuleScore objects for all modules

    Returns:
        Dictionary with score, max_score, rating, general_comment, and
        unevaluated_modules list.
    """
    if not scores:
        return {
            "score": 0,
            "max_score": 5.0,
            "rating": "Crítico",
            "general_comment": "Diagnóstico incompleto.",
            "unevaluated_modules": [],
        }

    evaluated = [s for s in scores if s.evaluated]
    unevaluated = [s.module_name for s in scores if not s.evaluated]

    if not evaluated:
        return {
            "score": 0,
            "max_score": 5.0,
            "rating": "Indisponível",
            "general_comment": "Nenhum módulo pôde ser avaliado. Verifique se o navegador está disponível no ambiente de deploy.",
            "unevaluated_modules": unevaluated,
        }

    total_score = sum(s.score for s in evaluated)
    average_score = total_score / len(evaluated)

    # Determine overall rating
    if average_score >= 4.5:
        rating = "Excelente"
        comment = "A operação de mídias pagas está madura com infraestrutura moderna e bem configurada."
    elif average_score >= 3.5:
        rating = "Avançado"
        comment = "A operação está bem estruturada. Alguns ajustes pontuais melhorariam ainda mais a performance."
    elif average_score >= 2.5:
        rating = "Intermediário"
        comment = "A operação possui a base de eventos bem configurada, mas sofre com problemas de atribuição ou infraestrutura."
    elif average_score >= 1.5:
        rating = "Básico"
        comment = "A operação tem limitações críticas. Recomenda-se ação imediata em atribuição e infraestrutura."
    else:
        rating = "Crítico"
        comment = "A operação apresenta falhas graves em rastreamento e atribuição. Intervenção urgente necessária."

    result = {
        "score": round(average_score, 2),
        "max_score": 5.0,
        "rating": rating,
        "general_comment": comment,
        "unevaluated_modules": unevaluated,
    }
    if unevaluated:
        result["general_comment"] += (
            f" Nota: {len(unevaluated)} módulo(s) não pôde(ram) ser avaliado(s)"
            " por indisponibilidade do navegador."
        )
    return result
