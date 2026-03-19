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
import tempfile
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
    FunnelDataLayerResult,
    ClassifiedUrl,
    FunnelStage,
    load_funnel_event_map,
)
from tools.helpers.shared.url_validator import validate_url
from tools.helpers.discover.page_selector import select_funnel_pages
from tools.helpers.intercept.tag_identifier import identify_tags
from tools.helpers.detect.sst_detector import detect_sst
from tools.helpers.report.scorer import score_module, calculate_overall
from tools.helpers.report.report_generator import generate_report
from tools.helpers.datalayer.funnel_analyzer import build_funnel_datalayer_result


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


@st.cache_resource(show_spinner="Verificando navegador Chromium...")
def check_browser_available() -> tuple[bool, str]:
    """Check/install Playwright Chromium once per app session.

    Returns (available, message).
    """
    try:
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            capture_output=True, text=True, timeout=180,
        )
        if result.returncode == 0:
            return True, "Chromium disponível"
        return False, f"Falha ao instalar Chromium: {result.stderr[:200]}"
    except subprocess.TimeoutExpired:
        return False, "Timeout ao instalar Chromium"
    except Exception as e:
        return False, f"Erro: {e}"


def _parse_pipeline_stderr(stderr: str) -> list[dict]:
    """Parse structured JSON-line stderr from run_browser_pipeline into messages."""
    messages = []
    for line in stderr.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
            messages.append(msg)
        except json.JSONDecodeError:
            # Legacy plain-text message
            messages.append({"stage": "pipeline", "status": "info", "detail": line})
    return messages


def _render_pipeline_progress(messages: list[dict], container):
    """Render structured pipeline messages as formatted status items."""
    status_icons = {"ok": "✅", "running": "🔄", "error": "❌", "info": "ℹ️"}
    for msg in messages:
        icon = status_icons.get(msg.get("status", "info"), "ℹ️")
        stage = msg.get("stage", "")
        detail = msg.get("detail", "")
        if detail:
            container.caption(f"{icon} **{stage}**: {detail}")


_STAGE_PROGRESS = {
    "browser_install": (18, "Preparando navegador..."),
    "spider":          (25, "Buscando páginas do funil..."),
    "intercept":       (45, "Interceptando requisições de rede..."),
    "datalayer":       (60, "Extraindo DataLayer..."),
    "attribution":     (70, "Testando atribuição de mídia..."),
    "page_datalayer":  (80, "Analisando DataLayer por página..."),
    "scoring":         (90, "Calculando scores..."),
}


def _stage_to_progress(stage: str) -> tuple[int, str]:
    """Map a pipeline stage name to (percent, description) for the progress bar."""
    return _STAGE_PROGRESS.get(stage, (None, None))


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
# FUNNEL DATALAYER DISPLAY
# ============================================================================


