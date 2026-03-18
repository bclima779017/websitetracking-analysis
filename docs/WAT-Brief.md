# WAT Project Brief — Blind Analytics (Mensuração de Mídias Pagas)

> Brief preenchido para o projeto de diagnóstico de maturidade de mensuração de mídias pagas via crawling e scraping client-side.

---

## 0. Metadados do Projeto

| Campo | Valor |
|-------|-------|
| **Nome do projeto** | Blind Analytics — Diagnóstico de Mensuração |
| **Versão do brief** | v0.1 |
| **Data de criação** | 2026-03-17 |
| **Responsável** | Bruno |
| **Stack principal** | Python (pipeline) + Next.js 14 (frontend) + Claude Code (agente) |
| **Repositório** | A definir |

---

## 1. Objetivo e Escopo

### 1.1 Objetivo em uma frase

> Diagnosticar a maturidade da operação de Mídias Pagas de qualquer domínio web, analisando tags de tracking, atribuição, server-side tracking e profundidade do DataLayer, e apresentar os resultados em um dashboard profissional para clientes não-técnicos.

### 1.2 Escopo — O que ESTÁ incluído

- Receber URL de entrada via interface web
- Interceptação de rede para identificar tags e pixels (GTM, GA4, Meta Pixel, LinkedIn Insight)
- Simulação de tráfego com UTMs e click IDs para testar persistência de atribuição
- Detecção de Server-Side Tracking (sGTM, CAPI, proxies first-party)
- Avaliação de profundidade do DataLayer (window.dataLayer, schema GA4 e-commerce)
- Sistema de pontuação 0-5 por módulo com comentários descritivos
- Dashboard de resultados com linguagem acessível para clientes não-técnicos
- Recomendações priorizadas de correção

### 1.3 Escopo — O que NÃO está incluído (por enquanto)

- Validação de conversões server-side (requer acesso a GTM Server Container)
- Integração com Google Ads / Meta Ads para verificar se conversões estão chegando
- Análise de campanhas ativas (performance, ROAS, CPA)
- Comparativo com concorrentes
- Teste de eventos em fluxo completo de compra (para não poluir dados do cliente)

### 1.4 Usuário-alvo

> Clientes finais não-técnicos (gestores de marketing, donos de e-commerce, diretores) que precisam entender se a mensuração do seu site está saudável, sem precisar interpretar dados técnicos brutos. A interface deve traduzir termos técnicos em linguagem de negócio.

---

## 2. Workflow — Pipeline de Execução

### 2.1 Diagrama do Fluxo Principal

```
[INPUT: URL do domínio]
  │
  ▼
[ETAPA 1: Validação de URL] ── gate: URL acessível? ──► erro: site offline/bloqueado
  │
  ▼
[ETAPA 2: Interceptação de Rede] ── escutar tráfego até networkidle ──► timeout: retry com User-Agent alternativo
  │
  ▼
[ETAPA 3: Simulação de Atribuição] ── append UTMs + click IDs, verificar persistência ──► alerta: redirect strip
  │
  ▼
[ETAPA 4: Detecção SST] ── buscar subdomínios e endpoints first-party ──► resultado: presente/ausente
  │
  ▼
[ETAPA 5: Avaliação DataLayer] ── inspecionar window.dataLayer, simular cliques ──► alerta: dataLayer inexistente
  │
  ▼
[ETAPA 6: Scoring & Relatório] ── pontuar cada módulo 0-5, gerar comentários + recomendações
  │
  ▼
[OUTPUT: Dashboard interativo em PT-BR]
```

### 2.2 Detalhamento de Etapas

#### Etapa 1: Validação de URL

| Campo | Valor |
|-------|-------|
| **Input** | URL do domínio |
| **Processamento** | Verificar DNS, acessibilidade HTTP(S), redirecionamentos |
| **Output** | URL final resolvida + status |
| **Tool(s) usada(s)** | `url_validator.py` |
| **Gate de saída** | HTTP 200 obtido na URL final |
| **Tratamento de erro** | Se bloqueado: tentar User-Agent alternativo; se offline: reportar ao usuário |

