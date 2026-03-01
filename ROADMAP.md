# ROADMAP — Stock Research & Tracking Bot

> Documento de arquitectura, decisiones y plan de evolución.
> Generado: 2026-02-27 | Actualizar tras cada fase completada.

---

## 1. ESTADO ACTUAL (v1.0)

### 1.1 Mapa del sistema

```
bot.py (entry point)
  |
  +-- config.py                 env vars: TOKEN, SERPAPI, OPENAI, ADMIN_IDS
  +-- services/db.py            SQLAlchemy engine + SessionLocal (SQLite)
  +-- services/models.py        10 tablas ORM
  |
  +-- handlers/
  |   +-- start.py              /start, /help, back_menu, cancel
  |   +-- menu.py               /datos - taxonomia, ratios, checklist
  |   +-- knowledge.py          /articulos - fetch, tag, resumir, biblioteca
  |   +-- sources.py            /fuentes - directorio por region/tipo
  |   +-- tracking.py           /tracking - watchlists, empresas, scoring, alertas, market data
  |   +-- admin.py              /admin - keys, seed, backup
  |
  +-- services/
  |   +-- knowledge/            article_fetcher, article_search, article_summarizer, article_tagger
  |   +-- sources/              sources_catalog, sources_seed (30+ fuentes, taxonomia, ratios)
  |   +-- tracking/             company_profile, scoring, watchlist, alerts
  |   +-- market_data/          yahoo_finance.py (yfinance)
  |
  +-- utils/                    text.py, validators.py, dates.py, logging.py
```

### 1.2 Comandos y callbacks

| Comando       | Handler          | Descripcion                            |
|---------------|------------------|----------------------------------------|
| `/start`      | start.py         | Menu principal                         |
| `/help`       | start.py         | Ayuda                                  |
| `/articulos`  | knowledge.py     | Base de conocimiento (684 lineas)      |
| `/datos`      | menu.py          | Taxonomia, ratios, checklist           |
| `/fuentes`    | sources.py       | Directorio de fuentes gratuitas        |
| `/tracking`   | tracking.py      | Watchlists, empresas, scoring, alertas |
| `/admin`      | admin.py         | Panel admin (protegido por user_id)    |
| `/cancel`     | start.py         | Cancelar operacion en curso            |

**65+ callbacks** registrados con prefijos: `kb_*`, `dat_*`, `src_*`, `trk_*`, `adm_*`, `back_*`, `menu_*`

**6 ConversationHandlers**: 1 en knowledge, 3 en sources, 1 mega en tracking.

### 1.3 Modelo de datos actual

```
articles (GLOBAL)
  +--< article_tags (N)
  +--< link_company_article (N) --> companies

companies (GLOBAL)
  +--< watchlist_items (N)
  +--< company_notes (N)          tipos: tesis, catalizador, riesgo
  +--< scores (N)                 5 categorias + total (promedio)
  +--< alerts (N)
  +--< link_company_article (N)

watchlists (PER-USER: user_id)
  +--< watchlist_items (N) --> companies

alerts (PER-USER: user_id)
  +---> company (nullable FK)

sources (GLOBAL, independiente, sin FKs)
```

| Tabla               | Per-user | Notas                                    |
|---------------------|----------|------------------------------------------|
| `watchlists`        | Si       | Filtrado por `user_id`                   |
| `alerts`            | Si       | Filtrado por `user_id`                   |
| `companies`         | GLOBAL   | Cualquier usuario ve/modifica            |
| `company_notes`     | GLOBAL   | Asociadas a company, no a user           |
| `scores`            | GLOBAL   | Asociadas a company, no a user           |
| `articles`          | GLOBAL   | Cualquier usuario ve todas               |
| `sources`           | GLOBAL   | Seed automatico, admin edita notas       |

### 1.4 Fuente de datos financieros

- **Unica fuente**: yfinance (scraping Yahoo Finance, sin API key)
- **Sin caching**: cada clic hace una llamada fresca
- **Sin rate-limiting**: se puede machacar la API
- **Cobertura**: US + Europa (SAN.MC, AIR.PA funciona)
- **Riesgos**: scraper no oficial, throttling agresivo (429s), bloqueos 24h+

### 1.5 Problemas identificados

