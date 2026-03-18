# Rubricas de Scoring Detalhadas — Blind Analytics

## Módulo 1: Tracking Infrastructure

### Nota 0 — Nenhuma Tag Detectada

**Evidência Procurada:**
- Ausência de `googletagmanager.com/gtm.js` em Network Requests
- Ausência de `google-analytics.com/g/collect` ou `/gtag.js`
- Ausência de `connect.facebook.net/fbevents.js` ou `facebook.com/tr/`
- Ausência de `snap.licdn.com` (LinkedIn)
- Sem event listeners de GTM no DOM

**Scoring Breakdown:**
```
Base: 0
  ❌ GTM detectado: NÃO
  ❌ GA4 detectado: NÃO
  ❌ Meta Pixel detectado: NÃO
  ❌ LinkedIn detectado: NÃO
─────────────
Total: 0 (sem tracking)
```

**Ação Recomendada:** Implementar pelo menos Google Analytics 4 e Meta Pixel.

---

### Nota 1-2 — Tags Duplicadas ou com Erros HTTP

**Evidência Procurada:**
- 2+ instâncias de GTM com mesmo Container ID
- 2+ instâncias de GA4 com mesmo Measurement ID
- Tags carregando com status HTTP 404 (Not Found) ou 500 (Server Error)
- Tags presentes mas sem eventos disparados (Network Requests vazias)
- IDs malformados (ex: `GTM-` sem caracteres, `G-` incompleto)

**Scoring Breakdown (exemplo 1: duplicata + erro HTTP):**
```
Base: 0
  ✅ GTM detectado: SIM (mas 2x instâncias)
  ⚠️  GTM status: 200 OK + 404 NOT FOUND
  ✅ GA4 detectado: SIM
  ❌ GA4 disparando eventos: NÃO (sem requisições de coleta)
  ⚠️  Meta Pixel detectado: SIM (com status 500)
─────────────
Observações:
  • Duplicata GTM: Script carregado 2x do mesmo Container (ID: GTM-ABC123)
  • GA4 sem eventos: Measurement ID G-XYZ789 presente mas sem /g/collect
  • Meta erro: Pixel ID 123456 retornando 500 (Server Error)

+1 por GA4 presente (apesar de sem eventos)
+1 por Meta Pixel presente (apesar do erro 500)
─────────────
Total: 2 (tags presentes mas com problemas críticos)
```

**Scoring Breakdown (exemplo 2: erro HTTP isolado):**
```
Base: 0
  ✅ GTM detectado: SIM
  ✅ GTM status: 200 OK, eventos disparando
  ✅ GA4 detectado: SIM
  ✅ GA4 status: 200 OK, eventos disparando
  ❌ Meta Pixel status: 404 NOT FOUND
─────────────
+1 por GTM OK
+1 por GA4 OK (ambos disparando)
+1 por Meta Pixel detectado (apesar de erro 404)
─────────────
Total: 2 (problema isolado em Meta)
```

**Ação Recomendada:** Remover duplicatas, investigar errors HTTP 404/500, verificar IDs de propriedade.

---

### Nota 3 — GA4 ou Meta Pixel Instalado (não ambos)

**Evidência Procurada:**
- GA4 presente (Measurement ID válido, HTTP 200, eventos disparando) **E**
- Meta Pixel **ausente** (sem fbevents.js, sem facebook.com/tr/)

**OU**

- Meta Pixel presente (Pixel ID válido, HTTP 200, eventos disparando) **E**
- GA4 **ausente** (sem google-analytics.com, sem gtag.js)

GTM é opcional neste nível.

**Scoring Breakdown (exemplo: GA4 SIM, Meta NÃO):**
```
Base: 0
  ✅ GTM detectado: SIM (Container: GTM-ABC123)
  ✅ GTM status: 200 OK, eventos OK
  ✅ GA4 detectado: SIM (Measurement: G-XYZ789)
  ✅ GA4 status: 200 OK, eventos disparando corretamente
  ❌ Meta Pixel detectado: NÃO
─────────────
+1 por GTM presente
+2 por GA4 presente e operacional (inclui dataLayer)
─────────────
Total: 3 (uma plataforma de tracking funcional)
```

