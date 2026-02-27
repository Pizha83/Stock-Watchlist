"""Tracking module: watchlists, companies, scoring, alerts, reporting."""

import csv
import io
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler,
    CallbackQueryHandler, MessageHandler, filters,
)
from sqlalchemy.orm import joinedload
from services.db import get_session
from services.models import Company, CompanyNote, Score, Alert, LinkCompanyArticle, Article
from services.tracking.company_profile import (
    create_company, get_company, get_all_companies, add_note, get_notes,
    link_article, delete_company,
)
from services.tracking.scoring import create_score, get_scores, get_latest_score, SCORING_CATEGORIES
from services.tracking.watchlist import (
    create_watchlist, get_watchlists, get_watchlist, add_to_watchlist,
    remove_from_watchlist, get_watchlist_items, delete_watchlist, export_watchlist_csv,
)
from services.tracking.alerts import (
    create_alert, get_active_alerts, deactivate_alert, get_weekly_summary,
)
from services.market_data.yahoo_finance import get_company_data, get_watchlist_quotes
from utils.text import escape_html, truncate, format_number, format_pct, format_ratio, format_price
from utils.dates import format_date, parse_date
from utils.validators import is_valid_ticker

logger = logging.getLogger("stockbot")

# Conversation states
WL_NAME, WL_TICKER, EMP_TICKER, NOTE_TEXT, SCORE_TEXT, ALERT_MSG, ALERT_DATE = range(7)


# ── MAIN MENU ────────────────────────────────────────────────────
async def trk_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()

    keyboard = [
        [InlineKeyboardButton("📋 Watchlists", callback_data="trk_wl")],
        [InlineKeyboardButton("🏢 Empresas", callback_data="trk_emp")],
        [InlineKeyboardButton("⭐ Scoring", callback_data="trk_scores")],
        [InlineKeyboardButton("🔔 Alertas", callback_data="trk_alerts")],
        [InlineKeyboardButton("📊 Resumen semanal", callback_data="trk_resumen")],
        [InlineKeyboardButton("◀️ Menú principal", callback_data="back_menu")],
    ]
    text = "📈 <b>Tracking</b>\n\nGestiona watchlists, empresas, scoring y alertas."
    markup = InlineKeyboardMarkup(keyboard)

    if query:
        await query.edit_message_text(text, reply_markup=markup, parse_mode="HTML")
    else:
        await update.message.reply_text(text, reply_markup=markup, parse_mode="HTML")


# ══════════════════════════════════════════════════════════════════
# WATCHLISTS
# ══════════════════════════════════════════════════════════════════
async def trk_wl_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    session = get_session()
    try:
        wls = get_watchlists(session, user_id)
        if not wls:
            text = "📋 <b>Watchlists</b>\n\nNo tienes watchlists. Crea una."
        else:
            text = "📋 <b>Tus Watchlists</b>\n\n"
            for wl in wls:
                items = get_watchlist_items(session, wl.id)
                text += f"• <b>{escape_html(wl.name)}</b> ({len(items)} empresas)\n"

        keyboard = [[InlineKeyboardButton(wl.name, callback_data=f"trk_wlv_{wl.id}")] for wl in wls]
        keyboard.append([InlineKeyboardButton("➕ Crear watchlist", callback_data="trk_wl_crear")])
        keyboard.append([InlineKeyboardButton("◀️ Volver", callback_data="menu_trk")])

        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    finally:
        session.close()


async def trk_wl_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    wl_id = int(query.data.split("_")[-1])

    session = get_session()
    try:
        wl = get_watchlist(session, wl_id)
        if not wl:
            await query.edit_message_text("❌ Watchlist no encontrada.")
            return

        items = get_watchlist_items(session, wl_id)
        text = f"📋 <b>{escape_html(wl.name)}</b>\n"
        text += f"Creada: {format_date(wl.created_at)}\n\n"

        if items:
            for item in items:
                c = item.company
                score = get_latest_score(session, c.id)
                score_str = f" | Score: {score.total}/5" if score else ""
                text += f"• <b>{escape_html(c.ticker)}</b> {escape_html(c.sector or '')}{score_str}\n"
                if item.notes:
                    text += f"  <i>{escape_html(truncate(item.notes, 60))}</i>\n"
        else:
            text += "Sin empresas. Añade un ticker."

        keyboard = []
        for item in items:
            keyboard.append([
                InlineKeyboardButton(f"🏢 {item.company.ticker}", callback_data=f"trk_empv_{item.company.id}"),
                InlineKeyboardButton("❌", callback_data=f"trk_wlrm_{wl_id}_{item.company.id}"),
            ])

        if items:
            keyboard.append([InlineKeyboardButton("📊 Precios en vivo", callback_data=f"trk_wlp_{wl_id}")])
        keyboard.append([InlineKeyboardButton("➕ Añadir ticker", callback_data=f"trk_wla_{wl_id}")])
        keyboard.append([
            InlineKeyboardButton("📥 Exportar CSV", callback_data=f"trk_wlx_{wl_id}"),
            InlineKeyboardButton("🗑️ Eliminar", callback_data=f"trk_wld_{wl_id}"),
        ])
        keyboard.append([InlineKeyboardButton("◀️ Volver", callback_data="trk_wl")])

        if len(text) > 4000:
            text = text[:3990] + "..."

        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    finally:
        session.close()