**Criticos:**
- No hay aislamiento multi-usuario (Company, Score, Note son globales)
- No hay validacion de propiedad en `trk_wl_detail()` (cualquier user ve cualquier watchlist si conoce el ID)
- Sin caching ni rate-limiting para yfinance

**Funcionales:**
- `WatchlistItem.notes` se guarda pero nunca se muestra/edita
- `Alert.company_id` nullable pero el display asume que existe
- Score parsing fragil ("3, 4, 2, 4, 5" con espacios falla)
- Paginacion de empresas limitada a 20 sin scroll
- `get_watchlist_quotes()` hace llamadas en serie (no paralelo)

**Seguridad:**
- `is_valid_url()` acepta HTTP (deberia forzar HTTPS)
- Admin backup envia DB sin cifrar
- Sin limites de longitud en inputs de usuario

**Ausencias:**
- No hay soporte para grupos de Telegram
- No hay cartera/portfolio
- No hay Q&A en lenguaje natural
- No hay background jobs (alertas solo se ven manualmente)
- No hay tests (0% cobertura)

### 1.6 Piezas core (no tocar)

| Modulo                  | Razon                                         |
|-------------------------|-----------------------------------------------|
| `services/db.py`        | Patron session estandar, funciona bien        |
| `services/models.py`    | Base solida. Solo EXTENDER, no modificar       |
| `handlers/start.py`     | Simple y estable                               |
| `handlers/menu.py`      | Datos estaticos, sin bugs                      |
| `handlers/knowledge.py` | Complejo pero funcional                        |
| `handlers/sources.py`   | Funcional, no requiere cambios                 |
| `utils/*`               | Utilidades solidas y reutilizables             |
| `services/sources/*`    | Seed + catalogo estables                       |

---

## 2. INVESTIGACION

### 2.1 Telegram: bots en grupos

**Privacy Mode** (habilitado por defecto):
- ON: bot solo ve comandos `/cmd@bot`, respuestas a sus mensajes, y mensajes de servicio
- OFF o bot admin: ve TODOS los mensajes del grupo
- Los usuarios pueden ver la config de privacidad del bot

Ref: https://core.telegram.org/bots/features

**Mencion (@bot):**
- Con privacy ON, los comandos deben incluir `@nombre_bot`
- Mensajes normales con mencion NO se ven con privacy ON (requiere admin o privacy OFF)

**Inline Mode** (`@bot query`):
- Funciona en cualquier chat sin que el bot este en el grupo
- El usuario escribe `@bot AAPL P/E` y recibe "tarjeta" seleccionable
- No genera spam (solo el usuario decide si la envia)
- Limitacion: no soporta inline keyboards en la respuesta

Ref: https://core.telegram.org/bots/inline

**Rate limits:**
- 30 msg/s global por token
- **20 msg/min por grupo** (limite critico)
- ~1 msg/s por chat privado
- Ediciones comparten el limite global

Ref: https://core.telegram.org/bots/faq

**Best practices para grupos:**
- Responder SOLO cuando se invoque explicitamente
- Inline keyboards (no reply keyboards) para no generar spam
- Editar mensajes en vez de enviar nuevos
- Cooldowns por usuario
- Mensajes cortos + boton "Ver mas" que abre chat privado

### 2.2 Fuentes de datos financieros gratuitas

**Stack recomendado "free-first":**

| Prioridad | Fuente        | Cobertura | Rate limit         | Datos                          | Fiabilidad |
|-----------|---------------|-----------|--------------------|---------------------------------|------------|
| 1         | **Finnhub**   | Global    | 60 req/min         | Quasi real-time, fundament.    | Alta       |
| 2         | **SEC EDGAR** | US        | 10 req/s           | Filings oficiales, XBRL        | Muy alta   |
| 3         | **yfinance**  | Global    | Throttling agresivo | Fundamentales, historicos       | Media      |
| 4         | **FRED**      | US/Global | Gratis con API key | 800K+ series macro              | Muy alta   |
| 5         | **ECB API**   | Europa    | Sin auth           | Tipos cambio, estadisticas      | Muy alta   |
| Backup    | **Twelve Data**| Global   | 8 req/min (free)   | Real-time US, delayed resto     | Alta       |
| Backup    | **FMP**       | Global    | 250 req/dia        | Fundamentales, estimaciones     | Alta       |