**Scoring Breakdown (exemplo: Meta SIM, GA4 NÃO):**
```
Base: 0
  ❌ GTM detectado: NÃO
  ❌ GA4 detectado: NÃO
  ✅ Meta Pixel detectado: SIM (Pixel ID: 123456789)
  ✅ Meta status: 200 OK, eventos disparando
─────────────
+3 por Meta Pixel presente e operacional
─────────────
Total: 3 (somente Meta, sem Google Analytics)
```

**Ação Recomendada:** Implementar a plataforma complementar (Meta ou GA4).

---

### Nota 4 — GTM + GA4 + Meta Disparando Corretamente

**Evidência Procurada:**
- GTM detectado com Container ID válido (GTM-XXXXXXXXX), HTTP 200, dataLayer inicializado
- GA4 detectado com Measurement ID válido (G-XXXXXXXXXX), HTTP 200, eventos disparando
- Meta Pixel detectado com Pixel ID válido, HTTP 200, eventos disparando
- **Nenhum** dos três retornando 404/500
- Sem duplicatas

**Scoring Breakdown:**
```
Base: 0
  ✅ GTM detectado: SIM
  ✅ GTM Container ID: GTM-ABC123XYZ (válido)
  ✅ GTM status: 200 OK, dataLayer inicializado
  ✅ GA4 detectado: SIM
  ✅ GA4 Measurement ID: G-XYZ789ABC (válido)
  ✅ GA4 status: 200 OK, eventos disparando
  ✅ Meta Pixel detectado: SIM
  ✅ Meta Pixel ID: 123456789 (válido)
  ✅ Meta status: 200 OK, eventos disparando
─────────────
+1 por GTM OK
+1 por GA4 OK
+1 por Meta OK
+1 por todos os 3 operacionais sem conflito
─────────────
Total: 4 (tracking infrastructure sólida)
```

**Ação Recomendada:** Considerar implementação de Server-Side Tracking (sGTM) e Meta CAPI para robustez.

---

### Nota 5 — Tudo OK + Meta Advanced Matching Detectado

**Evidência Procurada:**
- Atende **todos** critérios da Nota 4 (GTM + GA4 + Meta, todos HTTP 200)
- Meta Advanced Matching detectado (dados em hash sha256 ou hashed_email, hashed_phone, etc.)
- Possível: LinkedIn Insight Tag também presente (HTTP 200)
- Estrutura otimizada para Server-Side Tracking

**Scoring Breakdown:**
```
Base: 0
  ✅ GTM detectado: SIM (Container: GTM-ABC123XYZ)
  ✅ GTM status: 200 OK, dataLayer com eventos customizados
  ✅ GA4 detectado: SIM (Measurement: G-XYZ789ABC)
  ✅ GA4 status: 200 OK, eventos disparando
  ✅ Meta Pixel detectado: SIM (ID: 123456789)
  ✅ Meta status: 200 OK, eventos disparando
  ✅ Meta Advanced Matching: DETECTADO
    • hashed_email presente em eventos
    • hashed_phone presente em eventos
    • dados em sha256 válido
  ✅ LinkedIn Insight Tag: SIM (status 200 OK)
─────────────
+1 por GTM OK
+1 por GA4 OK
+1 por Meta OK
+1 por Advanced Matching
+1 por LinkedIn + estrutura robusta
─────────────
Total: 5 (tracking avançado, pronto para SST)
```

**Ação Recomendada:** Implementar sGTM para ofuscação de dados e bypass ITP.

---

## Módulo 2: Attribution Health

### Nota 0 — Redirecionamento + Limpeza de Query String + Sem Cookies

**Evidência Procurada:**
- URL inicial contém UTM (ex: `example.com?utm_source=google`)
- Após redirecionamento (302, 301), URL resultante sem UTM (`example.com/`)
- LocalStorage vazio (sem utm_source, utm_medium, etc.)
- Sem cookies observados (_gclid, _gcl_au, _fbp, _fbc)

