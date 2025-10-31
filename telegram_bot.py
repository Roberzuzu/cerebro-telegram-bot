#!/usr/bin/env python3
"""
Telegram Bot - AI Product Processor (Modern python-telegram-bot)
Escucha comandos de Telegram y procesa productos automáticamente usando python-telegram-bot
"""

import os
import sys
import json
import requests
import logging
import asyncio
import threading
from datetime import datetime
from typing import Optional
from http.server import HTTPServer, BaseHTTPRequestHandler

# Telegram Bot imports
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode

# Añadir el directorio actual al path para imports
sys.path.insert(0, os.path.dirname(__file__))

# Import asíncrono de Google Analytics
try:
    from google_analytics import track_telegram_event, track_ai_event
    GA_AVAILABLE = True
except ImportError:
    GA_AVAILABLE = False
    print("⚠️ Google Analytics no disponible")

# STANDALONE CONFIGURATION - Load from environment
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "7708509018:AAErAOblRAlC587j1QB4k19PAfDgoiZ3kWk")
TELEGRAM_CHAT_ID = int(os.getenv("TELEGRAM_CHAT_ID", "7202793910"))
BACKEND_URL = os.getenv("BACKEND_URL", "https://ai-agent-backend80.onrender.com/api")
WC_URL = os.getenv("WC_URL", "https://herramientasyaccesorios.store/wp-json/wc/v3")
WC_KEY = os.getenv("WC_KEY", "ck_4f50637d85ec404fff441fceb7b113b5050431ea")
WC_SECRET = os.getenv("WC_SECRET", "cs_e59ef18ea20d80ffdf835803ad2fdd834a4ba19f")
WP_URL = os.getenv("WP_URL", "https://herramientasyaccesorios.store/wp-json/wp/v2")
WP_USER = os.getenv("WP_USER", "agenteweb@herramientasyaccesorios.store")
WP_PASS = os.getenv("WP_PASS", "RWWLW1eVi8whOS5OsUosb5AU")

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)  # Solo stdout en Render
    ]
)
logger = logging.getLogger(__name__)

# Bot instance (se inicializará en main)
bot_instance: Optional[Bot] = None

# Health server
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        response = {
            "status": "Bot running",
            "service": "Telegram Bot",
            "timestamp": datetime.now().isoformat(),
            "backend_url": BACKEND_URL
        }
        self.wfile.write(json.dumps(response).encode())
    
    def log_message(self, format, *args):
        pass  # Suprimir logs HTTP


async def send_telegram_message_async(text: str, chat_id: Optional[int] = None) -> bool:
    """Enviar mensaje a Telegram usando python-telegram-bot"""
    try:
        target_chat_id = chat_id or TELEGRAM_CHAT_ID
        if bot_instance:
            await bot_instance.send_message(
                chat_id=target_chat_id,
                text=text,
                parse_mode=ParseMode.MARKDOWN
            )
            return True
        return False
    except Exception as e:
        logger.error(f"Error enviando mensaje: {e}")
        return False


