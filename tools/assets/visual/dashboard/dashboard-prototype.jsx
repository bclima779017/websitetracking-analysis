import { useState } from "react";
import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Cell,
} from "recharts";
import {
  AlertTriangle,
  CheckCircle,
  XCircle,
  Shield,
  Activity,
  Server,
  Layers,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  Info,
} from "lucide-react";

/* ─── Dados simulados (sample-diagnostic.json) ─── */
const diagnostic = {
  domain: "exemplo.com.br",
  audit_timestamp: "2026-03-17T10:30:00Z",
  modules: {
    tracking_infrastructure: {
      score: 4,
      max_score: 5,
      label: "Infraestrutura de Tags",
      icon: "Activity",
      comment:
        "As tags base (GTM e GA4) estão instaladas e operacionais. O Pixel do Meta está presente, mas não utiliza a funcionalidade de Advanced Matching.",
      data: {
        gtm_installed: true,
        ga4_installed: true,
        meta_pixel_installed: true,
        meta_advanced_matching: false,
        linkedin_insight_installed: false,
        duplicate_tags: false,
      },
    },
    attribution_health: {
      score: 2,
      max_score: 5,
      label: "Saúde da Atribuição",
      icon: "Shield",
      comment:
        "Alerta Crítico: Redirecionamentos limpam UTMs e o cookie _gcl_aw do Google Ads não é gerado. Campanhas perdendo dados de conversão.",
      data: {
        utm_persistence_on_redirect: false,
        redirect_strips_params: true,
        google_click_id_cookie_dropped: false,
        meta_click_id_cookie_dropped: true,
      },
    },
    server_side_tracking: {
      score: 0,
      max_score: 5,
      label: "Server-Side Tracking",
      icon: "Server",
      comment:
        "Nenhum proxy ou endpoint SST detectado. 100% client-side — vulnerável a AdBlockers e ITP do Safari.",
      data: {
        sst_detected: false,
        sgtm_subdomain: null,
        meta_capi_proxy: false,
        httponly_tracking_cookies: false,
      },
    },
    datalayer_depth: {
      score: 5,
      max_score: 5,
      label: "Profundidade do DataLayer",
      icon: "Layers",
      comment:
        "Excelente configuração. Eventos de funil completos com schema GA4 de e-commerce, ideal para catálogo dinâmico.",
      data: {
        datalayer_exists: true,
        datalayer_events_count: 8,
        ga4_schema_compliant: true,
        ecommerce_items_array: true,
      },
    },
  },
  overall_maturity: {
    score: 2.75,
    max_score: 5.0,
    rating: "Intermediário",
  },
  top_issues: [
    {
      rank: 1,
      severity: "critical",
      module: "attribution_health",
      title: "Atribuição de campanhas quebrada",
      description:
        "Redirecionamentos limpam UTMs e o cookie _gcl_aw não é gerado.",
      business_impact: "Investimento em Google Ads sem rastreamento de retorno",
      recommendation:
        "Corrigir redirecionamentos para preservar query strings e garantir geração do cookie _gcl_aw.",
    },
    {
      rank: 2,
      severity: "critical",
      module: "server_side_tracking",
      title: "Sem infraestrutura Server-Side",
      description:
        "100% client-side, vulnerável a AdBlockers e ITP. Dados de conversão perdidos silenciosamente.",
      business_impact: "Perda estimada de 15-30% dos dados de conversão",
      recommendation:
        "Implementar sGTM em subdomínio próprio para contornar bloqueadores e ITP.",
    },
    {
      rank: 3,
      severity: "warning",
      module: "tracking_infrastructure",
      title: "Meta Pixel sem Advanced Matching",
      description:
        "Pixel ativo mas sem Advanced Matching — taxa de match reduzida.",
      business_impact: "Públicos de remarketing menores e menos precisos",
      recommendation:
        "Ativar Advanced Matching no painel do Meta para enviar dados hashados.",
    },
  ],
  recommendations_summary: {
    quick_wins: [
      "Ativar Meta Advanced Matching (configuração no painel, sem código)",
      "Instalar LinkedIn Insight Tag se investir em LinkedIn Ads",
    ],
    medium_effort: [
      "Corrigir redirecionamentos para preservar UTMs e click IDs",
      "Garantir geração do cookie _gcl_aw do Google Ads",
    ],
    high_effort: [
      "Implementar sGTM em subdomínio próprio para Server-Side Tracking",
      "Configurar Meta CAPI via proxy first-party para bypass de ITP",
    ],
  },
};

