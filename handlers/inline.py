"""Inline mode handler: @bot TICKER query → cards with buttons."""

import logging
import hashlib
from telegram import (
    Update, InlineQueryResultArticle, InputTextMessageContent,
    InlineKeyboardButton, InlineKeyboardMarkup,
)
from telegram.ext import ContextTypes

from services.qa.router import parse_query
from services.qa.templates import render
from services.market_data.yahoo_finance import get_company_data
from config import DISCLAIMER
from utils.telegram import get_bot_username

logger = logging.getLogger("stockbot")

# Intent labels for the 4 inline cards
_CARD_INTENTS = [
    ("SUMMARY", "📊 Resumen"),
    ("PRICE", "💰 Precio"),
    ("VALUATION", "📈 Valoración"),
    ("MARGINS", "📋 Márgenes"),
]

def _make_help_result(bot_username: str) -> InlineQueryResultArticle:
    return InlineQueryResultArticle(
        id="help",
        title="❓ Cómo usar",
        description=f"Escribe un ticker: @{bot_username} AAPL, @{bot_username} SAN.MC ...",
        input_message_content=InputTextMessageContent(
            message_text=(
                "❓ <b>Consulta rápida</b>\n\n"
                f"Escribe <code>@{bot_username} TICKER</code> para ver datos.\n"
                f"Ejemplo: <code>@{bot_username} AAPL</code>, <code>@{bot_username} SAN.MC</code>\n\n"
                f"<i>⚠️ {DISCLAIMER}</i>"
            ),
            parse_mode="HTML",
        ),
    )


async def handle_inline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline queries: @bot TICKER [intent]."""
    query = update.inline_query
    text = (query.query or "").strip()
    bot_username = get_bot_username(context)
    help_result = _make_help_result(bot_username)

    if not text:
        await query.answer([help_result], cache_time=60, is_personal=False)
        return

    parsed = parse_query(text)
    tickers = parsed["tickers"]

    if not tickers:
        await query.answer([help_result], cache_time=30, is_personal=False)
        return

    ticker = tickers[0]

    # Fetch data once, reuse for all cards
    data = get_company_data(ticker)
    if not data:
        error_result = InlineQueryResultArticle(
            id=f"error_{ticker}",
            title=f"❌ {ticker}: sin datos",
            description="No se encontraron datos para este ticker.",
            input_message_content=InputTextMessageContent(
                message_text=f"❌ No se encontraron datos para <b>{ticker}</b>.\n\n<i>⚠️ {DISCLAIMER}</i>",
                parse_mode="HTML",
            ),
        )
        await query.answer([error_result], cache_time=60, is_personal=False)
        return

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

    name = data.get("name", ticker)
    results = []
    for intent, label in _CARD_INTENTS:
        content = render(intent, data, ticker)
        result_id = hashlib.md5(f"{ticker}:{intent}".encode()).hexdigest()
        results.append(
            InlineQueryResultArticle(
                id=result_id,
                title=f"{label} {ticker}",
                description=f"{name} — {label}",
                input_message_content=InputTextMessageContent(
                    message_text=content,
                    parse_mode="HTML",
                ),
                reply_markup=keyboard,
            )
        )

    await query.answer(results, cache_time=300, is_personal=False)
