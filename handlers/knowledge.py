"""Knowledge module: articles, search, library, tagging."""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler,
    CallbackQueryHandler, MessageHandler, filters,
)
from sqlalchemy.orm import joinedload
from services.db import get_session
from services.models import Article, ArticleTag, Company
from services.knowledge.article_fetcher import fetch_article_content
from services.knowledge.article_search import search_web, has_search_provider
from services.knowledge.article_summarizer import summarize_text
from services.knowledge.article_tagger import auto_tag, get_all_tags
from services.tracking.company_profile import link_article
from utils.text import escape_html, truncate
from utils.validators import is_valid_url
from utils.dates import format_date
from config import ITEMS_PER_PAGE

logger = logging.getLogger("stockbot")

# Conversation states
TOPIC, LANG, URL_INPUT, LIB_SEARCH = range(4)


# ── MENU ────────────────────────────────────────────────────────
async def kb_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()

    keyboard = [
        [InlineKeyboardButton("🔍 Buscar artículos", callback_data="kb_buscar")],
        [InlineKeyboardButton("📖 Ver biblioteca", callback_data="kb_bib")],
        [InlineKeyboardButton("➕ Añadir por URL", callback_data="kb_add_url")],
        [InlineKeyboardButton("🔄 Actualizar resúmenes", callback_data="kb_refresh")],
        [InlineKeyboardButton("◀️ Menú principal", callback_data="back_menu")],
    ]
    text = "📚 <b>Base de Conocimiento</b>\n\nGestiona artículos y guías sobre inversión."
    markup = InlineKeyboardMarkup(keyboard)

    if query:
        await query.edit_message_text(text, reply_markup=markup, parse_mode="HTML")
    else:
        await update.message.reply_text(text, reply_markup=markup, parse_mode="HTML")


# ── SEARCH CONVERSATION ─────────────────────────────────────────
async def kb_buscar_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not has_search_provider():
        keyboard = [
            [InlineKeyboardButton("➕ Añadir por URL", callback_data="kb_add_url")],
            [InlineKeyboardButton("◀️ Volver", callback_data="menu_kb")],
        ]
        await query.edit_message_text(
            "⚠️ <b>Sin proveedor de búsqueda</b>\n\n"
            "Configura <code>SERPAPI_KEY</code> en las variables de entorno "
            "para activar la búsqueda automática.\n\n"
            "Mientras tanto, puedes añadir artículos manualmente por URL.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML",
        )
        return ConversationHandler.END

    await query.edit_message_text(
        "🔍 <b>Buscar artículos</b>\n\n"
        "Escribe el tema que quieres buscar:\n"
        "<i>(ej: análisis fundamental, DCF, ROIC, SaaS metrics)</i>",
        parse_mode="HTML",
    )
    return TOPIC


async def kb_handle_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["search_topic"] = update.message.text
    keyboard = [
        [
            InlineKeyboardButton("🇪🇸 Español", callback_data="kb_lang_es"),
            InlineKeyboardButton("🇬🇧 English", callback_data="kb_lang_en"),
        ],
        [InlineKeyboardButton("🌍 Ambos", callback_data="kb_lang_both")],
    ]
    await update.message.reply_text(
        "Selecciona idioma de búsqueda:", reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return LANG


async def kb_handle_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang_code = query.data.split("_")[-1]
    topic = context.user_data.get("search_topic", "")

    await query.edit_message_text("🔄 Buscando...")
    lang = "es" if lang_code in ("es", "both") else "en"
    results = search_web(topic, lang, 10)

    if not results:
        await query.edit_message_text(
            "No se encontraron resultados.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("◀️ Volver", callback_data="menu_kb")]]
            ),
        )
        return ConversationHandler.END

    context.user_data["search_results"] = results
    text = f"🔍 Resultados para '<b>{escape_html(topic)}</b>':\n\n"
    keyboard = []
    for i, r in enumerate(results[:10]):
        text += f"{i + 1}. {escape_html(truncate(r['title'], 60))}\n"
        text += f"   <i>{escape_html(truncate(r.get('snippet', ''), 80))}</i>\n\n"
        keyboard.append([InlineKeyboardButton(f"💾 Guardar #{i + 1}", callback_data=f"kb_save_{i}")])

    keyboard.append([InlineKeyboardButton("◀️ Volver", callback_data="menu_kb")])

    if len(text) > 4000:
        text = text[:3990] + "..."

    await query.edit_message_text(
        text, reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML", disable_web_page_preview=True,
    )
    return ConversationHandler.END


