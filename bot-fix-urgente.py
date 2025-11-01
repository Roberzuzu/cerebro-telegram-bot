Aquí tienes el archivo completo `bot-fix-urgente.py`:
Action: file_editor view /app/bot-fix-urgente.py
Observation: /app/bot-fix-urgente.py:
1|#!/usr/bin/env python3
2|"""
3|FIX URGENTE - Bot Telegram → Backend Independiente
4|PROBLEMA: Bot conecta pero no procesa mensajes correctamente
5|"""
6|
7|import os
8|import requests
9|import logging
10|from flask import Flask, request, jsonify
11|
12|# CONFIGURACIÓN
13|TELEGRAM_TOKEN = "7708509018:AAErAOblRAlC587j1QB4k19PAfDgoiZ3kWk"
14|TELEGRAM_CHAT_ID = 7202793910
15|BACKEND_URL = "https://ai-agent-backend80.onrender.com/api"
16|
17|app = Flask(__name__)
18|logging.basicConfig(level=logging.INFO)
19|logger = logging.getLogger(__name__)
20|
21|def send_telegram_message(text: str, chat_id: int = None) -> bool:
22|    """Enviar mensaje a Telegram"""
23|    try:
24|        target_chat_id = chat_id or TELEGRAM_CHAT_ID
25|        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
26|        data = {"chat_id": target_chat_id, "text": text, "parse_mode": "Markdown"}
27|        response = requests.post(url, json=data, timeout=10)
28|        return response.json().get('ok', False)
29|    except Exception as e:
30|        logger.error(f"Error enviando mensaje: {e}")
31|        return False
32|
33|def call_backend_agent(command: str, user_id: str) -> dict:
34|    """Llamar al backend independiente - VERSION SIMPLIFICADA"""
35|    try:
36|        url = f"{BACKEND_URL}/agent/chat"
37|        payload = {"command": command, "user_id": user_id}
38|        
39|        logger.info(f"🚀 Enviando a {url}: {command[:50]}...")
40|        
41|        response = requests.post(url, json=payload, timeout=60)
42|        
43|        logger.info(f"📥 Respuesta: {response.status_code}")
44|        
45|        if response.status_code == 200:
46|            data = response.json()
47|            return {
48|                "success": True,
49|                "mensaje": data.get('mensaje', 'Procesado exitosamente'),
50|                "acciones": data.get('acciones', [])
51|            }
52|        else:
53|            logger.error(f"❌ Error backend: {response.status_code}")
54|            return {"success": False, "error": f"Backend error: {response.status_code}"}
55|            
56|    except Exception as e:
57|        logger.error(f"❌ Excepción: {e}")
58|        return {"success": False, "error": str(e)}
59|
60|@app.route('/', methods=['GET'])
61|def health_check():
62|    return jsonify({
63|        "status": "Bot FIX URGENTE running",
64|        "backend": BACKEND_URL,
65|        "version": "FIX-1.0"
66|    })
67|
68|@app.route('/webhook', methods=['POST'])
69|def telegram_webhook():
70|    """Webhook SIMPLIFICADO para recibir mensajes"""
71|    try:
72|        update = request.get_json()
73|        if not update:
74|            return jsonify({"ok": True})
75|        
76|        message = update.get('message', {})
77|        chat = message.get('chat', {})
78|        chat_id = chat.get('id')
79|        text = message.get('text', '')
80|        
81|        # Solo chat autorizado
82|        if chat_id != TELEGRAM_CHAT_ID:
83|            return jsonify({"ok": True})
84|        
85|        logger.info(f"📨 Mensaje: {text}")
86|        
87|        # Comandos especiales
88|        if text in ['/start', '/ayuda', '/help']:
89|            send_telegram_message(
90|                "🤖 *Bot Cerebro AI - FIX URGENTE*\n\n"
91|                f"🔗 Backend: {BACKEND_URL}\n"
92|                f"📱 Estado: Conectado y funcionando\n\n"
93|                "Envía cualquier mensaje para probar la conexión.",
94|                chat_id
95|            )
96|            return jsonify({"ok": True})
97|        
98|        # Procesar mensaje normal
99|        if text and not text.startswith('/'):
100|            logger.info(f"🔄 Procesando: {text}")
101|            
102|            # Llamar backend
103|            result = call_backend_agent(text, f"telegram_{chat_id}")
104|            
105|            if result['success']:
106|                mensaje = result.get('mensaje', 'Sin respuesta del backend')
107|                send_telegram_message(f"✅ {mensaje}", chat_id)
108|                logger.info("✅ Enviado correctamente")
109|            else:
110|                error = result.get('error', 'Error desconocido')
111|                send_telegram_message(f"❌ Error: {error}", chat_id)
112|                logger.error(f"❌ Error: {error}")
113|        
114|        return jsonify({"ok": True})
115|        
116|    except Exception as e:
117|        logger.error(f"❌ Error webhook: {e}")
118|        return jsonify({"ok": False, "error": str(e)}), 500
119|
120|if __name__ == "__main__":
121|    logger.info("🚀 INICIANDO BOT FIX URGENTE")
122|    logger.info(f"🔗 Backend: {BACKEND_URL}")
123|    
124|    # Test inicial
125|    try:
126|        test_response = requests.get(f"https://ai-agent-backend80.onrender.com/api/agent/status", timeout=10)
127|        if test_response.status_code == 200:
128|            logger.info("✅ Backend verificado")
129|            send_telegram_message("🔧 *Bot fix urgente activado y conectado*")
130|        else:
131|            logger.warning(f"⚠️ Backend respondió: {test_response.status_code}")
132|    except Exception as e:
133|        logger.error(f"⚠️ No se pudo verificar backend: {e}")
134|    
135|    port = int(os.environ.get('PORT', 8000))
136|    app.run(host='0.0.0.0', port=port, debug=False)
