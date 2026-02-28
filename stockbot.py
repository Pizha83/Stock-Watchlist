"""Stock Research & Tracking Telegram Bot - Entry point."""

import logging
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, InlineQueryHandler,
)
from config import TELEGRAM_BOT_TOKEN
from services.db import init_db, get_session
from services.sources.sources_seed import seed_sources
from utils.logging import setup_logging

from handlers.start import start, back_menu, cancel, help_cmd
from handlers.menu import (
    datos_menu, dat_resumen, dat_category, dat_ratios, dat_checklist, dat_export,
)
from handlers.knowledge import kb_menu, get_handlers as kb_handlers
from handlers.sources import src_menu, get_handlers as src_handlers
from handlers.tracking import trk_menu, get_handlers as trk_handlers
from handlers.admin import adm_menu, get_handlers as adm_handlers
from handlers.group import handle_q
from handlers.inline import handle_inline
from handlers.portfolio import portfolio_menu, get_handlers as pf_handlers


def main():
    logger = setup_logging()

    if not TELEGRAM_BOT_TOKEN:
        logger.error(
            "TELEGRAM_BOT_TOKEN no configurado. "
            "Establece la variable de entorno antes de ejecutar."
        )
        return

    # ── Initialize DB and seed data ──────────────────────────────
    init_db()
    session = get_session()
    try:
        seed_sources(session)
    finally:
        session.close()
    logger.info("Base de datos inicializada y fuentes cargadas.")

    # ── Build Telegram application ───────────────────────────────
    async def _post_init(application):
        me = await application.bot.get_me()
        application.bot_data["bot_username"] = me.username
        logger.info(f"Bot username: @{me.username}")

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).post_init(_post_init).build()

    # ── Command handlers ─────────────────────────────────────────
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("articulos", kb_menu))
    app.add_handler(CommandHandler("datos", datos_menu))
    app.add_handler(CommandHandler("fuentes", src_menu))
    app.add_handler(CommandHandler("tracking", trk_menu))
    app.add_handler(CommandHandler("cartera", portfolio_menu))
    app.add_handler(CommandHandler("q", handle_q))
    app.add_handler(CommandHandler("admin", adm_menu))
    app.add_handler(CommandHandler("cancel", cancel))

    # ── Inline query handler ─────────────────────────────────────
    app.add_handler(InlineQueryHandler(handle_inline))

    # ── Conversation + callback handlers from modules ────────────
    # ConversationHandlers must be registered before generic
    # CallbackQueryHandlers so they get priority on their entry points.
    for handler in kb_handlers():
        app.add_handler(handler)
    for handler in src_handlers():
        app.add_handler(handler)
    for handler in trk_handlers():
        app.add_handler(handler)
    for handler in pf_handlers():
        app.add_handler(handler)

    # ── Back to menu ─────────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(back_menu, pattern=r"^back_menu$"))

    # ── Datos (Data Model) callbacks ─────────────────────────────
    app.add_handler(CallbackQueryHandler(datos_menu, pattern=r"^menu_datos$"))
    app.add_handler(CallbackQueryHandler(dat_resumen, pattern=r"^dat_resumen$"))
    app.add_handler(CallbackQueryHandler(dat_category, pattern=r"^dat_cat_\d+$"))
    app.add_handler(CallbackQueryHandler(dat_ratios, pattern=r"^dat_ratios$"))
    app.add_handler(CallbackQueryHandler(dat_checklist, pattern=r"^dat_checklist$"))
    app.add_handler(CallbackQueryHandler(dat_export, pattern=r"^dat_export$"))

    # ── Admin callbacks ──────────────────────────────────────────
    for handler in adm_handlers():
        app.add_handler(handler)

    # ── Start polling ────────────────────────────────────────────
    logger.info("Bot iniciado. Esperando mensajes...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