# ── ADD URL CONVERSATION ─────────────────────────────────────────
async def kb_add_url_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "➕ <b>Añadir artículo por URL</b>\n\nPega la URL del artículo:",
        parse_mode="HTML",
    )
    return URL_INPUT


async def kb_handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if not is_valid_url(url):
        await update.message.reply_text(
            "❌ URL no válida. Inténtalo de nuevo o envía /cancel."
        )
        return URL_INPUT

    await update.message.reply_text("🔄 Extrayendo contenido...")

    result = fetch_article_content(url)
    if not result:
        await update.message.reply_text(
            "❌ No se pudo extraer contenido de esa URL.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("◀️ Volver", callback_data="menu_kb")]]
            ),
        )
        return ConversationHandler.END

    session = get_session()
    try:
        existing = session.query(Article).filter(Article.url == url).first()
        if existing:
            await update.message.reply_text(
                f"ℹ️ Este artículo ya existe: <b>{escape_html(existing.title)}</b>",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📄 Ver", callback_data=f"kb_det_{existing.id}")],
                    [InlineKeyboardButton("◀️ Volver", callback_data="menu_kb")],
                ]),
            )
            return ConversationHandler.END

        lang = _detect_language(result["text"])
        tags = auto_tag(result["text"], result["title"])
        summary = summarize_text(result["text"])

        article = Article(
            title=result["title"], url=url, publish_date=result["publish_date"],
            language=lang, source_domain=result["domain"],
            summary=summary, full_text=result["text"],
        )
        session.add(article)
        session.flush()
        for tag in tags:
            session.add(ArticleTag(article_id=article.id, tag=tag))
        session.commit()
        article_id = article.id

        tags_str = ", ".join(tags) if tags else "ninguno"
        await update.message.reply_text(
            f"✅ <b>Artículo guardado</b>\n\n"
            f"📄 {escape_html(result['title'])}\n"
            f"🌐 {escape_html(result['domain'])}\n"
            f"🏷️ Tags: {escape_html(tags_str)}\n"
            f"🗣️ Idioma: {lang}\n\n"
            f"<i>{escape_html(truncate(summary, 300))}</i>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📄 Ver detalle", callback_data=f"kb_det_{article_id}")],
                [InlineKeyboardButton("◀️ Biblioteca", callback_data="kb_bib")],
            ]),
        )
    finally:
        session.close()

    return ConversationHandler.END


# ── LIBRARY SEARCH CONVERSATION ──────────────────────────────────
async def kb_lib_search_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🔍 Escribe el texto a buscar en la biblioteca:")
    return LIB_SEARCH


async def kb_handle_lib_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query_text = update.message.text.strip()
    session = get_session()
    try:
        q = f"%{query_text}%"
        articles = (
            session.query(Article)
            .options(joinedload(Article.tags))
            .filter(
                (Article.title.ilike(q)) | (Article.summary.ilike(q))
            )
            .order_by(Article.ingested_at.desc())
            .all()
        )
        context.user_data["lib_ids"] = [a.id for a in articles]
        await _show_library_page(
            update.message, session, [a.id for a in articles], 0,
            f"Resultados para '{escape_html(query_text)}'",
        )
    finally:
        session.close()
    return ConversationHandler.END


