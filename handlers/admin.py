"""Admin panel handler."""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler
from config import ADMIN_USER_IDS, SERPAPI_KEY, OPENAI_API_KEY, DB_PATH
from services.db import get_session
from services.sources.sources_seed import seed_sources


async def adm_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()

    user_id = update.effective_user.id
    if user_id not in ADMIN_USER_IDS:
        text = "⚠️ No tienes permisos de administrador.\nConfigura ADMIN_USER_IDS."
        if query:
            await query.edit_message_text(text)
        else:
            await update.message.reply_text(text)
        return

    keyboard = [
        [InlineKeyboardButton("🔑 Estado de API keys", callback_data="adm_keys")],
        [InlineKeyboardButton("🌱 Seed/Reset fuentes", callback_data="adm_seed")],
        [InlineKeyboardButton("💾 Backup DB", callback_data="adm_backup")],
        [InlineKeyboardButton("◀️ Menú principal", callback_data="back_menu")],
    ]
    text = "⚙️ <b>Panel de Administración</b>"
    markup = InlineKeyboardMarkup(keyboard)

    if query:
        await query.edit_message_text(text, reply_markup=markup, parse_mode="HTML")
    else:
        await update.message.reply_text(text, reply_markup=markup, parse_mode="HTML")


async def adm_keys(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    serpapi = "✅ Configurada" if SERPAPI_KEY else "❌ No configurada"
    openai = "✅ Configurada" if OPENAI_API_KEY else "❌ No configurada"

    text = (
        "🔑 <b>Estado de API Keys</b>\n\n"
        f"SERPAPI_KEY: {serpapi}\n"
        f"OPENAI_API_KEY: {openai}\n\n"
        "<i>Configura variables de entorno antes de iniciar el bot.</i>"
    )
    keyboard = [[InlineKeyboardButton("◀️ Volver", callback_data="menu_adm")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")


async def adm_seed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    session = get_session()
    try:
        seed_sources(session)
        await query.edit_message_text(
            "🌱 Fuentes inicializadas correctamente.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("◀️ Volver", callback_data="menu_adm")]]
            ),
        )
    except Exception as e:
        await query.edit_message_text(
            f"❌ Error: {e}",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("◀️ Volver", callback_data="menu_adm")]]
            ),
        )
    finally:
        session.close()


async def adm_backup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        with open(str(DB_PATH), "rb") as f:
            await query.message.reply_document(
                document=f,
                filename="app_backup.db",
                caption="💾 Backup de la base de datos",
            )
    except Exception as e:
        await query.edit_message_text(
            f"❌ Error al crear backup: {e}",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("◀️ Volver", callback_data="menu_adm")]]
            ),
        )


def get_handlers():
    return [
        CallbackQueryHandler(adm_menu, pattern=r"^menu_adm$"),
        CallbackQueryHandler(adm_keys, pattern=r"^adm_keys$"),
        CallbackQueryHandler(adm_seed, pattern=r"^adm_seed$"),
        CallbackQueryHandler(adm_backup, pattern=r"^adm_backup$"),
    ]
