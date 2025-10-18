"""
Servidor Web para interactuar con el Bot de Telegram
Conecta la interfaz web con el bot de Telegram y la base de datos
VERSIÓN DINÁMICA - Sin datos hardcodeados
"""
import sys
import os
import unicodedata

def normalizar_texto(texto):
    """Eliminar tildes y normalizar texto para búsquedas"""
    # Convertir a minúsculas
    texto = texto.lower()
    # Eliminar tildes
    texto = ''.join(
        c for c in unicodedata.normalize('NFD', texto)
        if unicodedata.category(c) != 'Mn'
    )
    return texto

# Agregar la carpeta raíz del proyecto al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import telebot
from config import BOT_TOKEN, CHAT_IDS, RESTAURANT_CONFIG
from bot.restaurant_message_handlers import RestaurantMessageHandlers
from database.database_multirestaurante import DatabaseManager
import threading
import time
import random
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Inicializar bot y base de datos
bot = telebot.TeleBot(BOT_TOKEN)
message_handlers = RestaurantMessageHandlers(bot)
db = DatabaseManager()

# Almacenar sesiones de chat
chat_sessions = {}

class WebChatSession:
    """Simular una sesión de chat para usuarios web"""
    def __init__(self, session_id):
        self.session_id = session_id
        self.messages = []
        self.user_id = hash(session_id) % 1000000
        self.created_at = datetime.now()
        self.cart = []
        self.customer_name = None
        self.customer_phone = None
        self.customer_address = None
        self.customer_email = None
        self.pedido_id = None
        self.cliente_id = None
        self.registration_step = "needs_name"
        self.is_registered = False
    
    def add_message(self, text, is_user=True):
        message = {
            "text": text,
            "is_user": is_user,
            "timestamp": datetime.now().strftime("%H:%M")
        }
        self.messages.append(message)
        return message
    
    def add_to_cart(self, item):
        self.cart.append(item)

class MockMessage:
    def __init__(self, text, chat_id, user_id):
        self.text = text
        self.chat = MockChat(chat_id)
        self.from_user = MockUser(user_id)
        self.message_id = int(time.time() * 1000)
    
class MockChat:
    def __init__(self, chat_id):
        self.id = chat_id
        self.type = "private"

class MockUser:
    def __init__(self, user_id):
        self.id = user_id
        self.first_name = "Cliente"
        self.last_name = "Web"
        self.username = "web_user"

def send_notification_to_group(notification_type, data, session):
    """Enviar notificación al grupo de Telegram"""
    try:
        target_chat = CHAT_IDS.get("cocina") or CHAT_IDS.get("grupo_restaurante") or CHAT_IDS.get("admin")
        
        if not target_chat:
            print("⚠ No hay grupo configurado para notificaciones")
            return
        
        if notification_type == "new_order":
            if data['items'] and isinstance(data['items'][0], dict) and 'item_nombre' in data['items'][0]:
                items_text = "\n".join([
                    f"• {item['item_nombre']} x{item['cantidad']} - ${item['subtotal']}"
                    for item in data['items']
                ])
            else:
                items_text = "\n".join([
                    f"• {item['nombre']} x{item.get('cantidad', 1)} - ${item['precio']}"
                    for item in data['items']
                ])
            
            message = f"""🆕 NUEVO PEDIDO WEB

👤 Cliente: {session.customer_name}
📱 Teléfono: {session.customer_phone}
📧 Email: {session.customer_email or 'No proporcionado'}
📍 Dirección: {session.customer_address}
🌐 Origen: Interfaz Web
🆔 Session: {session.session_id[:8]}
📋 Pedido: #{data.get('order_number', 'N/A')}

🍽 PEDIDO:
{items_text}

💰 Total: ${data['total']}
⏰ Hora: {datetime.now().strftime('%d/%m/%Y %H:%M')}
🏪 Estado: Confirmado

✅ Pedido guardado en base de datos"""
            
            bot.send_message(target_chat, message)
            print(f"✅ Pedido notificado al grupo: {target_chat}")
            
        elif notification_type == "new_message":
            message = f"""💬 MENSAJE DEL CHAT WEB

👤 Usuario: {session.customer_name or 'Sin registrar'}
💬 Mensaje: {data['message']}
⏰ {datetime.now().strftime('%H:%M')}"""
            
            bot.send_message(target_chat, message)
            print(f"✅ Mensaje notificado al grupo: {target_chat}")
            
    except Exception as e:
        print(f"❌ Error enviando notificación: {e}")
        import traceback
        traceback.print_exc()

