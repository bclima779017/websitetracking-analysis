# tools/helpers/ — Código Executável

Módulos Python organizados por etapa do pipeline de diagnóstico de mensuração.

## Convenções

- Funções: snake_case com verbo (ex: `intercept_network_traffic`, `detect_sst_endpoints`)
- Docstrings: obrigatórias com Args, Returns, Raises
- Tipagem: type hints em parâmetros e retorno
- Erros: raise exceções tipadas, nunca retorne None silenciosamente
- `shared/` para utilitários comuns entre etapas (config, regex patterns, tipos)

## Subpastas por Etapa

```
helpers/
├── shared/         ← Utilitários comuns (config, tipos, constantes)
│   ├── config.py        Regex patterns, constantes, tipos de retorno
│   └── url_validator.py Valida DNS, acessibilidade, redirecionamentos (Etapa 1)
├── discover/       ← Etapa 1.5: Descoberta e Seleção de Páginas do Funil
│   ├── sitemap_parser.py      Fetch e parse de sitemap.xml (httpx, sem browser)
│   └── page_selector.py       Classifica URLs, spider BFS, seleciona amostra por stage
├── intercept/      ← Etapa 2: Interceptação de Rede
│   ├── network_interceptor.py   Escuta tráfego até networkidle
│   └── tag_identifier.py        Extrai IDs de tags por regex (GTM, GA4, Meta)
├── attribute/      ← Etapa 3: Simulação de Atribuição
│   └── attribution_tester.py    Testa UTMs, cookies, localStorage
├── detect/         ← Etapa 4: Detecção de SST
│   └── sst_detector.py          Busca subdomínios, endpoints CAPI, cookies HttpOnly
├── inspect/        ← Etapa 5: Avaliação de DataLayer
│   └── datalayer_inspector.py   Inspeciona window.dataLayer, valida schema GA4
└── report/         ← Etapa 6: Scoring & Relatório
    ├── scorer.py                Calcula scores 0-5 por módulo
    └── report_generator.py      Monta payload JSON + recomendações PT-BR
```

## Fluxo de Dependência

```
url_validator → page_selector (sitemap + spider) → network_interceptor → tag_identifier
                                    → attribution_tester
                                    → sst_detector
                                    → datalayer_inspector
                                                        → scorer → report_generator
```

## Consumidores dos Helpers (por Estágio)

Os helpers são escritos uma vez e consumidos de formas diferentes conforme o estágio de desenvolvimento:

| Estágio | Quem chama os helpers | Como |
|---------|----------------------|------|
| **A — Cowork** | Claude Cowork (agente) | Executa via bash/Python diretamente |
| **B — Streamlit** | `src/streamlit/app.py` | Importa como módulos Python (`from tools.helpers.intercept import ...`) |
| **C — Produção** | FastAPI + SDK Anthropic | Expostos como tool definitions no agent loop; chamados pela API |

**Princípio fundamental:** os helpers devem ser funções puras com input/output bem definido, sem dependência de framework específico. Isso garante que funcionem tanto quando chamados pelo Cowork, quanto importados pelo Streamlit, quanto wrappados pela FastAPI.