**Gratuito vs de pago:**

| Dato                          | Gratis | Mejor fuente gratuita              |
|-------------------------------|--------|-------------------------------------|
| Precio (delayed 15min)        | Si     | Finnhub, yfinance                   |
| Precio real-time              | Parcial| Finnhub (US si, EU no siempre)      |
| Fundamentales (IS, BS, CF)    | Si     | SEC EDGAR (US), yfinance (global)   |
| Margenes, ratios, ROE/ROA     | Si     | yfinance                             |
| Consenso analistas detallado  | **NO** | Solo basico en yfinance/Finnhub     |
| Historicos                    | Si     | yfinance (sin limite temporal)       |
| ESG                           | Parcial| Finnhub (basico)                     |
| Dividendos                    | Si     | yfinance                             |

**yfinance (2025-2026):**
- Sigue activo (v1.0, enero 2026) pero throttling cada vez mas agresivo
- Errores 429 frecuentes, bloqueos de 24h+
- Bug #2584: desalineacion datos en estados financieros
- Alternativa al mismo backend: **Yahooquery** (mas estable)
- Recomendacion: usar como FALLBACK, no como fuente primaria
- Cache agresivo obligatorio: TTL 5-15 min precios, 24h fundamentales

*Pendiente verificacion:* Estado IEX Cloud (cerrado ago 2024). Polygon.io ("Massive") tier gratuito actual.

**Cuando pagar:** Con $19-50/mes (FMP Starter o Alpha Vantage Pro) se eliminan la mayoria de limitaciones.

### 2.3 Seguridad y privacidad

- Bot admin en grupo sobreescribe privacy mode y ve TODO (implicaciones GDPR)
- **No guardar**: contenido de mensajes que no sean queries al bot, datos personales innecesarios
- **Guardar con cuidado**: user_id (considerar hashear), queries (TTL corto), carteras (cifrar en reposo)
- **GDPR**: desarrollador = data controller. Requiere consentimiento, politica privacidad, derecho eliminacion
- **Recomendacion**: mantener privacy ON, solo responder a menciones/comandos, redirigir datos sensibles (cartera) a chat privado

---

## 3. ESCENARIOS DE ARQUITECTURA

### Escenario A: Mencion + Privacy ON (RECOMENDADO)

- Privacy mode **ON** (defecto)
- Bot responde a: `/comando@bot`, respuestas a sus mensajes
- Alternativa: bot como admin sin permisos de escritura para poder ver menciones `@bot`
- Q&A: router regex determinista + plantillas
- Cartera: solo en chat privado
- Cache in-memory con TTL
- Rate limit: max 3 queries/min por usuario en grupo

| Aspecto        | Valoracion |
|----------------|------------|
| Privacidad     | Alta       |
| Riesgo spam    | Bajo       |
| UX             | Media      |
| Esfuerzo       | Medio      |
| Mantenimiento  | Bajo       |

### Escenario B: Bot admin + deteccion automatica de tickers

- Bot como admin (privacy OFF implicito)
- Detecta tickers en cualquier mensaje del grupo
- Rate-limit agresivo: max 1 respuesta/min no solicitada
- Filtro de ruido: solo responde si detecta intent financiero

| Aspecto        | Valoracion |
|----------------|------------|
| Privacidad     | **Baja**   |
| Riesgo spam    | **Alto**   |
| UX             | Alta       |
| Esfuerzo       | Alto       |
| Mantenimiento  | Alto       |

**Desaconsejado**: problemas de privacidad, falsos positivos ("me compre un APPLE"), usuarios incomodos.

### Escenario C: Inline mode + comandos en grupo

- Privacy mode **ON**
- Q&A via inline mode: `@bot AAPL` en cualquier chat -> tarjeta con datos
- Comandos basicos: `/precio@bot AAPL`
- Bot NO necesita estar en el grupo para inline mode

| Aspecto        | Valoracion |
|----------------|------------|
| Privacidad     | Muy alta   |
| Riesgo spam    | Nulo       |
| UX             | Media-baja |
| Esfuerzo       | Medio      |
| Mantenimiento  | Bajo       |