@app.route('/')
def index():
    return render_template('public/chat.html')

@app.route('/api/send_message', methods=['POST'])
def send_message():
    try:
        data = request.json
        message_text = data.get('message', '')
        session_id = data.get('session_id', 'default')
        
        if not message_text:
            return jsonify({"error": "Mensaje vacío"}), 400
        
        if session_id not in chat_sessions:
            chat_sessions[session_id] = WebChatSession(session_id)
        
        session = chat_sessions[session_id]
        session.add_message(message_text, is_user=True)
        
        mock_message = MockMessage(
            text=message_text,
            chat_id=session.user_id,
            user_id=session.user_id
        )
        
        # Obtener respuesta del bot
        bot_response = process_bot_message(mock_message, session)
        session.add_message(bot_response, is_user=False)
        
        # ✅ Registrar interacción COMPLETA en la base de datos (CON respuesta)
        if session.cliente_id:
            db.registrar_interaccion(
                cliente_id=session.cliente_id,
                mensaje=message_text,
                respuesta=bot_response,
                tipo='web',
                restaurante_id=1  # Ajusta según tu configuración
            )
        
        important_keywords = ['pedido', 'problema', 'queja', 'urgente', 'ayuda']
        if any(keyword in message_text.lower() for keyword in important_keywords):
            send_notification_to_group("new_message", {
                "message": message_text
            }, session)
        
        return jsonify({
            "success": True,
            "bot_response": bot_response,
            "timestamp": datetime.now().strftime("%H:%M")
        })
    
    except Exception as e:
        print(f"Error en send_message: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/get_history', methods=['GET'])
def get_history():
    session_id = request.args.get('session_id', 'default')
    
    if session_id in chat_sessions:
        return jsonify({
            "success": True,
            "messages": chat_sessions[session_id].messages
        })
    
    return jsonify({
        "success": True,
        "messages": []
    })

@app.route('/api/clear_history', methods=['POST'])
def clear_history():
    data = request.json
    session_id = data.get('session_id', 'default')
    
    if session_id in chat_sessions:
        chat_sessions[session_id].messages = []
        chat_sessions[session_id].cart = []
        chat_sessions[session_id].pedido_id = None
    
    return jsonify({"success": True})

def generar_respuesta_dinamica(session, text_lower, restaurante_id=1):
    """Generar respuestas dinámicas desde la base de datos - ÚNICA FUENTE DE VERDAD"""
    
    # MENÚ COMPLETO
    if any(word in text_lower for word in ['menu', 'menú', 'carta', 'comida', 'platillos']):
        menu_completo = db.get_menu_completo_display(restaurante_id)
        
        if not menu_completo:
            return "❌ Lo siento, no hay menú disponible en este momento."
        
        respuesta = f"🍽 ¡Bienvenido a {RESTAURANT_CONFIG['nombre']}!\n\nEstas son nuestras categorías disponibles:\n\n"
        
        for idx, cat_data in enumerate(menu_completo, 1):
            cat = cat_data['categoria']
            items = cat_data['items']
            
            icono = cat.get('icono', '🍴')
            respuesta += f"{idx}⃣ {icono} {cat['nombre_display']}"
            
            if items:
                precio_min = min(item['precio'] for item in items)
                respuesta += f" (desde ${precio_min})\n"
                respuesta += "   • " + "\n   • ".join([item['nombre'] for item in items[:3]])
                if len(items) > 3:
                    respuesta += f"\n   • ... y {len(items) - 3} más"
            
            respuesta += "\n\n"
        
        respuesta += "💡 Escribe el número de la categoría que te interesa\nEjemplo: '1' para ver la primera categoría"
        return respuesta
    
    # VER CATEGORÍA ESPECÍFICA
    if text_lower.isdigit():
        num = int(text_lower)
        menu_completo = db.get_menu_completo_display(restaurante_id)
        
        if 0 < num <= len(menu_completo):
            cat_data = menu_completo[num - 1]
            cat = cat_data['categoria']
            items = cat_data['items']
            
            respuesta = f"{cat.get('icono', '🍴')} *{cat['nombre_display'].upper()}*\n\n"
            
            if cat.get('cat_descripcion'):
                respuesta += f"{cat['cat_descripcion']}\n\n"
            
            for item in items:
                estado = "✅" if item['disponible'] else "❌ AGOTADO"
                vegano = " 🌱" if item.get('vegano') else ""
                
                respuesta += f"{estado} *{item['nombre']}*{vegano}\n"
                respuesta += f"   💰 ${item['precio']} • ⏱ {item.get('tiempo_preparacion', 'N/A')}\n"
                respuesta += f"   {item['descripcion']}\n\n"
            
            respuesta += "📝 Para ordenar, escribe:\n'Quiero [nombre del platillo]'\n\n"
            respuesta += "📙 Escribe 'menú' para regresar"
            return respuesta
    
    # BUSCAR Y AGREGAR AL CARRITO
    if any(word in text_lower for word in ['quiero', 'pedir', 'ordenar', 'me gustaría']):
        # Extraer el nombre del platillo (quitar palabras de acción)
        palabras_remover = ['quiero', 'pedir', 'ordenar', 'me gustaría', 'me gustaria', 'dame', 'un', 'una', 'el', 'la', 'los', 'las']
        texto_busqueda = text_lower
        for palabra in palabras_remover:
            texto_busqueda = texto_busqueda.replace(palabra, '')
        texto_busqueda = texto_busqueda.strip()

        # Buscar item en la BD de forma dinámica
        items_encontrados = db.buscar_items_por_texto(restaurante_id, texto_busqueda)
    
        if not items_encontrados:
            return "🤔 No logré identificar ese platillo.\n\nPor favor, escribe 'menú' para ver todas las opciones disponibles."
    
        # Tomar el primer resultado
        item = items_encontrados[0]
    
        if not item['disponible']:
            return f"😔 Lo siento, *{item['nombre']}* está temporalmente agotado.\n\nEscribe 'menú' para ver otras opciones."
    
        # Agregar al carrito
        platillo = {
            'id': item['id'],
            'codigo': item['codigo'],
            'nombre': item['nombre'],
            'precio': float(item['precio']),
            'categoria': item['categoria_nombre'],
            'cantidad': 1
        } 
    
        session.add_to_cart(platillo)
        total_cart = sum(item['precio'] * item.get('cantidad', 1) for item in session.cart)
        items_count = len(session.cart)
    
        respuesta = f"✅ ¡Excelente elección!\n\n"
        respuesta += f"📦 {item['nombre']} agregado a tu pedido\n"
        respuesta += f"💰 Precio: ${item['precio']}\n\n"
        respuesta += f"🛒 Resumen de tu pedido ({items_count} items):\n"
        respuesta += "\n".join([f"• {i['nombre']} - ${i['precio'] * i.get('cantidad', 1)}" for i in session.cart])
        respuesta += f"\n\n💵 Total actual: ${total_cart}\n\n"
        respuesta += "¿Deseas agregar algo más?\n"
        respuesta += "- Escribe 'menú' para ver más opciones\n"
        respuesta += "- Escribe 'confirmar pedido' para finalizar"
    
        return respuesta
    
    # PRECIOS DINÁMICOS - Calculados desde la BD
    if any(word in text_lower for word in ['precio', 'precios', 'costo', 'cuanto', 'cuánto', 'barato', 'caro']):
        menu_completo = db.get_menu_completo_display(restaurante_id)
        
        if not menu_completo:
            return "❌ No puedo consultar los precios en este momento."
        
        respuesta = "💰 NUESTROS PRECIOS\n\n"
        
        for cat_data in menu_completo:
            cat = cat_data['categoria']
            items = cat_data['items']
            
            if items:
                precios = [item['precio'] for item in items]
                precio_min = min(precios)
                precio_max = max(precios)
                
                icono = cat.get('icono', '🍴')
                respuesta += f"{icono} {cat['nombre_display']}: ${precio_min}"
                if precio_min != precio_max:
                    respuesta += f" - ${precio_max}"
                respuesta += "\n"
        
        respuesta += f"\n🚗 Delivery: ${RESTAURANT_CONFIG['delivery']['costo_envio']}"
        respuesta += f" (pedido mínimo ${RESTAURANT_CONFIG['delivery']['pedido_minimo']})\n\n"
        respuesta += "Escribe 'menú' para ver el menú completo con todos los detalles."
        
        return respuesta
    
    # Si no coincide nada, retornar None para continuar con otros handlers
    return None

def process_bot_message(mock_message, session):
    """Procesar mensaje y obtener respuesta del bot"""
    try:
        text = mock_message.text.strip()
        text_lower = text.lower()
        
        # ✅ DEFINIR RESTAURANTE_ID
        restaurante_id = 1  # TODO: Obtener dinámicamente según configuración/sesión
        
        # PROCESO DE REGISTRO DE USUARIO
        if not session.is_registered:
            
            # Paso 1: Pedir nombre
            if session.registration_step == "needs_name":
                session.registration_step = "waiting_name"
                return f"""¡Hola! Bienvenido a {RESTAURANT_CONFIG['nombre']} 🍽

Antes de empezar, necesito conocerte un poco mejor.

👤 Por favor, dime tu nombre completo:"""
            
            # Paso 2: Guardar nombre y pedir teléfono
            elif session.registration_step == "waiting_name":
                if len(text) < 3:
                    return "❌ Por favor ingresa un nombre válido (mínimo 3 caracteres)"
                
                session.customer_name = text
                session.registration_step = "waiting_phone"
                return f"""Mucho gusto, {session.customer_name}! 😊

📱 Ahora, ¿cuál es tu número de teléfono?
(Ejemplo: 9611234567)"""
            
            # Paso 3: Guardar teléfono y pedir dirección
            elif session.registration_step == "waiting_phone":
                phone_clean = text.replace(" ", "").replace("-", "")
                if not phone_clean.isdigit() or len(phone_clean) < 10:
                    return "❌ Por favor ingresa un número de teléfono válido (10 dígitos)"
                
                session.customer_phone = phone_clean
                session.registration_step = "waiting_address"
                return """Perfecto! 📞

📍 ¿Cuál es tu dirección de entrega?
(Calle, número, colonia)"""
            
            # Paso 4: Guardar dirección, crear cliente y completar registro
            elif session.registration_step == "waiting_address":
                if len(text) < 10:
                    return "❌ Por favor proporciona una dirección más completa"
                
                session.customer_address = text
                
                cliente = db.get_or_create_cliente(
                web_session_id=session.session_id,
                nombre=session.customer_name,
                restaurante_id=restaurante_id,  # ✅ AGREGAR ESTA LÍNEA
                origen="web"
)
                
                if cliente:
                    session.cliente_id = cliente['id']
                    
                    # Actualizar datos del cliente
                    db.actualizar_cliente(
                        session.cliente_id,
                        telefono=session.customer_phone,
                        direccion=session.customer_address
                    )
                    
                    session.is_registered = True
                    session.registration_step = "completed"
                    
                    return f"""✅ ¡Registro completado!

📝 Tus datos:
👤 Nombre: {session.customer_name}
📱 Teléfono: {session.customer_phone}
📍 Dirección: {session.customer_address}

🎉 ¡Perfecto! Ahora ya puedes hacer tu pedido.

Escribe "menu" para ver nuestras deliciosas opciones 🍽"""
                else:
                    return "❌ Error al registrar tus datos. Por favor intenta de nuevo."
        
        # SI YA ESTÁ REGISTRADO, PROCESAR NORMALMENTE
        
        # ✅ USAR RESPUESTA DINÁMICA (PRIORIDAD)
        respuesta_dinamica = generar_respuesta_dinamica(session, text_lower, restaurante_id)
        if respuesta_dinamica:
            return respuesta_dinamica

        # DELIVERY - Usando solo configuración
        if any(word in text_lower for word in ['delivery', 'domicilio', 'entregar', 'llevar', 'envio', 'envío']):
            return f"""🚗 SERVICIO DE DELIVERY

📍 Cobertura: {RESTAURANT_CONFIG['delivery']['zona_cobertura']}
⏱ Tiempo: {RESTAURANT_CONFIG['delivery']['tiempo_estimado']}
💰 Costo de envío: ${RESTAURANT_CONFIG['delivery']['costo_envio']}
🛒 Pedido mínimo: ${RESTAURANT_CONFIG['delivery']['pedido_minimo']}

📞 Contacto: {RESTAURANT_CONFIG['contacto']['telefono']}

Escribe "menú" para hacer tu pedido."""

        # HORARIO - Usando solo configuración
        elif any(word in text_lower for word in ['horario', 'horarios', 'abierto', 'cerrado', 'hora', 'abren', 'cierran']):
            return f"""🕐 HORARIOS DE SERVICIO

📅 Lunes a Viernes: {RESTAURANT_CONFIG['horario']['lunes_viernes']}
📅 Sábado: {RESTAURANT_CONFIG['horario']['sabado']}
📅 Domingo: {RESTAURANT_CONFIG['horario']['domingo']}

🚗 Delivery: Mismo horario del restaurante
⏰ Última orden: 30 minutos antes del cierre

🪑 Reservaciones disponibles:
{', '.join(RESTAURANT_CONFIG['horarios_reservacion'])}

¡Te esperamos!"""

        # CONTACTO - Usando solo configuración
        elif any(word in text_lower for word in ['donde', 'dirección', 'direccion', 'ubicación', 'ubicacion', 'telefono', 'teléfono', 'contacto', 'llamar']):
            return f"""📞 INFORMACIÓN DE CONTACTO

🏨 {RESTAURANT_CONFIG['nombre']}

📍 Dirección:
{RESTAURANT_CONFIG['contacto']['direccion']}

📱 Teléfono: {RESTAURANT_CONFIG['contacto']['telefono']}
💬 WhatsApp: {RESTAURANT_CONFIG['contacto']['whatsapp']}
📧 Email: {RESTAURANT_CONFIG['contacto']['email']}

🕐 Horario: {RESTAURANT_CONFIG['horario']['lunes_viernes']}

¡Estamos aquí para servirte!"""

        # CONFIRMAR PEDIDO
        elif 'confirmar' in text_lower and 'pedido' in text_lower:
            if len(session.cart) == 0:
                return """🛒 Tu carrito está vacío
        
Aún no has agregado ningún platillo a tu pedido.

Escribe "menú" para ver nuestras opciones."""
            
            try:
                resultado_pedido = db.crear_pedido_simple(restaurante_id, session.cliente_id, 'delivery', 'web')
                if not resultado_pedido or 'pedido_id' not in resultado_pedido:
                    return "❌ Error al crear el pedido. Por favor intenta de nuevo."
                
                pedido_id = resultado_pedido['pedido_id']
                numero_pedido = resultado_pedido['numero_pedido']
                session.pedido_id = pedido_id
                
                print(f"✅ Pedido creado - ID: {pedido_id}, Número: {numero_pedido}")
                
                items_agregados = 0
                for item in session.cart:
                    # Agregar directamente usando el código que ya viene del carrito
                    success = db.agregar_item_pedido(pedido_id, item['id'], item.get('cantidad', 1), float(item['precio']))
                    if success:
                        items_agregados += 1
                        print(f"✅ Item agregado: {item['nombre']}")
                    else:
                        print(f"⚠ No se pudo agregar: {item['nombre']}")
                
                if items_agregados == 0:
                    return "❌ No se pudieron agregar los items al pedido. Por favor intenta de nuevo."
                
                db.actualizar_estado_pedido(pedido_id, 'confirmado')
                
                pedido_final = db.get_pedido(pedido_id)
                detalles = db.get_detalle_pedido(pedido_id)
                
                if not pedido_final or not detalles:
                    print("⚠ No se pudieron obtener los detalles finales del pedido")
                    total = sum(item['precio'] * item.get('cantidad', 1) for item in session.cart)
                    order_summary = "\n".join([
                        f"• {item['nombre']} x{item.get('cantidad', 1)} - ${item['precio'] * item.get('cantidad', 1)}" 
                        for item in session.cart
                    ])
                else:
                    total = float(pedido_final['total'])
                    order_summary = "\n".join([
                        f"• {d['item_nombre']} x{d['cantidad']} - ${d['subtotal']}" 
                        for d in detalles
                    ])
                
                send_notification_to_group("new_order", {
                    "items": detalles if detalles else session.cart,
                    "total": total,
                    "order_number": numero_pedido
                }, session)
                
                session.cart = []
                
                return f"""✅ ¡PEDIDO CONFIRMADO!

🎫 Número de orden: {numero_pedido}

👤 Cliente: {session.customer_name}
📱 Teléfono: {session.customer_phone}
📍 Dirección: {session.customer_address}

📋 Tu pedido:
{order_summary}

💵 Total: ${total:.2f}

📞 Próximos pasos:
1️⃣ Te contactaremos al: {session.customer_phone}
2️⃣ Confirmaremos método de pago
3️⃣ Prepararemos tu pedido
4️⃣ ¡Te notificaremos cuando esté listo!

⏱ Tiempo estimado: {RESTAURANT_CONFIG['delivery']['tiempo_estimado']}

✅ Tu pedido ha sido guardado en nuestra base de datos

¡Gracias por elegirnos!

Escribe "menú" para hacer otro pedido."""
            
            except Exception as e:
                print(f"❌ Error confirmando pedido: {e}")
                import traceback
                traceback.print_exc()
                return "❌ Hubo un error al confirmar tu pedido. Por favor contacta al restaurante."

        # CANCELAR PEDIDO
        elif 'cancelar' in text_lower and 'pedido' in text_lower:
            session.cart = []
            return """🗑 Pedido cancelado

Tu carrito ha sido limpiado.

¿Deseas empezar un nuevo pedido?
Escribe "menú" para ver nuestras opciones."""

        # ✅ VER CARRITO MEJORADO
        elif 'carrito' in text_lower or 'pedido actual' in text_lower:
            if len(session.cart) == 0:
                return """🛒 Tu carrito está vacío

Aún no has agregado productos.

Escribe "menú" para ver nuestras opciones."""
            
            # ✅ Calcular total correctamente con cantidad
            total = sum(item['precio'] * item.get('cantidad', 1) for item in session.cart)
            
            # ✅ Mostrar cantidad en la lista
            items_list = "\n".join([
                f"• {item['nombre']} x{item.get('cantidad', 1)} - ${item['precio'] * item.get('cantidad', 1)}" 
                for item in session.cart
            ])
            
            return f"""🛒 Tu Carrito ({len(session.cart)} items)

{items_list}

💵 Total: ${total:.2f}

Opciones:
- Escribe "confirmar pedido" para finalizar
- Escribe "menú" para agregar más items
- Escribe "cancelar pedido" para limpiar"""

        # SALUDOS
        elif any(word in text_lower for word in ['hola', 'buenas', 'hi', 'hello', 'buenos días', 'buenas tardes', 'buenas noches', 'buen día']):
            saludos = [
                f"¡Bienvenido a {RESTAURANT_CONFIG['nombre']}! ¿Listo para una experiencia culinaria única?",
                f"¡Buen día! Me da mucho gusto saludarte. ¿Qué se te antoja hoy?",
                "¡Has llegado al lugar correcto para disfrutar de deliciosa comida!"
            ]
            return random.choice(saludos) + "\n\nEscribe 'menu' para ver todas nuestras opciones."

        # AGRADECIMIENTOS
        elif any(word in text_lower for word in ['gracias', 'excelente', 'perfecto', 'buenísimo', 'delicioso', 'rico']):
            return """¡Muchas gracias!

Nos hace muy felices poder ayudarte. Tu satisfacción es nuestra mayor recompensa.

¿Hay algo más en lo que pueda asistirte?
Escribe "menú" para ver nuestras opciones."""

        # DESPEDIDAS
        elif any(word in text_lower for word in ['adios', 'adiós', 'bye', 'hasta luego', 'nos vemos', 'chao']):
            despedidas = [
                f"¡Adiós! Esperamos verte pronto en {RESTAURANT_CONFIG['nombre']}!",
                "¡Hasta pronto! Que tengas un día delicioso",
                "¡Chao! Gracias por visitarnos. Te esperamos con los brazos abiertos!"
            ]
            return random.choice(despedidas)

        # ✅ RESPUESTA POR DEFECTO MEJORADA
        else:
            return """¿Te puedo ayudar con algo específico?

Puedo ayudarte con:
• Ver el menú (escribe "menú")
• Consultar precios
• Información de delivery y horarios
• Ver tu carrito actual

Para ordenar, escribe:
"Quiero [nombre del platillo]"

¿Qué necesitas? 🍽️"""
    
    except Exception as e:
        print(f"Error procesando mensaje: {e}")
        import traceback
        traceback.print_exc()
        return "Lo siento, hubo un error al procesar tu mensaje. ¿Podrías intentarlo de nuevo?"

def run_flask_server():
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)

if __name__ == "__main__":
    print("=" * 60)
    print("🌐 Iniciando Servidor Web para Bot de Restaurante")
    print("=" * 60)
    print("🔗 Servidor: http://localhost:5000")
    print("🤖 Bot de Telegram conectado")
    print("🗄 Base de datos MySQL conectada")
    print(f"📱 Grupo notificaciones: {CHAT_IDS.get('cocina', CHAT_IDS.get('admin', 'No configurado'))}")
    print("✅ Listo para recibir mensajes desde la web")
    print("🎯 MODO DINÁMICO: Todo se consulta desde la BD")
    print("=" * 60)
    
    run_flask_server()