# ── LIBRARY BROWSING ─────────────────────────────────────────────
async def kb_biblioteca(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    session = get_session()
    try:
        articles = (
            session.query(Article)
            .options(joinedload(Article.tags))
            .order_by(Article.ingested_at.desc())
            .all()
        )
        context.user_data["lib_ids"] = [a.id for a in articles]
        await _show_library_page(query, session, [a.id for a in articles], 0, "Todos los artículos")
    finally:
        session.close()


async def _show_library_page(target, session, article_ids, page, title):
    """Render a paginated library page."""
    per_page = ITEMS_PER_PAGE
    start = page * per_page
    page_ids = article_ids[start: start + per_page]
    total = len(article_ids)
    total_pages = max(1, (total + per_page - 1) // per_page)

    articles = (
        session.query(Article)
        .options(joinedload(Article.tags))
        .filter(Article.id.in_(page_ids))
        .order_by(Article.ingested_at.desc())
        .all()
    )

    if not article_ids:
        text = f"📖 <b>{title}</b>\n\nNo hay artículos."
    else:
        text = f"📖 <b>{title}</b> ({total} artículos)\n"
        text += f"Página {page + 1}/{total_pages}\n\n"
        for a in articles:
            fav = "⭐" if a.is_favorite else ""
            tags = ", ".join(t.tag for t in a.tags[:3]) if a.tags else ""
            text += f"{fav}📄 <b>{escape_html(truncate(a.title, 50))}</b>\n"
            text += f"   {a.language or '?'} | {escape_html(a.source_domain or '')} | {escape_html(tags)}\n\n"

    keyboard = []
    for a in articles:
        keyboard.append([InlineKeyboardButton(
            f"📄 {truncate(a.title, 35)}", callback_data=f"kb_det_{a.id}",
        )])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Anterior", callback_data=f"kb_pg_{page - 1}"))
    if start + per_page < total:
        nav.append(InlineKeyboardButton("Siguiente ➡️", callback_data=f"kb_pg_{page + 1}"))
    if nav:
        keyboard.append(nav)

    keyboard.append([
        InlineKeyboardButton("🏷️ Tag", callback_data="kb_f_tag"),
        InlineKeyboardButton("🗣️ Idioma", callback_data="kb_f_lang"),
        InlineKeyboardButton("🔍 Buscar", callback_data="kb_f_search"),
    ])
    keyboard.append([InlineKeyboardButton("◀️ Volver", callback_data="menu_kb")])

    if len(text) > 4000:
        text = text[:3990] + "..."

    markup = InlineKeyboardMarkup(keyboard)
    if hasattr(target, "edit_message_text"):
        await target.edit_message_text(text, reply_markup=markup, parse_mode="HTML")
    else:
        await target.reply_text(text, reply_markup=markup, parse_mode="HTML")


async def kb_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    page = int(query.data.split("_")[-1])
    article_ids = context.user_data.get("lib_ids", [])

    session = get_session()
    try:
        await _show_library_page(query, session, article_ids, page, "Biblioteca")
    finally:
        session.close()


# ── FILTERS ──────────────────────────────────────────────────────
async def kb_filter_tag(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    tags = get_all_tags()
    keyboard = []
    row = []
    for tag in tags:
        row.append(InlineKeyboardButton(tag, callback_data=f"kb_t_{tag[:20]}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("◀️ Volver", callback_data="kb_bib")])

    await query.edit_message_text(
        "🏷️ Selecciona un tag para filtrar:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def kb_tag_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tag = query.data[5:]  # Remove "kb_t_"

    session = get_session()
    try:
        articles = (
            session.query(Article)
            .options(joinedload(Article.tags))
            .join(ArticleTag)
            .filter(ArticleTag.tag.ilike(f"%{tag}%"))
            .order_by(Article.ingested_at.desc())
            .all()
        )
        context.user_data["lib_ids"] = [a.id for a in articles]
        await _show_library_page(query, session, [a.id for a in articles], 0, f"Tag: {tag}")
    finally:
        session.close()


async def kb_filter_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    keyboard = [
        [InlineKeyboardButton("🇪🇸 Español", callback_data="kb_fl_ES")],
        [InlineKeyboardButton("🇬🇧 English", callback_data="kb_fl_EN")],
        [InlineKeyboardButton("◀️ Volver", callback_data="kb_bib")],
    ]
    await query.edit_message_text(
        "🗣️ Filtrar por idioma:", reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def kb_lang_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = query.data.split("_")[-1]

    session = get_session()
    try:
        articles = (
            session.query(Article)
            .options(joinedload(Article.tags))
            .filter(Article.language == lang)
            .order_by(Article.ingested_at.desc())
            .all()
        )
        context.user_data["lib_ids"] = [a.id for a in articles]
        await _show_library_page(query, session, [a.id for a in articles], 0, f"Idioma: {lang}")
    finally:
        session.close()


# ── ARTICLE DETAIL ───────────────────────────────────────────────
async def kb_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    article_id = int(query.data.split("_")[-1])

    session = get_session()
    try:
        article = (
            session.query(Article)
            .options(joinedload(Article.tags))
            .get(article_id)
        )
        if not article:
            await query.edit_message_text("❌ Artículo no encontrado.")
            return

        fav = " ⭐" if article.is_favorite else ""
        tags = ", ".join(t.tag for t in article.tags) if article.tags else "sin tags"

        text = (
            f"📄 <b>{escape_html(article.title)}</b>{fav}\n\n"
            f"🔗 {escape_html(article.url)}\n"
            f"🌐 {escape_html(article.source_domain or '')}\n"
            f"📅 Publicado: {escape_html(article.publish_date or 'N/A')}\n"
            f"🗣️ Idioma: {article.language or '?'}\n"
            f"🏷️ Tags: {escape_html(tags)}\n"
            f"📥 Ingesta: {format_date(article.ingested_at)}\n\n"
            f"📋 <b>Resumen:</b>\n{escape_html(truncate(article.summary or '', 800))}"
        )
        if len(text) > 4000:
            text = text[:3990] + "..."

        fav_label = "💔 Quitar favorito" if article.is_favorite else "⭐ Favorito"
        keyboard = [
            [
                InlineKeyboardButton(fav_label, callback_data=f"kb_fav_{article.id}"),
                InlineKeyboardButton("🔄 Re-resumir", callback_data=f"kb_res_{article.id}"),
            ],
            [InlineKeyboardButton("🏢 Asignar a empresa", callback_data=f"kb_asgn_{article.id}")],
            [InlineKeyboardButton("◀️ Biblioteca", callback_data="kb_bib")],
        ]

        await query.edit_message_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML", disable_web_page_preview=True,
        )
    finally:
        session.close()


async def kb_favorite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    article_id = int(query.data.split("_")[-1])

    session = get_session()
    try:
        article = session.query(Article).get(article_id)
        if article:
            article.is_favorite = not article.is_favorite
            session.commit()
            status = "añadido a" if article.is_favorite else "quitado de"
            await query.answer(f"⭐ {status} favoritos")
    finally:
        session.close()

    # Refresh detail
    query.data = f"kb_det_{article_id}"
    await kb_detail(update, context)


async def kb_resummarize(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("🔄 Regenerando resumen...")
    article_id = int(query.data.split("_")[-1])

    session = get_session()
    try:
        article = session.query(Article).get(article_id)
        if article and article.full_text:
            article.summary = summarize_text(article.full_text)
            session.commit()
    finally:
        session.close()

    query.data = f"kb_det_{article_id}"
    await kb_detail(update, context)


async def kb_assign(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    article_id = int(query.data.split("_")[-1])
    context.user_data["assign_article_id"] = article_id

    session = get_session()
    try:
        companies = session.query(Company).order_by(Company.ticker).all()
        if not companies:
            await query.edit_message_text(
                "No hay empresas registradas.\nPrimero añade una en 📈 Tracking.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("◀️ Volver", callback_data=f"kb_det_{article_id}")]
                ]),
            )
            return

        keyboard = []
        for c in companies[:20]:
            keyboard.append([InlineKeyboardButton(
                f"{c.ticker} - {c.sector or 'N/A'}",
                callback_data=f"kb_ac_{c.id}",
            )])
        keyboard.append([InlineKeyboardButton("◀️ Volver", callback_data=f"kb_det_{article_id}")])

        await query.edit_message_text(
            "🏢 Selecciona empresa para asignar:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    finally:
        session.close()


async def kb_assign_company(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    company_id = int(query.data.split("_")[-1])
    article_id = context.user_data.get("assign_article_id")

    if article_id:
        session = get_session()
        try:
            link_article(session, company_id, article_id)
        finally:
            session.close()
        await query.answer("✅ Artículo asignado")
    else:
        await query.answer("❌ Error")
        return

    query.data = f"kb_det_{article_id}"
    await kb_detail(update, context)


async def kb_save_search_result(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    idx = int(query.data.split("_")[-1])
    results = context.user_data.get("search_results", [])

    if idx >= len(results):
        await query.answer("❌ Resultado no encontrado")
        return

    await query.answer("🔄 Descargando...")
    r = results[idx]
    content = fetch_article_content(r["url"])
    if not content:
        await query.answer("❌ No se pudo extraer")
        return

    session = get_session()
    try:
        existing = session.query(Article).filter(Article.url == r["url"]).first()
        if existing:
            await query.answer("ℹ️ Ya existe en biblioteca")
            return

        lang = _detect_language(content["text"])
        tags = auto_tag(content["text"], content["title"])
        summary = summarize_text(content["text"])

        article = Article(
            title=content["title"], url=r["url"],
            publish_date=content["publish_date"], language=lang,
            source_domain=content["domain"], summary=summary,
            full_text=content["text"],
        )
        session.add(article)
        session.flush()
        for tag in tags:
            session.add(ArticleTag(article_id=article.id, tag=tag))
        session.commit()
        await query.answer(f"✅ Guardado")
    finally:
        session.close()


async def kb_refresh_summaries(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("🔄 Actualizando...")

    session = get_session()
    try:
        articles = session.query(Article).filter(
            (Article.summary == "") | (Article.summary == None)
        ).all()

        count = 0
        for article in articles:
            if article.full_text:
                article.summary = summarize_text(article.full_text)
                count += 1
        session.commit()

        await query.edit_message_text(
            f"✅ Resúmenes actualizados: {count} artículos.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("◀️ Volver", callback_data="menu_kb")]]
            ),
        )
    finally:
        session.close()


# ── UTILS ────────────────────────────────────────────────────────
def _detect_language(text: str) -> str:
    es_words = {"que", "los", "las", "del", "para", "con", "una", "por", "como", "más", "pero"}
    words = text[:500].lower().split()
    es_count = sum(1 for w in words if w in es_words)
    return "ES" if es_count > 3 else "EN"


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
            CallbackQueryHandler(kb_buscar_start, pattern=r"^kb_buscar$"),
            CallbackQueryHandler(kb_add_url_start, pattern=r"^kb_add_url$"),
            CallbackQueryHandler(kb_lib_search_start, pattern=r"^kb_f_search$"),
        ],
        states={
            TOPIC: [MessageHandler(filters.TEXT & ~filters.COMMAND, kb_handle_topic)],
            LANG: [CallbackQueryHandler(kb_handle_lang, pattern=r"^kb_lang_")],
            URL_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, kb_handle_url)],
            LIB_SEARCH: [MessageHandler(filters.TEXT & ~filters.COMMAND, kb_handle_lib_search)],
        },
        fallbacks=[
            CommandHandler("cancel", _cancel),
            CallbackQueryHandler(_cancel, pattern=r"^(back_menu|menu_|cancel)"),
        ],
        allow_reentry=True,
        per_message=False,
    )

    callbacks = [
        CallbackQueryHandler(kb_menu, pattern=r"^menu_kb$"),
        CallbackQueryHandler(kb_biblioteca, pattern=r"^kb_bib$"),
        CallbackQueryHandler(kb_page, pattern=r"^kb_pg_\d+$"),
        CallbackQueryHandler(kb_detail, pattern=r"^kb_det_\d+$"),
        CallbackQueryHandler(kb_favorite, pattern=r"^kb_fav_\d+$"),
        CallbackQueryHandler(kb_resummarize, pattern=r"^kb_res_\d+$"),
        CallbackQueryHandler(kb_assign, pattern=r"^kb_asgn_\d+$"),
        CallbackQueryHandler(kb_assign_company, pattern=r"^kb_ac_\d+$"),
        CallbackQueryHandler(kb_save_search_result, pattern=r"^kb_save_\d+$"),
        CallbackQueryHandler(kb_refresh_summaries, pattern=r"^kb_refresh$"),
        CallbackQueryHandler(kb_filter_tag, pattern=r"^kb_f_tag$"),
        CallbackQueryHandler(kb_filter_lang, pattern=r"^kb_f_lang$"),
        CallbackQueryHandler(kb_tag_select, pattern=r"^kb_t_"),
        CallbackQueryHandler(kb_lang_select, pattern=r"^kb_fl_"),
    ]

    return [conv] + callbacks