async def trk_wl_remove_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    wl_id = int(parts[-2])
    company_id = int(parts[-1])

    session = get_session()
    try:
        remove_from_watchlist(session, wl_id, company_id)
    finally:
        session.close()

    query.data = f"trk_wlv_{wl_id}"
    await trk_wl_detail(update, context)


async def trk_wl_export(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    wl_id = int(query.data.split("_")[-1])

    session = get_session()
    try:
        csv_str = export_watchlist_csv(session, wl_id)
        wl = get_watchlist(session, wl_id)
        name = wl.name if wl else "watchlist"
    finally:
        session.close()

    bio = io.BytesIO(csv_str.encode("utf-8-sig"))
    bio.name = f"{name}.csv"
    await query.message.reply_document(document=bio, filename=f"{name}.csv", caption=f"📥 Watchlist: {name}")


async def trk_wl_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("🗑️ Watchlist eliminada")
    wl_id = int(query.data.split("_")[-1])

    session = get_session()
    try:
        delete_watchlist(session, wl_id)
    finally:
        session.close()

    query.data = "trk_wl"
    await trk_wl_list(update, context)


# ── WL CREATE CONVERSATION ───────────────────────────────────────
async def trk_wl_crear_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("📋 Escribe el nombre de la nueva watchlist:")
    return WL_NAME


async def trk_wl_crear_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    user_id = update.effective_user.id

    session = get_session()
    try:
        wl = create_watchlist(session, name, user_id)
        await update.message.reply_text(
            f"✅ Watchlist '<b>{escape_html(name)}</b>' creada.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📋 Ver", callback_data=f"trk_wlv_{wl.id}")],
                [InlineKeyboardButton("◀️ Watchlists", callback_data="trk_wl")],
            ]),
        )
    finally:
        session.close()
    return ConversationHandler.END


# ── WL ADD TICKER CONVERSATION ───────────────────────────────────
async def trk_wl_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    wl_id = int(query.data.split("_")[-1])
    context.user_data["add_wl_id"] = wl_id
    await query.edit_message_text(
        "Escribe el ticker de la empresa a añadir:\n"
        "<i>(Si no existe, se creará automáticamente)</i>",
        parse_mode="HTML",
    )
    return WL_TICKER


async def trk_wl_add_ticker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ticker = update.message.text.strip().upper()
    wl_id = context.user_data.get("add_wl_id")

    if not is_valid_ticker(ticker):
        await update.message.reply_text("❌ Ticker no válido. Inténtalo de nuevo o /cancel.")
        return WL_TICKER

    session = get_session()
    try:
        from services.tracking.company_profile import get_company_by_ticker
        company = get_company_by_ticker(session, ticker)
        if not company:
            # Auto-fill profile from yfinance
            yf_data = get_company_data(ticker)
            extra = {}
            if yf_data:
                extra = {
                    k: yf_data[k]
                    for k in ("sector", "industry", "country", "currency", "exchange")
                    if yf_data.get(k)
                }
            company = create_company(session, ticker, **extra)

        add_to_watchlist(session, wl_id, company.id)
        await update.message.reply_text(
            f"✅ <b>{ticker}</b> añadido a la watchlist.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📋 Ver watchlist", callback_data=f"trk_wlv_{wl_id}")],
            ]),
        )
    finally:
        session.close()
    return ConversationHandler.END


# ══════════════════════════════════════════════════════════════════
# COMPANIES
# ══════════════════════════════════════════════════════════════════
async def trk_emp_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    session = get_session()
    try:
        companies = get_all_companies(session)
        if not companies:
            text = "🏢 <b>Empresas</b>\n\nNo hay empresas registradas."
        else:
            text = f"🏢 <b>Empresas</b> ({len(companies)})\n\n"
            for c in companies[:20]:
                text += f"• <b>{escape_html(c.ticker)}</b> {escape_html(c.sector or '')}\n"

        keyboard = []
        for c in companies[:20]:
            keyboard.append([InlineKeyboardButton(
                f"{c.ticker} - {c.sector or 'N/A'}", callback_data=f"trk_empv_{c.id}",
            )])
        keyboard.append([InlineKeyboardButton("➕ Añadir empresa", callback_data="trk_emp_add")])
        keyboard.append([InlineKeyboardButton("◀️ Volver", callback_data="menu_trk")])

        if len(text) > 4000:
            text = text[:3990] + "..."

        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    finally:
        session.close()


