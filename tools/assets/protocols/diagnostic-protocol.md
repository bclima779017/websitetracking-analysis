# Protocolo de Diagnóstico — Blind Analytics

## Visão Geral
Este protocolo define o padrão de diagnóstico de maturidade em Mídias Pagas, avaliando 4 módulos independentes em escala 0-5. Cada módulo é executado sequencialmente durante o crawling do domínio.

---

## Módulo 1: Tracking Infrastructure
**Objetivo:** Verificar presença, integridade e funcionamento das tags de tracking client-side (GTM, GA4, Meta Pixel, LinkedIn).

### O que é Avaliado
- Detecção de scripts de tracking via análise de Network Requests (DOM)
- Status HTTP das requisições (200, 404, 500)
- Presença de duplicatas de tags
- Configuração correta de IDs de propriedade (GTM-*, G-*, Pixel ID)

### Coleta de Dados
- **GTM:** URL do gtm.js, Container ID (GTM-*), status HTTP, presença de dataLayer
- **GA4:** URL do g/collect, Measurement ID (G-*), status HTTP, eventos disparados
- **Meta Pixel:** URL fbevents.js, Pixel ID, status HTTP, eventos de conversão
- **LinkedIn:** URL snap.licdn.com, Partner ID, status HTTP

### Critérios de Aprovação
- ✅ Todas as tags presentes e com status HTTP 200
- ✅ Sem duplicatas de tags
- ✅ IDs válidos detectados (formato esperado)
- ✅ Tags disparando eventos corretamente

### Critérios de Falha
- ❌ Tags com status HTTP 404 ou 500
- ❌ Duplicatas de mesma tag (2x GTM, 2x GA4, etc.)
- ❌ Tags carregando mas sem eventos disparados
- ❌ IDs malformados ou ausentes

### Escala de Scoring (0-5)

**Nota 0:** Nenhuma tag detectada
- Sem GTM, sem GA4, sem Meta Pixel
- Sem LinkedIn Insight Tag
- Sem qualquer evidência de tracking

**Nota 1-2:** Tags duplicadas ou com erros HTTP
- Tags presentes mas com status 404 ou 500
- Duplicatas de mesma tag (2x GTM, 2x GA4)
- Tags carregam mas sem eventos disparados
- Um ou mais IDs malformados

**Nota 3:** GA4 ou Meta Pixel instalado, mas não ambos
- GA4 presente (HTTP 200) OU Meta Pixel presente (HTTP 200)
- Não ambos simultaneamente
- GTM opcional neste nível

**Nota 4:** GTM + GA4 + Meta Pixel disparando corretamente
- GTM detectado com Container ID válido (HTTP 200)
- GA4 detectado com Measurement ID válido (HTTP 200)
- Meta Pixel detectado com ID válido (HTTP 200)
- Todos os eventos disparando (sem 404/500)

**Nota 5:** Tudo OK + Meta Advanced Matching detectado
- Atende critérios da Nota 4
- Meta Advanced Matching ativo (dados em hash detectados)
- Possível: LinkedIn Insight Tag também presente
- Estrutura otimizada para SST

---

## Módulo 2: Attribution Health
**Objetivo:** Verificar persistência de UTMs, geração de cookies de click ID e preservação de parâmetros após navegação.

### O que é Avaliado
- Presença de parâmetros UTM na URL (utm_source, utm_medium, utm_campaign)
- Geração e persistência de cookies de Google (_gclid, _gcl_au)
- Geração e persistência de cookies Meta (_fbc, _fbp)
- Limpeza de query string após navegação
- Armazenamento em localStorage (cross-session)

### Coleta de Dados
- **URL Inicial:** utm_source, utm_medium, utm_campaign, utm_content, utm_term
- **Cookies HTTP-only:** _gclid, _gcl_au, _fbp, _fbc, observação de Path e MaxAge
- **localStorage:** Busca por valores de UTM ou GCLID persistidos
- **Behavior:** Se parâmetros são mantidos ou removidos após navegação interna

### Critérios de Aprovação
- ✅ UTMs presente na URL inicial
- ✅ Cookies de click ID (_gclid, _fbc) gerados com TTL > 90 dias
- ✅ Parâmetros preservados em navegação interna
- ✅ localStorage utilizado para persistência cross-session