**Limitacion**: tarjetas inline son estaticas (sin botones interactivos), UX menos fluida.

### Decision: Escenario A + elementos de C (hibrido)

Combinar comandos con mencion del Escenario A + inline mode del C para dar dos vias de uso en grupo. Cartera siempre en privado.

---

## 4. PROPUESTA DE ARQUITECTURA v2.0

### 4.1 Correcciones de enfoque

| Idea original                          | Problema                                             | Alternativa                                              |
|----------------------------------------|------------------------------------------------------|----------------------------------------------------------|
| Bot como "persona mas" en grupo        | Privacy OFF incomodo, lee todo                       | Privacy ON + comandos explicitos + inline mode            |
| Respuestas en lenguaje natural via LLM | Costoso, lento, innecesario para datos estructurados | Router regex + plantillas (95% de los casos). LLM solo opcional para reformular |
| Cartera visible en grupo               | Datos sensibles expuestos                            | Cartera en privado + boton "Compartir resumen" (solo tickers + %) |
| Alertas por cambios en fundamentales   | Datos yfinance se actualizan con retraso variable    | Solo alertas de precio (viable) + alertas manuales. Fundamentales en Fase futura con fuente premium |

### 4.2 Message Router

```
ENTRADA (texto del mensaje)
  |
  +-- 1. Extraer tickers por regex:
  |     /\$?([A-Z]{1,5}(\.[A-Z]{1,2})?)/
  |     Patrones: $NVDA, NVDA, SAN.MC, AIR.PA, 0700.HK
  |     Blacklist: ["CEO","EPS","ETF","IPO","USA","EUR","USD","FCF","ROE","ROA",...]
  |
  +-- 2. Detectar intent:
  |     "precio|cotizacion|price|quote"         -> INTENT_PRICE
  |     "valoracion|valuation|P/E|PER|EV"       -> INTENT_VALUATION
  |     "margen|margin|bruto|operativo|neto"     -> INTENT_MARGINS
  |     "deuda|debt|apalancamiento|leverage"     -> INTENT_DEBT
  |     "dividendo|dividend|yield|payout"        -> INTENT_DIVIDEND
  |     "FCF|free cash|cash flow|flujo"          -> INTENT_CASHFLOW
  |     "resumen|summary|overview|ficha"         -> INTENT_SUMMARY
  |     "comparar|compare|vs"                    -> INTENT_COMPARE
  |     (sin match)                              -> INTENT_SUMMARY (default)
  |
  +-- 3. Sin ticker:
  |     "cartera|portfolio"  -> redirigir a /cartera (privado)
  |     fallback             -> "No entendi. Prueba: /q@bot AAPL valoracion"
  |
  +-- 4. Generar respuesta:
        +-- Cache hit? -> respuesta instantanea
        +-- Cache miss -> fetch fuente -> cache -> respuesta
        +-- Formato: compacto (3-5 lineas) + boton [Ver mas]
```

**Ejemplo de respuesta compacta (grupo):**

```
AAPL | Apple Inc. | USD 245.32 (+1.2%)
P/E: 32.5x | EV/EBITDA: 26.8x | Margen neto: 26.3%
MCap: 3.78T | FCF: 110.5B | Div yield: 0.5%
No es asesoramiento financiero.
[Ver mas] [Comparar]
```

### 4.3 Modelo de cartera (MVP)

**Tablas nuevas** (se crean automaticamente con `init_db()`, no rompen nada):

```
portfolios
  id              INTEGER PK
  user_id         INTEGER NOT NULL        -- Telegram user_id
  name            VARCHAR(200)            -- "Mi cartera", "Especulativa"
  base_currency   VARCHAR(10) DEFAULT 'EUR'
  created_at      DATETIME

positions
  id              INTEGER PK
  portfolio_id    INTEGER FK -> portfolios
  company_id      INTEGER FK -> companies
  shares          FLOAT NOT NULL          -- num acciones actual
  avg_price       FLOAT NOT NULL          -- precio medio de compra
  currency        VARCHAR(10)             -- moneda de la posicion
  created_at      DATETIME
  updated_at      DATETIME

transactions
  id              INTEGER PK
  position_id     INTEGER FK -> positions
  tx_type         VARCHAR(10)             -- 'buy' | 'sell' | 'dividend'
  shares          FLOAT
  price           FLOAT
  commission      FLOAT DEFAULT 0
  date            DATETIME
  notes           TEXT
  created_at      DATETIME
```