**Scoring Breakdown:**
```
Base: 0
  ✅ UTM presente na URL inicial: SIM
    • utm_source: google
    • utm_medium: cpc
    • utm_campaign: q1_2026
  ⚠️  Redirecionamento detectado: SIM
    • 302 Found → https://example.com/
    • Query string removida
  ❌ UTM na URL final: NÃO
  ❌ Cookies Google: NÃO DETECTADO
  ❌ Cookies Meta: NÃO DETECTADO
  ❌ localStorage com UTM: NÃO
─────────────
Observação: Redirect stripping destrói toda attributição
─────────────
Total: 0 (attribution flow quebrado)
```

**Ação Recomendada:** Remover redirect stripping, implementar persistência de UTM via localStorage ou Server-Side Tracking.

---

### Nota 1-2 — Mantém UTM mas Sem Cookies de Click ID

**Evidência Procurada:**
- URL contém utm_source, utm_medium, utm_campaign (visíveis)
- Sem redirecionamento (ou redirect preserva UTM)
- Google cookies (_gclid, _gcl_au) ausentes OU presentes mas vazios
- Meta cookies (_fbc, _fbp) ausentes OU presentes mas vazios
- localStorage vazio ou apenas com dados genéricos

**Scoring Breakdown (exemplo: UTM visível, sem cookies):**
```
Base: 0
  ✅ UTM presente na URL: SIM
    • utm_source: facebook
    • utm_medium: social
    • utm_campaign: summer_sale
  ✅ Redirecionamento: NÃO (URL mantida)
  ❌ Cookies Google (_gclid): NÃO DETECTADO
  ❌ Cookies Google (_gcl_au): NÃO DETECTADO
  ❌ Cookies Meta (_fbc): NÃO DETECTADO
  ❌ Cookies Meta (_fbp): NÃO DETECTADO
  ❌ localStorage com click IDs: NÃO
─────────────
Observação: UTM dados mas sem click ID tracking
─────────────
Total: 1 (parcial)
```

**Scoring Breakdown (exemplo: alguns cookies malformados):**
```
Base: 0
  ✅ UTM presente: SIM
  ✅ Sem redirect: SIM
  ⚠️  Cookies Google: DETECTADO mas vazio
    • Cookie: _gclid="" (empty string)
    • Cookie: _gcl_au="" (empty string)
  ⚠️  Cookies Meta: DETECTADO mas incompleto
    • Cookie: _fbp="fb.1.123456789.unknown" (sem fbc_id)
  ❌ localStorage: Vazio
─────────────
Observação: Cookies presentes mas sem valor útil
─────────────
Total: 2 (cookies framework presente, dados ausentes)
```

**Ação Recomendada:** Verificar Tags GTM para conversão de click_id (gclid via UTM, fbclid para Meta), implementar localStorage como fallback.

---

### Nota 3 — Sem Redirects + Cookies Google e Meta

**Evidência Procurada:**
- URL sem redirecionamento (HTTP 200, não 301/302)
- UTM presente na URL
- Cookie _gclid OU _gcl_au gerado com valor válido (não vazio, TTL ≥ 1 dia)
- Cookie _fbc OU _fbp gerado com valor válido (fbclid visible ou _fbp preenchido)
- localStorage vazio OU não utilizado ainda

**Scoring Breakdown:**
```
Base: 0
  ✅ URL sem redirecionamento: SIM (HTTP 200)
  ✅ UTM presente: SIM
    • utm_source: google_ads
    • utm_medium: cpc
  ✅ Cookie _gclid: DETECTADO
    • Valor: gclid=CjwKCAjw5pSwBRA1EiwAXQ-zxQ... (válido)
    • MaxAge: 8640000 (100 dias)
    • Path: / (global)
  ✅ Cookie _fbp: DETECTADO
    • Valor: fb.1.1609459200.123456789 (válido)
    • MaxAge: 7776000 (90 dias)
  ❌ localStorage com UTM: NÃO VERIFICADO
─────────────
Observação: Cookies básicos funcionando, sem persistência cross-session
─────────────
Total: 3 (attribution inicial OK)
```

