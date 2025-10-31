#!/usr/bin/env python3
"""
Telegram Bot - AI Product Processor (Webhook + Perplexity Integration)
Recibe mensajes vía webhook y procesa con Perplexity AI
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
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY", "")  # Agregamos Perplexity
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


def query_perplexity(question: str) -> dict:
    """Consultar Perplexity AI directamente"""
    try:
        if not PERPLEXITY_API_KEY:
            return {
                "success": False,
                "error": "Perplexity API key no configurada"
            }
        
        url = "https://api.perplexity.ai/chat/completions"
        headers = {
            "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
           "model": "sonar-medium-online",
            "messages": [
                {
                    "role": "system",
                    "content": "Eres un asistente experto en comercio electrónico, análisis web, SEO y marketing digital. Proporciona respuestas precisas, actuales y con fuentes cuando sea posible."
                },
                {
                    "role": "user", 
                    "content": question
                }
            ],
            "max_tokens": 1000,
            "temperature": 0.2,
            "top_p": 0.9,
            "return_citations": True
        }
        
        logger.info(f"Consultando Perplexity: {question[:50]}...")
        response = requests.post(url, json=payload, headers=headers, timeout=60)
        
        logger.info(f"Respuesta Perplexity: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            content = data['choices'][0]['message']['content']
            
            # Agregar fuentes si están disponibles
            citations = data.get('citations', [])
            if citations:
                content += "\n\n**Fuentes:**\n"
                for i, citation in enumerate(citations[:3], 1):
                    content += f"{i}. {citation}\n"
            
            logger.info("✅ Respuesta exitosa de Perplexity")
            return {
                "success": True,
                "content": content,
                "citations": citations
            }
        else:
            error_text = response.text
            logger.error(f"Error Perplexity: {response.status_code} - {error_text}")
            return {
                "success": False,
                "error": f"Error API: {response.status_code} - {error_text[:100]}"
            }
            
    except Exception as e:
        logger.error(f"Error en Perplexity: {e}")
        return {
            "success": False,
            "error": str(e)
        }


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


def process_command(product_id: int, chat_id: int) -> None:
    """Procesar comando /procesar usando Perplexity"""
    logger.info(f"Procesando producto {product_id} con Perplexity")
    
    # Obtener información del producto
    product = get_woocommerce_product(product_id)
    if not product:
        send_telegram_message(f"❌ No se pudo obtener información del producto {product_id}", chat_id)
        return
    
    product_name = product.get('name', 'Producto sin nombre')
    product_description = product.get('description', '')
    
    # Crear prompt para Perplexity
    prompt = f"""
    Analiza este producto de herramientas y accesorios:
    
    Nombre: {product_name}
    Descripción actual: {product_description[:200]}...
    
    Por favor:
    1. Genera una descripción SEO optimizada de 150-200 palabras
    2. Sugiere un precio competitivo basado en productos similares del mercado
    3. Recomienda 3-5 palabras clave para SEO
    4. Proporciona 2-3 puntos de venta únicos
    
    Enfócate en el mercado español de herramientas.
    """
    
    try:
        # Consultar Perplexity
        result = query_perplexity(prompt)
        
        if result['success']:
            # Enviar resultado formateado
            mensaje = f"✅ **Análisis del Producto {product_id}**\n\n"
            mensaje += f"**Producto:** {product_name}\n\n"
            mensaje += f"**Análisis de IA:**\n{result['content']}\n\n"
            mensaje += f"🔗 **Ver producto:**\n"
            mensaje += f"https://herramientasyaccesorios.store/wp-admin/post.php?post={product_id}&action=edit"
            
            send_telegram_message(mensaje, chat_id)
            logger.info(f"✅ Producto {product_id} procesado con Perplexity")
        else:
            send_telegram_message(f"❌ Error procesando con IA: {result['error']}", chat_id)
    
    except Exception as e:
        logger.error(f"Error procesando comando: {e}")
        send_telegram_message(f"❌ Error: {str(e)}", chat_id)


def process_natural_command(command: str, chat_id: int) -> None:
    """Procesar comando en lenguaje natural usando Perplexity"""
    logger.info(f"Comando natural: {command}")
    
    # Notificar que está procesando
    send_telegram_message(f"🧠 *Analizando tu solicitud...*\n\n'{command}'", chat_id)
    
    try:
        # Mejorar el prompt con contexto del negocio
        enhanced_prompt = f"""
        Contexto: Soy propietario de una tienda online de herramientas y accesorios (herramientasyaccesorios.store) que vende principalmente herramientas eléctricas, manuales y accesorios para bricolaje y profesionales.
        
        Solicitud del usuario: {command}
        
        Por favor proporciona una respuesta detallada, práctica y específica para mi negocio de herramientas. Si necesitas hacer análisis web, enfócate en el sector de herramientas en España.
        """
        
        result = query_perplexity(enhanced_prompt)
        
        if result['success']:
            # Construir respuesta
            respuesta = f"✅ **Análisis completado**\n\n"
            respuesta += result['content']
            
            send_telegram_message(respuesta, chat_id)
            logger.info(f"✅ Comando natural procesado con Perplexity")
        else:
            send_telegram_message(f"❌ Error: {result['error']}", chat_id)
    
    except Exception as e:
        logger.error(f"Error en comando natural: {e}")
        send_telegram_message(
            f"❌ *Error procesando tu solicitud*\n\n{str(e)}",
            chat_id
        )


# Routes
@app.route('/', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "Bot running",
        "service": "Telegram Bot Webhook + Perplexity",
        "timestamp": datetime.now().isoformat(),
        "perplexity_configured": bool(PERPLEXITY_API_KEY)
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
                "🤖 *Bot AI con Perplexity - Comandos disponibles*\n\n"
                "*Comandos básicos:*\n"
                "• `/procesar [ID]` - Analizar producto con IA\n"
                "• `/ayuda` - Ver esta ayuda\n\n"
                "*Comandos en lenguaje natural:*\n"
                "También puedes escribir en lenguaje natural:\n\n"
                "• 'Haz una auditoría de la web herramientasyaccesorios.store'\n"
                "• 'Busca 10 herramientas eléctricas en tendencia'\n"
                "• 'Analiza la competencia de sierras circulares'\n"
                "• 'Qué productos sin stock debo reponer'\n"
                "• 'Estrategia SEO para mi tienda de herramientas'\n\n"
                "*Powered by Perplexity AI* 🧠",
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
    logger.info("🚀 Iniciando Cerebro AI Bot (Webhook + Perplexity)...")
    
    # Verificar configuración
    if not TELEGRAM_TOKEN:
        logger.error("❌ TELEGRAM_BOT_TOKEN no configurado")
        exit(1)
    
    if not TELEGRAM_CHAT_ID:
        logger.error("❌ TELEGRAM_CHAT_ID no configurado")
        exit(1)
    
    logger.info(f"✅ Token configurado: {TELEGRAM_TOKEN[:10]}...")
    logger.info(f"✅ Chat ID: {TELEGRAM_CHAT_ID}")
    logger.info(f"✅ Perplexity: {'Configurado' if PERPLEXITY_API_KEY else 'NO CONFIGURADO'}")
    
    # Enviar mensaje de inicio
    try:
        send_telegram_message("🤖 *Bot AI activado con Perplexity*\n\nEnvía `/ayuda` para ver comandos disponibles.")
        logger.info("✅ Mensaje de inicio enviado")
    except Exception as e:
        logger.warning(f"⚠️ No se pudo enviar mensaje de inicio: {e}")
    
    # Iniciar Flask app
    port = int(os.environ.get('PORT', 8000))
    logger.info(f"🌐 Bot iniciado en puerto {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
