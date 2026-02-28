import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from config import ADMIN_USER_IDS, DISCLAIMER
from services.market_data.yahoo_finance import get_company_data
from services.qa.templates import render
from utils.telegram import get_bot_username
from utils.text import safe_truncate_html

logger = logging.getLogger("stockbot")

MAIN_KEYBOARD = [
    [InlineKeyboardButton("📚 Artículos", callback_data="menu_kb")],
    [InlineKeyboardButton("🧩 Datos necesarios", callback_data="menu_datos")],
    [InlineKeyboardButton("🌍 Fuentes", callback_data="menu_src")],
    [InlineKeyboardButton("📈 Tracking", callback_data="menu_trk")],
    [InlineKeyboardButton("💼 Mi Cartera", callback_data="menu_pf")],
    [InlineKeyboardButton("🔍 Buscar ticker", switch_inline_query_current_chat="")],
]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show main menu, or handle deep-link payloads."""
    # Deep-link handling: /start detail_AAPL or /start portfolio
    if context.args:
        payload = context.args[0]
        if payload.startswith("detail_"):
            await _deep_link_detail(update, context, payload[7:])
            return
        if payload == "portfolio":
            from handlers.portfolio import portfolio_menu
            await portfolio_menu(update, context)
            return

    user_id = update.effective_user.id
    keyboard = list(MAIN_KEYBOARD)
    if user_id in ADMIN_USER_IDS:
        keyboard.append([InlineKeyboardButton("⚙️ Admin", callback_data="menu_adm")])

    text = (
        "🏦 <b>Stock Research &amp; Tracking Bot</b>\n\n"
        "Sistema de investigación y seguimiento de empresas.\n"
        "Selecciona una opción:"
    )
    markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=markup, parse_mode="HTML")
    else:
        await update.message.reply_text(text, reply_markup=markup, parse_mode="HTML")


async def _deep_link_detail(update: Update, context: ContextTypes.DEFAULT_TYPE, ticker: str):
    """Handle /start detail_TICKER deep-link: show full financial detail."""
    ticker = ticker.upper()
    data = get_company_data(ticker)

    if not data:
        await update.message.reply_text(
            f"❌ No se encontraron datos para <b>{ticker}</b>.\n\n<i>⚠️ {DISCLAIMER}</i>",
            parse_mode="HTML",
        )
        return

    # Build a comprehensive detail view from all intents
    sections = []
    for intent in ("SUMMARY", "PRICE", "VALUATION", "MARGINS", "DEBT", "DIVIDEND", "CASHFLOW", "ANALYSTS"):
        sections.append(render(intent, data, ticker))

    # Join sections (each already has header+disclaimer, so strip duplicate disclaimers)
    suffix = f"\n<i>⚠️ {DISCLAIMER}</i>"
    cleaned = []
    for s in sections:
        if s.endswith(suffix):
            s = s[: -len(suffix)]
        cleaned.append(s)

    text = "\n\n".join(cleaned) + f"\n\n<i>⚠️ {DISCLAIMER}</i>"

    text = safe_truncate_html(text, suffix=f"\n...\n\n<i>⚠️ {DISCLAIMER}</i>")

    bot_username = get_bot_username(context)
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💼 Mi Cartera", url=f"https://t.me/{bot_username}?start=portfolio"),
            InlineKeyboardButton("◀️ Menú", callback_data="back_menu"),
        ],
        [
            InlineKeyboardButton("🔍 Otro ticker", switch_inline_query_current_chat=""),
        ],
    ])

    await update.message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)


async def back_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    await start(update, context)
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    if update.callback_query:
        await update.callback_query.answer()
    if update.message:
        await update.message.reply_text("Operación cancelada.")
    await start(update, context)
    return ConversationHandler.END


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot_username = get_bot_username(context)
    text = (
        "📖 <b>Ayuda</b>\n\n"
        "<b>Comandos privados</b>\n"
        "/start — Menú principal\n"
        "/cartera — Gestión de cartera\n"
        "/articulos — Base de conocimiento\n"
        "/datos — Datos necesarios\n"
        "/fuentes — Directorio de fuentes\n"
        "/tracking — Watchlists y seguimiento\n"
        "/admin — Administración\n"
        "/cancel — Cancelar operación\n\n"
        "<b>En grupos</b>\n"
        f"<code>/q TICKER</code> — Consulta rápida\n"
        f"<code>/q AAPL valoración</code> — Con intent\n\n"
        "<b>Inline (en cualquier chat)</b>\n"
        f"<code>@{bot_username} AAPL</code> — Tarjetas de datos\n"
    )
    await update.message.reply_text(text, parse_mode="HTML")