async def trk_emp_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    company_id = int(query.data.split("_")[-1])

    session = get_session()
    try:
        c = get_company(session, company_id)
        if not c:
            await query.edit_message_text("❌ Empresa no encontrada.")
            return

        text = f"🏢 <b>{escape_html(c.ticker)}</b>\n\n"
        text += f"Bolsa: {escape_html(c.exchange or 'N/A')}\n"
        text += f"País: {escape_html(c.country or 'N/A')}\n"
        text += f"Sector: {escape_html(c.sector or 'N/A')}\n"
        text += f"Industria: {escape_html(c.industry or 'N/A')}\n"
        text += f"Moneda: {escape_html(c.currency or 'N/A')}\n\n"

        # Notes
        for ntype, emoji, label in [("tesis", "📋", "Tesis"), ("catalizador", "🎯", "Catalizadores"), ("riesgo", "⚠️", "Riesgos")]:
            notes = get_notes(session, company_id, ntype)
            if notes:
                text += f"{emoji} <b>{label}:</b>\n"
                for n in notes[:3]:
                    text += f"  • {escape_html(truncate(n.content, 100))} <i>({format_date(n.created_at)})</i>\n"
                text += "\n"

        # Latest score
        score = get_latest_score(session, company_id)
        if score:
            text += (
                f"⭐ <b>Último scoring:</b> {score.total}/5\n"
                f"  Negocio:{score.business} Finanzas:{score.finances} "
                f"Valoración:{score.valuation} Riesgo:{score.risk} Management:{score.management}\n"
            )
            if score.comment:
                text += f"  <i>{escape_html(truncate(score.comment, 80))}</i>\n"
            text += "\n"

        # Linked articles
        links = session.query(LinkCompanyArticle).filter_by(company_id=company_id).all()
        if links:
            text += "📚 <b>Artículos vinculados:</b>\n"
            for lnk in links[:5]:
                a = session.query(Article).get(lnk.article_id)
                if a:
                    text += f"  • {escape_html(truncate(a.title, 50))}\n"

        if len(text) > 4000:
            text = text[:3990] + "..."

        keyboard = [
            [InlineKeyboardButton("📊 Datos de mercado", callback_data=f"trk_mkt_{c.id}")],
            [
                InlineKeyboardButton("📋 Tesis", callback_data=f"trk_ntt_{c.id}"),
                InlineKeyboardButton("🎯 Catalizador", callback_data=f"trk_ntc_{c.id}"),
                InlineKeyboardButton("⚠️ Riesgo", callback_data=f"trk_ntr_{c.id}"),
            ],
            [
                InlineKeyboardButton("⭐ Scoring", callback_data=f"trk_sca_{c.id}"),
                InlineKeyboardButton("📊 Ver scores", callback_data=f"trk_scv_{c.id}"),
            ],
            [InlineKeyboardButton("🗑️ Eliminar empresa", callback_data=f"trk_empd_{c.id}")],
            [InlineKeyboardButton("◀️ Volver", callback_data="trk_emp")],
        ]

        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    finally:
        session.close()


async def trk_emp_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("🗑️ Empresa eliminada")
    company_id = int(query.data.split("_")[-1])

    session = get_session()
    try:
        delete_company(session, company_id)
    finally:
        session.close()

    query.data = "trk_emp"
    await trk_emp_list(update, context)


# ── ADD COMPANY CONVERSATION ─────────────────────────────────────
async def trk_emp_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🏢 <b>Añadir empresa</b>\n\n"
        "Escribe el ticker (ej: AAPL, MSFT, SAN.MC):",
        parse_mode="HTML",
    )
    return EMP_TICKER