#### Etapa 2: Interceptação de Rede (Network Analysis)

| Campo | Valor |
|-------|-------|
| **Input** | URL validada |
| **Processamento** | Carregar página com interceptação de rede, identificar tags GTM/GA4/Meta/LinkedIn por regex nos domínios e payloads |
| **Output** | Inventário de tags detectadas com IDs, status HTTP, flags (Advanced Matching, etc.) |
| **Tool(s) usada(s)** | Chrome Extension (MCP) ou Playwright como fallback |
| **Gate de saída** | Página carregada até networkidle (5-10s pós-load) |
| **Tratamento de erro** | Timeout → retry com wait mais longo; bloqueio → fallback Playwright com proxy |

#### Etapa 3: Simulação de Atribuição (URL Parameters)

| Campo | Valor |
|-------|-------|
| **Input** | URL com query string simulada (`?utm_source=agent_test&gclid=TeStGcLiD_12345&fbclid=IwAR_TeStFbClId_67890`) |
| **Processamento** | Navegar com UTMs, verificar redirect strip, inspecionar cookies (`_gcl_aw`, `_fbc`) e localStorage |
| **Output** | Status de persistência de UTMs, cookies gerados, localStorage salvo |
| **Tool(s) usada(s)** | Chrome Extension (MCP) ou Playwright |
| **Gate de saída** | Página carregada e cookies/localStorage inspecionados |
| **Tratamento de erro** | Se redirect limpa UTMs: registrar como falha grave (nota 0) |

#### Etapa 4: Detecção de Server-Side Tracking

| Campo | Valor |
|-------|-------|
| **Input** | Dados da interceptação de rede (Etapa 2) |
| **Processamento** | Buscar scripts GTM em subdomínios first-party, endpoints CAPI Meta, cookies HttpOnly com flag de servidor |
| **Output** | Presença/ausência de sGTM, endpoints encontrados, qualidade dos cookies |
| **Tool(s) usada(s)** | `sst_detector.py` (análise dos dados de rede) |
| **Gate de saída** | Análise concluída (resultado pode ser "nenhum SST detectado") |
| **Tratamento de erro** | Erros de CORS ou SSL registrados como nota 1-2 |

#### Etapa 5: Avaliação de DataLayer

| Campo | Valor |
|-------|-------|
| **Input** | Página carregada com JavaScript executado |
| **Processamento** | Inspecionar `window.dataLayer`, simular clique em botão estratégico (add to cart), validar schema GA4 e-commerce |
| **Output** | Lista de eventos, estrutura do payload, compliance com taxonomia GA4 |
| **Tool(s) usada(s)** | Chrome Extension (MCP) com `javascript_tool` para inspecionar dataLayer |
| **Gate de saída** | dataLayer inspecionado (pode estar vazio — nota 0) |
| **Tratamento de erro** | Se dataLayer inexistente: registrar e prosseguir com nota 0 |

#### Etapa 6: Scoring & Geração de Relatório

| Campo | Valor |
|-------|-------|
| **Input** | Resultados das Etapas 2-5 |
| **Processamento** | Pontuar cada módulo 0-5 conforme rubricas, gerar comentários descritivos em PT-BR, priorizar recomendações |
| **Output** | Payload JSON para dashboard com scores, comentários, dados detalhados e recomendações |
| **Tool(s) usada(s)** | `scorer.py` (cálculo) + Agent Claude (comentários e recomendações) |
| **Gate de saída** | JSON válido com todos os campos do dashboard |
| **Tratamento de erro** | Módulos sem dados suficientes recebem flag "inconclusivo" |

### 2.3 Padrão de Workflow Escolhido