**Calculo P&L:**
- Precio medio: recalculado con cada buy/sell (media ponderada)
- P&L no realizado: `(precio_actual - avg_price) * shares`
- P&L realizado: acumulado de ventas `(sell_price - avg_price_at_sell) * shares_sold`
- Base currency: conversion FX aplazada a Fase 2 (todo en moneda local de la posicion)

**Flujo UX:**

```
/cartera (solo en chat privado)
  +-- Ver cartera         -> resumen con P&L por posicion
  +-- Anadir posicion     -> ticker -> num acciones -> precio medio
  +-- Registrar compra    -> seleccionar posicion -> shares + precio
  +-- Registrar venta     -> seleccionar posicion -> shares + precio
  +-- Rendimiento         -> P&L total, por posicion, % ganancia
  +-- Compartir en grupo  -> resumen anonimo (solo tickers + %)
```

### 4.4 Menu principal actualizado

```
/start
  +-- Articulos             (existente)
  +-- Datos necesarios      (existente)
  +-- Fuentes               (existente)
  +-- Tracking              (existente: watchlists, scoring, alertas)
  +-- Mi Cartera            (NUEVO - solo privado)
  +-- Pregunta rapida       (NUEVO - Q&A directo)
  +-- Admin                 (existente - solo admins)
```

### 4.5 Interaccion en grupo

```
Opcion 1 (comando):  /q@bot AAPL valoracion
Opcion 2 (inline):   @bot AAPL valoracion   -> tarjeta seleccionable
Opcion 3 (reply):    responder a mensaje del bot -> follow-up
```

- Boton [Ver mas] -> abre chat privado via deep link (t.me/bot?start=mkt_AAPL)
- Asi el grupo no se llena de mensajes largos

### 4.6 Alertas mejoradas

| Tipo                          | Viabilidad  | Implementacion                                      |
|-------------------------------|-------------|-----------------------------------------------------|
| Manual (fecha)                | Ya existe   | Mantener tal cual                                   |
| **Por precio**                | Viable      | Polling cada 15 min con `get_quick_quote`. Tabla `price_alerts` |
| Por cambio % diario           | Viable      | Mismo polling. "Avisame si AAPL cae >5%"           |
| Por cambio en fundamentales   | **No fiable** | Datos yfinance con retraso variable. Fase futura con fuente premium |

Background job necesario: `python-telegram-bot` soporta `JobQueue`. Job cada 15 min que comprueba alertas de precio activas.

### 4.7 Cache

```
services/cache.py

Estrategia: in-memory dict con TTL por categoria

  PRECIOS:         TTL  5 min    (get_quick_quote)
  FUNDAMENTALES:   TTL  1 hora   (get_company_data parcial)
  PERFIL:          TTL 24 horas  (sector, industry, country)

Interfaz:
  cache_get(ticker, category) -> dict | None
  cache_set(ticker, category, data, ttl_seconds)
  cache_clear(ticker=None)     -- limpiar todo o por ticker

Rate limiting (grupo):
  max 3 queries/min por user_id
  max 10 queries/min por chat_id (grupo)
  cooldown de 2s entre respuestas del bot en mismo grupo
```

---

## 5. PREGUNTAS DE DECISION (pendientes de respuesta)

> Responder antes de empezar Fase 1.

1. **Cartera individual o compartida?**
   Recomendacion: individual por user_id, con opcion de compartir resumen.

2. **Base currency EUR o multi-currency?**
   Recomendacion: EUR para MVP. Multi-currency con conversion FX (ECB API) en Fase 2.

3. **Solo acciones o tambien ETFs/cripto?**
   yfinance soporta ETFs y algo de cripto. Impacta el modelo de datos.

4. **Quien puede usar el bot?**
   Abierto a cualquiera, o whitelist de user_ids? Impacta privacidad en grupos publicos.

5. **Idioma de respuestas en grupo:**
   Siempre espanol, o detectar idioma del mensaje?

6. **Inline mode ademas de comandos?**
   Inline mode es mas trabajo pero mejor UX. Puede ir en Fase 2.

