# WAT Stage Transitions — Blind Analytics

> Mapa completo de mudanças de arquivos entre os estágios A, B e C do projeto Blind Analytics. Complementa o `WAT-Brief.md` (Seção 5.4).

---

## Convenções

| Ícone | Significado |
|-------|-------------|
| 🆕 | Arquivo novo — criado nesta transição |
| ✏️ | Arquivo modificado — já existia, ganha conteúdo ou alterações |
| 🗄️ | Arquivo aposentado — pode ser removido ou mantido como referência |
| ➡️ | Arquivo inalterado — permanece exatamente como estava |

---

## Estado Inicial — Pós-Scaffolding (estado atual)

Arquivos gerados pelo scaffolding. Estrutura completa, código mínimo.

### Documentação (com conteúdo real)

| Arquivo | Conteúdo |
|---------|----------|
| `CLAUDE.md` | Contexto do projeto, 4 módulos, pipeline, estratégia de 3 estágios |
| `README.md` | Setup mínimo |
| `docs/WAT-Brief.md` | Brief completo preenchido (v0.1) |
| `docs/WAT-Stage-Transitions.md` | Este documento |
| `tools/CONTEXT.md` | Manifesto: helpers executam, assets informam |
| `tools/helpers/CONTEXT.md` | Convenções + subpastas por etapa + consumidores por estágio |
| `tools/assets/CONTEXT.md` | Regras de leitura + organização por estágio |

### Configuração

| Arquivo | Conteúdo |
|---------|----------|
| `.env.example` | Placeholders para `ANTHROPIC_API_KEY`, `DATABASE_URL` |
| `.gitignore` | Python + Node.js + secrets + DB |
| `requirements.txt` | Dependências comentadas (playwright, httpx, pydantic) |
| `package.json` | Next.js base mínimo |

### Protótipos visuais (gerados, não operacionais)

| Arquivo | Descrição |
|---------|-----------|
| `tools/assets/visual/dashboard/dashboard-prototype.html` | Protótipo visual do dashboard (referência para Estágio C) |
| `tools/assets/visual/dashboard/dashboard-prototype.jsx` | Versão React do protótipo |
| `tools/assets/visual/pipeline-explorer.ipynb` | Notebook exploratório do pipeline |
| `tools/assets/examples/sample-diagnostic.json` | Contrato de dados — payload completo de exemplo |

### Pastas vazias

```
tools/helpers/shared/          (sem .py)
tools/helpers/discover/        (sem .py)
tools/helpers/intercept/       (sem .py)
tools/helpers/attribute/       (sem .py)
tools/helpers/detect/          (sem .py)
tools/helpers/inspect/         (sem .py)
tools/helpers/report/          (sem .py)
tools/assets/protocols/        (sem arquivos)
tools/assets/visual/streamlit/ (sem arquivos)
src/app/                       (sem arquivos)
src/components/                (sem arquivos)
src/lib/                       (sem arquivos)
src/styles/                    (sem arquivos)
prompts/                       (sem arquivos)
tests/                         (sem arquivos)
```

---

## Transição → Estágio A (Prototipagem com Cowork)

> O pipeline ganha vida. Assets de protocolo alimentam o Cowork, helpers são codificados progressivamente.

### Assets de Protocolo (fonte de verdade para o diagnóstico)

| Arquivo | Status | Descrição |
|---------|--------|-----------|
| `tools/assets/protocols/diagnostic-protocol.md` | 🆕 | Protocolo completo dos 4 módulos (Tracking Infrastructure, Attribution Health, SST, DataLayer) com critérios detalhados |
| `tools/assets/protocols/scoring-rubrics.md` | 🆕 | Rubricas de scoring: o que é nota 0, 1, 2, 3, 4, 5 para cada módulo |
| `tools/assets/protocols/regex-patterns.json` | 🆕 | Patterns de regex para identificação de tags (GTM: `googletagmanager.com/gtm.js`, GA4: `google-analytics.com/g/collect`, Meta: `facebook.net/fbevents.js`, LinkedIn: `snap.licdn.com`) |
| `tools/assets/protocols/ga4-events-taxonomy.json` | 🆕 | Dicionário de eventos GA4 e-commerce (view_item, add_to_cart, purchase, etc.) com campos obrigatórios e recomendados |
| `tools/assets/protocols/funnel-heuristics.json` | 🆕 | Heurísticas de classificação de URL por stage do funil (home/category/product/cart/checkout), seletores CSS de conteúdo, paths de sitemap |