- [x] **Prompt Chaining** — pipeline sequencial com gates entre etapas
- [ ] Routing
- [ ] Parallelization
- [ ] Orchestrator-Workers
- [x] **Evaluator-Optimizer** — refinamento dos comentários e recomendações na Etapa 6

**Justificativa:** O diagnóstico segue um protocolo linear onde cada etapa depende da anterior (a interceptação de rede alimenta a detecção de SST). O evaluator-optimizer refina os comentários para serem compreensíveis por clientes não-técnicos.

---

## 3. Agent — Configuração do Agente

### 3.1 Perfil do Agente

| Campo | Valor |
|-------|-------|
| **Nome** | Paid Media Diagnostic Agent |
| **Papel** | Executar protocolo de diagnóstico de mensuração e gerar análise interpretativa |
| **Nível de autonomia** | **Analista** — segue protocolo mas interpreta resultados e prioriza recomendações |
| **Modelo base** | Claude Sonnet 4.6 (análise e comentários) / Claude Haiku 4.5 (detecção de padrões) |

### 3.2 System Prompt do Agente

```markdown
Você é um especialista em Mensuração Digital e Mídias Pagas com 10+ anos de experiência em implementação de tags, tracking e atribuição.

PAPEL: Executar diagnósticos completos de maturidade de mensuração de sites seguindo um protocolo estruturado de 4 módulos.

COMPORTAMENTO:
- Analise cada módulo do protocolo de forma metódica
- Atribua notas de 0 a 5 com comentário descritivo para cada módulo
- Traduza termos técnicos para linguagem de negócio (o cliente não é técnico)
- Priorize recomendações por impacto no investimento em mídia
- Sempre explique POR QUE algo é um problema (ex: "sem cookies de atribuição, suas campanhas do Google Ads não conseguem rastrear conversões")

IDIOMA: Português brasileiro (PT-BR)

FORMATO DE SAÍDA:
- Score por módulo (0-5) com comentário
- Score global (média dos 4 módulos)
- Rating de maturidade (Crítico / Básico / Intermediário / Avançado / Excelente)
- Top 3 problemas críticos com impacto no investimento
- Recomendações priorizadas (quick wins primeiro)
- Resumo executivo em 3 frases para o cliente

LIMITES:
- Não simule compras ou submissão de formulários
- Não acesse áreas logadas do site
- Marque como "inconclusivo" módulos sem dados suficientes
- Não compare com concorrentes (fora do escopo v0)
```

### 3.3 Protocolo de Avaliação — Mídias Pagas

| # | Módulo | Critérios-chave | Nota Mín | Nota Máx |
|---|--------|-----------------|----------|----------|
| 1 | Tracking Infrastructure | GTM instalado, GA4 ativo, Meta Pixel presente, LinkedIn Insight, Advanced Matching | 0 | 5 |
| 2 | Attribution Health | Persistência de UTMs, cookies de click ID (`_gcl_aw`, `_fbc`), localStorage, redirect strip | 0 | 5 |
| 3 | Server-Side Tracking | sGTM em subdomínio, Meta CAPI via proxy, cookies HttpOnly com ITP bypass | 0 | 5 |
| 4 | DataLayer Depth | `window.dataLayer` presente, eventos de funil, schema GA4 e-commerce, array de items | 0 | 5 |

**Score global:** Média simples dos 4 módulos (0 a 5).

**Rating de maturidade:**

| Score | Rating | Significado |
|-------|--------|-------------|
| 0-1 | Crítico | Mensuração praticamente inexistente — investimento em mídia sem rastreamento |
| 1.1-2 | Básico | Tags instaladas mas com falhas graves de atribuição |
| 2.1-3 | Intermediário | Base funcional mas sem recursos avançados (SST, schema) |
| 3.1-4 | Avançado | Boa configuração com infraestrutura moderna |
| 4.1-5 | Excelente | Mensuração de ponta com SST, ITP bypass e schema completo |