7. **Alertas de precio en MVP o Fase 2?**
   Requiere JobQueue + tabla nueva. Medio esfuerzo.

8. **Fuente de datos primaria:**
   Solo yfinance + cache agresivo, o anadir Finnhub ya en MVP?

---

## 6. ROADMAP DE FASES

### Fase 1 — MVP (2 iteraciones)

**Iteracion 1.1: Infraestructura + Q&A**

- [ ] `services/cache.py` — Cache in-memory con TTL configurable
- [ ] `services/qa/router.py` — Extraccion de tickers (regex) + deteccion de intents
- [ ] `services/qa/templates.py` — Plantillas de respuesta compacta por intent
- [ ] `handlers/group.py` — Handler para `/q@bot TICKER intent` en grupo
- [ ] `config.py` — Nuevas constantes: `CACHE_TTL_*`, `RATE_LIMIT_*`
- [ ] `bot.py` — Registrar handlers de grupo
- [ ] Disclaimer automatico en cada respuesta financiera
- [ ] Rate limiting por usuario y por grupo

**Iteracion 1.2: Cartera + Alertas precio**

- [ ] `services/models.py` — Anadir modelos: `Portfolio`, `Position`, `Transaction`, `PriceAlert`
- [ ] `services/tracking/portfolio.py` — CRUD cartera, calculos P&L
- [ ] `services/tracking/price_alerts.py` — CRUD alertas + `check_price_alerts()`
- [ ] `handlers/portfolio.py` — ConversationHandler: anadir, comprar, vender, ver P&L
- [ ] `handlers/start.py` — Anadir botones "Mi Cartera" y "Pregunta rapida"
- [ ] `bot.py` — Registrar portfolio handlers + JobQueue para alertas (polling 15 min)
- [ ] Validacion: cartera solo accesible en chat privado

### Fase 2 — Mejoras avanzadas

- [ ] Inline mode para Q&A (`@bot AAPL` desde cualquier chat)
- [ ] Comparador de 2 tickers lado a lado
- [ ] Import CSV de transacciones
- [ ] Multi-currency con conversion FX (ECB API)
- [ ] Fuentes adicionales: Finnhub como primaria, yfinance como fallback
- [ ] Graficos de precio (matplotlib -> imagen -> enviar como foto)
- [ ] Reporting mensual automatico (resumen cartera via Telegram)
- [ ] Boton "Compartir en grupo" desde cartera privada (solo tickers + %)
- [ ] Paginacion completa para empresas (>20)
- [ ] Validacion de propiedad en watchlists
- [ ] Fix: score parsing tolerante a espacios
- [ ] Fix: forzar HTTPS en URLs de articulos
- [ ] Tests unitarios para scoring, dates, text, cache, router

### Fase 3 — Premium (opcional)

- [ ] Dashboard web (Flask/FastAPI) con graficos interactivos
- [ ] Fuente premium (FMP Starter ~$19/mes) para estimaciones analistas
- [ ] Alertas por cambios en fundamentales (requiere baseline historico)
- [ ] Notificaciones push de earnings/dividendos
- [ ] Multi-idioma (ES/EN) automatico
- [ ] Exportacion PDF de informes de cartera

---

## 7. PLAN DE CAMBIOS EN CODIGO

### Ficheros a modificar

| Fichero               | Cambio                                                         |
|-----------------------|----------------------------------------------------------------|
| `bot.py`              | Registrar handlers grupo, cartera, Q&A. Anadir JobQueue        |
| `config.py`           | Constantes: `CACHE_TTL_*`, `RATE_LIMIT_*`, `ALLOWED_USER_IDS`  |
| `services/models.py`  | Anadir: Portfolio, Position, Transaction, PriceAlert. **No tocar tablas existentes** |
| `handlers/start.py`   | Botones "Mi Cartera" y "Pregunta rapida" en menu principal      |
| `handlers/tracking.py`| Enlace a cartera desde watchlist (opcional)                     |
| `requirements.txt`    | Sin cambios (todo lo necesario ya esta instalado)               |

### Ficheros nuevos

