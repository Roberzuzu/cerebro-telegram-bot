"""
CEREBRO AI - BOT DE TELEGRAM
Conecta directamente con https://ai-agent-backend80.onrender.com y Perplexity.
"""

import os
import aiohttp
import asyncio
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# ------------------- CONFIGURACIÓN SEGURA --------------------
TELEGRAM_TOKEN      = os.environ.get("TELEGRAM_TOKEN")
CEREBRO_API         = os.environ.get("CEREBRO_API")    # Ej: https://ai-agent-backend80.onrender.com/api/agent
BACKEND_URL         = os.environ.get("BACKEND_URL")    # Ej: https://ai-agent-backend80.onrender.com/api
PERPLEXITY_API_KEY  = os.environ.get("PERPLEXITY_API_KEY")

# ------------------- LOGGING -------------------------------
logging.basicConfig(
    format="%(asctime)s %(levelname)s %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ------------------- ESTADO DE USUARIOS --------------------
user_sessions = {}

# ------------------- UTILS DE COMUNICACIÓN ----------------

async def ejecutar_comando(comando: str, telegram_user_id: int) -> str:
    """Ejecuta comando en tu backend Cerebro."""
    payload = {
        "command": comando,
        "user_id": f"telegram_{telegram_user_id}"
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{CEREBRO_API}/execute", json=payload, timeout=30) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get('mensaje') or data.get('message') or str(data)
                else:
                    error_text = await resp.text()
                    return f"Error {resp.status}: {error_text}"
    except asyncio.TimeoutError:
        return "⏱ Timeout: El backend tardó demasiado en responder"
    except Exception as e:
        return f"Error de conexión: {str(e)}"

async def get_perplexity_answer(prompt: str) -> str:
    """Consulta IA Perplexity y devuelve respuesta."""
    url = "https://api.perplexity.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json"
    }
    body = {
        "model": "pplx-70b-chat",
        "messages": [{"role": "user", "content": prompt}]
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=body, timeout=40) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    return result['choices'][0]['message']['content']
                err = await resp.text()
                return f"Error IA {resp.status}: {err}"
    except Exception as e:
        return f"Error con IA: {e}"

# ------------------- HANDLERS DE COMANDOS -----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_sessions[user_id] = {"activo": True}
    mensaje = (
        "¡Bienvenido a *CEREBRO AI*!\n"
        "Escribe /ayuda para ver todos los comandos disponibles o háblame en lenguaje natural."
    )
    await update.message.reply_text(mensaje, parse_mode="Markdown")

async def ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    comandos = [
        "/productos - Lista productos",
        "/crear - Crear producto",
        "/pedidos - Ver últimos pedidos",
        "/clientes - Estadísticas de clientes",
        "/status - Ver estado backend",
        "/ayuda - Ver todos los comandos",
        "\nModo IA: Escribe lo que quieras saber, por ejemplo:",
        "• \"¿Cuánto he vendido hoy?\"",
        "• \"Crea un producto llamado Taladro Makita\""
    ]
    msg = "🧠 *Comandos CEREBRO AI*\n" + "\n".join(comandos)
    await update.message.reply_text(msg, parse_mode="Markdown")

async def productos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Consultando productos...")
    respuesta = await ejecutar_comando("lista los productos", update.effective_user.id)
    await update.message.reply_text(respuesta)

async def crear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    argumentos = context.args
    if not argumentos:
        await update.message.reply_text("Uso: /crear [nombre del producto]")
        return
    nombre = " ".join(argumentos)
    await update.message.reply_text(f"Creando producto '{nombre}'...")
    respuesta = await ejecutar_comando(f"crea un producto llamado {nombre}", update.effective_user.id)
    await update.message.reply_text(respuesta)

async def pedidos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Consultando pedidos...")
    respuesta = await ejecutar_comando("muestra los últimos 10 pedidos", update.effective_user.id)
    await update.message.reply_text(respuesta)

async def clientes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Consultando clientes...")
    respuesta = await ejecutar_comando("estadísticas de clientes", update.effective_user.id)
    await update.message.reply_text(respuesta)

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Verificando estado del backend...")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{CEREBRO_API}/status", timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    mensaje = (
                        f"*Backend operativo*\n"
                        f"Estado: {data.get('status', 'OK')}\n"
                        f"Agente: {'Activo' if data.get('agente_activo') else 'Inactivo'}\n"
                        f"Base de datos: {'Conectada' if data.get('database_connected') else 'Desconectada'}\n"
                        f"Modelo: {data.get('modelo', 'N/A')}\n"
                        f"Conversaciones: {data.get('conversaciones_totales', 0)}\n"
                        f"Herramientas: {data.get('herramientas_disponibles', 0)}"
                    )
                    await update.message.reply_text(mensaje, parse_mode="Markdown")
                else:
                    await update.message.reply_text(f"Backend respondió con error: {resp.status}")
    except Exception as e:
        await update.message.reply_text(f"Error al conectar: {str(e)}")

async def manejar_mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja mensajes en lenguaje natural (IA o backend)"""
    user_id = update.effective_user.id
    texto = update.message.text
    await update.message.reply_text("Procesando...")
    # Primero prueba como comando backend
    backend_respuesta = await ejecutar_comando(texto, user_id)
    if backend_respuesta and "Error" not in backend_respuesta:
        await update.message.reply_text(backend_respuesta)
        return
    # Si el backend no responde, consulta IA
    ia_respuesta = await get_perplexity_answer(texto)
    await update.message.reply_text(ia_respuesta)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"Error: {context.error}")
    if update and update.message:
        await update.message.reply_text(f"Ocurrió un error inesperado: {context.error}")

# ------------------- MAIN -----------------

def main():
    print("Iniciando Cerebro AI Bot...")
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    # Handlers de comandos
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ayuda", ayuda))
    app.add_handler(CommandHandler("productos", productos))
    app.add_handler(CommandHandler("crear", crear))
    app.add_handler(CommandHandler("pedidos", pedidos))
    app.add_handler(CommandHandler("clientes", clientes))
    app.add_handler(CommandHandler("status", status))
    # Handler para mensajes en lenguaje natural
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, manejar_mensaje))
    # Handler de errores
    app.add_error_handler(error_handler)
    print("Bot listo. Esperando mensajes...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()                                                                                                                                                                                                                                                                                      "user_id": f"telegram_{user_id}"
                                                                                                                                                                                                                                                                                                                                                                }
                                                                                                                                                                                                                                                                                                                                                                            
                                                                                                                                                                                                                                                                                                                                                                                        async with session.post(
                                                                                                                                                                                                                                                                                                                                                                                                        f"{CEREBRO_API}/execute",
                                                                                                                                                                                                                                                                                                                                                                                                                        json=payload,
                                                                                                                                                                                                                                                                                                                                                                                                                                        timeout=30
                                                                                                                                                                                                                                                                                                                                                                                                                                                    ) as resp:
                                                                                                                                                                                                                                                                                                                                                                                                                                                                    
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    if resp.status == 200:
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        data = await resp.json()
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            return data.get('mensaje') or data.get('message') or data.get('respuesta') or str(data)
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            else:
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                error_text = await resp.text()
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    return f" Error {resp.status}: {error_text}"
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        except asyncio.TimeoutError:
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                return "⏱ Timeout: El servidor tardó demasiado en responder"
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    except Exception as e:
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            return f" Error de conexión: {str(e)}"


                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            async def manejar_mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                """Maneja mensajes de texto normales"""
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    user_id = update.effective_user.id
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        texto = update.message.text
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                # Indicador de que está procesando
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    await update.message.reply_text(" Procesando...")
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            # Ejecutar comando
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                respuesta = await ejecutar_comando(texto, user_id)
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        # Responder
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            await update.message.reply_text(respuesta)


                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                """Maneja errores"""
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    print(f" Error: {context.error}")
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        if update and update.message:
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                await update.message.reply_text(f" Ocurrió un error: {context.error}")


                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                def main():
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    """Inicia el bot"""
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        print(" Iniciando Cerebro AI Bot...")
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                # Crear aplicación
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    app = Application.builder().token(TELEGRAM_TOKEN).build()
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            # Comandos
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                app.add_handler(CommandHandler("start", start))
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    app.add_handler(CommandHandler("ayuda", ayuda))
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        app.add_handler(CommandHandler("help", ayuda))
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            app.add_handler(CommandHandler("productos", productos))
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                app.add_handler(CommandHandler("crear", crear_producto))
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    app.add_handler(CommandHandler("pedidos", pedidos))
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        app.add_handler(CommandHandler("status", status))
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                # Mensajes de texto
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, manejar_mensaje))
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        # Procesar mensaje normal
99|        if text and not text.startswith('/'):
100|            logger.info(f" Procesando: {text}")
101|            
102|            # Llamar backend
103|            result = call_backend_agent(text, f"telegram_{chat_id}")
104|            
105|            if result['success']:
106|                mensaje = result.get('mensaje', 'Sin respuesta del backend')
107|                send_telegram_message(f" {mensaje}", chat_id)
108|                logger.info(" Enviado correctamente")
109|            else:
110|                error = result.get('error', 'Error desconocido')
111|                send_telegram_message(f" Error: {error}", chat_id)
112|                logger.error(f" Error: {error}")
113|        
114|        return jsonify({"ok": True})
115|        
116|    except Exception as e:
117|        logger.error(f" Error webhook: {e}")
118|        return jsonify({"ok": False, "error": str(e)}), 500
119|
120|if __name__ == "__main__":
121|    logger.info(" INICIANDO TELEGRAM BOT URGENTE")
122|    logger.info(f" Backend: {BACKEND_URL}")
123|    
124|    # Test inicial
125|    try:
126|        test_response = requests.get(f"https://ai-agent-backend80.onrender.com/api/agent/status", timeout=10)
127|        if test_response.status_code == 200:
128|            logger.info(" Backend verificado")
129|            send_telegram_message(" *Bot fix urgente activado y conectado*")
130|        else:
131|            logger.warning(f" Backend respondió: {test_response.status_code}")
132|    except Exception as e:
133|        logger.error(f" No se pudo verificar backend: {e}")
134|    
135|    port = int(os.environ.get('PORT', 8000))
136|    app.run(host='0.0.0.0', port=port, debug=False)
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            # Error handler
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                app.add_error_handler(error_handler)
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        # Iniciar
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            print(" Bot iniciado. Esperando mensajes...")
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                app.run_polling(allowed_updates=Update.ALL_TYPES)


                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                if __name__ == "__main__":
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    main()