**Ação Recomendada:** Implementar localStorage para persistência cross-session de utm_source, utm_medium.

---

### Nota 4 — Cookies + Preservação de Parâmetros Após Navegação Interna

**Evidência Procurada:**
- Cookies gerados conforme Nota 3 (Google + Meta)
- **Simulação de navegação:** clique em link interno, carregar página 2
- Cookies persist na página 2 com mesmo valor e TTL renovado
- UTM ainda visível OU em query string preservada

**Scoring Breakdown:**
```
Base: 0
  ✅ Cookies gerados na Página 1: SIM
    • _gclid: CjwKCAjw5pSwBRA1E... (válido, MaxAge: 8640000)
    • _fbp: fb.1.1609459200.123456789 (válido, MaxAge: 7776000)
  ✅ Navegação interna (clique interno): SIM
    • Página 1: /products/item-123?utm_source=google
    • Página 2: /products/item-123/reviews
  ✅ Cookies na Página 2: SIM
    • _gclid: PERSISTIDO (mesmo valor, TTL renovado)
    • _fbp: PERSISTIDO (mesmo valor, TTL renovado)
  ✅ UTM na navegação interna: SIMULADO (query string não mais visível)
  ❌ localStorage com backup: NÃO
─────────────
Observação: Cookies persistem mas sem fallback localStorage
─────────────
Total: 4 (attribution robusta em session atual)
```

**Ação Recomendada:** Implementar localStorage para persistência multi-session (caso cookies sejam limpos).

---

### Nota 5 — Cookies + localStorage (Cross-Session)

**Evidência Procurada:**
- Atende critérios da Nota 4 (cookies persiste em navegação)
- localStorage contém utm_source, utm_medium, utm_campaign **OU** gclid value
- localStorage TTL ou verificação de date stored
- Possível: dados criptografados em localStorage

**Scoring Breakdown:**
```
Base: 0
  ✅ Cookies persistem em navegação interna: SIM (Nota 4 atendida)
  ✅ localStorage implementado: SIM
    • localStorage.utm_source: "google_ads" (string)
    • localStorage.utm_medium: "cpc"
    • localStorage.utm_campaign: "q1_2026"
    • localStorage.stored_at: "2026-03-17T14:32:00Z"
  ✅ GCLID persistido no localStorage: SIM
    • localStorage.gclid: "CjwKCAjw5pSwBRA1E..." (válido)
    • localStorage.gclid_timestamp: "2026-03-17T14:32:00Z"
  ✅ Cookies com TTL longo: SIM
    • _gclid: 8640000 seg (100 dias)
    • _fbp: 7776000 seg (90 dias)
  ✅ Cross-session verificação: SIM (fecha e abre browser, localStorage persiste)
─────────────
Observação: Attribution robusta mesmo após limpeza de cookies
─────────────
Total: 5 (attribution avançada, cross-session segura)
```

**Ação Recomendada:** Considerar Server-Side Tracking para armazenamento server-side de click IDs.

---

## Módulo 3: Server-Side Tracking

### Nota 0 — Nenhum Indício de SST (Apenas Client-Side)

**Evidência Procurada:**
- Todas as requisições de tracking vão para domínios externos (googletagmanager.com, facebook.com, etc.)
- Sem subdomínios de tracking (sem sgtm.*, data.*, tag.*, collect.*)
- Sem cookies HttpOnly
- Sem requisições internas de tracking

**Scoring Breakdown:**
```
Base: 0
  ❌ Subdomínio sGTM detectado: NÃO
  ❌ Subdomínio data.* detectado: NÃO
  ❌ Subdomínio tag.* detectado: NÃO
  ❌ Subdomínio collect.* detectado: NÃO
  ❌ Cookies HttpOnly: NÃO DETECTADO
  ❌ CAPI endpoint (first-party): NÃO
  ✅ GTM client-side: SIM (googletagmanager.com)
  ✅ Meta Pixel client-side: SIM (facebook.com/tr/)
───────────────
Observação: 100% client-side, sem infrastructure SST
─────────────
Total: 0 (sem Server-Side Tracking)
```

