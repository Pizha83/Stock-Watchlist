from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from config import ADMIN_USER_IDS


MAIN_KEYBOARD = [
    [InlineKeyboardButton("📚 Artículos", callback_data="menu_kb")],
    [InlineKeyboardButton("🧩 Datos necesarios", callback_data="menu_datos")],
    [InlineKeyboardButton("🌍 Fuentes", callback_data="menu_src")],
    [InlineKeyboardButton("📈 Tracking", callback_data="menu_trk")],
]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show main menu."""
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
    text = (
        "📖 <b>Ayuda</b>\n\n"
        "/start - Menú principal\n"
        "/articulos - Base de conocimiento\n"
        "/datos - Datos necesarios\n"
        "/fuentes - Directorio de fuentes\n"
        "/tracking - Watchlists y seguimiento\n"
        "/admin - Administración\n"
        "/cancel - Cancelar operación\n"
    )
    await update.message.reply_text(text, parse_mode="HTML")