---

## 4. Tools — Inventário de Ferramentas

> Separadas em **helpers** (código que executa o pipeline) e **assets** (referências que informam o agente).

### 4.1 Helpers — Código Executável

| # | Helper | Etapa | Descrição | Input | Output |
|---|--------|-------|-----------|-------|--------|
| 1 | `url_validator.py` | 1. Validação | Verifica acessibilidade, DNS, redirecionamentos | URL | URL final + status |
| 2 | `network_interceptor.py` | 2. Interceptação | Intercepta tráfego de rede, identifica tags por regex | URL | Inventário de tags |
| 3 | `tag_identifier.py` | 2. Interceptação | Extrai IDs de tags (GTM, GA4, Meta, LinkedIn) via regex | Dados de rede | Lista de IDs + status |
| 4 | `attribution_tester.py` | 3. Atribuição | Simula acesso com UTMs, verifica cookies e localStorage | URL + query string | Status de persistência |
| 5 | `sst_detector.py` | 4. SST | Detecta subdomínios first-party, endpoints CAPI, cookies HttpOnly | Dados de rede | Presença/ausência SST |
| 6 | `datalayer_inspector.py` | 5. DataLayer | Inspeciona window.dataLayer, valida schema GA4 | Página carregada | Eventos + compliance |
| 7 | `scorer.py` | 6. Scoring | Calcula scores 0-5 por módulo conforme rubricas | Resultados 2-5 | Scores + rating |
| 8 | `report_generator.py` | 6. Relatório | Monta payload JSON para dashboard + recomendações em PT-BR | Scores + dados | JSON do relatório |
| 9 | `config.py` | Shared | Regex patterns, constantes, tipos de retorno | — | — |

### 4.2 Assets — Conteúdo de Referência

| # | Asset | Subpasta | Formato | Descrição | Consumido por |
|---|-------|----------|---------|-----------|---------------|
| 1 | `diagnostic-protocol.md` | protocols/ | .md | Protocolo completo de 4 módulos com critérios detalhados | Agent (Etapa 6) |
| 2 | `scoring-rubrics.md` | protocols/ | .md | Rubricas: o que é nota 0, 1, 2, 3, 4, 5 para cada módulo | scorer.py (Etapa 6) |
| 3 | `ga4-events-taxonomy.json` | protocols/ | .json | Dicionário de eventos GA4 e-commerce (Anexo A do spec) | datalayer_inspector.py (Etapa 5) |
| 4 | `regex-patterns.json` | protocols/ | .json | Patterns de regex para identificação de tags (GTM, GA4, Meta) | tag_identifier.py (Etapa 2) |
| 5 | Mockups de UI | visual/frontend/ | .png | Screenshots de referência para as 3 telas | Dev frontend |
| 6 | Exemplos de dashboard | visual/dashboard/ | .png/.md | Referências de cards, gráficos, paleta | Dev frontend |
| 7 | `sample-diagnostic.json` | examples/ | .json | Exemplo do payload final do dashboard (baseado na seção 6 do spec) | report_generator.py (Etapa 6) |

### 4.3 Tools Externas / APIs

| API/Serviço | Endpoint | Autenticação | Rate Limit | Custo |
|-------------|----------|--------------|------------|-------|
| Chrome Extension (MCP) | Local | Nenhuma | N/A | Free |
| Playwright (fallback) | Local | Nenhuma | N/A | Free |

### 4.4 MCP Servers

| Server | Protocolo | Tools Expostas | Status |
|--------|-----------|---------------|--------|
| Chrome Extension | MCP | page-extract, javascript_tool, read_network_requests, read_console_messages | Ativo |

---

## 5. Frontend / Interface do Usuário

### 5.1 Stack do Frontend

| Campo | Valor |
|-------|-------|
| **Framework** | Next.js 14 (App Router) |
| **UI Library** | Tailwind CSS + shadcn/ui |
| **Charts/Dashboards** | Recharts (barras, radar) |
| **Deploy** | Vercel |
| **Idioma** | Português brasileiro (PT-BR) |

