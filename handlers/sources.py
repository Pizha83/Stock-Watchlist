"""Sources directory handler."""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler,
    CallbackQueryHandler, MessageHandler, filters,
)
from services.db import get_session
from services.sources.sources_catalog import (
    REGIONS, SOURCE_TYPES, get_sources_by_region, get_sources_by_type,
    search_sources, get_source_detail, toggle_recommended, update_notes, add_source,
)
from utils.text import escape_html, truncate, safe_truncate_html
from config import ADMIN_USER_IDS

# Conversation states
SRC_SEARCH, SRC_NAME, SRC_URL, SRC_TYPE, SRC_NOTES = range(5)


# ── MENU ────────────────────────────────────────────────────────
async def src_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()

    keyboard = [
        [InlineKeyboardButton("🌍 Por región", callback_data="src_region")],
        [InlineKeyboardButton("📊 Por tipo de dato", callback_data="src_tipo")],
        [InlineKeyboardButton("🔍 Buscar fuente", callback_data="src_buscar")],
        [InlineKeyboardButton("➕ Sugerir fuente", callback_data="src_sugerir")],
        [InlineKeyboardButton("◀️ Menú principal", callback_data="back_menu")],
    ]
    text = "🌍 <b>Directorio de Fuentes</b>\n\nFuentes gratuitas para datos de mercados."
    markup = InlineKeyboardMarkup(keyboard)

    if query:
        await query.edit_message_text(text, reply_markup=markup, parse_mode="HTML")
    else:
        await update.message.reply_text(text, reply_markup=markup, parse_mode="HTML")


# ── BROWSE BY REGION ─────────────────────────────────────────────
async def src_by_region(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    keyboard = [[InlineKeyboardButton(label, callback_data=f"src_r_{key}")] for key, label in REGIONS.items()]
    keyboard.append([InlineKeyboardButton("◀️ Volver", callback_data="menu_src")])

    await query.edit_message_text(
        "🌍 Selecciona región:", reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def src_region_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    region = query.data[6:]

    session = get_session()
    try:
        sources = get_sources_by_region(session, region)
        label = REGIONS.get(region, region)

        if not sources:
            await query.edit_message_text(
                f"No hay fuentes para {escape_html(label)}.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("◀️ Volver", callback_data="src_region")]]
                ),
            )
            return

        text = f"🌍 <b>Fuentes: {escape_html(label)}</b>\n\n"
        keyboard = []
        for s in sources:
            rec = "⭐ " if s.is_recommended else ""
            text += f"• {rec}<b>{escape_html(s.name)}</b> [{escape_html(s.source_type)}]\n"
            keyboard.append([InlineKeyboardButton(f"{rec}{s.name}", callback_data=f"src_d_{s.id}")])

        keyboard.append([InlineKeyboardButton("◀️ Volver", callback_data="src_region")])
        if len(text) > 4000:
            text = safe_truncate_html(text)

        await query.edit_message_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML",
        )
    finally:
        session.close()


# ── BROWSE BY TYPE ───────────────────────────────────────────────
async def src_by_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    keyboard = [[InlineKeyboardButton(label, callback_data=f"src_tp_{key}")] for key, label in SOURCE_TYPES.items()]
    keyboard.append([InlineKeyboardButton("◀️ Volver", callback_data="menu_src")])

    await query.edit_message_text(
        "📊 Selecciona tipo de dato:", reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def src_type_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    stype = query.data[7:]

    session = get_session()
    try:
        sources = get_sources_by_type(session, stype)
        label = SOURCE_TYPES.get(stype, stype)

        if not sources:
            await query.edit_message_text(
                f"No hay fuentes de tipo {escape_html(label)}.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("◀️ Volver", callback_data="src_tipo")]]
                ),
            )
            return

        text = f"📊 <b>Fuentes: {escape_html(label)}</b>\n\n"
        keyboard = []
        for s in sources:
            rec = "⭐ " if s.is_recommended else ""
            text += f"• {rec}<b>{escape_html(s.name)}</b> [{escape_html(s.coverage)}]\n"
            keyboard.append([InlineKeyboardButton(f"{rec}{s.name}", callback_data=f"src_d_{s.id}")])

        keyboard.append([InlineKeyboardButton("◀️ Volver", callback_data="src_tipo")])
        if len(text) > 4000:
            text = safe_truncate_html(text)

        await query.edit_message_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML",
        )
    finally:
        session.close()