**Ação Recomendada:** Implementar sGTM em subdomínio (sgtm.example.com), Meta CAPI em /capi/ endpoint.

---

### Nota 1-2 — Subdomínio Detectado com Erros CORS ou SSL

**Evidência Procurada:**
- Subdomínio de tracking detectado (sgtm.*, data.*, tag.*, collect.*)
- Erro CORS: "Access to XMLHttpRequest has been blocked by CORS policy"
- Erro SSL: "certificate validation failed", status 495
- Ou status 403 Forbidden em requisições internas
- Sem cookies HttpOnly completos

**Scoring Breakdown (exemplo: CORS error):**
```
Base: 0
  ✅ Subdomínio detectado: SIM (data.example.com)
  ⚠️  Requisição ao subdomínio: SIM
    • URL: https://data.example.com/gtm.js
    • Status: 200 OK (arquivo baixado)
  ❌ CORS error observado: SIM
    • "Access to XMLHttpRequest blocked by CORS policy"
    • Origin: https://example.com não autorizado
  ❌ Requisições de dados ao subdomínio: FALHANDO
    • POST /capi: 403 Forbidden
    • GET /track: 403 Forbidden
  ❌ Cookies HttpOnly: NÃO
───────────────
Observação: Subdomínio existe mas CORS impede uso
─────────────
Total: 1 (infraestrutura incompleta)
```

**Scoring Breakdown (exemplo: SSL error):**
```
Base: 0
  ✅ Subdomínio detectado: SIM (sgtm.example.com)
  ❌ SSL error: SIM
    • "certificate validation failed"
    • Certificado autossinado ou inválido
  ❌ Requisições falhando: SIM
    • Status: 495 SSL Certificate Error
    • Firewall ou proxy bloqueando
  ❌ Cookies HttpOnly: NÃO
───────────────
Observação: Infraestrutura SST com erro TLS
─────────────
Total: 2 (SST setup mas com falha de segurança)
```

**Ação Recomendada:** Verificar CORS headers (Access-Control-Allow-Origin), renovar certificado SSL, configurar proxy reverso.

---

### Nota 3 — sGTM Carregando gtm.js do Próprio Domínio

**Evidência Procurada:**
- Subdomínio first-party funcional (http 200, sem CORS error, sem SSL error)
- Arquivo gtm.js carregando de `https://sgtm.example.com/gtm.js` (ou similar)
- Cookies recebidos de primeiro party (Set-Cookie com Domain=.example.com)
- Sem CAPI integrada ou CAPI com erro

**Scoring Breakdown:**
```
Base: 0
  ✅ Subdomínio first-party: SIM (sgtm.example.com)
  ✅ Status: 200 OK (sem CORS, sem SSL error)
  ✅ gtm.js carregando: SIM
    • URL: https://sgtm.example.com/gtm.js
    • Status: 200 OK
    • Tamanho: 85KB (válido)
  ✅ Cookies recebidos: SIM
    • Set-Cookie: _gat=...; Domain=.example.com
    • Set-Cookie: _gid=...; Domain=.example.com
  ❌ Meta CAPI integrada: NÃO
  ❌ Conversions API endpoint: NÃO DETECTADO
───────────────
Observação: sGTM funcional mas sem CAPI
─────────────
Total: 3 (Server-Side Tracking parcial)
```

**Ação Recomendada:** Integrar Meta Conversions API (CAPI) em /capi/ endpoint no sGTM.

---

### Nota 4 — sGTM Ativo + Meta CAPI em First-Party

**Evidência Procurada:**
- Atende critérios da Nota 3 (sGTM em first-party, gtm.js carregando, cookies OK)
- Meta Pixel redirecionado para `https://example.com/capi/` (ou similar endpoint first-party)
- Google Conversions enviadas para first-party em vez de googletagmanager.com
- Cookies HttpOnly detectados parcialmente