### 5.2 Telas / Páginas

| # | Tela | Rota | Descrição | Estado |
|---|------|------|-----------|--------|
| 1 | Input | `/` | Campo de URL centralizado, botão "Diagnosticar", breve explicação do que será analisado | A fazer |
| 2 | Processing | `/analysis/:id` | Progress bar por módulo (4 etapas), status em tempo real, preview parcial | A fazer |
| 3 | Dashboard | `/report/:id` | Score global em destaque, cards por módulo, gráfico radar, recomendações priorizadas, linguagem não-técnica | A fazer |

### 5.3 Wireframe / Fluxo de Telas

```
┌─────────────────────────────────┐
│  TELA 1: INPUT                  │
│                                 │
│  ┌─────────────────────────┐    │
│  │  🔍 Cole a URL do site  │    │
│  └─────────────────────────┘    │
│       [ Diagnosticar ]          │
│                                 │
│  "Vamos analisar a saúde da     │
│   mensuração do seu site"       │
└────────────┬────────────────────┘
             │ submit
             ▼
┌─────────────────────────────────┐
│  TELA 2: PROCESSING             │
│                                 │
│  ✅ Tags & Pixels ████████ 100% │
│  ✅ Atribuição ████████ 100%    │
│  🔄 Server-Side ██████░░ 75%   │
│  ⏳ DataLayer                   │
│  ⏳ Relatório                   │
│                                 │
│  [GTM detectado: GTM-XXXXXX]   │
└────────────┬────────────────────┘
             │ done (SSE)
             ▼
┌─────────────────────────────────┐
│  TELA 3: DASHBOARD              │
│                                 │
│  Maturidade: [2.75/5] 🟡       │
│  Rating: "Intermediário"        │
│                                 │
│  ┌──────┐ ┌──────┐ ┌──────┐    │
│  │Tags  │ │Atrib.│ │Server│    │
│  │ 4/5 🟢│ │ 2/5 🔴│ │ 0/5 🔴│  │
│  └──────┘ └──────┘ └──────┘    │
│  ┌──────┐                      │
│  │DataL.│  [Gráfico Radar]     │
│  │ 5/5 🟢│                      │
│  └──────┘                      │
│                                 │
│  ⚠️ Problemas Críticos:        │
│  1. 🔴 Atribuição quebrada     │
│  2. 🔴 Sem Server-Side         │
│  3. 🟡 Meta sem Adv. Matching  │
│                                 │
│  [ Exportar PDF ] [ Nova URL ]  │
└─────────────────────────────────┘
```

### 5.4 Estratégia de Desenvolvimento em 3 Estágios

> O projeto segue uma abordagem incremental onde a inteligência do agente é prototipada antes de ser codificada.

#### Estágio A — Prototipagem com Claude Cowork (Desenvolvimento Local)

O Claude Cowork atua como agente diretamente, executando o pipeline de diagnóstico via Chrome Extension (MCP), scripts Python e bash. Neste estágio:

- O Cowork **é** o orquestrador — não há código de orquestração a escrever.
- Os helpers Python em `tools/helpers/` são executados pelo Cowork como ferramentas.
- Os assets em `tools/assets/` são o contexto que o Cowork lê para tomar decisões.
- Os resultados são salvos como JSON e validados visualmente.
- **Foco:** refinar a lógica de diagnóstico, rubricas, regex patterns e formato de output.

#### Estágio B — Validação Funcional com Streamlit (Deploy Leve)

O Streamlit entra como interface de validação e primeiro produto entregável:

- **Input:** campo de URL + botão "Diagnosticar".
- **Pipeline:** execução sequencial dos helpers Python (Playwright headless).
- **Output:** tabela de avaliação com scores por módulo, detalhes dos achados, recomendações.
- **Deploy:** Streamlit Community Cloud (gratuito) ou Railway/Render.
- **Valor:** permite mostrar resultados para clientes enquanto o frontend definitivo é construído.

