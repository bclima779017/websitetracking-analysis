# assets/ — Conteúdo de Referência para o Agente

## O que é esta pasta

Contém **material de referência que o agente consulta para tomar decisões**, mas que **nunca é executado como código**. São fontes de verdade que informam o comportamento do agente durante o pipeline.

## Estrutura

```
assets/
├── protocols/           ← Protocolos e rubricas de avaliação
│   ├── diagnostic-protocol.md     Protocolo completo dos 4 módulos
│   ├── scoring-rubrics.md         Rubricas: o que é nota 0 a 5 para cada módulo
│   ├── ga4-events-taxonomy.json   Dicionário de eventos GA4 e-commerce (Anexo A)
│   └── regex-patterns.json        Patterns para identificação de tags
├── visual/              ← Referências visuais para UI (por estágio)
│   ├── streamlit/                 Referências para o app Streamlit (Estágio B)
│   └── dashboard/                 Referências para o dashboard Next.js (Estágio C)
└── examples/            ← Exemplos de input/output esperados
    └── sample-diagnostic.json     Exemplo do payload final (contrato de dados)
```

## Como o Agente deve usar cada subpasta

### protocols/
**Finalidade:** Define O QUE o agente avalia e COMO atribui notas.

**Instrução ao agente:** Antes de iniciar scoring (Etapa 6), SEMPRE leia `diagnostic-protocol.md` e `scoring-rubrics.md`. Use `ga4-events-taxonomy.json` para validar compliance de DataLayer. Use `regex-patterns.json` para identificação de tags. Estes arquivos são a fonte de verdade.

### visual/
**Finalidade:** Define COMO as interfaces devem se parecer em cada estágio de desenvolvimento.

**Organização por estágio:**
- `visual/streamlit/` — Referências para a interface Streamlit (Estágio B): layout da tabela de scores, formato das recomendações, estrutura da página de resultados. Interface funcional, não estética.
- `visual/dashboard/` — Referências para o dashboard Next.js (Estágio C): mockups dos cards de módulo, gráfico radar, paleta de cores, componentes shadcn/ui. Interface profissional para cliente final.

**Instrução ao agente:** Ao gerar componentes de UI, consulte a subpasta correspondente ao estágio atual. Lembre-se que o usuário final é não-técnico — a linguagem visual deve ser didática e acessível em ambos os estágios.

### examples/
**Finalidade:** Exemplos concretos do formato de saída esperado.

**Instrução ao agente:** Use `sample-diagnostic.json` como template de formato (contrato de dados entre pipeline e interface), não de conteúdo. Este JSON é consumido tanto pelo Streamlit (Estágio B) quanto pelo Next.js (Estágio C) — a estrutura deve ser estável entre estágios. Produza saídas com mesma estrutura mas dados reais do site analisado.

## Regras Gerais

1. **Somente leitura** — o agente NUNCA modifica arquivos em `assets/` durante execução
2. **Fonte de verdade** — em caso de conflito entre o system prompt e um arquivo em `assets/`, o arquivo prevalece
3. **Versionamento** — alterações em `assets/` devem ser commitadas com mensagem descritiva
4. **Novos arquivos** — qualquer novo asset deve ter formato documentado neste CONTEXT.md
5. **Estabilidade do contrato de dados** — o formato de `sample-diagnostic.json` deve ser respeitado em todos os estágios para garantir transição limpa entre Streamlit e Next.js