### Helpers Python (ordem de criação recomendada)

| Arquivo | Status | Etapa | Descrição |
|---------|--------|-------|-----------|
| `tools/helpers/shared/config.py` | 🆕 | Base | Constantes, dataclasses de retorno (Pydantic), importação dos regex patterns e taxonomia GA4 dos assets JSON |
| `tools/helpers/shared/url_validator.py` | 🆕 | 1 | Valida DNS, acessibilidade HTTP(S), resolve redirects. Retorna URL final + status. Gate: HTTP 200 |
| `tools/helpers/discover/sitemap_parser.py` | 🆕 | 1.5 | Fetch e parse de sitemap.xml/robots.txt via httpx (sem browser). Retorna `list[DiscoveredUrl]` ordenada por priority |
| `tools/helpers/discover/page_selector.py` | 🆕 | 1.5 | Classifica URLs por heurística de funil (URL patterns + conteúdo), spider BFS com Playwright, seleciona amostra representativa. Retorna `FunnelSelection` |
| `tools/helpers/intercept/network_interceptor.py` | 🆕 | 2 | Usa Playwright headless para carregar a página, interceptar todos os requests de rede até networkidle. Retorna lista de URLs + status HTTP + headers |
| `tools/helpers/intercept/tag_identifier.py` | 🆕 | 2 | Recebe lista de requests, aplica regex patterns do asset, extrai IDs de tags (GTM-XXXXX, G-XXXXX, pixel IDs). Função pura, sem browser |
| `tools/helpers/attribute/attribution_tester.py` | 🆕 | 3 | Usa Playwright para navegar com UTMs simuladas (`?utm_source=agent_test&gclid=TeStGcLiD`), inspeciona `document.cookie` e `localStorage`. Verifica persistência e redirect strip |
| `tools/helpers/detect/sst_detector.py` | 🆕 | 4 | Analisa dados de rede capturados na Etapa 2: busca subdomínios first-party (sgtm.*, data.*), endpoints CAPI, cookies HttpOnly via Set-Cookie headers. Sem browser, análise pura dos dados |
| `tools/helpers/inspect/datalayer_inspector.py` | 🆕 | 5 | Executa `window.dataLayer` via Playwright, filtra eventos por nome, valida schema GA4 contra taxonomia do asset. Simula clique em botão estratégico (add to cart) |
| `tools/helpers/report/scorer.py` | 🆕 | 6 | Recebe resultados das etapas 2-5, aplica rubricas do asset `scoring-rubrics.md`, calcula score 0-5 por módulo + score global + rating de maturidade |
| `tools/helpers/report/report_generator.py` | 🆕 | 6 | Monta payload JSON conforme contrato de dados de `sample-diagnostic.json`. Gera comentários em PT-BR, recomendações priorizadas (quick wins / medium / high effort) |

### System Prompt e Testes

| Arquivo | Status | Descrição |
|---------|--------|-----------|
| `prompts/diagnostic-agent.md` | 🆕 | System prompt do agente de diagnóstico (seção 3.2 do WAT-Brief). Estável entre estágios |
| `tests/tools/test_url_validator.py` | 🆕 | Testa resolução de DNS, handling de redirects, timeout |
| `tests/tools/test_tag_identifier.py` | 🆕 | Testa regex patterns contra requests reais capturados |
| `tests/tools/test_attribution_tester.py` | 🆕 | Testa detecção de cookies, redirect strip |
| `tests/tools/test_sst_detector.py` | 🆕 | Testa identificação de subdomínios, CAPI endpoints |
| `tests/tools/test_datalayer_inspector.py` | 🆕 | Testa validação de schema GA4, contagem de eventos |
| `tests/tools/test_scorer.py` | 🆕 | Testa cálculo de scores contra rubricas |
| `tests/fixtures/network_requests_sample.json` | 🆕 | Snapshot de 187 requests interceptados de um site real |
| `tests/fixtures/datalayer_sample.json` | 🆕 | Snapshot de window.dataLayer com 8 eventos |
| `tests/fixtures/cookies_sample.json` | 🆕 | Snapshot de document.cookie com _ga, _fbc, etc. |

### Arquivos Modificados