#### Estágio C — Produção com Next.js + Agent Tool Use

Conversão para aplicação de produção:

- Os helpers Python ganham uma camada **FastAPI** expondo endpoints (`/api/analyze`).
- O system prompt do Cowork vira o system prompt do `client.messages.create()` (SDK Anthropic).
- As ferramentas que o Cowork executava viram **tool definitions** no SDK.
- O loop de orquestração vira código Python explícito (agent tool use loop).
- O **Next.js** substitui o Streamlit como frontend (shadcn/ui + Recharts).
- O Streamlit é aposentado.

#### Artefatos de Validação por Estágio

| Estágio | Artefato | Formato | Localização | Status |
|---------|----------|---------|-------------|--------|
| A | Resultado de diagnóstico | JSON | `assets/examples/sample-diagnostic.json` | Criado |
| A | Tabela de avaliação | Markdown/terminal | Output do Cowork | A fazer |
| B | App Streamlit | Python (`app.py`) | `src/streamlit/` | A fazer |
| B | Tabela de scores por módulo | Streamlit `st.dataframe` | Renderizado no app | A fazer |
| C | Dashboard interativo | Next.js + Recharts | `src/app/` | Futuro |
| C | API do agente | FastAPI + SDK Anthropic | `src/api/` | Futuro |

#### Por que esta abordagem (e não direto para Next.js)

1. **Custo de iteração quase zero** no Estágio A — toda energia vai para a lógica de negócio.
2. **Validação real** no Estágio B — Streamlit é deployável e mostrável para clientes.
3. **Transição limpa** para o Estágio C — a separação WAT (Workflow/Agent/Tools) garante que os helpers, assets e system prompt migrem sem refatoração.
4. **Padrão replicável** — qualquer projeto WAT com agent tool use pode seguir a mesma receita: Cowork → Streamlit → Produção.

**Nota sobre a arquitetura WAT:** A separação entre Workflow, Agent e Tools é o que permite essa transição entre estágios. Os helpers (Tools) são os mesmos nos três estágios. O Agent muda de forma (Cowork → Streamlit sequencial → SDK tool use), mas o system prompt e o protocolo de avaliação permanecem. O Workflow (pipeline sequencial) é constante.

**Mapa detalhado de arquivos:** Consulte `docs/WAT-Stage-Transitions.md` para a lista completa de arquivos criados, modificados e aposentados em cada transição de estágio.

---

## 6. Dados e Armazenamento

| Campo | Valor |
|-------|-------|
| **Banco de dados** | SQLite (v0.1) → PostgreSQL (v1.0) |
| **Cache** | In-memory (resultados de interceptação durante análise) |
| **Persistência de resultados** | Sim, relatórios salvos por 30 dias |
| **Formato de saída** | JSON (API) → Dashboard (frontend) → PDF (exportação futura) |

---

## 7. Infraestrutura e Deploy

### 7.1 Stack de Infra

| Campo | Estágio A (Cowork) | Estágio B (Streamlit) | Estágio C (Produção) |
|-------|-------------------|----------------------|---------------------|
| **Backend** | Claude Cowork (agente direto) | Python + Playwright headless | FastAPI + SDK Anthropic |
| **Frontend** | Terminal / JSON output | Streamlit | Next.js 14 + shadcn/ui + Recharts |
| **Deploy** | Local | Streamlit Cloud / Railway | Vercel (Next.js) + Railway (FastAPI) |
| **CI/CD** | — | GitHub Actions | GitHub Actions |
| **Monitoramento** | Logs manuais | `st.status()` + logs | Sentry (v1.0) |
| **Variáveis de ambiente** | — | `ANTHROPIC_API_KEY` (se usar LLM no scoring) | `ANTHROPIC_API_KEY`, `DATABASE_URL` |

