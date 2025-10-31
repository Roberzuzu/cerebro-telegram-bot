#!/usr/bin/env python3
"""
Telegram Bot - AI Product Processor (Webhook Version)
Recibe mensajes vía webhook y procesa productos automáticamente
"""

import os
import sys
import json
import requests
import logging
from datetime import datetime
from flask import Flask, request, jsonify

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

# Flask app
app = Flask(__name__)

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def send_telegram_message(text: str, chat_id: int = None) -> bool:
    """Enviar mensaje a Telegram usando API HTTP directa"""
    try:
        target_chat_id = chat_id or TELEGRAM_CHAT_ID
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {
            "chat_id": target_chat_id,
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


def process_command(product_id: int, chat_id: int) -> None:
    """Procesar comando /procesar"""
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
                send_telegram_message(mensaje, chat_id)
                logger.info(f"✅ Producto {product_id} procesado por el agente")
            else:
                send_telegram_message(f"❌ Error: {result.get('error', 'Error desconocido')}", chat_id)
        else:
            send_telegram_message(f"❌ Error de conexión con el agente", chat_id)
    
    except Exception as e:
        logger.error(f"Error usando agente: {e}")
        send_telegram_message(f"❌ Error: {str(e)}", chat_id)


def process_natural_command(command: str, chat_id: int) -> None:
    """Procesar comando en lenguaje natural usando el agente inteligente"""
    logger.info(f"Comando natural: {command}")
    
    # Notificar que está procesando
    send_telegram_message(f"🧠 *Analizando tu solicitud...*\n\n'{command}'", chat_id)
    
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
                
                send_telegram_message(respuesta, chat_id)
                logger.info(f"✅ Comando natural procesado: {command}")
            else:
                send_telegram_message(f"❌ Error: {result.get('error', 'Error desconocido')}", chat_id)
        else:
            send_telegram_message(f"❌ Error de conexión: {response.status_code}", chat_id)
    
    except Exception as e:
        logger.error(f"Error en comando natural: {e}")
        send_telegram_message(
            f"❌ *Error procesando tu solicitud*\n\n"
            f"Intenta reformular el comando o usa `/ayuda` para ver ejemplos.",
            chat_id
        )


# Routes
@app.route('/', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "Bot running",
        "service": "Telegram Bot Webhook",
        "timestamp": datetime.now().isoformat(),
        "backend_url": BACKEND_URL
    })


@app.route('/webhook', methods=['POST'])
def telegram_webhook():
    """Webhook para recibir mensajes de Telegram"""
    try:
        update = request.get_json()
        
        if not update:
            return jsonify({"ok": True})
        
        # Extraer información del mensaje
        message = update.get('message', {})
        chat = message.get('chat', {})
        chat_id = chat.get('id')
        text = message.get('text', '')
        
        # Solo responder al chat autorizado
        if chat_id != TELEGRAM_CHAT_ID:
            logger.warning(f"⚠️ Mensaje ignorado de chat no autorizado: {chat_id}")
            return jsonify({"ok": True})
        
        logger.info(f"📨 Mensaje recibido: {text}")
        
        # Procesar comandos
        if text.startswith('/procesar'):
            parts = text.split()
            if len(parts) >= 2 and parts[1].isdigit():
                product_id = int(parts[1])
                process_command(product_id, chat_id)
            else:
                send_telegram_message(
                    "❌ Formato incorrecto.\n\n"
                    "Usa: `/procesar [ID]`\n"
                    "Ejemplo: `/procesar 4146`",
                    chat_id
                )
        
        elif text in ['/ayuda', '/start']:
            send_telegram_message(
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
                chat_id
            )
        
        elif not text.startswith('/'):
            # Comando en lenguaje natural
            process_natural_command(text, chat_id)
        
        return jsonify({"ok": True})
        
    except Exception as e:
        logger.error(f"Error en webhook: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


if __name__ == "__main__":
    logger.info("🚀 Iniciando Cerebro AI Bot (Webhook Version)...")
    
    # Verificar configuración
    if not TELEGRAM_TOKEN:
        logger.error("❌ TELEGRAM_BOT_TOKEN no configurado")
        exit(1)
    
    if not TELEGRAM_CHAT_ID:
        logger.error("❌ TELEGRAM_CHAT_ID no configurado")
        exit(1)
    
    logger.info(f"✅ Token configurado: {TELEGRAM_TOKEN[:10]}...")
    logger.info(f"✅ Chat ID: {TELEGRAM_CHAT_ID}")
    logger.info(f"✅ Backend URL: {BACKEND_URL}")
    
    # Enviar mensaje de inicio
    try:
        send_telegram_message("🤖 *Bot AI activado (Webhook)*\n\nEnvía `/procesar [ID]` para procesar productos.")
        logger.info("✅ Mensaje de inicio enviado")
    except Exception as e:
        logger.warning(f"⚠️ No se pudo enviar mensaje de inicio: {e}")
    
    # Iniciar Flask app
    port = int(os.environ.get('PORT', 8000))
    logger.info(f"🌐 Bot iniciado en puerto {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
