 import os
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
import aiohttp
from datetime import datetime

# CONFIGURACIÓN SEGURA
REQUIRED_ENV = [
    "TELEGRAM_TOKEN", "CEREBRO_API", "BACKEND_URL"
]
for key in REQUIRED_ENV:
    if not os.environ.get(key):
        raise EnvironmentError(f"Falta la variable de entorno: {key}")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CEREBRO_API = os.environ.get("CEREBRO_API")
BACKEND_URL = os.environ.get("BACKEND_URL")

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# GESTIÓN DE USUARIOS Y PERMISOS
ADMIN_IDS = [int(x) for x in os.environ.get("ADMIN_IDS", "").split(",") if x]
user_sessions = {}

def is_admin(userid):
    return userid in ADMIN_IDS

# UTILS HTTP ASYNC
async def get_backend_data(endpoint):
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{CEREBRO_API}/{endpoint}", timeout=10) as resp:
            if resp.status != 200:
                raise Exception(f"Error backend {endpoint}: {resp.status}")
            return await resp.json()

# COMANDOS
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    userid = update.effective_user.id
    user_sessions[userid] = {"activo": True, "inicio": datetime.now()}
    await update.message.reply_text("¡Bienvenido a CEREBRO AI! Usa /ayuda para ver comandos.")

async def ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    comandos = [
        "/productos - Lista productos",
        "/crear <nombre> - Crear producto",
        "/pedidos - Últimos pedidos",
        "/clientes - Estadísticas clientes",
        "/dashboard - Panel avanzado",
        "/ayuda - Ver comandos",
        "/status - Ver estado backend"
    ]
    await update.message.reply_text("🧠 *CEREBRO AI Comandos*\n" + "\n".join(comandos), parse_mode="Markdown")

async def productos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Consultando productos...")
    try:
        productos = await get_backend_data("productos")
        respuesta = "\n".join([f"{p['nombre']} | {p['precio']}€ | Stock: {p['stock']}" for p in productos[:10]])
        await update.message.reply_text(f"*Productos:*\n{respuesta}", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Error al consultar productos: {e}")

# COMANDO ESPECIAL DASHBOARD
async def dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Generando dashboard avanzado...")
    # Aquí podrías implementar lógica adicional, gráficos, CSV, etc.

# HANDLER DE TEXTO NATURAL INTELIGENTE
async def texto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto_str = update.message.text.lower()
    if "producto" in texto_str:
        await productos(update, context)
    elif "pedido" in texto_str:
        await update.message.reply_text("Comando 'pedido' no implementado todavía.")
    # Extiende para otros comandos

# HANDLER DE ERRORES GENERAL
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.exception(f"Error: {context.error}")
    if isinstance(update, Update) and update.message:
        await update.message.reply_text("Ocurrió un error inesperado. Por favor, intenta de nuevo.")

# MAIN
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ayuda", ayuda))
    app.add_handler(CommandHandler("productos", productos))
    app.add_handler(CommandHandler("dashboard", dashboard))
    # Otros comandos...
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, texto))
    app.add_error_handler(error_handler)
    logger.info("Bot listo")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