### 7.2 Scaffolding — Arquivos de Inicialização

Arquivos de configuração gerados na criação do projeto:

| Arquivo | Status | Observações |
|---------|--------|-------------|
| `.env.example` | Criado | Placeholders para `ANTHROPIC_API_KEY`, `DATABASE_URL` |
| `.gitignore` | Criado | Python + Node.js + secrets + DB |
| `requirements.txt` | Criado | Playwright, httpx, pydantic |
| `package.json` | Criado | Next.js base + Recharts + shadcn |
| `CLAUDE.md` | Criado | Contexto: 4 módulos, pipeline, convenções, referências WAT |
| `README.md` | Criado | Setup + run + documentação |

---

## 8. Riscos e Mitigações

| Risco | Impacto | Probabilidade | Mitigação |
|-------|---------|---------------|-----------|
| Site bloqueia crawler/bot | Alto | Média | User-Agent rotation, proxies residenciais, fallback Playwright |
| Cloudflare "Under Attack" mode | Alto | Baixa | Proxy residencial + fingerprint de browser real |
| Tags carregadas via lazy loading (não no networkidle) | Médio | Média | Aguardar 5-10s pós-load, scroll na página |
| DataLayer não populado sem interação do usuário | Médio | Alta | Simular clique em botão estratégico (add to cart) |
| SPA sem SSR (conteúdo renderizado via JS) | Médio | Média | Chrome headless com execução completa de JS |
| Site sem e-commerce (DataLayer simplificado) | Baixo | Alta | Adaptar rubrica de DataLayer para sites não-ecommerce |

---

## 9. Cronograma / Fases

| Fase | Estágio | Entregas | Estimativa |
|------|---------|----------|------------|
| **v0.1 — Pipeline Local** | A (Cowork) | Helpers Python funcionais + diagnóstico via Cowork + JSON de resultado validado | 1 semana |
| **v0.2 — Streamlit MVP** | B (Streamlit) | App Streamlit com input de URL, execução do pipeline, tabela de scores e recomendações | 1 semana |
| **v0.3 — Streamlit Completo** | B (Streamlit) | 4 módulos completos, SST detection, DataLayer validation, deploy no Streamlit Cloud | 1 semana |
| **v0.4 — Produção MVP** | C (Next.js) | FastAPI wrapping os helpers, Next.js consumindo a API, dashboard com shadcn/Recharts | 2 semanas |
| **v1.0 — Release** | C (Next.js) | Agent tool use loop, PostgreSQL, histórico de relatórios, autenticação, export PDF | 2 semanas |

---

## 10. Checklist de Kickoff

- [x] Objetivo e escopo definidos (Seção 1)
- [x] Pipeline de workflow desenhado (Seção 2)
- [x] Agente configurado com system prompt (Seção 3)
- [x] Protocolo de avaliação documentado (Seção 3.3)
- [x] Helpers inventariados com etapas mapeadas (Seção 4.1)
- [x] Assets documentados com formatos definidos (Seção 4.2)
- [ ] CONTEXT.md escritos para tools/, helpers/ e assets/ (Seção 4)
- [x] Stack de frontend definida (Seção 5)
- [x] Wireframes das telas desenhados (Seção 5.3)
- [x] Formatos de preview escolhidos (Seção 5.4)
- [x] Infraestrutura de deploy planejada (Seção 7.1)
- [x] Scaffolding criado (Seção 7.2)
- [x] Riscos mapeados (Seção 8)
- [x] Fases de entrega definidas (Seção 9)

**Documento de referência:** `Especificação Técnica: Agente de Diagnóstico de Mídias Pagas.docx` (Área de Trabalho)

**Status: BRIEF COMPLETO — AGUARDANDO CONTEXT.md E PREVIEWS**

---

*WAT Project Brief — Blind Analytics v0.1*
