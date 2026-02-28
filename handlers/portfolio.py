"""Portfolio handler: manage positions, buy/sell, P&L (private chat only)."""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler,
    CallbackQueryHandler, MessageHandler, filters,
)

from config import DISCLAIMER
from services.db import get_session
from services.tracking.portfolio import (
    get_or_create_portfolio, list_positions, add_position,
    record_buy, record_sell, calc_total_pnl, get_positions_for_selection,
)
from services.market_data.yahoo_finance import get_quick_quote
from utils.text import escape_html, format_price, format_number, safe_truncate_html
from utils.validators import is_valid_ticker
from utils.telegram import get_bot_username

logger = logging.getLogger("stockbot")

# Conversation states
PF_TICKER, PF_SHARES, PF_PRICE, PF_SELECT_BUY, PF_BUY_SHARES, PF_BUY_PRICE = range(6)
PF_SELECT_SELL, PF_SELL_SHARES, PF_SELL_PRICE = range(6, 9)

_PRIVATE_ONLY = (
    "💼 La cartera solo está disponible en chat privado.\n"
    "Pulsa el botón para abrir el chat."
)


# ── MAIN MENU ────────────────────────────────────────────────────

async def portfolio_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show portfolio menu. Only works in private chat."""
    # Handle both commands and callbacks
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        chat_type = update.effective_chat.type
        if chat_type != "private":
            bot_username = get_bot_username(context)
            await query.edit_message_text(
                _PRIVATE_ONLY,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("💼 Abrir cartera", url=f"https://t.me/{bot_username}?start=portfolio"),
                ]]),
            )
            return
        await _show_portfolio_menu(query.edit_message_text, update, context)
    else:
        chat_type = update.effective_chat.type
        if chat_type != "private":
            bot_username = get_bot_username(context)
            await update.message.reply_text(
                _PRIVATE_ONLY,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("💼 Abrir cartera", url=f"https://t.me/{bot_username}?start=portfolio"),
                ]]),
            )
            return
        await _show_portfolio_menu(update.message.reply_text, update, context)


async def _show_portfolio_menu(send_fn, update, context):
    keyboard = [
        [InlineKeyboardButton("📊 Ver posiciones", callback_data="pf_positions")],
        [InlineKeyboardButton("➕ Añadir posición", callback_data="pf_add")],
        [InlineKeyboardButton("💰 Registrar compra", callback_data="pf_buy")],
        [InlineKeyboardButton("💸 Registrar venta", callback_data="pf_sell")],
        [InlineKeyboardButton("📈 Rendimiento total", callback_data="pf_pnl")],
        [InlineKeyboardButton("◀️ Menú principal", callback_data="back_menu")],
    ]
    await send_fn(
        "💼 <b>Mi Cartera</b>\n\nGestiona tus posiciones e inversiones.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )


# ── VIEW POSITIONS ───────────────────────────────────────────────

async def pf_view_positions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    session = get_session()
    try:
        positions = list_positions(session, user_id)
    finally:
        session.close()

    if not positions:
        await query.edit_message_text(
            "💼 <b>Posiciones</b>\n\nNo tienes posiciones. Añade una.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Añadir posición", callback_data="pf_add")],
                [InlineKeyboardButton("◀️ Cartera", callback_data="menu_pf")],
            ]),
        )
        return

    text = "💼 <b>Mis Posiciones</b>\n\n"
    for p in positions:
        chg_emoji = "🟢" if p["unrealized_pnl"] > 0 else ("🔴" if p["unrealized_pnl"] < 0 else "⚪")
        price_str = format_price(p["current_price"], p["currency"]) if p["current_price"] else "N/A"
        pnl_pct = ((p["current_price"] - p["avg_price"]) / p["avg_price"] * 100) if p["current_price"] and p["avg_price"] else 0
        text += (
            f"{chg_emoji} <b>{escape_html(p['ticker'])}</b> × {p['shares']:.2f}\n"
            f"   Precio: {price_str} | Medio: {format_price(p['avg_price'], p['currency'])}\n"
            f"   P&L: {p['unrealized_pnl']:+,.2f} ({pnl_pct:+.1f}%)\n\n"
        )

    if len(text) > 4000:
        text = safe_truncate_html(text)

    text += f"\n<i>⚠️ {DISCLAIMER}</i>"

    keyboard = [
        [InlineKeyboardButton("📈 Rendimiento total", callback_data="pf_pnl")],
        [InlineKeyboardButton("◀️ Cartera", callback_data="menu_pf")],
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")


# ── TOTAL P&L ────────────────────────────────────────────────────

async def pf_total_pnl(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    session = get_session()
    try:
        pnl = calc_total_pnl(session, user_id)
    finally:
        session.close()

    if pnl["num_positions"] == 0:
        await query.edit_message_text(
            "📈 Sin posiciones abiertas.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ Cartera", callback_data="menu_pf")],
            ]),
        )
        return

    emoji = "🟢" if pnl["total_pnl"] > 0 else ("🔴" if pnl["total_pnl"] < 0 else "⚪")
    currencies = pnl.get("currencies", [])
    cur_label = currencies[0] if len(currencies) == 1 else ""
    multi_note = ""
    if len(currencies) > 1:
        multi_note = f"\n⚠️ Multi-moneda ({', '.join(currencies)}): importes sumados sin conversión FX.\n"

    text = (
        f"📈 <b>Rendimiento total</b>\n\n"
        f"Posiciones: {pnl['num_positions']}{multi_note}\n"
        f"Coste total: {format_price(pnl['total_cost'], cur_label)}\n"
        f"Valor actual: {format_price(pnl['total_value'], cur_label)}\n\n"
        f"{emoji} <b>P&L no realizado: {pnl['unrealized_pnl']:+,.2f} {cur_label}</b>\n"
        f"P&L realizado: {pnl['realized_pnl']:+,.2f} {cur_label}\n"
        f"P&L total: {pnl['total_pnl']:+,.2f} {cur_label} ({pnl['pct']:+.1f}%)\n\n"
        f"<i>⚠️ {DISCLAIMER}</i>"
    )

    keyboard = [
        [InlineKeyboardButton("📊 Ver posiciones", callback_data="pf_positions")],
        [InlineKeyboardButton("◀️ Cartera", callback_data="menu_pf")],
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")


# ── ADD POSITION CONVERSATION ────────────────────────────────────

async def pf_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "➕ <b>Añadir posición</b>\n\nEscribe el ticker (ej: AAPL, SAN.MC):",
        parse_mode="HTML",
    )
    return PF_TICKER


async def pf_add_ticker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ticker = update.message.text.strip().upper()
    if not is_valid_ticker(ticker):
        await update.message.reply_text("❌ Ticker no válido. Inténtalo de nuevo o /cancel.")
        return PF_TICKER

    # Validate ticker exists
    q = get_quick_quote(ticker)
    if not q:
        await update.message.reply_text(f"❌ No se encontraron datos para {ticker}. Verifica el ticker.")
        return PF_TICKER

    context.user_data["pf_ticker"] = ticker
    context.user_data["pf_currency"] = q.get("currency", "EUR")
    await update.message.reply_text(
        f"✅ <b>{escape_html(ticker)}</b> ({escape_html(q.get('name', ticker))})\n"
        f"Precio actual: {format_price(q.get('price'), q.get('currency', 'USD'))}\n\n"
        f"¿Cuántas acciones tienes?",
        parse_mode="HTML",
    )
    return PF_SHARES


async def pf_add_shares(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        shares = float(update.message.text.strip().replace(",", "."))
        if shares <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Número no válido. Escribe una cantidad positiva.")
        return PF_SHARES

    context.user_data["pf_shares"] = shares
    await update.message.reply_text("💰 ¿A qué precio medio compraste? (por acción)")
    return PF_PRICE


async def pf_add_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        price = float(update.message.text.strip().replace(",", "."))
        if price <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Precio no válido. Escribe un número positivo.")
        return PF_PRICE

    user_id = update.effective_user.id
    ticker = context.user_data.get("pf_ticker")
    shares = context.user_data.get("pf_shares")
    currency = context.user_data.get("pf_currency", "EUR")

    session = get_session()
    try:
        pos = add_position(session, user_id, ticker, shares, price, currency)
        await update.message.reply_text(
            f"✅ Posición creada: <b>{escape_html(ticker)}</b>\n"
            f"{shares:.2f} acciones × {format_price(price, currency)}",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📊 Ver posiciones", callback_data="pf_positions")],
                [InlineKeyboardButton("◀️ Cartera", callback_data="menu_pf")],
            ]),
        )
    finally:
        session.close()
    return ConversationHandler.END


# ── BUY CONVERSATION ─────────────────────────────────────────────

async def pf_buy_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    session = get_session()
    try:
        positions = get_positions_for_selection(session, user_id)
    finally:
        session.close()

    if not positions:
        await query.edit_message_text(
            "No tienes posiciones. Añade una primero.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Añadir posición", callback_data="pf_add")],
            ]),
        )
        return ConversationHandler.END

    keyboard = [[InlineKeyboardButton(
        f"{p.ticker} ({p.shares:.2f})", callback_data=f"pfb_{p.id}",
    )] for p in positions]

    await query.edit_message_text(
        "💰 <b>Registrar compra</b>\n\nSelecciona la posición:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return PF_SELECT_BUY


async def pf_buy_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pos_id = int(query.data.split("_")[-1])
    context.user_data["pf_buy_pos_id"] = pos_id
    await query.edit_message_text("¿Cuántas acciones compraste?")
    return PF_BUY_SHARES


async def pf_buy_shares(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        shares = float(update.message.text.strip().replace(",", "."))
        if shares <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Número no válido.")
        return PF_BUY_SHARES

    context.user_data["pf_buy_shares"] = shares
    await update.message.reply_text("💰 ¿A qué precio?")
    return PF_BUY_PRICE


async def pf_buy_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        price = float(update.message.text.strip().replace(",", "."))
        if price <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Precio no válido.")
        return PF_BUY_PRICE

    user_id = update.effective_user.id
    pos_id = context.user_data.get("pf_buy_pos_id")
    shares = context.user_data.get("pf_buy_shares")

    session = get_session()
    try:
        pos = record_buy(session, user_id, pos_id, shares, price)
        if not pos:
            await update.message.reply_text("❌ Posición no encontrada.")
            return ConversationHandler.END

        await update.message.reply_text(
            f"✅ Compra registrada: +{shares:.2f} × {price:.2f}\n"
            f"Nuevo precio medio: {pos.avg_price:.2f} | Total: {pos.shares:.2f} acciones",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📊 Ver posiciones", callback_data="pf_positions")],
                [InlineKeyboardButton("◀️ Cartera", callback_data="menu_pf")],
            ]),
        )
    finally:
        session.close()
    return ConversationHandler.END


# ── SELL CONVERSATION ────────────────────────────────────────────

async def pf_sell_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    session = get_session()
    try:
        positions = get_positions_for_selection(session, user_id)
    finally:
        session.close()

    if not positions:
        await query.edit_message_text(
            "No tienes posiciones abiertas.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ Cartera", callback_data="menu_pf")],
            ]),
        )
        return ConversationHandler.END

    keyboard = [[InlineKeyboardButton(
        f"{p.ticker} ({p.shares:.2f})", callback_data=f"pfs_{p.id}",
    )] for p in positions]

    await query.edit_message_text(
        "💸 <b>Registrar venta</b>\n\nSelecciona la posición:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return PF_SELECT_SELL


async def pf_sell_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pos_id = int(query.data.split("_")[-1])
    context.user_data["pf_sell_pos_id"] = pos_id
    await query.edit_message_text("¿Cuántas acciones vendiste?")
    return PF_SELL_SHARES


async def pf_sell_shares(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        shares = float(update.message.text.strip().replace(",", "."))
        if shares <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Número no válido.")
        return PF_SELL_SHARES

    context.user_data["pf_sell_shares"] = shares
    await update.message.reply_text("💸 ¿A qué precio vendiste?")
    return PF_SELL_PRICE


async def pf_sell_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        price = float(update.message.text.strip().replace(",", "."))
        if price <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Precio no válido.")
        return PF_SELL_PRICE

    user_id = update.effective_user.id
    pos_id = context.user_data.get("pf_sell_pos_id")
    shares = context.user_data.get("pf_sell_shares")

    session = get_session()
    try:
        pos, err = record_sell(session, user_id, pos_id, shares, price)
        if err == "position_not_found":
            await update.message.reply_text("❌ Posición no encontrada.")
            return ConversationHandler.END
        if err == "insufficient_shares":
            await update.message.reply_text("❌ No tienes suficientes acciones para esta venta.")
            return ConversationHandler.END

        realized = (price - pos.avg_price) * shares
        emoji = "🟢" if realized > 0 else "🔴"
        await update.message.reply_text(
            f"✅ Venta registrada: -{shares:.2f} × {price:.2f}\n"
            f"{emoji} P&L realizado: {realized:+,.2f}\n"
            f"Quedan: {pos.shares:.2f} acciones",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📊 Ver posiciones", callback_data="pf_positions")],
                [InlineKeyboardButton("◀️ Cartera", callback_data="menu_pf")],
            ]),
        )
    finally:
        session.close()
    return ConversationHandler.END


# ── CANCEL ───────────────────────────────────────────────────────

async def _pf_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    if update.callback_query:
        await update.callback_query.answer()
    if update.message:
        await update.message.reply_text("Operación cancelada.")
    return ConversationHandler.END


# ── HANDLER REGISTRATION ─────────────────────────────────────────

def get_handlers():
    add_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(pf_add_start, pattern=r"^pf_add$"),
        ],
        states={
            PF_TICKER: [MessageHandler(filters.TEXT & ~filters.COMMAND, pf_add_ticker)],
            PF_SHARES: [MessageHandler(filters.TEXT & ~filters.COMMAND, pf_add_shares)],
            PF_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, pf_add_price)],
        },
        fallbacks=[
            CommandHandler("cancel", _pf_cancel),
            CallbackQueryHandler(_pf_cancel, pattern=r"^(back_menu|menu_)"),
        ],
        allow_reentry=True,
        per_message=False,
    )

    buy_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(pf_buy_start, pattern=r"^pf_buy$"),
        ],
        states={
            PF_SELECT_BUY: [CallbackQueryHandler(pf_buy_select, pattern=r"^pfb_\d+$")],
            PF_BUY_SHARES: [MessageHandler(filters.TEXT & ~filters.COMMAND, pf_buy_shares)],
            PF_BUY_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, pf_buy_price)],
        },
        fallbacks=[
            CommandHandler("cancel", _pf_cancel),
            CallbackQueryHandler(_pf_cancel, pattern=r"^(back_menu|menu_)"),
        ],
        allow_reentry=True,
        per_message=False,
    )

    sell_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(pf_sell_start, pattern=r"^pf_sell$"),
        ],
        states={
            PF_SELECT_SELL: [CallbackQueryHandler(pf_sell_select, pattern=r"^pfs_\d+$")],
            PF_SELL_SHARES: [MessageHandler(filters.TEXT & ~filters.COMMAND, pf_sell_shares)],
            PF_SELL_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, pf_sell_price)],
        },
        fallbacks=[
            CommandHandler("cancel", _pf_cancel),
            CallbackQueryHandler(_pf_cancel, pattern=r"^(back_menu|menu_)"),
        ],
        allow_reentry=True,
        per_message=False,
    )

    callbacks = [
        CallbackQueryHandler(portfolio_menu, pattern=r"^menu_pf$"),
        CallbackQueryHandler(pf_view_positions, pattern=r"^pf_positions$"),
        CallbackQueryHandler(pf_total_pnl, pattern=r"^pf_pnl$"),
    ]

    return [add_conv, buy_conv, sell_conv] + callbacks