| Arquivo | Status | O que muda |
|---------|--------|------------|
| `requirements.txt` | ✏️ | Descomenta e pina: `playwright>=1.40.0`, `httpx>=0.27.0`, `pydantic>=2.0.0`, `pytest>=8.0.0`, `ruff>=0.5.0` |
| `tools/helpers/CONTEXT.md` | ✏️ | Subpastas documentadas com os helpers reais criados |
| `tools/assets/CONTEXT.md` | ✏️ | Assets reais documentados nos protocols/ |

### Inalterados

| Arquivo | Status |
|---------|--------|
| `tools/CONTEXT.md` | ➡️ |
| `tools/assets/examples/sample-diagnostic.json` | ➡️ |
| `.env.example` | ➡️ |
| `.gitignore` | ➡️ |
| `package.json` | ➡️ |

---

## Transição A → B (Streamlit — Validação Funcional)

> Streamlit entra como interface web. Importa os helpers diretamente como módulos Python.

### Arquivos Novos

| Arquivo | Status | Descrição |
|---------|--------|-----------|
| `src/streamlit/app.py` | 🆕 | App principal Streamlit. `st.text_input("URL")` → botão "Diagnosticar" → importa e executa helpers sequencialmente → renderiza com `st.metric` (score global), `st.dataframe` (tabela de módulos), `st.expander` (evidências detalhadas), `st.markdown` (recomendações) |
| `src/streamlit/requirements.txt` | 🆕 | `streamlit>=1.30.0`, `playwright>=1.40.0`, `httpx>=0.27.0`, `pydantic>=2.0.0`. Separado do raiz para deploy independente no Streamlit Cloud |
| `src/streamlit/pages/module_details.py` | 🆕 | Página multi-page Streamlit para ver evidências detalhadas de cada módulo (check-by-check com result, score_impact, detail) |
| `tools/assets/visual/streamlit/layout-reference.md` | 🆕 | Descrição da estrutura da interface: ordem dos elementos, quais métricas em destaque, como formatar a tabela de scores |

### Arquivos Modificados

| Arquivo | Status | O que muda |
|---------|--------|------------|
| `CLAUDE.md` | ✏️ | Seção "Estratégia de Desenvolvimento": Estágio A (atual) → Estágio B (atual) |
| `.env.example` | ✏️ | Adiciona `ANTHROPIC_API_KEY=sk-ant-...` (descomentado se usar LLM para gerar comentários no scoring) |

### Inalterados (o pipeline NÃO muda)

| Arquivo/Pasta | Status | Justificativa |
|---------------|--------|---------------|
| `tools/helpers/**/*.py` | ➡️ | Streamlit importa os helpers — não os reescreve |
| `tools/assets/protocols/**` | ➡️ | Fonte de verdade permanente |
| `tools/assets/examples/sample-diagnostic.json` | ➡️ | Contrato de dados estável |
| `prompts/diagnostic-agent.md` | ➡️ | System prompt estável entre estágios |
| `tests/**` | ➡️ | Testes continuam passando — helpers inalterados |
| `requirements.txt` (raiz) | ➡️ | O Streamlit usa seu próprio requirements.txt |
| `package.json` | ➡️ | Next.js ainda não entrou — não é tocado |

---

## Transição B → C (Next.js + FastAPI — Produção)

> Transição mais pesada em volume. FastAPI wrappa os helpers como API. Next.js substitui o Streamlit.

### Backend — FastAPI + Agent Tool Use

| Arquivo | Status | Descrição |
|---------|--------|-----------|
| `src/api/main.py` | 🆕 | App FastAPI: CORS configurado para o Next.js, middleware de logs, inicialização do Playwright no startup |
| `src/api/routes/analyze.py` | 🆕 | `POST /api/analyze` — recebe `{"url": "..."}`, executa pipeline completo via agent loop, retorna JSON do diagnóstico |
| `src/api/routes/status.py` | 🆕 | `GET /api/status/{id}` — Server-Sent Events (SSE) emitindo progresso por etapa em tempo real |
| `src/api/routes/report.py` | 🆕 | `GET /api/report/{id}` — retorna relatório salvo por ID |
| `src/api/agent/orchestrator.py` | 🆕 | **O coração do Estágio C.** Agent loop: `client.messages.create(model, system, tools, messages)` → verifica se response tem tool_use → executa helper correspondente → devolve resultado → loop até diagnóstico completo |
| `src/api/agent/tools.py` | 🆕 | Tool definitions no formato SDK Anthropic. Cada helper vira: `{"name": "intercept_network_traffic", "description": "...", "input_schema": {"type": "object", "properties": {"url": {"type": "string"}}}}` |
| `src/api/agent/system_prompt.py` | 🆕 | Carrega `prompts/diagnostic-agent.md` como string e passa no parâmetro `system` do `client.messages.create()` |
| `src/api/requirements.txt` | 🆕 | `fastapi>=0.110.0`, `uvicorn>=0.27.0`, `anthropic>=0.40.0`, `playwright>=1.40.0`, `pydantic>=2.0.0` |