def send_telegram_message(text: str, chat_id: Optional[int] = None) -> bool:
    """Versión sync de envío de mensaje (para compatibilidad)"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {
            "chat_id": chat_id or TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "Markdown"
        }
        response = requests.post(url, json=data, timeout=10)
        return response.json().get('ok', False)
    except Exception as e:
        logger.error(f"Error enviando mensaje: {e}")
        return False


def get_woocommerce_product(product_id):
    """Obtener producto de WooCommerce"""
    try:
        url = f"{WC_URL}/products/{product_id}"
        response = requests.get(url, auth=(WC_KEY, WC_SECRET), timeout=15)
        
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        logger.error(f"Error obteniendo producto {product_id}: {e}")
        return None


def process_with_ai(product_name, category, base_price):
    """Procesar producto con backend AI"""
    try:
        url = f"{BACKEND_URL}/ai/product/complete"
        data = {
            "product_name": product_name,
            "category": category,
            "base_price": base_price,
            "generate_images": True
        }
        
        logger.info(f"Procesando con AI: {product_name}")
        response = requests.post(url, json=data, timeout=180)
        
        if response.status_code == 200:
            return response.json()
        
        logger.error(f"Error AI: {response.status_code} - {response.text}")
        return None
    except Exception as e:
        logger.error(f"Error procesando con AI: {e}")
        return None


def update_woocommerce_product(product_id, ai_result):
    """Actualizar producto en WooCommerce"""
    try:
        url = f"{WC_URL}/products/{product_id}"
        
        update_data = {}
        
        # Actualizar descripción
        if ai_result.get('description'):
            desc = ai_result['description']
            update_data['description'] = desc.get('description', '')
            update_data['short_description'] = desc.get('meta_description', '')
        
        # Actualizar precio
        if ai_result.get('pricing'):
            optimal_price = ai_result['pricing'].get('optimal_price')
            if optimal_price:
                update_data['regular_price'] = str(optimal_price)
        
        if update_data:
            response = requests.put(
                url,
                json=update_data,
                auth=(WC_KEY, WC_SECRET),
                timeout=15
            )
            
            if response.status_code == 200:
                logger.info(f"Producto {product_id} actualizado en WooCommerce")
                return True
        
        return False
    except Exception as e:
        logger.error(f"Error actualizando WooCommerce: {e}")
        return False


def upload_images_to_wordpress(product_id, ai_result):
    """Subir imágenes a WordPress y asignarlas al producto"""
    try:
        images = ai_result.get('images', {}).get('images', [])
        if not images:
            return 0
        
        image_ids = []
        
        for idx, img_data in enumerate(images):
            img_url = img_data.get('url')
            if not img_url:
                continue
            
            # Descargar imagen
            img_response = requests.get(img_url, timeout=30)
            if img_response.status_code != 200:
                continue
            
            # Subir a WordPress
            files = {
                'file': (f'ai-image-{idx+1}.jpg', img_response.content, 'image/jpeg')
            }
            
            wp_response = requests.post(
                f"{WP_URL}/media",
                files=files,
                auth=(WP_USER, WP_PASS),
                timeout=30
            )
            
            if wp_response.status_code == 201:
                media_id = wp_response.json().get('id')
                image_ids.append(media_id)
                logger.info(f"Imagen {idx+1} subida: ID {media_id}")
        
        # Asignar imágenes al producto
        if image_ids:
            images_data = [{'id': img_id} for img_id in image_ids]
            
            url = f"{WC_URL}/products/{product_id}"
            response = requests.put(
                url,
                json={'images': images_data},
                auth=(WC_KEY, WC_SECRET),
                timeout=15
            )
            
            if response.status_code == 200:
                logger.info(f"{len(image_ids)} imágenes asignadas al producto {product_id}")
                return len(image_ids)
        
        return 0
    except Exception as e:
        logger.error(f"Error subiendo imágenes: {e}")
        return 0


async def process_command_async(product_id: int, update: Update) -> None:
    """Procesar comando /procesar de forma asíncrona"""
    logger.info(f"Procesando producto {product_id}")
    
    # Usar el agente inteligente
    command = f"Procesa el producto {product_id} con AI: genera descripción SEO, calcula precio óptimo, crea 2 imágenes profesionales y actualiza todo en WooCommerce"
    
    try:
        response = requests.post(
            f"{BACKEND_URL}/agent/execute",
            json={
                "command": command,
                "user_id": f"telegram_{TELEGRAM_CHAT_ID}"
            },
            timeout=180
        )
        
        if response.status_code == 200:
            result = response.json()
            
            if result.get("success"):
                # Enviar resultado
                mensaje = (
                    f"✅ *{result.get('mensaje', 'Completado')}*\n\n"
                    f"Plan ejecutado: {result.get('plan', 'N/A')}\n\n"
                    f"🔗 Ver producto:\n"
                    f"https://herramientasyaccesorios.store/wp-admin/post.php?post={product_id}&action=edit"
                )
                await update.message.reply_text(mensaje, parse_mode=ParseMode.MARKDOWN)
                logger.info(f"✅ Producto {product_id} procesado por el agente")
            else:
                await update.message.reply_text(f"❌ Error: {result.get('error', 'Error desconocido')}")
        else:
            await update.message.reply_text(f"❌ Error de conexión con el agente")
    
    except Exception as e:
        logger.error(f"Error usando agente: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def process_natural_command_async(command: str, update: Update) -> None:
    """Procesar comando en lenguaje natural usando el agente inteligente"""
    logger.info(f"Comando natural: {command}")
    chat_id = update.effective_chat.id
    
    # Notificar que está procesando
    await update.message.reply_text(
        f"🧠 *Analizando tu solicitud...*\n\n'{command}'",
        parse_mode=ParseMode.MARKDOWN
    )
    
    try:
        response = requests.post(
            f"{BACKEND_URL}/agent/execute",
            json={
                "command": command,
                "user_id": f"telegram_{chat_id}"
            },
            timeout=180
        )
        
        if response.status_code == 200:
            result = response.json()
            
            if result.get("success"):
                mensaje = result.get("mensaje", "Procesado")
                plan = result.get("plan", "")
                resultados = result.get("resultados", [])
                
                # Construir respuesta
                respuesta = f"✅ *{mensaje}*\n\n"
                
                if plan:
                    respuesta += f"📋 *Plan:* {plan}\n\n"
                
                if resultados:
                    respuesta += "*Resultados:*\n"
                    for idx, res in enumerate(resultados, 1):
                        herramienta = res.get("herramienta", "")
                        resultado_data = res.get("resultado", {})
                        
                        if resultado_data.get("success"):
                            respuesta += f"✓ {herramienta}\n"
                        else:
                            respuesta += f"✗ {herramienta}: {resultado_data.get('error', 'Error')}\n"
                
                await update.message.reply_text(respuesta, parse_mode=ParseMode.MARKDOWN)
                logger.info(f"✅ Comando natural procesado: {command}")
            else:
                await update.message.reply_text(f"❌ Error: {result.get('error', 'Error desconocido')}")
        else:
            await update.message.reply_text(f"❌ Error de conexión: {response.status_code}")
    
    except Exception as e:
        logger.error(f"Error en comando natural: {e}")
        await update.message.reply_text(
            f"❌ *Error procesando tu solicitud*\n\n"
            f"Intenta reformular el comando o usa `/ayuda` para ver ejemplos.",
            parse_mode=ParseMode.MARKDOWN
        )


# Handlers del bot
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para comando /start y /ayuda"""
    await update.message.reply_text(
        "🤖 *Bot AI - Comandos disponibles*\n\n"
        "*Comandos básicos:*\n"
        "• `/procesar [ID]` - Procesar producto con AI\n"
        "• `/ayuda` - Ver esta ayuda\n\n"
        "*Comandos en lenguaje natural:*\n"
        "También puedes escribir en lenguaje natural:\n\n"
        "• 'Busca 10 herramientas eléctricas tendencia'\n"
        "• 'Analiza la competencia de sierras'\n"
        "• 'Crea una campaña para el producto 4146'\n"
        "• 'Muéstrame los productos sin precio'\n"
        "• 'Optimiza el SEO del producto 4124'\n\n"
        "*El bot entenderá y ejecutará tu solicitud* 🧠",
        parse_mode=ParseMode.MARKDOWN
    )