**Scoring Breakdown:**
```
Base: 0
  ✅ sGTM em first-party: SIM (Nota 3 atendida)
    • sgtm.example.com operacional
    • gtm.js carregando, cookies OK
  ✅ Meta CAPI integrada: SIM
    • Requisição redirecionada: /capi/track (em example.com)
    • Status: 200 OK
    • Dados: event_type, user_data enviados
  ✅ Google Conversions enviadas: SIM
    • POST /gtm/collect
    • Status: 200 OK
  ⚠️  Cookies HttpOnly detectados: PARCIAL
    • _gac: HttpOnly=true (Google)
    • _ga: HttpOnly=false (não está com flag)
───────────────
Observação: SST + CAPI funcionando, flags de segurança parciais
─────────────
Total: 4 (Server-Side Tracking robusto)
```

**Ação Recomendada:** Verificar flag HttpOnly em todos cookies, implementar SameSite=None; Secure para cross-domain.

---

### Nota 5 — sGTM/CAPI 100% Isolada com HttpOnly + ITP Bypass

**Evidência Procurada:**
- Atende critérios da Nota 4 (sGTM + CAPI em first-party)
- **Todos** cookies com flag HttpOnly presentes (não acessíveis via JavaScript)
- Cookies com SameSite=None; Secure (para requisições cross-domain)
- Mecanismo de first-party cookie (FPC) implementado
- Subdomínio com subdomain cookie (Domain=.example.com)
- CAPI operacional sem dependência de cross-domain

**Scoring Breakdown:**
```
Base: 0
  ✅ sGTM em first-party: SIM (Nota 3 atendida)
    • sgtm.example.com operacional
    • gtm.js carregando do próprio domínio
  ✅ Meta CAPI em first-party: SIM (Nota 4 atendida)
    • /capi/ endpoint em example.com
    • Status 200 OK
  ✅ Cookies HttpOnly (todas): SIM
    • Set-Cookie: _gac=...; HttpOnly; Secure; SameSite=Lax
    • Set-Cookie: _ga=...; HttpOnly; Secure; SameSite=Lax
    • Set-Cookie: fbp=...; HttpOnly; Secure; Domain=.example.com
    • Set-Cookie: fbc=...; HttpOnly; Secure; SameSite=None
  ✅ FPC (First-Party Cookie) detectado: SIM
    • Domain=.example.com em todas as respostas
    • Cookies persistem em subdomínios
  ✅ ITP Bypass implementado: SIM
    • Cookies com MaxAge ≥ 400 dias
    • localStorage alternativo para fallback
    • Server-side session validation
───────────────
Observação: SST avançada, compliant com ITP/Privacy regulations
─────────────
Total: 5 (Server-Side Tracking enterprise-grade)
```

**Ação Recomendada:** Monitorar performance de CAPI, considerar data warehouse integration para offline conversions.

---

## Módulo 4: DataLayer Depth

### Nota 0 — window.dataLayer Inexistente

**Evidência Procurada:**
- Tentativa de acessar `window.dataLayer` retorna `undefined`
- Sem inicialização de dataLayer em nenhuma etapa do funil
- Sem eventos em nenhum page load

**Scoring Breakdown:**
```
Base: 0
  ❌ window.dataLayer existe: NÃO
    • Variável: undefined
    • typeof: undefined
  ❌ Eventos detectados: NÃO
───────────────
Observação: Sem estrutura de dados para tracking
─────────────
Total: 0 (DataLayer não implementado)
```

**Ação Recomendada:** Implementar window.dataLayer com Google Tag Manager ou manualmente.

---

### Nota 1 — dataLayer Existe mas Sem Eventos Úteis

**Evidência Procurada:**
- `window.dataLayer` declarada e acessível (typeof = "object")
- Array vazio ou com apenas eventos genéricos
- Sem dados contextuais (sem value, currency, items)
- Sem nomes de eventos conformes GA4

**Scoring Breakdown (exemplo: dataLayer vazia):**
```
Base: 0
  ✅ window.dataLayer existe: SIM
    • Tipo: Array
    • Tamanho: 0 elementos (vazio)
  ❌ Eventos presentes: NÃO
───────────────
Observação: DataLayer estrutura pronta mas sem implementação
─────────────
Total: 1 (infraestrutura, sem dados)
```