### Frontend — Next.js 14

| Arquivo | Status | Descrição |
|---------|--------|-----------|
| `src/app/page.tsx` | 🆕 | Tela de Input: campo de URL centralizado, botão "Diagnosticar", breve explicação. POST para `/api/analyze` no submit |
| `src/app/analysis/[id]/page.tsx` | 🆕 | Tela de Processing: consome SSE de `/api/status/{id}`, progress bar por módulo (4 etapas + scoring), preview parcial dos resultados |
| `src/app/report/[id]/page.tsx` | 🆕 | Tela de Dashboard: score global em destaque, 4 cards de módulo, gráfico radar (Recharts), recomendações priorizadas, botões "Exportar PDF" e "Nova URL" |
| `src/app/layout.tsx` | 🆕 | Root layout: metadata, fonts, Tailwind provider |
| `src/components/ui/button.tsx` | 🆕 | shadcn/ui Button |
| `src/components/ui/card.tsx` | 🆕 | shadcn/ui Card |
| `src/components/ui/input.tsx` | 🆕 | shadcn/ui Input |
| `src/components/ui/badge.tsx` | 🆕 | shadcn/ui Badge (para severity: critical/warning/info) |
| `src/components/ui/progress.tsx` | 🆕 | shadcn/ui Progress (para barra de progresso) |
| `src/components/dashboard/ScoreCard.tsx` | 🆕 | Card de score por módulo: nota, cor (verde/amarelo/vermelho), comentário resumido, ícone |
| `src/components/dashboard/RadarChart.tsx` | 🆕 | Gráfico radar Recharts com os 4 módulos |
| `src/components/dashboard/RecommendationList.tsx` | 🆕 | Lista de recomendações agrupadas: quick wins, medium effort, high effort |
| `src/components/dashboard/EvidencePanel.tsx` | 🆕 | Painel expansível com evidências check-by-check de cada módulo |
| `src/components/layout/Header.tsx` | 🆕 | Header com logo e navegação |
| `src/components/layout/Footer.tsx` | 🆕 | Footer com créditos |
| `src/lib/types.ts` | 🆕 | Tipos TypeScript espelhando `sample-diagnostic.json`: `DiagnosticResult`, `ModuleResult`, `Evidence`, `Recommendation` |
| `src/lib/api.ts` | 🆕 | Funções fetch para comunicar com a FastAPI: `startAnalysis(url)`, `getStatus(id)`, `getReport(id)` |
| `src/lib/utils.ts` | 🆕 | Utilitários: `cn()` para classnames, `formatScore()`, `getScoreColor()` |
| `src/styles/globals.css` | 🆕 | Tailwind base + camada de design tokens (cores, tipografia) |

### Configuração Next.js

| Arquivo | Status | Descrição |
|---------|--------|-----------|
| `next.config.js` | 🆕 | Configuração do Next.js: rewrites para proxy da FastAPI em dev |
| `tailwind.config.js` | 🆕 | Configuração do Tailwind: cores customizadas (score colors), font family |
| `tsconfig.json` | 🆕 | TypeScript config com path aliases (`@/components`, `@/lib`) |
| `postcss.config.js` | 🆕 | PostCSS para Tailwind |
| `components.json` | 🆕 | Config do shadcn/ui CLI |

### Persistência (opcional)

| Arquivo | Status | Descrição |
|---------|--------|-----------|
| `prisma/schema.prisma` | 🆕 | Schema de banco: tabela `Report` (id, domain, result_json, created_at, expires_at) |
| `prisma/migrations/` | 🆕 | Migrações SQLite → PostgreSQL |

### Arquivos Modificados

