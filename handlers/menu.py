"""Handler for the 'Datos necesarios' (Data Model) section."""

import csv
import io
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from services.sources.sources_seed import DATA_TAXONOMY, RATIOS
from utils.text import escape_html, safe_truncate_html


async def datos_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()

    keyboard = [
        [InlineKeyboardButton("📋 Qué datos necesito", callback_data="dat_resumen")],
        [InlineKeyboardButton("📐 Ratios y fórmulas", callback_data="dat_ratios")],
        [InlineKeyboardButton("✅ Plantilla checklist", callback_data="dat_checklist")],
        [InlineKeyboardButton("📥 Exportar plantilla (CSV)", callback_data="dat_export")],
        [InlineKeyboardButton("◀️ Menú principal", callback_data="back_menu")],
    ]
    text = (
        "🧩 <b>Modelo de Datos</b>\n\n"
        "Consulta qué datos necesitas para analizar empresas, "
        "ratios clave y plantillas de análisis."
    )
    markup = InlineKeyboardMarkup(keyboard)

    if query:
        await query.edit_message_text(text, reply_markup=markup, parse_mode="HTML")
    else:
        await update.message.reply_text(text, reply_markup=markup, parse_mode="HTML")


async def dat_resumen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    text = "🧩 <b>Datos necesarios por categoría</b>\n\n"
    categories = list(DATA_TAXONOMY.keys())

    for cat_name, cat_data in DATA_TAXONOMY.items():
        fields = cat_data["fields"]
        names = ", ".join(f["name"] for f in fields[:5])
        extra = f" (+{len(fields) - 5})" if len(fields) > 5 else ""
        text += f"• <b>{escape_html(cat_name)}</b>: {escape_html(names)}{extra}\n"

    keyboard = []
    for i, cat in enumerate(categories):
        keyboard.append([InlineKeyboardButton(f"📂 {cat}", callback_data=f"dat_cat_{i}")])
    keyboard.append([InlineKeyboardButton("◀️ Volver", callback_data="menu_datos")])

    if len(text) > 4000:
        text = safe_truncate_html(text)

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")


async def dat_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    cat_idx = int(query.data.split("_")[-1])
    categories = list(DATA_TAXONOMY.keys())
    if cat_idx >= len(categories):
        return

    cat_name = categories[cat_idx]
    cat_data = DATA_TAXONOMY[cat_name]

    text = f"📂 <b>{escape_html(cat_name)}</b>\n"
    text += f"<i>{escape_html(cat_data['description'])}</i>\n\n"

    for f in cat_data["fields"]:
        text += f"• <b>{escape_html(f['name'])}</b>: {escape_html(f['definition'])}\n"
        text += f"  Unidad: {f['unit']} | Periodicidad: {f.get('periodicity', 'N/A')}\n"
        if f.get("sources"):
            text += f"  Fuentes: {escape_html(f['sources'])}\n"
        text += "\n"

    if len(text) > 4000:
        text = safe_truncate_html(text)

    keyboard = [[InlineKeyboardButton("◀️ Volver", callback_data="dat_resumen")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")


async def dat_ratios(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    text = "📐 <b>Ratios y Fórmulas Clave</b>\n\n"
    for r in RATIOS:
        text += f"<b>{escape_html(r['name'])}</b>\n"
        text += f"  Fórmula: <code>{escape_html(r['formula'])}</code>\n"
        text += f"  {escape_html(r['definition'])}\n"
        text += f"  Unidad: {r['unit']} | {r['periodicity']}\n\n"

    if len(text) > 4000:
        text = safe_truncate_html(text)

    keyboard = [[InlineKeyboardButton("◀️ Volver", callback_data="menu_datos")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")


async def dat_checklist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    items = [
        "1. Entender el negocio (qué hace, cómo gana dinero)",
        "2. Revisar estados financieros (3-5 años)",
        "3. Calcular ratios clave (márgenes, ROE, ROIC)",
        "4. Evaluar deuda y liquidez",
        "5. Analizar flujo de caja libre (FCF)",
        "6. Comparar con peers (múltiplos)",
        "7. Evaluar management y governance",
        "8. Identificar moat / ventaja competitiva",
        "9. Analizar riesgos (regulación, concentración, divisa)",
        "10. Estimar valoración (DCF, múltiplos)",
        "11. Definir tesis de inversión",
        "12. Establecer catalizadores y triggers",
        "13. Definir precio objetivo y margen de seguridad",
        "14. Monitorizar eventos (earnings, guidance)",
    ]

    text = "✅ <b>Checklist de Análisis</b>\n\n"
    for item in items:
        text += f"☐ {item}\n"

    keyboard = [[InlineKeyboardButton("◀️ Volver", callback_data="menu_datos")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")


async def dat_export(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Categoria", "Campo", "Definicion", "Unidad", "Periodicidad", "Fuentes"])

    for cat_name, cat_data in DATA_TAXONOMY.items():
        for f in cat_data["fields"]:
            writer.writerow([
                cat_name, f["name"], f["definition"],
                f["unit"], f.get("periodicity", ""), f.get("sources", ""),
            ])

    writer.writerow([])
    writer.writerow(["Ratio", "Formula", "Definicion", "Unidad", "Periodicidad", "Fuentes"])
    for r in RATIOS:
        writer.writerow([r["name"], r["formula"], r["definition"], r["unit"], r["periodicity"], r["sources"]])

    csv_bytes = output.getvalue().encode("utf-8-sig")
    bio = io.BytesIO(csv_bytes)
    bio.name = "modelo_datos.csv"

    await query.message.reply_document(
        document=bio, filename="modelo_datos.csv",
        caption="📥 Plantilla del modelo de datos",
    )