def render_funnel_datalayer(funnel_dl: dict):
    """Render per-page funnel DataLayer analysis as a visual table.

    Shows each funnel stage with event badges (green=present, red=missing,
    gray=interaction) and a score progress bar.

    Args:
        funnel_dl: FunnelDataLayerResult as dict (from report JSON)
    """
    pages = funnel_dl.get("pages", {})
    if not pages:
        return

    st.markdown("### 📊 DataLayer por Página do Funil")

    aggregate = funnel_dl.get("aggregate_score", 0)
    coverage = funnel_dl.get("funnel_coverage", 0)
    total_matched = funnel_dl.get("total_matched_load_events", 0)
    total_expected = funnel_dl.get("total_expected_load_events", 0)

    st.caption(
        f"Score agregado: {aggregate:.1f}/5 · "
        f"Cobertura: {int(coverage * 100)}% · "
        f"Eventos load: {total_matched}/{total_expected}"
    )

    for stage_key, (icon, label) in STAGE_LABELS.items():
        page_data = pages.get(stage_key)
        if page_data is None:
            continue

        accessible = page_data.get("accessible", False)
        page_score = page_data.get("page_score", 0)

        col1, col2, col3 = st.columns([1.5, 5, 1.5])

        with col1:
            st.markdown(f"**{icon} {label}**")

        with col2:
            if not accessible:
                st.markdown("⚪ *Página inacessível (login/redirect)*")
            elif not page_data.get("datalayer_exists", False):
                st.markdown("❌ *DataLayer não encontrado*")
            else:
                badges = []
                for ev in page_data.get("matched_events", []):
                    badges.append(f"🟢 `{ev}`")
                for ev in page_data.get("missing_load_events", []):
                    badges.append(f"🔴 `{ev}`")
                for ev in page_data.get("missing_interaction_events", []):
                    badges.append(f"⚪ `{ev}`")
                st.markdown(" ".join(badges) if badges else "✅ Sem eventos esperados")

        with col3:
            if accessible:
                st.progress(min(page_score / 5.0, 1.0), text=f"{page_score:.1f}/5")
            else:
                st.progress(0, text="—")

        # Expandable sample events
        if accessible and page_data.get("sample_events"):
            with st.expander(f"Amostra de eventos — {label}", expanded=False):
                st.json(page_data["sample_events"][:3])

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
    funnel_pages_dict = None
    try:
        selection: FunnelSelection = select_funnel_pages(final_url, use_spider=False)
        st.session_state["funnel_selection"] = selection

        # Build {stage: url} dict for subprocess
        funnel_pages_dict = {}
        for stage_key, page_obj in selection.pages.items():
            if page_obj is not None:
                funnel_pages_dict[stage_key] = page_obj.url
        if not funnel_pages_dict:
            funnel_pages_dict = None
    except Exception as e:
        st.warning(f"Descoberta de páginas falhou: {e}. Continuando com URL principal.")
        st.session_state["funnel_selection"] = None

    # Steps 2, 3, 5: Browser pipeline in subprocess (complete process isolation)
    progress.progress(15, text="Etapas 2-5/6 — Verificando navegador e analisando página...")

    # Check browser availability (cached — runs once per session)
    browser_ok, browser_msg = check_browser_available()
    if not browser_ok:
        st.error(
            f"🚫 **Navegador indisponível**: {browser_msg}\n\n"
            "Instale manualmente com: `playwright install chromium`\n\n"
            "Os módulos que dependem de navegador (Tracking, Attribution, DataLayer) "
            "não poderão ser avaliados."
        )
        browser_unavailable = True
    else:
        browser_unavailable = False

    script = PROJECT_ROOT / "tools" / "helpers" / "run_browser_pipeline.py"

    cmd = [sys.executable, str(script), final_url, domain]
    timeout = 120
    gaps_list = selection.gaps if selection else []
    if funnel_pages_dict:
        cmd.extend(["--pages", json.dumps(funnel_pages_dict)])
        timeout = 180  # More time for multi-page analysis
    if gaps_list:
        cmd.extend(["--gaps", json.dumps(gaps_list)])
        timeout = 180

    # Use a temp file for stdout to avoid pipe deadlock (large JSON output
    # can fill the OS pipe buffer while we block reading stderr line-by-line).
    try:
        with tempfile.NamedTemporaryFile(
            mode="w+", suffix=".json", delete=False, encoding="utf-8",
        ) as stdout_file:
            stdout_path = stdout_file.name

            proc = subprocess.Popen(
                cmd,
                stdout=stdout_file,
                stderr=subprocess.PIPE,
                text=True,
                cwd=str(PROJECT_ROOT),
            )

            # Stream stderr line-by-line to update progress in real time
            log_container = st.container()
            status_icons = {"ok": "✅", "running": "🔄", "error": "❌", "info": "ℹ️"}

            for line in proc.stderr:
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    msg = {"stage": "pipeline", "status": "info", "detail": line}

                # Update progress bar based on stage
                stage = msg.get("stage", "")
                pct, desc = _stage_to_progress(stage)
                if pct is not None:
                    progress.progress(pct, text=desc)

                # Show the log line
                icon = status_icons.get(msg.get("status", "info"), "ℹ️")
                detail = msg.get("detail", "")
                if detail:
                    log_container.caption(f"{icon} **{stage}**: {detail}")

            # stderr is exhausted — process has finished writing; wait for exit
            proc.wait(timeout=timeout)

        # Read stdout from temp file
        stdout_data = Path(stdout_path).read_text(encoding="utf-8")
        Path(stdout_path).unlink(missing_ok=True)

        if proc.returncode != 0 and not stdout_data.strip():
            st.error("❌ O pipeline retornou erro.")
            return None

        pipeline = json.loads(stdout_data or '{}')

        # Handle structured browser error from subprocess
        if pipeline.get("browser_error"):
            st.error(
                f"🚫 **Erro no navegador**: {pipeline['browser_error']}\n\n"
                "Os módulos de Tracking, Attribution e DataLayer serão marcados como não avaliados."
            )
            browser_unavailable = True

        # If pipeline returned empty/missing data, use safe defaults
        if not pipeline.get("requests") and not pipeline.get("browser_error"):
            pipeline.setdefault("requests", [])
        pipeline.setdefault("requests", [])
        pipeline.setdefault("dl_data", {})
        pipeline.setdefault("attr_data", {})
        pipeline.setdefault("per_page_dl", {})

    except subprocess.TimeoutExpired:
        proc.kill()
        Path(stdout_path).unlink(missing_ok=True)
        st.error(f"⏱️ Timeout: a análise excedeu {timeout} segundos.")
        return None
    except json.JSONDecodeError:
        st.error("❌ Erro ao interpretar resultado do pipeline. Saída inválida.")
        return None
    except Exception as e:
        st.error(f"❌ Erro no pipeline: {type(e).__name__}: {e}")
        return None

    # Merge spider-discovered pages back into FunnelSelection for display
    spider_pages = pipeline.get("funnel_pages", {})
    spider_stats = pipeline.get("spider_stats", {})
    if spider_pages and selection:
        for stage_key, page_info in spider_pages.items():
            if page_info and selection.pages.get(stage_key) is None:
                selection.pages[stage_key] = ClassifiedUrl(
                    url=page_info["url"],
                    stage=FunnelStage(page_info["stage"]),
                    confidence=page_info["confidence"],
                    source=page_info.get("source", "spider"),
                    classification_signals=page_info.get("signals", []),
                )
        selection.discovery_stats["spider_urls"] = spider_stats.get("spider_urls", 0)
        selection.total_discovered += spider_stats.get("spider_urls", 0)
        selection.gaps = [
            stage for stage in ["home", "category", "product", "cart", "checkout"]
            if selection.pages.get(stage) is None
        ]
        st.session_state["funnel_selection"] = selection

    # Render funnel pages once (after spider merge, so all sources are included)
    if selection:
        render_funnel_pages(selection)

    # Parse subprocess results into Pydantic models
    raw_requests = pipeline.get("requests", [])
    requests: list[NetworkRequest] = [NetworkRequest(**r) for r in raw_requests]

    st.info(f"{len(requests)} requests interceptados")

    # Step 2b: Tag Identification (pure Python)
    progress.progress(85, text="Etapa 2b/6 — Identificando tags...")
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
    elif browser_unavailable:
        st.warning("⚠️ Tags não verificadas — navegador indisponível")
    else:
        st.warning("Nenhuma tag de mídia detectada")

    # Step 4: SST Detection (pure Python)
    progress.progress(88, text="Etapa 4/6 — Detectando Server-Side Tracking...")
    sst_data: SSTResult = detect_sst(requests, domain)

    # Parse attribution and dataLayer from subprocess
    raw_attr = pipeline.get("attr_data", {})
    attr_data = AttributionResult(**raw_attr) if raw_attr else AttributionResult()

    raw_dl = pipeline.get("dl_data", {})
    dl_data = DataLayerResult(**raw_dl) if raw_dl else DataLayerResult(datalayer_exists=False)

    # Build per-page funnel DataLayer result (if available)
    raw_per_page_dl = pipeline.get("per_page_dl", {})
    funnel_dl_result = None
    funnel_data_for_scorer = None
    if raw_per_page_dl:
        try:
            event_map = load_funnel_event_map()
            funnel_dl_result = build_funnel_datalayer_result(raw_per_page_dl, event_map)
            funnel_data_for_scorer = funnel_dl_result.model_dump()
        except Exception as e:
            st.warning(f"Erro na análise de funil por página: {e}")

    # Step 6: Scoring & Report
    progress.progress(90, text="Etapa 6/6 — Scoring: Tracking Infrastructure...")
    tracking_score = score_module("tracking_infrastructure", tag_data.model_dump())

    progress.progress(92, text="Etapa 6/6 — Scoring: Attribution Health...")
    attribution_score = score_module("attribution_health", attr_data.model_dump())

    progress.progress(94, text="Etapa 6/6 — Scoring: Server-Side Tracking...")
    sst_score = score_module("server_side_tracking", sst_data.model_dump())

    progress.progress(96, text="Etapa 6/6 — Scoring: DataLayer Depth...")
    datalayer_score = score_module("datalayer_depth", dl_data.model_dump(), funnel_data=funnel_data_for_scorer)

    # Mark browser-dependent modules as unevaluated if browser was unavailable
    if browser_unavailable:
        for mod in [tracking_score, attribution_score, datalayer_score]:
            mod.evaluated = False
            mod.comment = "Módulo não avaliado — navegador indisponível no ambiente de execução."
            mod.rating = "Não avaliado"

    all_scores = [tracking_score, attribution_score, sst_score, datalayer_score]
    overall = calculate_overall(all_scores)

    progress.progress(98, text="Etapa 6/6 — Gerando relatório final...")
    diagnostic = generate_report(
        url=domain,
        tag_data=tag_data,
        attribution_data=attr_data,
        sst_data=sst_data,
        datalayer_data=dl_data,
        scores=all_scores,
        overall=overall,
        funnel_datalayer=funnel_dl_result,
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

    # Overall score header
    score = overall.get("score", 0)
    rating = overall.get("rating", "—")
    emoji = get_score_emoji(score)
    color = get_score_color(score)

    st.markdown("---")
    st.markdown(f"## {emoji} Maturidade: {score:.2f}/5 — {rating}")
    st.markdown(f"*{overall.get('general_comment', '')}*")

    unevaluated = overall.get("unevaluated_modules", [])
    if unevaluated:
        st.warning(
            f"⚠️ {len(unevaluated)} módulo(s) não avaliado(s) por indisponibilidade do navegador. "
            "O score reflete apenas os módulos que puderam ser verificados."
        )

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
        is_evaluated = module.get("evaluated", True)

        with cols[i]:
            if not is_evaluated:
                st.markdown(
                    f'<div class="score-card" style="background-color: #f3f4f6; border-left: 4px solid #9ca3af;">'
                    f'<h2>⚪ N/A</h2>'
                    f'<p><strong>{icon} {label}</strong></p>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                st.caption(module.get("comment", "Não avaliado"))
            else:
                mod_emoji = get_score_emoji(mod_score)
                css_class = get_score_class(mod_score)
                st.markdown(
                    f'<div class="score-card {css_class}">'
                    f'<h2>{mod_emoji} {mod_score}/5</h2>'
                    f'<p><strong>{icon} {label}</strong></p>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                st.caption(module.get("comment", ""))

    # Funnel DataLayer per-page analysis
    funnel_analysis = report.get("funnel_analysis")
    if funnel_analysis and funnel_analysis.get("pages"):
        render_funnel_datalayer(funnel_analysis)

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