async def trk_emp_add_ticker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ticker = update.message.text.strip().upper()
    if not is_valid_ticker(ticker):
        await update.message.reply_text("❌ Ticker no válido. Inténtalo de nuevo o /cancel.")
        return EMP_TICKER

    session = get_session()
    try:
        from services.tracking.company_profile import get_company_by_ticker
        existing = get_company_by_ticker(session, ticker)
        if existing:
            await update.message.reply_text(
                f"ℹ️ <b>{ticker}</b> ya existe.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🏢 Ver", callback_data=f"trk_empv_{existing.id}")],
                ]),
            )
            return ConversationHandler.END

        # Auto-fill profile from yfinance
        yf_data = get_company_data(ticker)
        extra = {}
        if yf_data:
            extra = {
                k: yf_data[k]
                for k in ("sector", "industry", "country", "currency", "exchange")
                if yf_data.get(k)
            }
        company = create_company(session, ticker, **extra)
        filled = " (perfil auto-completado)" if extra else ""
        await update.message.reply_text(
            f"✅ Empresa <b>{ticker}</b> creada{filled}.\n"
            "Puedes añadir tesis, catalizadores y riesgos desde el detalle.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏢 Ver detalle", callback_data=f"trk_empv_{company.id}")],
                [InlineKeyboardButton("◀️ Empresas", callback_data="trk_emp")],
            ]),
        )
    finally:
        session.close()
    return ConversationHandler.END


# ── ADD NOTE CONVERSATIONS ───────────────────────────────────────
async def _note_start(update: Update, context: ContextTypes.DEFAULT_TYPE, note_type: str, emoji: str, label: str):
    query = update.callback_query
    await query.answer()
    company_id = int(query.data.split("_")[-1])
    context.user_data["note_company_id"] = company_id
    context.user_data["note_type"] = note_type
    await query.edit_message_text(f"{emoji} Escribe {label}:")
    return NOTE_TEXT


async def trk_note_thesis_start(update, context):
    return await _note_start(update, context, "tesis", "📋", "la tesis de inversión")


async def trk_note_catalyst_start(update, context):
    return await _note_start(update, context, "catalizador", "🎯", "el catalizador")


async def trk_note_risk_start(update, context):
    return await _note_start(update, context, "riesgo", "⚠️", "el riesgo identificado")


async def trk_note_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    company_id = context.user_data.get("note_company_id")
    note_type = context.user_data.get("note_type", "general")

    session = get_session()
    try:
        add_note(session, company_id, note_type, text)
        await update.message.reply_text(
            f"✅ Nota ({note_type}) guardada.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏢 Ver empresa", callback_data=f"trk_empv_{company_id}")],
            ]),
        )
    finally:
        session.close()
    return ConversationHandler.END


# ══════════════════════════════════════════════════════════════════
# SCORING
# ══════════════════════════════════════════════════════════════════
async def trk_scores_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    session = get_session()
    try:
        companies = get_all_companies(session)
        if not companies:
            await query.edit_message_text(
                "⭐ <b>Scoring</b>\n\nNo hay empresas. Añade una primero.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("◀️ Volver", callback_data="menu_trk")]]
                ),
            )
            return

        text = "⭐ <b>Scoring por empresa</b>\n\n"
        keyboard = []
        for c in companies[:20]:
            score = get_latest_score(session, c.id)
            label = f"{c.ticker}: {score.total}/5" if score else f"{c.ticker}: sin score"
            text += f"• {escape_html(label)}\n"
            keyboard.append([InlineKeyboardButton(label, callback_data=f"trk_scv_{c.id}")])

        keyboard.append([InlineKeyboardButton("◀️ Volver", callback_data="menu_trk")])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    finally:
        session.close()


async def trk_score_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    company_id = int(query.data.split("_")[-1])

    session = get_session()
    try:
        c = get_company(session, company_id)
        scores = get_scores(session, company_id)

        if not scores:
            text = f"⭐ <b>Scores: {escape_html(c.ticker)}</b>\n\nSin scoring todavía."
        else:
            text = f"⭐ <b>Scores: {escape_html(c.ticker)}</b>\n\n"
            for s in scores[:5]:
                text += (
                    f"📅 {format_date(s.created_at)} - <b>Total: {s.total}/5</b>\n"
                    f"  Negocio:{s.business} Finanzas:{s.finances} "
                    f"Valoración:{s.valuation} Riesgo:{s.risk} Mgmt:{s.management}\n"
                )
                if s.comment:
                    text += f"  <i>{escape_html(truncate(s.comment, 80))}</i>\n"
                text += "\n"

        keyboard = [
            [InlineKeyboardButton("➕ Nuevo scoring", callback_data=f"trk_sca_{company_id}")],
            [InlineKeyboardButton("◀️ Empresa", callback_data=f"trk_empv_{company_id}")],
        ]

        if len(text) > 4000:
            text = text[:3990] + "..."
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    finally:
        session.close()