| Arquivo | Status | O que muda |
|---------|--------|------------|
| `package.json` | ✏️ | Dependências reais: `next@14`, `react@18`, `recharts`, `tailwindcss`, `@shadcn/ui`, `lucide-react` |
| `.env.example` | ✏️ | `ANTHROPIC_API_KEY` obrigatória, `DATABASE_URL`, `NEXT_PUBLIC_API_URL` |
| `CLAUDE.md` | ✏️ | Estágio atual: C. Stack completa documentada |
| `README.md` | ✏️ | Instruções de setup expandidas: instalar Python + Node, rodar API + frontend, variáveis obrigatórias |

### Arquivos Aposentados

| Arquivo | Status | Destino |
|---------|--------|---------|
| `src/streamlit/app.py` | 🗄️ | Removido ou movido para `_archive/`. Streamlit Cloud desligado |
| `src/streamlit/requirements.txt` | 🗄️ | Idem |
| `src/streamlit/pages/module_details.py` | 🗄️ | Idem |

### Inalterados (o pipeline CONTINUA o mesmo)

| Arquivo/Pasta | Status | Justificativa |
|---------------|--------|---------------|
| `tools/helpers/**/*.py` | ➡️ | FastAPI chama os helpers — não os reescreve. `orchestrator.py` importa e executa |
| `tools/assets/protocols/**` | ➡️ | Fonte de verdade permanente |
| `tools/assets/examples/sample-diagnostic.json` | ➡️ | Contrato de dados: Next.js `types.ts` espelha esta estrutura |
| `prompts/diagnostic-agent.md` | ➡️ | Carregado por `system_prompt.py` — texto idêntico |
| `tests/tools/**` | ➡️ | Testes continuam passando |

---

## Resumo Visual — Ciclo de Vida dos Arquivos

```
                         Scaffolding    Estágio A      A → B         B → C
                         ───────────    ─────────      ─────         ─────
CLAUDE.md                    🆕            ✏️            ✏️            ✏️
requirements.txt             🆕            ✏️            ➡️            ➡️
package.json                 🆕            ➡️            ➡️            ✏️
.env.example                 🆕            ➡️            ✏️            ✏️

protocols/*.md|.json         (vazio)       🆕            ➡️            ➡️
examples/sample.json         🆕            ➡️            ➡️            ➡️

helpers/shared/config.py     (vazio)       🆕            ➡️            ➡️
helpers/discover/*.py        (vazio)       🆕            ➡️            ➡️
helpers/intercept/*.py       (vazio)       🆕            ➡️            ➡️
helpers/attribute/*.py       (vazio)       🆕            ➡️            ➡️
helpers/detect/*.py          (vazio)       🆕            ➡️            ➡️
helpers/inspect/*.py         (vazio)       🆕            ➡️            ➡️
helpers/report/*.py          (vazio)       🆕            ➡️            ➡️

prompts/diagnostic-agent.md  (vazio)       🆕            ➡️            ➡️
tests/**                     (vazio)       🆕            ➡️            ➡️

src/streamlit/app.py         (vazio)       —             🆕            🗄️
src/streamlit/requirements   (vazio)       —             🆕            🗄️

src/api/main.py              (vazio)       —             —             🆕
src/api/agent/orchestrator   (vazio)       —             —             🆕
src/api/agent/tools.py       (vazio)       —             —             🆕
src/api/routes/*.py          (vazio)       —             —             🆕

src/app/**/*.tsx             (vazio)       —             —             🆕
src/components/**/*.tsx      (vazio)       —             —             🆕
src/lib/*.ts                 (vazio)       —             —             🆕
src/styles/globals.css       (vazio)       —             —             🆕
```

---

## Princípio Fundamental

> **Os helpers, assets e system prompt são escritos uma vez (Estágio A) e consumidos por todos os estágios subsequentes.** Cada transição adiciona uma camada de interface/infraestrutura ao redor do pipeline existente — nunca reescreve o pipeline em si.

Isso funciona porque:
1. **Helpers são funções puras** — `intercept_network_traffic(url) → List[NetworkRequest]` funciona igual chamado pelo Cowork, Streamlit ou FastAPI
2. **Assets são somente leitura** — `scoring-rubrics.md` é a mesma fonte de verdade nos três estágios
3. **O contrato de dados é estável** — `sample-diagnostic.json` é consumido por `st.dataframe` no Estágio B e por `ScoreCard.tsx` no Estágio C
4. **O system prompt é estável** — mesmo texto em `prompts/diagnostic-agent.md` é lido pelo Cowork (A), referenciado pelo Streamlit (B) e passado no `client.messages.create()` (C)

---

*WAT Stage Transitions — Blind Analytics v1.0*
