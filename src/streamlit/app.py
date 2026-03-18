"""
Blind Analytics — Diagnóstico de Mensuração de Mídias Pagas
Estágio B: Interface de validação funcional com Streamlit

Usage:
    cd blind-analytics
    streamlit run src/streamlit/app.py
"""

import sys
import json
import subprocess
import asyncio
from pathlib import Path
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor

# Add project root to path so helpers can be imported
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

# Thread pool for async helpers (URL validation only)
_executor = ThreadPoolExecutor(max_workers=1)

# Pipeline helpers
from tools.helpers.shared.config import (
    UrlValidationResult,
    NetworkRequest,
    TagIdentification,
    AttributionResult,
    SSTResult,
    DataLayerResult,
    ModuleScore,
    FunnelSelection,
    ClassifiedUrl,
    FunnelStage,
)
from tools.helpers.shared.url_validator import validate_url
from tools.helpers.discover.page_selector import select_funnel_pages
from tools.helpers.intercept.tag_identifier import identify_tags
from tools.helpers.detect.sst_detector import detect_sst
from tools.helpers.report.scorer import score_module, calculate_overall
from tools.helpers.report.report_generator import generate_report


# ============================================================================
# PAGE CONFIG
# ============================================================================

st.set_page_config(
    page_title="Blind Analytics — Diagnóstico de Mídias Pagas",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ============================================================================
# STYLES
# ============================================================================

st.markdown("""
<style>
    .score-card {
        padding: 1.2rem;
        border-radius: 0.5rem;
        text-align: center;
        margin-bottom: 0.5rem;
    }
    .score-critical { background-color: #fee2e2; border-left: 4px solid #ef4444; }
    .score-basic { background-color: #ffedd5; border-left: 4px solid #f97316; }
    .score-intermediate { background-color: #fef9c3; border-left: 4px solid #eab308; }
    .score-advanced { background-color: #dcfce7; border-left: 4px solid #22c55e; }
    .score-excellent { background-color: #dbeafe; border-left: 4px solid #3b82f6; }
</style>
""", unsafe_allow_html=True)


# ============================================================================
# HELPERS
# ============================================================================

def get_score_color(score: float) -> str:
    """Return color hex based on score."""
    if score <= 1:
        return "#ef4444"
    elif score <= 2:
        return "#f97316"
    elif score <= 3:
        return "#eab308"
    elif score <= 4:
        return "#22c55e"
    else:
        return "#3b82f6"


def get_score_class(score: float) -> str:
    """Return CSS class based on score."""
    if score <= 1:
        return "score-critical"
    elif score <= 2:
        return "score-basic"
    elif score <= 3:
        return "score-intermediate"
    elif score <= 4:
        return "score-advanced"
    else:
        return "score-excellent"


def get_score_emoji(score: float) -> str:
    """Return emoji based on score."""
    if score <= 1:
        return "🔴"
    elif score <= 2:
        return "🟠"
    elif score <= 3:
        return "🟡"
    elif score <= 4:
        return "🟢"
    else:
        return "🔵"


def run_async(coro):
    """Run an async coroutine from sync Streamlit context via ThreadPoolExecutor.

    Always delegates to asyncio.run() in a separate thread to avoid
    NotImplementedError on Windows ProactorEventLoop.
    """
    future = _executor.submit(asyncio.run, coro)
    return future.result(timeout=30)


def extract_domain(url: str) -> str:
    """Extract clean domain from URL."""
    from urllib.parse import urlparse
    parsed = urlparse(url if "://" in url else f"https://{url}")
    return parsed.netloc or parsed.path.split("/")[0]


# ============================================================================
# FUNNEL PAGES DISPLAY
# ============================================================================

STAGE_LABELS = {
    "home": ("🏠", "Home"),
    "category": ("📂", "Categoria"),
    "product": ("📦", "Produto"),
    "cart": ("🛒", "Carrinho"),
    "checkout": ("💳", "Checkout"),
}


def render_funnel_pages(selection: FunnelSelection):
    """Render the discovered funnel pages as a visual table.

    Shows each funnel stage with its selected URL, confidence score,
    discovery source, and classification signals. Highlights gaps
    where no candidate page was found.

    Args:
        selection: FunnelSelection with pages, stats, gaps, warnings.
    """
    stats = selection.discovery_stats
    sitemap_count = stats.get("sitemap_urls", 0)
    spider_count = stats.get("spider_urls", 0)

    st.markdown("### 🗺️ Páginas do Funil Identificadas")
    st.caption(
        f"{selection.total_discovered} URLs descobertas "
        f"({sitemap_count} via sitemap, {spider_count} via spider) · "
        f"{selection.total_classified} classificadas"
    )

    # Build table rows
    for stage_key, (icon, label) in STAGE_LABELS.items():
        page: ClassifiedUrl | None = selection.pages.get(stage_key)

        if page is not None:
            confidence_pct = int(page.confidence * 100)
            # Truncate long URLs for display
            display_url = page.url
            if len(display_url) > 80:
                display_url = display_url[:77] + "..."

            source_badge = "🟢 sitemap" if page.source == "sitemap" else "🔵 spider"
            if page.source == "forced":
                source_badge = "⚪ padrão"

            signals = ", ".join(page.classification_signals[:3]) if page.classification_signals else "—"

            col1, col2, col3, col4 = st.columns([1.5, 4, 1.5, 3])
            with col1:
                st.markdown(f"**{icon} {label}**")
            with col2:
                st.markdown(f"[{display_url}]({page.url})")
            with col3:
                st.progress(page.confidence, text=f"{confidence_pct}%")
            with col4:
                st.caption(f"{source_badge} · {signals}")
        else:
            col1, col2, col3, col4 = st.columns([1.5, 4, 1.5, 3])
            with col1:
                st.markdown(f"**{icon} {label}**")
            with col2:
                st.markdown("⚠️ *Nenhuma página encontrada*")
            with col3:
                st.progress(0, text="0%")
            with col4:
                st.caption("—")

    # Gaps warning
    if selection.gaps:
        gap_labels = [STAGE_LABELS.get(g, ("", g))[1] for g in selection.gaps]
        st.warning(
            f"**Gaps no funil:** {', '.join(gap_labels)}. "
            "Essas etapas não puderam ser identificadas automaticamente."
        )

    # Non-fatal warnings
    if selection.warnings:
        with st.expander("⚠️ Avisos da descoberta"):
            for w in selection.warnings:
                st.caption(f"• {w}")

    st.markdown("---")


# ============================================================================
# PIPELINE
# ============================================================================

def run_diagnostic(url: str) -> dict:
    """
    Execute the full 6-step diagnostic pipeline.

    Browser stages (2, 3, 5) run in a single subprocess to completely
    isolate Playwright from Streamlit's event loop on Windows.
    Returns the final JSON report matching sample-diagnostic.json contract.
    """
    progress = st.progress(0, text="Iniciando diagnóstico...")

    # Step 1: URL Validation
    progress.progress(5, text="Etapa 1/6 — Validando URL...")
    try:
        url_result: UrlValidationResult = run_async(validate_url(url))
        if url_result.status_code >= 400:
            st.error(f"URL inacessível (HTTP {url_result.status_code}). Verifique o endereço.")
            return None
        final_url = url_result.final_url
        domain = extract_domain(final_url)
    except Exception as e:
        st.error(f"Erro na validação de URL: {e}")
        return None

    st.success(f"URL validada: {final_url}")

    # Step 1.5: Page Discovery
    progress.progress(8, text="Etapa 1.5/6 — Descobrindo páginas do funil...")
    try:
        selection: FunnelSelection = select_funnel_pages(final_url)
        st.session_state["funnel_selection"] = selection
        render_funnel_pages(selection)
    except Exception as e:
        st.warning(f"Descoberta de páginas falhou: {e}. Continuando com URL principal.")
        st.session_state["funnel_selection"] = None

    # Steps 2, 3, 5: Browser pipeline in subprocess (complete process isolation)
    progress.progress(15, text="Etapas 2-5/6 — Analisando página...")

    script = PROJECT_ROOT / "tools" / "helpers" / "run_browser_pipeline.py"

    try:
        proc = subprocess.run(
            [sys.executable, str(script), final_url, domain],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(PROJECT_ROOT),
        )

        if proc.stderr:
            st.caption(f"Log: {proc.stderr.strip()[:200]}")

        pipeline = json.loads(proc.stdout or '{"requests":[],"dl_data":{},"attr_data":{}}')

    except subprocess.TimeoutExpired:
        st.error("Timeout: a análise excedeu 120 segundos.")
        return None
    except Exception as e:
        st.error(f"Erro no pipeline: {type(e).__name__}: {e}")
        return None

    # Parse subprocess results into Pydantic models
    raw_requests = pipeline.get("requests", [])
    requests: list[NetworkRequest] = [NetworkRequest(**r) for r in raw_requests]

    st.info(f"{len(requests)} requests interceptados")

    # Step 2b: Tag Identification (pure Python)
    progress.progress(60, text="Etapa 2/6 — Identificando tags...")
    tag_data: TagIdentification = identify_tags(requests)

    tags_found = []
    if tag_data.gtm_ids:
        tags_found.append(f"GTM: {', '.join(tag_data.gtm_ids)}")
    if tag_data.ga4_ids:
        tags_found.append(f"GA4: {', '.join(tag_data.ga4_ids)}")
    if tag_data.meta_pixel_ids:
        tags_found.append(f"Meta Pixel: {', '.join(tag_data.meta_pixel_ids)}")
    if tag_data.linkedin_ids:
        tags_found.append(f"LinkedIn: {', '.join(tag_data.linkedin_ids)}")

    if tags_found:
        st.info(f"Tags detectadas: {' | '.join(tags_found)}")
    else:
        st.warning("Nenhuma tag de mídia detectada")

    # Step 4: SST Detection (pure Python)
    progress.progress(70, text="Etapa 4/6 — Detectando Server-Side Tracking...")
    sst_data: SSTResult = detect_sst(requests, domain)

    # Parse attribution and dataLayer from subprocess
    raw_attr = pipeline.get("attr_data", {})
    attr_data = AttributionResult(**raw_attr) if raw_attr else AttributionResult()

    raw_dl = pipeline.get("dl_data", {})
    dl_data = DataLayerResult(**raw_dl) if raw_dl else DataLayerResult(datalayer_exists=False)

    # Step 6: Scoring & Report
    progress.progress(90, text="Etapa 6/6 — Calculando scores e gerando relatório...")

    tracking_score = score_module("tracking_infrastructure", tag_data.model_dump())
    attribution_score = score_module("attribution_health", attr_data.model_dump())
    sst_score = score_module("server_side_tracking", sst_data.model_dump())
    datalayer_score = score_module("datalayer_depth", dl_data.model_dump())

    all_scores = [tracking_score, attribution_score, sst_score, datalayer_score]
    overall = calculate_overall(all_scores)

    diagnostic = generate_report(
        url=domain,
        tag_data=tag_data,
        attribution_data=attr_data,
        sst_data=sst_data,
        datalayer_data=dl_data,
        scores=all_scores,
        overall=overall,
    )

    report = diagnostic.model_dump()

    progress.progress(100, text="Diagnóstico concluído!")
    return report


# ============================================================================
# UI: INPUT PAGE
# ============================================================================

def render_input():
    """Render the URL input form."""
    st.markdown("## 📊 Blind Analytics")
    st.markdown("### Diagnóstico de Mensuração de Mídias Pagas")
    st.markdown(
        "Analise a maturidade do tracking, atribuição, server-side e DataLayer "
        "do seu site. Cole a URL abaixo para começar."
    )

    col1, col2 = st.columns([4, 1])
    with col1:
        url = st.text_input(
            "URL do site",
            placeholder="https://exemplo.com.br",
            label_visibility="collapsed",
        )
    with col2:
        run = st.button("Diagnosticar", type="primary", use_container_width=True)

    st.markdown(
        "<small>Vamos analisar 4 módulos: infraestrutura de tags, "
        "saúde da atribuição, server-side tracking e profundidade do DataLayer.</small>",
        unsafe_allow_html=True,
    )

    return url, run


# ============================================================================
# UI: DASHBOARD
# ============================================================================

def render_dashboard(report: dict):
    """Render the diagnostic results dashboard."""

    overall = report.get("overall_maturity", {})
    modules = report.get("modules", {})

    # Funnel pages summary (if available from discovery step)
    funnel_sel = st.session_state.get("funnel_selection")
    if funnel_sel is not None:
        with st.expander("🗺️ Páginas do Funil Analisadas", expanded=False):
            for stage_key, (icon, label) in STAGE_LABELS.items():
                page_data = funnel_sel.pages.get(stage_key)
                if page_data is not None:
                    conf = int(page_data.confidence * 100)
                    st.markdown(f"**{icon} {label}** — [{page_data.url}]({page_data.url}) ({conf}%)")
                else:
                    st.markdown(f"**{icon} {label}** — ⚠️ Não identificada")

    # Overall score header
    score = overall.get("score", 0)
    rating = overall.get("rating", "—")
    emoji = get_score_emoji(score)
    color = get_score_color(score)

    st.markdown("---")
    st.markdown(f"## {emoji} Maturidade: {score:.2f}/5 — {rating}")
    st.markdown(f"*{overall.get('general_comment', '')}*")

    # Module score cards
    st.markdown("### Scores por Módulo")

    module_labels = {
        "tracking_infrastructure": ("🏷️", "Tracking Infrastructure"),
        "attribution_health": ("🔗", "Attribution Health"),
        "server_side_tracking": ("🖥️", "Server-Side Tracking"),
        "datalayer_depth": ("📦", "DataLayer Depth"),
    }

    cols = st.columns(4)
    for i, (key, (icon, label)) in enumerate(module_labels.items()):
        module = modules.get(key, {})
        mod_score = module.get("score", 0)
        mod_emoji = get_score_emoji(mod_score)
        css_class = get_score_class(mod_score)

        with cols[i]:
            st.markdown(
                f'<div class="score-card {css_class}">'
                f'<h2>{mod_emoji} {mod_score}/5</h2>'
                f'<p><strong>{icon} {label}</strong></p>'
                f'</div>',
                unsafe_allow_html=True,
            )
            st.caption(module.get("comment", ""))

    # Top issues
    top_issues = report.get("top_issues", [])
    if top_issues:
        st.markdown("### ⚠️ Problemas Críticos")
        for issue in top_issues:
            severity = issue.get("severity", "info")
            icon = "🔴" if severity == "critical" else "🟡" if severity == "warning" else "ℹ️"
            st.markdown(
                f"**{icon} {issue.get('title', '')}**\n\n"
                f"{issue.get('description', '')}\n\n"
                f"*Impacto:* {issue.get('business_impact', '')}"
            )
            st.markdown("---")

    # Recommendations
    recommendations = report.get("recommendations_summary", {})
    if recommendations:
        st.markdown("### 💡 Recomendações")

        quick_wins = recommendations.get("quick_wins", [])
        medium = recommendations.get("medium_effort", [])
        high = recommendations.get("high_effort", [])

        if quick_wins:
            st.markdown("**Quick Wins (implementação rápida):**")
            for r in quick_wins:
                st.markdown(f"- ✅ {r}")

        if medium:
            st.markdown("**Esforço Médio:**")
            for r in medium:
                st.markdown(f"- 🔧 {r}")

        if high:
            st.markdown("**Esforço Alto:**")
            for r in high:
                st.markdown(f"- 🏗️ {r}")

    # Evidence details (expandable)
    st.markdown("### 🔍 Evidências Detalhadas")

    for key, (icon, label) in module_labels.items():
        module = modules.get(key, {})
        evidence = module.get("evidence", [])
        if evidence:
            with st.expander(f"{icon} {label} — {len(evidence)} verificações"):
                for ev in evidence:
                    result = ev.get("result", "info")
                    result_icon = "✅" if result == "pass" else "❌" if result == "fail" else "⚠️" if result == "partial" else "ℹ️"
                    st.markdown(
                        f"**{result_icon} {ev.get('check', '')}** "
                        f"(impacto: {ev.get('score_impact', '—')})"
                    )
                    st.markdown(f"  {ev.get('detail', '')}")
                    source = ev.get("source", "")
                    if source:
                        st.caption(f"Fonte: {source}")
                    st.markdown("---")

    # Raw JSON (for debugging / validation)
    with st.expander("📋 JSON completo do diagnóstico"):
        st.json(report)


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Main app entry point."""

    url, run = render_input()

    if run and url:
        url = url.strip()
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        report = run_diagnostic(url)

        if report:
            st.session_state["last_report"] = report
            render_dashboard(report)

    elif "last_report" in st.session_state:
        render_dashboard(st.session_state["last_report"])


if __name__ == "__main__":
    main()
