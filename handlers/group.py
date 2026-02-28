"""Group handler: /q command for quick Q&A in groups."""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import RATE_LIMIT_GROUP_PER_USER, RATE_LIMIT_WINDOW
from services.qa.router import parse_query
from services.qa.templates import render
from services.market_data.yahoo_finance import get_company_data
from services.rate_limit import rate_limit_allow
from utils.telegram import get_bot_username

logger = logging.getLogger("stockbot")

_HELP_TEXT = (
    "❓ <b>Consulta rápida</b>\n\n"
    "Uso: <code>/q TICKER [intent]</code>\n\n"
    "Ejemplos:\n"
    "  <code>/q AAPL</code> — resumen\n"
    "  <code>/q SAN.MC valoración</code>\n"
    "  <code>/q NVDA márgenes</code>\n"
    "  <code>/q ASML dividendo</code>\n"
    "  <code>/q MSFT deuda</code>\n\n"
    "Intents: precio, valoración, márgenes, deuda, dividendo, FCF, analistas, resumen"
)


async def handle_q(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /q command in any chat."""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    # Rate limit in groups
    if update.effective_chat.type in ("group", "supergroup"):
        key = f"group:{chat_id}:user:{user_id}"
        if not rate_limit_allow(key, RATE_LIMIT_GROUP_PER_USER, RATE_LIMIT_WINDOW):
            await update.message.reply_text(
                "⏳ Demasiadas consultas. Espera un momento.",
                parse_mode="HTML",
            )
            return

    # Parse the query text (everything after /q)
    text = update.message.text or ""
    # Remove the /q command itself (and possible @botname)
    raw = text.strip()

    parsed = parse_query(raw)
    tickers = parsed["tickers"]
    intent = parsed["intent"]

    if not tickers:
        await update.message.reply_text(_HELP_TEXT, parse_mode="HTML")
        return

    ticker = tickers[0]
    data = get_company_data(ticker)

    if not data:
        data = {"error": f"No se encontraron datos para {ticker}"}

    response = render(intent, data, ticker)
    bot_username = get_bot_username(context)
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📋 Ver más",
                url=f"https://t.me/{bot_username}?start=detail_{ticker}",
            ),
            InlineKeyboardButton(
                "💼 Mi cartera",
                url=f"https://t.me/{bot_username}?start=portfolio",
            ),
        ],
    ])

    await update.message.reply_text(
        response, parse_mode="HTML", reply_markup=keyboard,
    )
