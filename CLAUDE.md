# Blind Analytics — Diagnóstico de Mensuração de Mídias Pagas

## Contexto
Diagnostica a maturidade da operação de Mídias Pagas de qualquer domínio web, analisando tags de tracking, atribuição, server-side tracking e profundidade do DataLayer via crawling/scraping client-side. Apresenta resultados em dashboard profissional para clientes não-técnicos em PT-BR.

## Arquitetura
Este projeto segue a arquitetura WAT (Workflow, Agent, Tools). Consulte:
- `docs/WAT-Brief.md` — briefing completo do projeto
- `docs/WAT-Stage-Transitions.md` — mapa de mudanças de arquivos entre estágios A/B/C
- `tools/CONTEXT.md` — manifest da pasta de ferramentas
- `tools/helpers/CONTEXT.md` — convenções dos helpers
- `tools/assets/CONTEXT.md` — guia dos assets de referência

## Pipeline (6 etapas)
1. Validação de URL — DNS, acessibilidade, redirecionamentos
2. Interceptação de Rede — tags GTM/GA4/Meta/LinkedIn via regex
3. Simulação de Atribuição — UTMs, cookies (_gcl_aw, _fbc), localStorage
4. Detecção SST — subdomínios first-party, sGTM, CAPI, cookies HttpOnly
5. Avaliação DataLayer — window.dataLayer, schema GA4 e-commerce
6. Scoring & Relatório — notas 0-5 por módulo, comentários PT-BR, recomendações

## 4 Módulos de Avaliação
1. **Tracking Infrastructure** — presença e saúde de tags (GTM, GA4, Meta, LinkedIn)
2. **Attribution Health** — persistência de UTMs, cookies de click ID, redirect strip
3. **Server-Side Tracking** — sGTM, Meta CAPI, cookies HttpOnly, ITP bypass
4. **DataLayer Depth** — eventos de funil, schema GA4, compliance e-commerce

## Convenções
- Helpers: snake_case, docstrings obrigatórias, tipagem de retorno
- Assets: somente leitura, nunca modificados por código
- Commits: tipo(escopo): descrição — ex: feat(interceptor): add meta pixel detection
- Idioma do código: inglês. Idioma da UI: PT-BR.

## Estratégia de Desenvolvimento (3 Estágios)
O projeto segue uma abordagem incremental onde a inteligência do agente é prototipada antes de ser codificada:
- **Estágio A (atual):** Claude Cowork como agente + helpers Python + validação local
- **Estágio B:** Streamlit como interface funcional + deploy leve (Streamlit Cloud)
- **Estágio C:** Next.js 14 + FastAPI + SDK Anthropic (agent tool use) em produção

## Stack por Estágio
- **Estágio A:** Python + Playwright + Chrome Extension (MCP) — execução local via Cowork
- **Estágio B:** Streamlit + Python + Playwright headless — deploy no Streamlit Cloud / Railway
- **Estágio C:** Next.js 14 (App Router + Tailwind + shadcn/ui + Recharts) + FastAPI + SDK Anthropic
- Agent: Claude Sonnet 4.6 (análise) / Claude Haiku 4.5 (detecção)
- DB: SQLite (v0) → PostgreSQL (v1)

## Documento de Referência
`Especificação Técnica: Agente de Diagnóstico de Mídias Pagas.docx` na Área de Trabalho contém o protocolo completo com regex patterns, rubricas de scoring e estrutura de output JSON.

## Referência Global
Para padrões e conceitos WAT, consulte:
- `../_global/docs/WAT-Architecture-Guide.md`