/* ─── Helpers ─── */
const iconMap = { Activity, Shield, Server, Layers };

function getScoreColor(score, max = 5) {
  const pct = score / max;
  if (pct >= 0.8) return "#22c55e";
  if (pct >= 0.6) return "#eab308";
  if (pct >= 0.4) return "#f97316";
  return "#ef4444";
}

function getSeverityStyle(severity) {
  if (severity === "critical")
    return { bg: "bg-red-50", border: "border-red-200", text: "text-red-700", icon: XCircle };
  if (severity === "warning")
    return { bg: "bg-amber-50", border: "border-amber-200", text: "text-amber-700", icon: AlertTriangle };
  return { bg: "bg-blue-50", border: "border-blue-200", text: "text-blue-700", icon: Info };
}

function getRatingStyle(rating) {
  const map = {
    "Crítico": { bg: "bg-red-100", text: "text-red-800" },
    "Básico": { bg: "bg-orange-100", text: "text-orange-800" },
    "Intermediário": { bg: "bg-yellow-100", text: "text-yellow-800" },
    "Avançado": { bg: "bg-green-100", text: "text-green-800" },
    "Excelente": { bg: "bg-emerald-100", text: "text-emerald-800" },
  };
  return map[rating] || map["Intermediário"];
}

/* ─── Score Ring ─── */
function ScoreRing({ score, max = 5, size = 120 }) {
  const pct = score / max;
  const r = (size - 12) / 2;
  const circ = 2 * Math.PI * r;
  const offset = circ * (1 - pct);
  const color = getScoreColor(score, max);

  return (
    <svg width={size} height={size} className="mx-auto">
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#e5e7eb" strokeWidth="8" />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        fill="none"
        stroke={color}
        strokeWidth="8"
        strokeDasharray={circ}
        strokeDashoffset={offset}
        strokeLinecap="round"
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
        style={{ transition: "stroke-dashoffset 0.8s ease" }}
      />
      <text x={size / 2} y={size / 2 - 6} textAnchor="middle" className="text-2xl font-bold" fill={color}>
        {score.toFixed(score % 1 ? 2 : 0)}
      </text>
      <text x={size / 2} y={size / 2 + 14} textAnchor="middle" className="text-xs" fill="#9ca3af">
        de {max}
      </text>
    </svg>
  );
}