# ── SCORING CONVERSATION ─────────────────────────────────────────
async def trk_score_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    company_id = int(query.data.split("_")[-1])
    context.user_data["score_company_id"] = company_id

    cats = "\n".join(f"  {i+1}. {label} - {desc}" for i, (_, label, desc) in enumerate(SCORING_CATEGORIES))
    await query.edit_message_text(
        f"⭐ <b>Nuevo Scoring</b>\n\n"
        f"Categorías (0-5):\n{cats}\n\n"
        "Escribe 5 números separados por comas y opcionalmente un comentario:\n"
        "<code>3,4,2,4,5 Buen negocio con margen de mejora</code>",
        parse_mode="HTML",
    )
    return SCORE_TEXT


async def trk_score_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    company_id = context.user_data.get("score_company_id")

    # Parse: "3,4,2,4,5 comment" or "3,4,2,4,5"
    parts = text.split(None, 1)
    scores_str = parts[0]
    comment = parts[1] if len(parts) > 1 else ""

    try:
        values = [float(x.strip()) for x in scores_str.split(",")]
        if len(values) != 5:
            raise ValueError("need 5 values")
        for v in values:
            if v < 0 or v > 5:
                raise ValueError("values must be 0-5")
    except (ValueError, IndexError):
        await update.message.reply_text(
            "❌ Formato incorrecto. Usa: <code>3,4,2,4,5 comentario</code>\n"
            "(5 números del 0 al 5 separados por comas)",
            parse_mode="HTML",
        )
        return SCORE_TEXT

    session = get_session()
    try:
        score = create_score(
            session, company_id,
            business=values[0], finances=values[1], valuation=values[2],
            risk=values[3], management=values[4], comment=comment,
        )
        await update.message.reply_text(
            f"✅ Scoring guardado: <b>{score.total}/5</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📊 Ver scores", callback_data=f"trk_scv_{company_id}")],
                [InlineKeyboardButton("🏢 Empresa", callback_data=f"trk_empv_{company_id}")],
            ]),
        )
    finally:
        session.close()
    return ConversationHandler.END


# ══════════════════════════════════════════════════════════════════
# ALERTS
# ══════════════════════════════════════════════════════════════════
async def trk_alerts_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    session = get_session()
    try:
        alerts = get_active_alerts(session, user_id)
        if not alerts:
            text = "🔔 <b>Alertas</b>\n\nNo tienes alertas activas."
        else:
            text = f"🔔 <b>Alertas activas</b> ({len(alerts)})\n\n"
            for a in alerts[:15]:
                company = f"[{a.company.ticker}] " if a.company else ""
                due = format_date(a.due_date) if a.due_date else "sin fecha"
                text += f"• {company}<b>{escape_html(truncate(a.message, 60))}</b>\n"
                text += f"  📅 {due} | Tipo: {a.alert_type}\n\n"

        keyboard = []
        for a in alerts[:10]:
            keyboard.append([InlineKeyboardButton(
                f"✅ Desactivar: {truncate(a.message, 25)}", callback_data=f"trk_ald_{a.id}",
            )])
        keyboard.append([InlineKeyboardButton("➕ Nueva alerta", callback_data="trk_alert_add")])
        keyboard.append([InlineKeyboardButton("◀️ Volver", callback_data="menu_trk")])

        if len(text) > 4000:
            text = text[:3990] + "..."
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    finally:
        session.close()


async def trk_alert_deactivate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("✅ Alerta desactivada")
    alert_id = int(query.data.split("_")[-1])

    session = get_session()
    try:
        deactivate_alert(session, alert_id)
    finally:
        session.close()

    query.data = "trk_alerts"
    await trk_alerts_list(update, context)


# ── ALERT CONVERSATION ───────────────────────────────────────────
async def trk_alert_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🔔 <b>Nueva alerta</b>\n\nEscribe el mensaje de la alerta:\n"
        "<i>(ej: Revisar earnings Q1 de AAPL)</i>",
        parse_mode="HTML",
    )
    return ALERT_MSG


async def trk_alert_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["alert_msg"] = update.message.text.strip()
    await update.message.reply_text(
        "📅 Escribe la fecha de la alerta (dd/mm/yyyy):\n"
        "<i>O escribe 'sin fecha' para alerta sin fecha</i>",
        parse_mode="HTML",
    )
    return ALERT_DATE