### Critérios de Falha
- ❌ Site redireciona com redirect stripping (limpa UTM)
- ❌ Sem geração de cookies de click ID
- ❌ Cookies com TTL baixo (< 1 dia)
- ❌ Sem mecanismo de persistência (localStorage)

### Escala de Scoring (0-5)

**Nota 0:** Site redireciona e limpa query string + não gera cookies
- Redirecionamento imediato remove UTMs
- Sem cookies detectados após redirect
- Sem localStorage para persistência

**Nota 1-2:** Mantém UTM na URL mas cookies de click_id não são gerados
- UTMs visíveis na URL
- Google cookies (_gclid, _gcl_au) ausentes
- Meta cookies (_fbc, _fbp) ausentes ou malformados

**Nota 3:** Sem redirects e gera cookies básicos do Google e Meta
- URL sem redirect stripping (UTMs mantidos)
- _gclid ou _gcl_au gerado com status OK
- _fbc ou _fbp gerado com status OK
- Sem localStorage ou com dados insuficientes

**Nota 4:** Gera cookies e preserva parâmetros após navegação interna
- Cookies persistem após cliques internos (Page 1 → Page 2)
- UTMs ainda visíveis ou em query string preservada
- localStorage vazio ou não utilizado

**Nota 5:** Gera cookies + salva UTM/GCLID no localStorage (cross-session)
- Atende critérios da Nota 4
- localStorage contém utm_source, utm_medium, utm_campaign OU GCLID value
- Cookies com TTL ≥ 90 dias
- Persistência cross-session verificada

---

## Módulo 3: Server-Side Tracking
**Objetivo:** Verificar presença e integridade de infraestrutura server-side (sGTM, Meta CAPI, cookies HttpOnly, bypass ITP).

### O que é Avaliado
- Detecção de subdomínios dedicados a tracking (sgtm.*, data.*, tag.*, collect.*)
- Presença de servidor GTM em primeiro party (sGTM)
- Meta Conversions API (CAPI) enviando dados para endpoint first-party
- Cookies HttpOnly (não acessíveis via JavaScript)
- Mecanismos de bypass ITP (Intelligent Tracking Prevention)

### Coleta de Dados
- **DNS Lookup:** Subdomínios tracking.*, data.*, tag.*, sgtm.*
- **Network Analysis:** Requisições internas (same-domain) vs. cross-domain
- **Cookies HTTP-only:** Verificação de flag HttpOnly em Set-Cookie headers
- **CAPI Endpoint:** URL pattern /capi/, /conversion/, /webhook/
- **CORS Headers:** Verificação de Origin policy

### Critérios de Aprovação
- ✅ Subdomínio first-party para tracking detectado
- ✅ sGTM operacional (gtm.js carregando from first-party)
- ✅ CAPI enviando dados para endpoint próprio
- ✅ Cookies com flag HttpOnly presentes

### Critérios de Falha
- ❌ Sem subdomínio dedicado para tracking
- ❌ Subdomínio com erro CORS ou SSL
- ❌ sGTM desativado ou sem eventos
- ❌ CAPI enviando para domínio externo (Meta)

### Escala de Scoring (0-5)

**Nota 0:** Nenhum indício de SST (apenas client-side)
- Sem subdomínios de tracking detectados
- Todas as requisições para googletagmanager.com, facebook.com, etc. (cross-domain)
- Sem cookies HttpOnly
- Sem evidência de CAPI

**Nota 1-2:** Subdomínio para tracking encontrado mas com erros CORS ou SSL
- Subdomínio detectado (sgtm.*, data.*, tag.*, etc.)
- Erro CORS (blocked by CORS policy)
- Erro SSL/TLS (certificate validation failed)
- Requisições falhando com status 403 ou 495

**Nota 3:** sGTM carregando gtm.js do próprio domínio
- Subdomínio first-party funcional (HTTP 200)
- Arquivo gtm.js carregado de first-party
- Cookies recebidos de primeiro party
- Sem CAPI integrada ou CAPI com erro

**Nota 4:** sGTM ativo + Meta Pixel enviando para endpoint first-party
- Atende critérios da Nota 3
- Meta Pixel redirecionado para /capi/ ou similar (first-party)
- Google Conversions enviadas para first-party
- Cookies HttpOnly detectados

**Nota 5:** sGTM/CAPI 100% isolada gerando cookies HttpOnly com ITP bypass
- Atende critérios da Nota 4
- Cookies com flag HttpOnly presentes em 100% das respostas
- Mecanismo de first-party cookie (FPC) implementado
- Subdomínio com subdomain cookie (SameSite=None; Secure)
- CAPI operacional sem dependência de cross-domain