/* ─── Module Card ─── */
function ModuleCard({ moduleKey, module }) {
  const [open, setOpen] = useState(false);
  const Icon = iconMap[module.icon] || Activity;
  const color = getScoreColor(module.score);

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg" style={{ backgroundColor: color + "18" }}>
            <Icon size={20} style={{ color }} />
          </div>
          <div>
            <h3 className="font-semibold text-gray-900 text-sm">{module.label}</h3>
            <div className="flex items-center gap-2 mt-0.5">
              <div className="h-1.5 w-24 bg-gray-100 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-700"
                  style={{ width: `${(module.score / module.max_score) * 100}%`, backgroundColor: color }}
                />
              </div>
              <span className="text-xs font-medium" style={{ color }}>
                {module.score}/{module.max_score}
              </span>
            </div>
          </div>
        </div>
      </div>

      <p className="text-sm text-gray-600 leading-relaxed">{module.comment}</p>

      <button
        onClick={() => setOpen(!open)}
        className="mt-3 flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700 transition-colors"
      >
        {open ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        {open ? "Ocultar detalhes" : "Ver detalhes técnicos"}
      </button>

      {open && (
        <div className="mt-3 p-3 bg-gray-50 rounded-lg">
          <div className="grid grid-cols-2 gap-2">
            {Object.entries(module.data).map(([key, val]) => (
              <div key={key} className="flex items-center gap-2 text-xs">
                {typeof val === "boolean" ? (
                  val ? (
                    <CheckCircle size={12} className="text-green-500 flex-shrink-0" />
                  ) : (
                    <XCircle size={12} className="text-red-400 flex-shrink-0" />
                  )
                ) : (
                  <span className="w-3 h-3 rounded-full bg-gray-300 flex-shrink-0" />
                )}
                <span className="text-gray-600 truncate">
                  {key.replace(/_/g, " ")}: {typeof val === "boolean" ? (val ? "Sim" : "Não") : String(val ?? "—")}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/* ─── Issue Card ─── */
function IssueCard({ issue }) {
  const style = getSeverityStyle(issue.severity);
  const SevIcon = style.icon;

  return (
    <div className={`rounded-xl border p-4 ${style.bg} ${style.border}`}>
      <div className="flex items-start gap-3">
        <SevIcon size={18} className={`${style.text} mt-0.5 flex-shrink-0`} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className={`text-xs font-semibold uppercase ${style.text}`}>
              {issue.severity === "critical" ? "Crítico" : "Atenção"}
            </span>
            <span className="text-xs text-gray-400">#{issue.rank}</span>
          </div>
          <h4 className="font-semibold text-gray-900 text-sm">{issue.title}</h4>
          <p className="text-xs text-gray-600 mt-1">{issue.description}</p>
          <div className="mt-2 p-2 bg-white bg-opacity-60 rounded-lg">
            <p className="text-xs">
              <span className="font-medium text-gray-700">Impacto: </span>
              <span className="text-gray-600">{issue.business_impact}</span>
            </p>
            <p className="text-xs mt-1">
              <span className="font-medium text-gray-700">Ação: </span>
              <span className="text-gray-600">{issue.recommendation}</span>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ─── Recommendation Pill ─── */
function RecSection({ title, items, color }) {
  return (
    <div>
      <h4 className="text-sm font-semibold text-gray-700 mb-2">{title}</h4>
      <div className="space-y-1.5">
        {items.map((item, i) => (
          <div key={i} className="flex items-start gap-2 text-xs text-gray-600">
            <span className="mt-0.5 w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: color }} />
            {item}
          </div>
        ))}
      </div>
    </div>
  );
}

/* ─── Radar Data ─── */
const radarData = Object.entries(diagnostic.modules).map(([, m]) => ({
  module: m.label.split(" ").slice(0, 2).join(" "),
  score: m.score,
  fullMark: m.max_score,
}));

const barData = Object.entries(diagnostic.modules).map(([, m]) => ({
  name: m.label.split(" ")[0],
  score: m.score,
  max: m.max_score,
}));

/* ─── Main Dashboard ─── */
export default function BlindAnalyticsDashboard() {
  const [tab, setTab] = useState("overview");
  const { overall_maturity: maturity } = diagnostic;
  const rStyle = getRatingStyle(maturity.rating);

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div>
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 bg-indigo-600 rounded-lg flex items-center justify-center">
                <Activity size={16} className="text-white" />
              </div>
              <h1 className="text-lg font-bold text-gray-900">Blind Analytics</h1>
            </div>
            <p className="text-sm text-gray-500 mt-1 ml-11">
              Diagnóstico de Maturidade de Mensuração
            </p>
          </div>
          <div className="text-right">
            <div className="flex items-center gap-2 text-sm text-gray-600">
              <ExternalLink size={14} />
              <span className="font-medium">{diagnostic.domain}</span>
            </div>
            <p className="text-xs text-gray-400 mt-0.5">
              {new Date(diagnostic.audit_timestamp).toLocaleString("pt-BR")}
            </p>
          </div>
        </div>
      </header>

      {/* Tabs */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-6xl mx-auto px-6 flex gap-6">
          {[
            { id: "overview", label: "Visão Geral" },
            { id: "issues", label: "Problemas" },
            { id: "actions", label: "Plano de Ação" },
          ].map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`py-3 text-sm font-medium border-b-2 transition-colors ${
                tab === t.id
                  ? "border-indigo-600 text-indigo-600"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <main className="max-w-6xl mx-auto px-6 py-6">
        {tab === "overview" && (
          <div className="space-y-6">
            {/* Score Hero */}
            <div className="bg-white rounded-xl border border-gray-200 p-6">
              <div className="flex items-center gap-8">
                <ScoreRing score={maturity.score} max={maturity.max_score} size={130} />
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-2">
                    <h2 className="text-xl font-bold text-gray-900">Maturidade Geral</h2>
                    <span className={`px-3 py-1 rounded-full text-xs font-semibold ${rStyle.bg} ${rStyle.text}`}>
                      {maturity.rating}
                    </span>
                  </div>
                  <p className="text-sm text-gray-600 leading-relaxed">
                    A operação possui a base de eventos bem configurada, mas sofre com quebras severas
                    de atribuição e carece de modernização da infraestrutura Server-Side.
                  </p>
                  <div className="flex gap-4 mt-4">
                    <div className="text-center">
                      <p className="text-2xl font-bold text-red-500">2</p>
                      <p className="text-xs text-gray-500">Críticos</p>
                    </div>
                    <div className="text-center">
                      <p className="text-2xl font-bold text-amber-500">1</p>
                      <p className="text-xs text-gray-500">Atenção</p>
                    </div>
                    <div className="text-center">
                      <p className="text-2xl font-bold text-green-500">1</p>
                      <p className="text-xs text-gray-500">Excelente</p>
                    </div>
                  </div>
                </div>
                <div className="w-64 h-48">
                  <ResponsiveContainer>
                    <RadarChart data={radarData}>
                      <PolarGrid stroke="#e5e7eb" />
                      <PolarAngleAxis dataKey="module" tick={{ fontSize: 10, fill: "#6b7280" }} />
                      <PolarRadiusAxis angle={90} domain={[0, 5]} tick={{ fontSize: 9 }} />
                      <Radar
                        dataKey="score"
                        stroke="#6366f1"
                        fill="#6366f1"
                        fillOpacity={0.2}
                        strokeWidth={2}
                      />
                    </RadarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>

            {/* Module Cards */}
            <div>
              <h2 className="text-base font-semibold text-gray-900 mb-3">Módulos Avaliados</h2>
              <div className="grid grid-cols-2 gap-4">
                {Object.entries(diagnostic.modules).map(([key, mod]) => (
                  <ModuleCard key={key} moduleKey={key} module={mod} />
                ))}
              </div>
            </div>

            {/* Bar Chart */}
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <h3 className="text-sm font-semibold text-gray-900 mb-4">Comparativo por Módulo</h3>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={barData} barCategoryGap="30%">
                  <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
                  <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                  <YAxis domain={[0, 5]} tick={{ fontSize: 11 }} />
                  <Tooltip
                    contentStyle={{ fontSize: 12, borderRadius: 8 }}
                    formatter={(v) => [`${v}/5`, "Score"]}
                  />
                  <Bar dataKey="score" radius={[6, 6, 0, 0]}>
                    {barData.map((entry, i) => (
                      <Cell key={i} fill={getScoreColor(entry.score)} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {tab === "issues" && (
          <div className="space-y-4">
            <h2 className="text-base font-semibold text-gray-900">
              Problemas Encontrados ({diagnostic.top_issues.length})
            </h2>
            {diagnostic.top_issues.map((issue) => (
              <IssueCard key={issue.rank} issue={issue} />
            ))}
          </div>
        )}

        {tab === "actions" && (
          <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-6">
            <h2 className="text-base font-semibold text-gray-900">Plano de Ação Recomendado</h2>
            <RecSection
              title="Vitórias Rápidas (sem código)"
              items={diagnostic.recommendations_summary.quick_wins}
              color="#22c55e"
            />
            <RecSection
              title="Esforço Médio (configuração técnica)"
              items={diagnostic.recommendations_summary.medium_effort}
              color="#eab308"
            />
            <RecSection
              title="Esforço Alto (infraestrutura)"
              items={diagnostic.recommendations_summary.high_effort}
              color="#ef4444"
            />
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-gray-200 bg-white mt-8 py-4">
        <p className="text-center text-xs text-gray-400">
          Blind Analytics — Protótipo de Dashboard (dados simulados)
        </p>
      </footer>
    </div>
  );
}