**Scoring Breakdown (exemplo: eventos genéricos):**
```
Base: 0
  ✅ window.dataLayer existe: SIM
    • Tipo: Array
    • Tamanho: 3 elementos
  ⚠️  Eventos presentes: SIM (mas genéricos)
    • event: "page_view_generic"
    • event: "user_action"
    • event: "custom_event_123"
  ❌ Eventos conformes GA4: NÃO
  ❌ Dados monetários: NÃO (sem value, currency)
  ❌ Items array: NÃO
───────────────
Observação: Eventos não mapeados para GA4 taxonomy
─────────────
Total: 1 (dataLayer presente mas sem estrutura)
```

**Ação Recomendada:** Mapear eventos para GA4 (view_item, add_to_cart, purchase, etc.), adicionar value e currency.

---

### Nota 2 — Eventos de Clique com Nomes Genéricos

**Evidência Procurada:**
- Eventos disparados em cliques de botão/link (detectados)
- Nomes **não** conformes com GA4 (ex: "click", "button_click", "link_click")
- Sem estrutura de items array
- Sem valor monetário (value, currency)

**Scoring Breakdown:**
```
Base: 0
  ✅ window.dataLayer existe: SIM
  ✅ Eventos disparados: SIM
    • Evento 1: event: "click", button_text: "Add to Cart"
    • Evento 2: event: "link_click", link_url: "/checkout"
    • Evento 3: event: "button_click", button_id: "submit"
  ❌ Eventos conformes GA4: NÃO
    • Esperado: add_to_cart, begin_checkout, purchase
    • Encontrado: click, button_click, link_click
  ❌ Items array: NÃO
  ❌ Value/currency: NÃO
───────────────
Observação: Comportamento rastreado mas sem semântica GA4
─────────────
Total: 2 (rastreamento básico de cliques)
```

**Ação Recomendada:** Renomear eventos para GA4 taxonomy, adicionar itens e valores.

---

### Nota 3 — Eventos de Funil Corretos mas Estrutura Plana

**Evidência Procurada:**
- Eventos nomeados segundo GA4 (view_item, add_to_cart, begin_checkout, etc.)
- Estrutura **plana** (sem items array OU items como objeto único, não Array)
- Currency e value presentes mas sem detalhe por produto
- Falta de campos recomendados (item_brand, item_category)

**Scoring Breakdown:**
```
Base: 0
  ✅ window.dataLayer existe: SIM
  ✅ Eventos de funil presentes: SIM
    • event: "view_item"
    • event: "add_to_cart"
    • event: "begin_checkout"
  ✅ Eventos conformes GA4: SIM
  ✅ Value/currency presentes: SIM
    • value: 149.99
    • currency: "BRL"
  ⚠️  Items array: DETECTADO (estrutura plana)
    • items: { item_id: "SKU123", price: 149.99 } (objeto, não array)
    • Esperado: items: [{ item_id: "SKU123", ... }]
  ❌ Campos recomendados: FALTANDO
    • item_brand, item_category, item_variant ausentes
───────────────
Observação: Eventos corretos mas sem detalhe por item
─────────────
Total: 3 (rastreamento de funil, sem profundidade)
```

**Ação Recomendada:** Converter items para Array, adicionar item_brand, item_category, item_category2, item_variant.

---

### Nota 4 — Eventos GA4 com Schema eCommerce Presente

**Evidência Procurada:**
- Todos eventos nomeados segundo GA4 (view_item_list, view_item, add_to_cart, remove_from_cart, view_cart, begin_checkout, add_shipping_info, add_payment_info, purchase, refund)
- Items **array** com múltiplos itens
- Fields obrigatórios presentes: item_id, item_name, price, quantity
- Currency e value calculados corretamente
- Possível: campos recomendados ausentes (item_brand, item_category)