async def procesar_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para comando /procesar"""
    # Verificar chat autorizado
    if update.effective_chat.id != TELEGRAM_CHAT_ID:
        logger.warning(f"⚠️ Comando ignorado de chat no autorizado: {update.effective_chat.id}")
        return
    
    # Verificar argumentos
    if context.args and len(context.args) >= 1:
        try:
            product_id = int(context.args[0])
            await process_command_async(product_id, update)
        except ValueError:
            await update.message.reply_text(
                "❌ Formato incorrecto.\n\n"
                "Usa: `/procesar [ID]`\n"
                "Ejemplo: `/procesar 4146`"
            )
    else:
        await update.message.reply_text(
            "❌ Formato incorrecto.\n\n"
            "Usa: `/procesar [ID]`\n"
            "Ejemplo: `/procesar 4146`"
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para comando /ayuda"""
    await start_command(update, context)


async def natural_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para mensajes en lenguaje natural"""
    # Verificar chat autorizado
    if update.effective_chat.id != TELEGRAM_CHAT_ID:
        logger.warning(f"⚠️ Mensaje ignorado de chat no autorizado: {update.effective_chat.id}")
        return
    
    text = update.message.text
    logger.info(f"📨 Mensaje recibido: {text}")
    
    # Procesar como comando natural
    await process_natural_command_async(text, update)


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler global para errores"""
    logger.error(f"Update {update} caused error {context.error}")
    
    if update and update.message:
        await update.message.reply_text(
            "❌ *Error interno del bot*\n\n"
            "Por favor intenta de nuevo en unos momentos.",
            parse_mode=ParseMode.MARKDOWN
        )


def start_health_server():
    """Iniciar servidor HTTP para health check"""
    try:
        port = int(os.getenv('PORT', 8000))
        server = HTTPServer(('0.0.0.0', port), HealthHandler)
        logger.info(f"✅ Servidor HTTP iniciado en puerto {port}")
        server.serve_forever()
    except Exception as e:
        logger.error(f"❌ Error iniciando servidor HTTP: {e}")


async def main():
    """Función principal del bot"""
    global bot_instance
    
    logger.info("🚀 Iniciando Cerebro AI Bot (Optimizado con python-telegram-bot)...")
    
    # Verificar configuración
    if not TELEGRAM_TOKEN or TELEGRAM_TOKEN == "":
        logger.error("❌ TELEGRAM_BOT_TOKEN no configurado")
        return
    
    if not TELEGRAM_CHAT_ID:
        logger.error("❌ TELEGRAM_CHAT_ID no configurado")
        return
    
    logger.info(f"✅ Token configurado: {TELEGRAM_TOKEN[:10]}...")
    logger.info(f"✅ Chat ID: {TELEGRAM_CHAT_ID}")
    logger.info(f"✅ Backend URL: {BACKEND_URL}")
    
    # Crear aplicación
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    bot_instance = app.bot
    
    # Agregar handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("ayuda", help_command))
    app.add_handler(CommandHandler("procesar", procesar_command))
    
    # Handler para mensajes de texto (lenguaje natural)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, natural_message_handler))
    
    # Handler de errores
    app.add_error_handler(error_handler)
    
    # Enviar mensaje de inicio
    try:
        await app.bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text="🤖 *Bot AI activado*\n\nEnvía `/procesar [ID]` para procesar productos.",
            parse_mode=ParseMode.MARKDOWN
        )
        logger.info("✅ Mensaje de inicio enviado")
    except Exception as e:
        logger.warning(f"⚠️ No se pudo enviar mensaje de inicio: {e}")
    
    # Iniciar bot
    logger.info("🤖 Bot iniciado. Escuchando mensajes...")
    await app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    # Iniciar servidor HTTP en background
    health_thread = threading.Thread(target=start_health_server, daemon=True)
    health_thread.start()
    
    # Iniciar bot principal
    asyncio.run(main())