# ── SOURCE DETAIL ────────────────────────────────────────────────
async def src_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    source_id = int(query.data.split("_")[-1])

    session = get_session()
    try:
        s = get_source_detail(session, source_id)
        if not s:
            await query.edit_message_text("❌ Fuente no encontrada.")
            return

        rec = " ⭐ Recomendada" if s.is_recommended else ""
        ver = "✅ Verificada" if s.verified else "⚠️ Pendiente verificación"

        text = (
            f"📋 <b>{escape_html(s.name)}</b>{rec}\n\n"
            f"📊 Tipo: {escape_html(s.source_type)}\n"
            f"🌍 Cobertura: {escape_html(s.coverage)}\n"
            f"🔗 URL: {escape_html(s.url)}\n"
            f"🔑 Acceso: {escape_html(s.access_type)}\n"
            f"📈 Fiabilidad: {escape_html(s.reliability)}\n"
            f"{ver}\n\n"
            f"<b>Datos ofrecidos:</b>\n{escape_html(truncate(s.data_offered, 400))}\n\n"
            f"<b>Limitaciones:</b>\n{escape_html(s.limitations or 'N/A')}\n\n"
            f"<b>Notas:</b>\n{escape_html(s.notes or 'N/A')}"
        )
        if len(text) > 4000:
            text = safe_truncate_html(text)

        fav_label = "💔 Quitar recomendada" if s.is_recommended else "⭐ Recomendar"
        keyboard = [[InlineKeyboardButton(fav_label, callback_data=f"src_rec_{s.id}")]]

        if update.effective_user.id in ADMIN_USER_IDS:
            keyboard.append([InlineKeyboardButton("✏️ Editar notas", callback_data=f"src_edit_{s.id}")])

        keyboard.append([InlineKeyboardButton("◀️ Volver", callback_data="menu_src")])

        await query.edit_message_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML", disable_web_page_preview=True,
        )
    finally:
        session.close()


async def src_recommend(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    source_id = int(query.data.split("_")[-1])

    session = get_session()
    try:
        toggle_recommended(session, source_id)
        await query.answer("⭐ Actualizado")
    finally:
        session.close()

    query.data = f"src_d_{source_id}"
    await src_detail(update, context)


# ── SEARCH CONVERSATION ─────────────────────────────────────────
async def src_search_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🔍 Escribe el nombre o tipo de fuente a buscar:")
    return SRC_SEARCH


async def src_handle_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query_text = update.message.text.strip()
    session = get_session()
    try:
        sources = search_sources(session, query_text)
        if not sources:
            await update.message.reply_text(
                f"No se encontraron fuentes para '{escape_html(query_text)}'.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("◀️ Volver", callback_data="menu_src")]]
                ),
            )
            return ConversationHandler.END

        text = f"🔍 Resultados para '<b>{escape_html(query_text)}</b>':\n\n"
        keyboard = []
        for s in sources:
            text += f"• <b>{escape_html(s.name)}</b> [{escape_html(s.source_type)}]\n"
            keyboard.append([InlineKeyboardButton(s.name, callback_data=f"src_d_{s.id}")])

        keyboard.append([InlineKeyboardButton("◀️ Volver", callback_data="menu_src")])
        await update.message.reply_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML",
        )
    finally:
        session.close()
    return ConversationHandler.END


# ── SUGGEST CONVERSATION ─────────────────────────────────────────
async def src_suggest_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "➕ <b>Sugerir nueva fuente</b>\n\nEscribe el nombre de la fuente:",
        parse_mode="HTML",
    )
    return SRC_NAME


