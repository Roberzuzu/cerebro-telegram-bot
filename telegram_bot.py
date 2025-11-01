                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              return f" Error {resp.status}: {error_text}"
    import os
import aiohttp
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
BACKEND_URL = os.environ.get("BACKEND_URL")
user_vars = {}

async def setvar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Uso: /setvar clave valor")
        return
    key, value = context.args[0], " ".join(context.args[1:])
    user_vars[update.effective_user.id] = user_vars.get(update.effective_user.id, {})
    user_vars[update.effective_user.id][key] = value
    await update.message.reply_text(f"🔧 Variable '{key}' configurada como '{value}'.")

async def gestion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    texto = update.message.text
    payload = {
        "command": texto,
        "user_id": f"telegram_{user_id}",
        "vars": user_vars.get(user_id, {})
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{BACKEND_URL}/agent/execute", json=payload, timeout=30) as resp:
            data = await resp.json()
            respuesta = data.get('mensaje') or str(data)
            await update.message.reply_text(respuesta)

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("setvar", setvar))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, gestion))
    app.run_polling()

if __name__ == "__main__":
    main()
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                # Mensajes de texto
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, manejar_mensaje))
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        # Procesar mensaje normal


                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                if __name__ == "__main__":
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    main()
