# Blind Analytics

> Diagnóstico de maturidade de mensuração de Mídias Pagas via crawling e scraping client-side.

## Setup

```bash
# Configurar variáveis de ambiente
cp .env.example .env
# Edite .env com seus valores reais

# Python (pipeline)
pip install -r requirements.txt

# Node.js (frontend)
npm install
```

## Rodar

```bash
# Frontend (Next.js)
npm run dev

# Pipeline (Python)
python -m tools.helpers.[modulo]
```

## Stack

- **Frontend:** Next.js 14 + Tailwind CSS + shadcn/ui + Recharts
- **Backend:** Next.js API Routes + Python (tools do pipeline)
- **Agente:** Claude Sonnet 4.6 (análise) / Haiku 4.5 (detecção)
- **Browser:** Chrome Extension (MCP) + Playwright (fallback)

## Documentação

- `CLAUDE.md` — Contexto para Claude Code
- `docs/WAT-Brief.md` — Briefing completo do projeto
- `docs/protocol/` — Protocolo e rubricas de avaliação

## Referência

Consulte `../_global/docs/WAT-Architecture-Guide.md` para referência conceitual.