| Fichero                             | Proposito                                              |
|-------------------------------------|--------------------------------------------------------|
| `services/cache.py`                 | Cache in-memory con TTL. `cache_get()`, `cache_set()`  |
| `services/qa/router.py`             | `parse_query(text) -> (tickers, intent)`. Regex tickers + intents |
| `services/qa/templates.py`          | Plantillas respuesta por intent. Formato compacto grupo |
| `services/tracking/portfolio.py`    | CRUD cartera: `create_portfolio`, `add_position`, `record_transaction`, `calc_pnl` |
| `services/tracking/price_alerts.py` | CRUD alertas precio + `check_price_alerts()` para JobQueue |
| `handlers/portfolio.py`             | ConversationHandler cartera (solo privado)               |
| `handlers/group.py`                 | Handler mensajes grupo: parsear query, router, responder |

### Migracion de DB

**Estrategia**: Sin Alembic (overkill para SQLite).

- Tablas nuevas se crean automaticamente con `init_db()` (`Base.metadata.create_all()` no toca tablas existentes)
- **No se modifican tablas existentes** -> cero riesgo de rotura
- Backup antes de desplegar: admin puede hacer backup desde `/admin`

### Estructura final esperada (v2.0)

```
bot.py
config.py
requirements.txt
data/
  app.db
services/
  db.py
  models.py
  cache.py                           <-- NUEVO
  knowledge/
    article_fetcher.py
    article_search.py
    article_summarizer.py
    article_tagger.py
  sources/
    sources_catalog.py
    sources_seed.py
  tracking/
    company_profile.py
    scoring.py
    watchlist.py
    alerts.py
    portfolio.py                     <-- NUEVO
    price_alerts.py                  <-- NUEVO
  market_data/
    yahoo_finance.py
  qa/                                <-- NUEVO
    router.py
    templates.py
handlers/
  start.py
  menu.py
  knowledge.py
  sources.py
  tracking.py
  admin.py
  portfolio.py                       <-- NUEVO
  group.py                           <-- NUEVO
utils/
  text.py
  validators.py
  dates.py
  logging.py
```

---

## 8. TESTS DE ACEPTACION

### Cache
- [ ] Pedir datos de AAPL 2 veces seguidas: la 2a es instantanea (cache hit)
- [ ] Esperar TTL + pedir de nuevo: fetch fresco
- [ ] `cache_clear("AAPL")` invalida solo AAPL

### Q&A en grupo
- [ ] Anadir bot al grupo
- [ ] `/q@bot AAPL precio` -> respuesta compacta con precio actual
- [ ] `/q@bot SAN.MC valoracion` -> P/E, EV/EBITDA, P/B
- [ ] `/q@bot NVDA margenes` -> margenes bruto, operativo, neto
- [ ] `/q@bot ASML resumen` -> ficha completa compacta
- [ ] `/q@bot` sin ticker -> mensaje de ayuda
- [ ] 5 queries en 30s -> rate limit activo ("espera un momento")
- [ ] Verificar disclaimer en cada respuesta

### Cartera (privado)
- [ ] `/cartera` -> crear cartera "Principal"
- [ ] Anadir posicion: AAPL, 10 acciones, precio 200
- [ ] Registrar compra: +5 a 210 -> precio medio actualizado correctamente
- [ ] Ver P&L: muestra ganancia/perdida con precio actual de mercado
- [ ] Registrar venta: -3 a 250 -> P&L realizado calculado
- [ ] Ver resumen: total invertido, valor actual, P&L %
- [ ] Intentar `/cartera` en grupo -> redirige a privado

### Alertas de precio
- [ ] Crear alerta: "AAPL por encima de 250"
- [ ] Verificar que JobQueue comprueba cada 15 min
- [ ] Cuando se active: notificacion en privado
- [ ] Desactivar alerta manualmente

### Regresion (no romper lo existente)
- [ ] `/start` -> menu principal con nuevos botones + los antiguos
- [ ] `/tracking` -> watchlists funcionan igual
- [ ] Crear watchlist + anadir ticker -> auto-fill sigue funcionando
- [ ] Datos de mercado -> muestra datos (ahora desde cache)
- [ ] `/articulos` -> biblioteca completa funciona
- [ ] `/fuentes` -> directorio funciona
- [ ] `/admin` -> backup, seed, keys funcionan
- [ ] Scoring -> formato "3,4,2,4,5 comentario" sigue funcionando
