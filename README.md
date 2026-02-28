# Stock Research & Tracking Bot

Bot de Telegram para investigación y seguimiento de empresas cotizadas. Incluye base de conocimiento de artículos, modelo de datos para análisis, directorio de fuentes gratuitas, y sistema de tracking con watchlists, scoring y alertas.

## Funcionalidades

- **Consulta rápida (inline)**: Escribe `@bot AAPL` en cualquier chat para ver tarjetas con datos financieros (resumen, precio, valoración, márgenes) con botones interactivos
- **Consulta en grupos** (`/q`): Usa `/q TICKER [intent]` en grupos para consultas rápidas con rate limiting
- **Cartera de inversión**: Gestión de posiciones, registro de compras/ventas, cálculo de P&L realizado y no realizado, precio medio ponderado
- **Artículos**: Buscar, guardar, clasificar y resumir artículos sobre inversión (ES/EN)
- **Datos necesarios**: Taxonomía completa de campos, ratios y fórmulas para análisis fundamental
- **Fuentes**: Directorio de fuentes gratuitas por región y tipo (SEC EDGAR, CNMV, FRED, ECB...)
- **Tracking**: Watchlists con validación de propiedad, perfiles de empresa, tesis, scoring (0-5) y alertas
- **Datos de mercado**: Información financiera con caché en tiempo real vía Yahoo Finance (yfinance)
  - Precio actual, variación, rango 52 semanas
  - Valoración: Market Cap, EV, P/E, EV/EBITDA, P/B, P/S
  - Resultados: Revenue, EBITDA, Net Income, EPS
  - Márgenes: Bruto, Operativo, Neto
  - Rentabilidad: ROE, ROA, FCF, Operating Cash Flow
  - Deuda: Total debt, Cash, Debt/Equity
  - Dividendo: Yield, payout ratio, ex-dividend date
  - Analistas: Recomendación consenso, precio objetivo y rango
  - Caché inteligente: 5 min precios, 4h fundamentales, 24h perfiles
  - Precios en vivo de toda una watchlist de un vistazo
  - Auto-completado de perfil (sector, industria, país, bolsa, moneda) al añadir empresas
- **Admin**: Estado de API keys, seed de fuentes, backup de base de datos

## Requisitos