**Scoring Breakdown:**
```
Base: 0
  ✅ window.dataLayer existe: SIM
  ✅ Eventos GA4 presentes: SIM (8+ eventos detectados)
    • view_item_list, view_item, add_to_cart, view_cart, begin_checkout, purchase
  ✅ Items array (estrutura): SIM
    • items: [
        { item_id: "SKU001", item_name: "Produto A", price: 99.99, quantity: 1 },
        { item_id: "SKU002", item_name: "Produto B", price: 149.99, quantity: 2 }
      ]
  ✅ Campos obrigatórios: SIM
    • item_id: presente (todos itens)
    • item_name: presente (todos itens)
    • price: presente (todos itens)
    • quantity: presente (todos itens)
  ✅ Value/currency: SIM
    • value: 399.97 (soma correta)
    • currency: "BRL"
  ⚠️  Campos recomendados: PARCIAL
    • item_brand: FALTANDO
    • item_category: FALTANDO
    • item_category2: FALTANDO
    • item_variant: PRESENTE (em alguns itens)
───────────────
Observação: Schema GA4 correto, campos recomendados faltando
─────────────
Total: 4 (DataLayer e-commerce funcional)
```

**Ação Recomendada:** Adicionar item_brand, item_category, item_category2 a todos itens.

---

### Nota 5 — Schema 100% Compatível GA4 eCommerce

**Evidência Procurada:**
- Atende critérios da Nota 4 (eventos GA4, items array, campos obrigatórios OK)
- **Todos** campos recomendados presentes: item_brand, item_category, item_category2, item_variant, coupon, discount, index, affiliation
- Coupon/discount aplicáveis e corretos
- Index (posição em list) presente
- Sem valores nulos, todos string/number válidos
- Compliance 100% verificado

**Scoring Breakdown:**
```
Base: 0
  ✅ window.dataLayer existe: SIM
  ✅ Eventos GA4 presentes: SIM (10 eventos, todos corretos)
  ✅ Items array: SIM
    • items: [
        {
          item_id: "SKU001",
          item_name: "Camiseta Premium",
          price: 99.99,
          quantity: 1,
          item_brand: "MeuBrand",
          item_category: "Vestuário",
          item_category2: "Camisetas",
          item_category3: "Masculino",
          item_variant: "Azul - Tamanho P",
          coupon: "SUMMER10",
          discount: 10.00,
          index: 1,
          affiliation: "ecommerce_direct"
        },
        {
          item_id: "SKU002",
          item_name: "Calça Jeans",
          price: 149.99,
          quantity: 1,
          item_brand: "MeuBrand",
          item_category: "Vestuário",
          item_category2: "Calças",
          item_category3: "Feminino",
          item_variant: "Preto - Tamanho M",
          coupon: "SUMMER10",
          discount: 15.00,
          index: 2,
          affiliation: "ecommerce_direct"
        }
      ]
  ✅ Campos obrigatórios: SIM (100%)
  ✅ Campos recomendados: SIM (100%)
  ✅ Value/currency: SIM
    • value: 414.98 (cálculo com desconto correto)
    • currency: "BRL"
  ✅ Coupon/discount: SIM (corretos)
  ✅ Index: SIM (posição em lista)
  ✅ Affiliation: SIM (origem da transação)
  ✅ Sem valores nulos: SIM (validação OK)
  ✅ Compliance GA4 eCommerce: 100% ✓
───────────────
Observação: DataLayer enterprise-grade, 100% conforme GA4 spec
─────────────
Total: 5 (DataLayer advanced, pronto para analysis)
```

**Ação Recomendada:** Monitorar qualidade de dados, considerar custom dimensions para análise adicional.

---

## Notas de Implementação

- **Scoring Breakdown Format:** Use para documentação interna do agente. Sempre mostrar ao usuário em português (PT-BR).
- **Evidência Crítica:** Se algum critério crítico não for atendido (ex: CORS error em Nota 4 SST), descer um nível no score.
- **Incrementalidade:** Nota 5 é sempre superset de Nota 4, que é superset de Nota 3, etc.
- **Ponderação:** O agente pode considerar contexto de negócio ao fazer recomendações (ex: PME pode parar em Nota 3, enterprise deve ir para 5).