async def trk_alert_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    date_text = update.message.text.strip()
    user_id = update.effective_user.id
    msg = context.user_data.get("alert_msg", "")

    due_date = None
    if date_text.lower() not in ("sin fecha", "no", "-"):
        due_date = parse_date(date_text)
        if not due_date:
            await update.message.reply_text("❌ Fecha no válida. Usa dd/mm/yyyy o escribe 'sin fecha'.")
            return ALERT_DATE

    session = get_session()
    try:
        alert = create_alert(session, user_id, msg, due_date=due_date)
        date_str = format_date(due_date) if due_date else "sin fecha"
        await update.message.reply_text(
            f"✅ Alerta creada:\n{escape_html(msg)}\n📅 {date_str}",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔔 Ver alertas", callback_data="trk_alerts")],
                [InlineKeyboardButton("◀️ Tracking", callback_data="menu_trk")],
            ]),
        )
    finally:
        session.close()
    return ConversationHandler.END


# ══════════════════════════════════════════════════════════════════
# WEEKLY SUMMARY
# ══════════════════════════════════════════════════════════════════
async def trk_weekly_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    session = get_session()
    try:
        data = get_weekly_summary(session, user_id)

        text = "📊 <b>Resumen Semanal</b>\n\n"

        # Watchlists
        text += "📋 <b>Watchlists:</b>\n"
        if data["watchlists"]:
            for wl in data["watchlists"]:
                tickers = ", ".join(wl["tickers"][:5])
                text += f"  • {escape_html(wl['name'])} ({wl['count']}): {escape_html(tickers)}\n"
        else:
            text += "  Sin watchlists\n"
        text += "\n"

        # Upcoming alerts
        text += "🔔 <b>Alertas próximas (7 días):</b>\n"
        if data["upcoming_alerts"]:
            for a in data["upcoming_alerts"]:
                company = f"[{a.company.ticker}] " if a.company else ""
                text += f"  • {company}{escape_html(truncate(a.message, 50))} - {format_date(a.due_date)}\n"
        else:
            text += "  Sin alertas próximas\n"
        text += "\n"

        # Recent articles
        text += "📚 <b>Últimos artículos:</b>\n"
        if data["recent_articles"]:
            for a in data["recent_articles"]:
                text += f"  • {escape_html(truncate(a.title, 50))} ({a.language})\n"
        else:
            text += "  Sin artículos recientes\n"

        if len(text) > 4000:
            text = text[:3990] + "..."

        keyboard = [[InlineKeyboardButton("◀️ Volver", callback_data="menu_trk")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    finally:
        session.close()


# ══════════════════════════════════════════════════════════════════
# MARKET DATA
# ══════════════════════════════════════════════════════════════════
async def trk_market_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show comprehensive market data for a company."""
    query = update.callback_query
    await query.answer()
    company_id = int(query.data.split("_")[-1])

    session = get_session()
    try:
        c = get_company(session, company_id)
        if not c:
            await query.edit_message_text("❌ Empresa no encontrada.")
            return
        ticker = c.ticker
    finally:
        session.close()

    await query.edit_message_text(f"⏳ Obteniendo datos de <b>{escape_html(ticker)}</b>...", parse_mode="HTML")

    data = get_company_data(ticker)
    if not data:
        await query.edit_message_text(
            f"❌ No se encontraron datos para <b>{escape_html(ticker)}</b>.\n"
            "Verifica que el ticker sea correcto.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ Volver", callback_data=f"trk_empv_{company_id}")],
            ]),
        )
        return

    cur = data.get("currency", "USD")
    name = escape_html(data.get("name", ticker))

    # Build the message
    chg = data.get("change_pct", 0)
    chg_emoji = "🟢" if chg > 0 else ("🔴" if chg < 0 else "⚪")

    text = f"📊 <b>{name}</b> ({escape_html(ticker)})\n"
    text += f"{escape_html(data.get('sector', ''))} | {escape_html(data.get('industry', ''))}\n"
    text += f"🌍 {escape_html(data.get('country', ''))} | 🏛️ {escape_html(data.get('exchange', ''))}\n\n"

    # Price
    text += f"<b>💰 Precio</b>\n"
    text += f"  Actual: <b>{format_price(data.get('price'), cur)}</b> {chg_emoji} {chg:+.2f}%\n"
    text += f"  52s Alto: {format_price(data.get('high_52w'), cur)}\n"
    text += f"  52s Bajo: {format_price(data.get('low_52w'), cur)}\n"
    text += f"  Vol. medio: {format_number(data.get('avg_volume'))}\n\n"

    # Market & Valuation
    text += f"<b>📈 Mercado y Valoración</b>\n"
    text += f"  Market Cap: {format_number(data.get('market_cap'), cur)}\n"
    text += f"  EV: {format_number(data.get('enterprise_value'), cur)}\n"
    text += f"  P/E (TTM): {format_ratio(data.get('pe_trailing'))}\n"
    text += f"  P/E (Fwd): {format_ratio(data.get('pe_forward'))}\n"
    text += f"  EV/EBITDA: {format_ratio(data.get('ev_ebitda'))}\n"
    text += f"  EV/Revenue: {format_ratio(data.get('ev_revenue'))}\n"
    text += f"  P/B: {format_ratio(data.get('pb'))}\n"
    text += f"  P/S: {format_ratio(data.get('ps'))}\n\n"

    # Income
    text += f"<b>💵 Cuenta de resultados (TTM)</b>\n"
    text += f"  Revenue: {format_number(data.get('revenue'), cur)}\n"
    text += f"  Gross Profit: {format_number(data.get('gross_profit'), cur)}\n"
    text += f"  EBITDA: {format_number(data.get('ebitda'), cur)}\n"
    text += f"  Net Income: {format_number(data.get('net_income'), cur)}\n"
    text += f"  EPS (TTM): {format_price(data.get('eps'), cur)}\n"
    text += f"  EPS (Fwd): {format_price(data.get('forward_eps'), cur)}\n\n"

    # Margins
    text += f"<b>📊 Márgenes</b>\n"
    text += f"  Bruto: {format_pct(data.get('gross_margin'))}\n"
    text += f"  Operativo: {format_pct(data.get('operating_margin'))}\n"
    text += f"  Neto: {format_pct(data.get('net_margin'))}\n\n"

    # Profitability & Cash Flow
    text += f"<b>🏦 Rentabilidad y Cash Flow</b>\n"
    text += f"  ROE: {format_pct(data.get('roe'))}\n"
    text += f"  ROA: {format_pct(data.get('roa'))}\n"
    text += f"  FCF: {format_number(data.get('free_cash_flow'), cur)}\n"
    text += f"  Op. Cash Flow: {format_number(data.get('operating_cash_flow'), cur)}\n\n"

    # Debt
    text += f"<b>💳 Deuda</b>\n"
    text += f"  Deuda total: {format_number(data.get('total_debt'), cur)}\n"
    text += f"  Cash total: {format_number(data.get('total_cash'), cur)}\n"
    d2e = data.get("debt_to_equity")
    text += f"  Debt/Equity: {f'{d2e:.1f}%' if d2e else 'N/A'}\n\n"

    # Dividend
    div_yield = data.get("dividend_yield")
    if div_yield:
        text += f"<b>💸 Dividendo</b>\n"
        text += f"  Yield: {format_pct(div_yield)}\n"
        text += f"  Tasa: {format_price(data.get('dividend_rate'), cur)}\n"
        text += f"  Payout: {format_pct(data.get('payout_ratio'))}\n"
        text += f"  Ex-div: {data.get('ex_dividend_date', 'N/A')}\n\n"

    # Analyst
    rec = data.get("recommendation", "")
    if rec:
        text += f"<b>🎯 Analistas</b> ({data.get('num_analysts', 0)} opiniones)\n"
        text += f"  Recomendación: <b>{escape_html(rec.upper())}</b>\n"
        text += f"  Precio objetivo: {format_price(data.get('target_mean'), cur)}\n"
        text += f"  Rango: {format_price(data.get('target_low'), cur)} - {format_price(data.get('target_high'), cur)}\n"

    if len(text) > 4000:
        text = text[:3990] + "..."

    keyboard = [
        [InlineKeyboardButton("🔄 Actualizar", callback_data=f"trk_mkt_{company_id}")],
        [InlineKeyboardButton("◀️ Volver a empresa", callback_data=f"trk_empv_{company_id}")],
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")


async def trk_wl_prices(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show live price summary for all tickers in a watchlist."""
    query = update.callback_query
    await query.answer()
    wl_id = int(query.data.split("_")[-1])

    session = get_session()
    try:
        wl = get_watchlist(session, wl_id)
        if not wl:
            await query.edit_message_text("❌ Watchlist no encontrada.")
            return

        items = get_watchlist_items(session, wl_id)
        tickers = [item.company.ticker for item in items]
        wl_name = wl.name
    finally:
        session.close()

    if not tickers:
        await query.edit_message_text(
            "📊 Sin empresas en esta watchlist.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ Volver", callback_data=f"trk_wlv_{wl_id}")],
            ]),
        )
        return

    await query.edit_message_text(f"⏳ Obteniendo precios de {len(tickers)} empresas...")

    quotes = get_watchlist_quotes(tickers)

    text = f"📊 <b>Precios: {escape_html(wl_name)}</b>\n\n"

    for ticker in tickers:
        q = quotes.get(ticker)
        if not q:
            text += f"• <b>{escape_html(ticker)}</b>: sin datos\n"
            continue

        chg = q.get("change_pct", 0)
        chg_emoji = "🟢" if chg > 0 else ("🔴" if chg < 0 else "⚪")
        cur = q.get("currency", "USD")
        name = escape_html(q.get("name", ticker))

        text += (
            f"{chg_emoji} <b>{escape_html(ticker)}</b> "
            f"{format_price(q.get('price'), cur)} "
            f"({chg:+.2f}%)\n"
            f"   {name} | MCap: {format_number(q.get('market_cap'), cur)}"
        )
        pe = q.get("pe_trailing")
        if pe:
            text += f" | P/E: {format_ratio(pe)}"
        text += "\n\n"

    if len(text) > 4000:
        text = text[:3990] + "..."

    keyboard = [
        [InlineKeyboardButton("🔄 Actualizar", callback_data=f"trk_wlp_{wl_id}")],
        [InlineKeyboardButton("◀️ Volver a watchlist", callback_data=f"trk_wlv_{wl_id}")],
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")


# ── CANCEL ───────────────────────────────────────────────────────
async def _cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    if update.callback_query:
        await update.callback_query.answer()
    if update.message:
        await update.message.reply_text("Operación cancelada.")
    return ConversationHandler.END


# ── HANDLER REGISTRATION ────────────────────────────────────────
def get_handlers():
    conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(trk_wl_crear_start, pattern=r"^trk_wl_crear$"),
            CallbackQueryHandler(trk_wl_add_start, pattern=r"^trk_wla_\d+$"),
            CallbackQueryHandler(trk_emp_add_start, pattern=r"^trk_emp_add$"),
            CallbackQueryHandler(trk_note_thesis_start, pattern=r"^trk_ntt_\d+$"),
            CallbackQueryHandler(trk_note_catalyst_start, pattern=r"^trk_ntc_\d+$"),
            CallbackQueryHandler(trk_note_risk_start, pattern=r"^trk_ntr_\d+$"),
            CallbackQueryHandler(trk_score_start, pattern=r"^trk_sca_\d+$"),
            CallbackQueryHandler(trk_alert_start, pattern=r"^trk_alert_add$"),
        ],
        states={
            WL_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, trk_wl_crear_name)],
            WL_TICKER: [MessageHandler(filters.TEXT & ~filters.COMMAND, trk_wl_add_ticker)],
            EMP_TICKER: [MessageHandler(filters.TEXT & ~filters.COMMAND, trk_emp_add_ticker)],
            NOTE_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, trk_note_save)],
            SCORE_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, trk_score_save)],
            ALERT_MSG: [MessageHandler(filters.TEXT & ~filters.COMMAND, trk_alert_msg)],
            ALERT_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, trk_alert_date)],
        },
        fallbacks=[
            CommandHandler("cancel", _cancel),
            CallbackQueryHandler(_cancel, pattern=r"^(back_menu|menu_|cancel)"),
        ],
        allow_reentry=True,
        per_message=False,
    )

    callbacks = [
        CallbackQueryHandler(trk_menu, pattern=r"^menu_trk$"),
        # Watchlists
        CallbackQueryHandler(trk_wl_list, pattern=r"^trk_wl$"),
        CallbackQueryHandler(trk_wl_detail, pattern=r"^trk_wlv_\d+$"),
        CallbackQueryHandler(trk_wl_remove_item, pattern=r"^trk_wlrm_\d+_\d+$"),
        CallbackQueryHandler(trk_wl_export, pattern=r"^trk_wlx_\d+$"),
        CallbackQueryHandler(trk_wl_delete, pattern=r"^trk_wld_\d+$"),
        # Companies
        CallbackQueryHandler(trk_emp_list, pattern=r"^trk_emp$"),
        CallbackQueryHandler(trk_emp_detail, pattern=r"^trk_empv_\d+$"),
        CallbackQueryHandler(trk_emp_delete, pattern=r"^trk_empd_\d+$"),
        # Scoring
        CallbackQueryHandler(trk_scores_menu, pattern=r"^trk_scores$"),
        CallbackQueryHandler(trk_score_view, pattern=r"^trk_scv_\d+$"),
        # Market data
        CallbackQueryHandler(trk_market_data, pattern=r"^trk_mkt_\d+$"),
        CallbackQueryHandler(trk_wl_prices, pattern=r"^trk_wlp_\d+$"),
        # Alerts
        CallbackQueryHandler(trk_alerts_list, pattern=r"^trk_alerts$"),
        CallbackQueryHandler(trk_alert_deactivate, pattern=r"^trk_ald_\d+$"),
        # Summary
        CallbackQueryHandler(trk_weekly_summary, pattern=r"^trk_resumen$"),
    ]

    return [conv] + callbacks
