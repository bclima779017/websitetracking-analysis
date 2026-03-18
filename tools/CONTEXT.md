# tools/ — Contexto para o Agente

Esta pasta contém **tudo que o agente precisa para executar o pipeline**: tanto o código executável quanto o material de referência que informa suas decisões.

## Estrutura

```
tools/
├── helpers/    ← CÓDIGO EXECUTÁVEL (funções, scripts, módulos)
└── assets/     ← CONTEÚDO DE REFERÊNCIA (protocolos, visuais, exemplos)
```

## Regra de Interpretação

| Pasta | O que contém | Como o agente deve usar |
|-------|-------------|------------------------|
| `helpers/` | Scripts Python, funções, módulos | **Executar** — chamar como tool no pipeline |
| `assets/` | Documentos, imagens, dados de referência | **Consultar** — ler para informar decisões, nunca executar |

## Importante

- Arquivos em `helpers/` são **código**: devem ser importados, chamados, testados.
- Arquivos em `assets/` são **conhecimento**: devem ser lidos, interpretados, usados como contexto.
- O agente **nunca deve executar** arquivos de `assets/` como código.
- O agente **nunca deve modificar** arquivos de `assets/` durante execução do pipeline — são fontes de verdade.

Consulte `helpers/CONTEXT.md` e `assets/CONTEXT.md` para instruções específicas de cada pasta.