---

## Módulo 4: DataLayer Depth
**Objetivo:** Verificar presença, profundidade e conformidade de window.dataLayer com taxonomia GA4.

### O que é Avaliado
- Existência de window.dataLayer
- Presença de eventos de funil (view_item, add_to_cart, purchase)
- Estrutura de objetos (flat vs. aninhado)
- Conformidade com schema GA4 e-commerce
- Presença de array `items[]` com propriedades obrigatórias

### Coleta de Dados
- **Estrutura:** `window.dataLayer` tipo Array, eventos com propriedade `event`
- **Eventos:** Nome do evento, timestamp, propriedades contextuais
- **Items Array:** Presença de `items[]`, verificação de item_id, price, quantity
- **Taxonomia:** Validação contra lista oficial GA4 (view_item_list, add_to_cart, etc.)
- **Compliance:** Presença de `currency`, `value`, campos obrigatórios

### Critérios de Aprovação
- ✅ window.dataLayer existe e contém eventos válidos
- ✅ Eventos nomeados segundo GA4 (view_item, add_to_cart, etc.)
- ✅ Items array com item_id, price, quantity presentes
- ✅ Currency e value informados
- ✅ Sem valores nulos ou undefined obrigatórios

### Critérios de Falha
- ❌ window.dataLayer ausente
- ❌ Eventos com nomes genéricos ou customizados
- ❌ Items array vazio ou estrutura malformada
- ❌ Propriedades obrigatórias ausentes (item_id, price)

### Escala de Scoring (0-5)

**Nota 0:** window.dataLayer inexistente
- Variável window.dataLayer não declarada
- Sem eventos em nenhuma etapa do funil
- Sem possibilidade de análise

**Nota 1:** dataLayer existe mas sem eventos úteis
- window.dataLayer declarada mas vazia (Array vazio [])
- Eventos presentes mas com nomes genéricos (event: "page_view_generic")
- Sem dados contextuais (sem value, currency, items)

**Nota 2:** Eventos de clique com nomes genéricos
- Eventos disparados em cliques de botão/link
- Nomes não conformes (ex: "click", "user_action" em vez de GA4)
- Sem estrutura de items
- Sem valor monetário

**Nota 3:** Eventos de funil corretos mas estrutura plana
- Eventos de funil presentes (view_item, add_to_cart, begin_checkout)
- Nomes conformes com GA4
- Estrutura plana (sem items array ou items com um objeto, não array)
- Currency e value presentes mas sem detalhe por produto

**Nota 4:** Eventos respeitando taxonomia GA4 (schema ecommerce presente)
- Todos eventos nomeados segundo GA4 (view_item_list, view_item, add_to_cart, etc.)
- Items array presente com múltiplos itens
- item_id, item_name, price, quantity presentes
- Currency e value calculados corretamente
- Possível: campos recomendados ausentes (item_brand, item_category)

**Nota 5:** Schema 100% compatível com GA4 e-commerce
- Atende critérios da Nota 4
- Items array com **todos** campos obrigatórios e recomendados
  - Obrigatórios: item_id, item_name, price, quantity
  - Recomendados: item_brand, item_category, item_category2, item_variant
- Coupon/discount aplicáveis e corretos
- Index (posição do item em list) presente
- Sem valores nulos, todos string/number válidos
- Compliance 100% verificado

---

## Fluxo de Execução

1. **Coleta Inicial:** URL validada, navegador inicia crawling
2. **Interceptação (Módulo 1):** Network requests analisadas, tags detectadas
3. **Simulação de Atribuição (Módulo 2):** Cookies e localStorage lidos
4. **Detecção SST (Módulo 3):** DNS lookup, CORS headers, cookies HttpOnly
5. **Avaliação DataLayer (Módulo 4):** window.dataLayer inspecionado
6. **Scoring:** Cada módulo recebe nota 0-5, comentários em PT-BR

---

## Notas Importantes

- **Módulos Independentes:** Falha em um módulo não prejudica outro
- **Scoring Incremental:** Nota 5 requer cumprimento de Nota 4 (não é baseado em um critério único)
- **Evidência Coletada:** Todas as observações são documentadas no relatório final
- **Contexto do Negócio:** O agente pode fornecer recomendações além da nota

