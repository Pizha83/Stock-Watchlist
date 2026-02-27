# Stock Research & Tracking Bot

Bot de Telegram para investigación y seguimiento de empresas cotizadas. Incluye base de conocimiento de artículos, modelo de datos para análisis, directorio de fuentes gratuitas, y sistema de tracking con watchlists, scoring y alertas.

## Funcionalidades

- **Artículos**: Buscar, guardar, clasificar y resumir artículos sobre inversión (ES/EN)
- **Datos necesarios**: Taxonomía completa de campos, ratios y fórmulas para análisis fundamental
- **Fuentes**: Directorio de fuentes gratuitas por región y tipo (SEC EDGAR, CNMV, FRED, ECB...)
- **Tracking**: Watchlists, perfiles de empresa, tesis, scoring (0-5) y alertas
- **Datos de mercado**: Información financiera en tiempo real vía Yahoo Finance (yfinance)
  - Precio actual, variación, rango 52 semanas
  - Valoración: Market Cap, EV, P/E, EV/EBITDA, P/B, P/S
  - Resultados: Revenue, EBITDA, Net Income, EPS
  - Márgenes: Bruto, Operativo, Neto
  - Rentabilidad: ROE, ROA, FCF, Operating Cash Flow
  - Deuda: Total debt, Cash, Debt/Equity
  - Dividendo: Yield, payout ratio, ex-dividend date
  - Analistas: Recomendación consenso, precio objetivo y rango
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
```

En Windows (PowerShell):
```powershell
$env:TELEGRAM_BOT_TOKEN = "tu_token_aqui"
$env:ADMIN_USER_IDS = "tu_user_id"
```

> Para obtener tu user ID, usa [@userinfobot](https://t.me/userinfobot) en Telegram.

## Ejecución

```bash
python bot.py
```

## Uso

### Comandos disponibles

| Comando | Descripción |
|---------|-------------|
| `/start` | Menú principal |
| `/articulos` | Base de conocimiento |
| `/datos` | Modelo de datos y ratios |
| `/fuentes` | Directorio de fuentes |
| `/tracking` | Watchlists y seguimiento |
| `/admin` | Panel de administración |
| `/cancel` | Cancelar operación actual |

### Flujo típico

1. **Añadir artículo**: `/articulos` → Añadir por URL → Pegar URL → Se extrae, resume y clasifica automáticamente
2. **Consultar datos**: `/datos` → Ratios y fórmulas → Ver qué métricas calcular
3. **Ver fuentes**: `/fuentes` → Por región → USA → SEC EDGAR (ver detalle)
4. **Crear watchlist**: `/tracking` → Watchlists → Crear → Añadir tickers (perfil auto-completado desde Yahoo Finance)
5. **Ver datos de mercado**: Detalle de empresa → 📊 Datos de mercado → Información financiera completa
6. **Precios en vivo**: Detalle de watchlist → 📊 Precios en vivo → Resumen de precios de todas las empresas
7. **Scoring**: Detalle de empresa → Scoring → Introducir puntuaciones (ej: `4,3,3,4,5 Buen negocio`)
8. **Alertas**: `/tracking` → Alertas → Nueva alerta → Mensaje y fecha

## Estructura del proyecto

```
bot.py                          # Entry point
config.py                       # Configuración y variables de entorno
requirements.txt                # Dependencias
data/
  app.db                        # Base de datos SQLite (se crea automáticamente)
services/
  db.py                         # Engine y sesiones SQLAlchemy
  models.py                     # Modelos ORM (Article, Source, Company, etc.)
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
  market_data/
    yahoo_finance.py             # Datos financieros en tiempo real (yfinance)
handlers/
  start.py                      # /start, menú principal, cancel
  menu.py                       # Sección "Datos necesarios"
  knowledge.py                  # Sección "Artículos"
  sources.py                    # Sección "Fuentes"
  tracking.py                   # Sección "Tracking"
  admin.py                      # Sección "Admin"
utils/
  text.py                       # Escape HTML, truncar, formateo de números/precios/ratios
  validators.py                 # Validación de URLs y tickers
  dates.py                      # Formateo y parseo de fechas
  logging.py                    # Configuración de logging
```

## Modo sin API keys

El bot funciona completamente sin API keys externas:

- **Sin SERPAPI_KEY**: La búsqueda automática se desactiva. Puedes añadir artículos manualmente por URL.
- **Sin OPENAI_API_KEY**: Los resúmenes se generan con un algoritmo heurístico local (extractivo).
- **Yahoo Finance (yfinance)**: No requiere API key. Los datos de mercado funcionan directamente.
- **Todas las fuentes del directorio** son gratuitas y de acceso público.

## Base de datos

Se utiliza SQLite con SQLAlchemy. La base de datos se crea automáticamente en `data/app.db` al primer arranque. Las fuentes iniciales se cargan automáticamente (seed).

### Tablas

`articles`, `article_tags`, `sources`, `companies`, `watchlists`, `watchlist_items`, `company_notes`, `scores`, `alerts`, `link_company_article`