- Python 3.11+
- Un bot de Telegram (crear con [@BotFather](https://t.me/BotFather))

## Instalación

```bash
# 1. Crear entorno virtual
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate

# 2. Instalar dependencias
pip install -r requirements.txt
```

## Configuración

Establece las variables de entorno antes de ejecutar:

```bash
# Obligatorio: token del bot de Telegram
export TELEGRAM_BOT_TOKEN="tu_token_aqui"

# Opcional: búsqueda web automática de artículos
export SERPAPI_KEY="tu_serpapi_key"

# Opcional: resúmenes avanzados con IA
export OPENAI_API_KEY="tu_openai_key"

# Opcional: IDs de usuario admin (separados por comas)
export ADMIN_USER_IDS="123456789,987654321"

# Opcional: Finnhub API key (fuente alternativa de datos)
export FINNHUB_API_KEY="tu_finnhub_key"
```

En Windows (PowerShell):
```powershell
$env:TELEGRAM_BOT_TOKEN = "tu_token_aqui"
$env:ADMIN_USER_IDS = "tu_user_id"
```

> Para obtener tu user ID, usa [@userinfobot](https://t.me/userinfobot) en Telegram.

## Ejecución

```bash
python stockbot.py
```

## Uso

### Comandos disponibles

| Comando | Descripción |
|---------|-------------|
| `/start` | Menú principal (con deep-links) |
| `/cartera` | Gestión de cartera de inversión |
| `/q TICKER [intent]` | Consulta rápida (funciona en grupos) |
| `/articulos` | Base de conocimiento |
| `/datos` | Modelo de datos y ratios |
| `/fuentes` | Directorio de fuentes |
| `/tracking` | Watchlists y seguimiento |
| `/admin` | Panel de administración |
| `/cancel` | Cancelar operación actual |

### Modo inline

Escribe `@nombre_del_bot TICKER` en cualquier chat de Telegram para ver tarjetas interactivas:
- `@bot AAPL` → 4 tarjetas: Resumen, Precio, Valoración, Márgenes
- Cada tarjeta incluye botones para ver más detalle o abrir la cartera

### Consulta en grupos

Usa `/q` seguido del ticker y opcionalmente un intent:
- `/q AAPL` → resumen general
- `/q SAN.MC valoración` → datos de valoración
- `/q NVDA márgenes` → márgenes y rentabilidad
- Intents: precio, valoración, márgenes, deuda, dividendo, FCF, analistas, resumen

### Cartera de inversión

- Añadir posiciones con ticker, cantidad y precio medio
- Registrar compras adicionales (recalcula precio medio ponderado)
- Registrar ventas (calcula P&L realizado)
- Ver posiciones con precios en vivo y P&L no realizado
- Rendimiento total de la cartera

### Flujo típico

1. **Consulta rápida**: `@bot AAPL` en cualquier chat → tarjeta con datos → botón "Ver más" para detalle completo
2. **Gestionar cartera**: `/cartera` → Añadir posición → Ticker → Acciones → Precio
3. **Añadir artículo**: `/articulos` → Añadir por URL → Pegar URL → Se extrae, resume y clasifica automáticamente
4. **Consultar datos**: `/datos` → Ratios y fórmulas → Ver qué métricas calcular
5. **Ver fuentes**: `/fuentes` → Por región → USA → SEC EDGAR (ver detalle)
6. **Crear watchlist**: `/tracking` → Watchlists → Crear → Añadir tickers (perfil auto-completado desde Yahoo Finance)
7. **Ver datos de mercado**: Detalle de empresa → 📊 Datos de mercado → Información financiera completa
8. **Precios en vivo**: Detalle de watchlist → 📊 Precios en vivo → Resumen de precios de todas las empresas
9. **Scoring**: Detalle de empresa → Scoring → Introducir puntuaciones (ej: `4,3,3,4,5 Buen negocio`)
10. **Alertas**: `/tracking` → Alertas → Nueva alerta → Mensaje y fecha

## Estructura del proyecto

```
stockbot.py                     # Entry point
config.py                       # Configuración y variables de entorno
requirements.txt                # Dependencias
data/
  app.db                        # Base de datos SQLite (se crea automáticamente)
services/
  db.py                         # Engine y sesiones SQLAlchemy
  models.py                     # Modelos ORM (Article, Source, Company, Portfolio, etc.)
  cache.py                      # Caché in-memory con TTL
  rate_limit.py                 # Rate limiter (sliding window)
  knowledge/
    article_fetcher.py           # Extracción de contenido con trafilatura
    article_search.py            # Búsqueda web con SerpAPI
    article_summarizer.py        # Resumen heurístico / LLM
    article_tagger.py            # Auto-tagging por keywords
  sources/
    sources_catalog.py           # CRUD de fuentes
    sources_seed.py              # Datos iniciales + taxonomía + ratios
  tracking/
    company_profile.py           # CRUD de empresas y notas
    scoring.py                   # Sistema de puntuación
    watchlist.py                 # Gestión de watchlists
    alerts.py                    # Alertas y resumen semanal
    portfolio.py                 # Gestión de cartera: posiciones, transacciones, P&L
  market_data/
    yahoo_finance.py             # Datos financieros con caché (yfinance)
  qa/
    router.py                    # Extracción de tickers + detección de intents
    templates.py                 # Plantillas de respuesta por intent
handlers/
  start.py                      # /start, deep-links, menú principal, cancel
  menu.py                       # Sección "Datos necesarios"
  knowledge.py                  # Sección "Artículos"
  sources.py                    # Sección "Fuentes"
  tracking.py                   # Sección "Tracking" (con validación de propiedad)
  admin.py                      # Sección "Admin"
  portfolio.py                  # Gestión de cartera (chat privado)
  group.py                      # Comando /q para consultas en grupos
  inline.py                     # Modo inline: @bot TICKER
utils/
  text.py                       # Escape HTML, truncar, formateo de números/precios/ratios
  validators.py                 # Validación de URLs y tickers
  dates.py                      # Formateo y parseo de fechas
  logging.py                    # Configuración de logging
```

## Seguridad

- **Propiedad de recursos**: Watchlists, alertas y posiciones de cartera solo son accesibles por el usuario que las creó
- **Empresas globales**: La eliminación de empresas del tracking está restringida a usuarios admin (`ADMIN_USER_IDS`)
- **Truncado seguro**: Los mensajes largos se truncan en límites de línea para evitar romper el formato HTML de Telegram
- **Validación de ownership**: Cada operación de modificación verifica que el recurso pertenece al usuario solicitante

## Modo sin API keys

El bot funciona completamente sin API keys externas:

- **Sin SERPAPI_KEY**: La búsqueda automática se desactiva. Puedes añadir artículos manualmente por URL.
- **Sin OPENAI_API_KEY**: Los resúmenes se generan con un algoritmo heurístico local (extractivo).
- **Yahoo Finance (yfinance)**: No requiere API key. Los datos de mercado funcionan directamente.
- **Todas las fuentes del directorio** son gratuitas y de acceso público.

## Base de datos

Se utiliza SQLite con SQLAlchemy. La base de datos se crea automáticamente en `data/app.db` al primer arranque. Las fuentes iniciales se cargan automáticamente (seed).

### Tablas

`articles`, `article_tags`, `sources`, `companies`, `watchlists`, `watchlist_items`, `company_notes`, `scores`, `alerts`, `link_company_article`, `portfolios`, `positions`, `transactions`, `price_alerts`