async def src_handle_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_src_name"] = update.message.text.strip()
    await update.message.reply_text("Escribe la URL de la fuente:")
    return SRC_URL


async def src_handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_src_url"] = update.message.text.strip()
    keyboard = [[InlineKeyboardButton(label, callback_data=f"src_st_{key}")] for key, label in SOURCE_TYPES.items()]
    await update.message.reply_text(
        "Selecciona el tipo de fuente:", reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return SRC_TYPE


async def src_handle_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    stype = query.data[7:]

    name = context.user_data.get("new_src_name", "")
    url = context.user_data.get("new_src_url", "")

    session = get_session()
    try:
        add_source(
            session, name=name, url=url, source_type=stype,
            coverage="", data_offered="", access_type="web",
            verified=False, notes="Sugerida por usuario",
        )
        await query.edit_message_text(
            f"✅ Fuente sugerida: <b>{escape_html(name)}</b>\nPendiente de verificación.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("◀️ Volver", callback_data="menu_src")]]
            ),
        )
    finally:
        session.close()
    return ConversationHandler.END


# ── EDIT NOTES CONVERSATION ──────────────────────────────────────
async def src_edit_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    source_id = int(query.data.split("_")[-1])
    context.user_data["edit_source_id"] = source_id
    await query.edit_message_text("✏️ Escribe las nuevas notas para esta fuente:")
    return SRC_NOTES


async def src_handle_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    source_id = context.user_data.get("edit_source_id")
    notes = update.message.text.strip()

    session = get_session()
    try:
        update_notes(session, source_id, notes)
        await update.message.reply_text(
            "✅ Notas actualizadas.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("📋 Ver fuente", callback_data=f"src_d_{source_id}")]]
            ),
        )
    finally:
        session.close()
    return ConversationHandler.END


# ── CANCEL ───────────────────────────────────────────────────────
async def _cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    if update.callback_query:
        await update.callback_query.answer()
    return ConversationHandler.END


# ── HANDLER REGISTRATION ────────────────────────────────────────
def get_handlers():
    search_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(src_search_start, pattern=r"^src_buscar$")],
        states={SRC_SEARCH: [MessageHandler(filters.TEXT & ~filters.COMMAND, src_handle_search)]},
        fallbacks=[
            CommandHandler("cancel", _cancel),
            CallbackQueryHandler(_cancel, pattern=r"^(back_menu|menu_|cancel)"),
        ],
        allow_reentry=True,
    )

    suggest_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(src_suggest_start, pattern=r"^src_sugerir$")],
        states={
            SRC_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, src_handle_name)],
            SRC_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, src_handle_url)],
            SRC_TYPE: [CallbackQueryHandler(src_handle_type, pattern=r"^src_st_")],
        },
        fallbacks=[
            CommandHandler("cancel", _cancel),
            CallbackQueryHandler(_cancel, pattern=r"^(back_menu|menu_|cancel)"),
        ],
        allow_reentry=True,
    )

    edit_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(src_edit_start, pattern=r"^src_edit_\d+$")],
        states={SRC_NOTES: [MessageHandler(filters.TEXT & ~filters.COMMAND, src_handle_notes)]},
        fallbacks=[
            CommandHandler("cancel", _cancel),
            CallbackQueryHandler(_cancel, pattern=r"^(back_menu|menu_|cancel)"),
        ],
        allow_reentry=True,
    )

    callbacks = [
        CallbackQueryHandler(src_menu, pattern=r"^menu_src$"),
        CallbackQueryHandler(src_by_region, pattern=r"^src_region$"),
        CallbackQueryHandler(src_region_select, pattern=r"^src_r_"),
        CallbackQueryHandler(src_by_type, pattern=r"^src_tipo$"),
        CallbackQueryHandler(src_type_select, pattern=r"^src_tp_"),
        CallbackQueryHandler(src_detail, pattern=r"^src_d_\d+$"),
        CallbackQueryHandler(src_recommend, pattern=r"^src_rec_\d+$"),
    ]

    return [search_conv, suggest_conv, edit_conv] + callbacks
