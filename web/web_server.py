"""
Servidor Web para interactuar con el Bot de Telegram
Conecta la interfaz web con el bot de Telegram y la base de datos
VERSIÓN MULTI-RESTAURANTE - Dinámico por Slug
"""
import sys
import os
import unicodedata
import json
from datetime import datetime

def normalizar_texto(texto):
    """Eliminar tildes y normalizar texto para búsquedas"""
    texto = texto.lower()
    texto = ''.join(
        c for c in unicodedata.normalize('NFD', texto)
        if unicodedata.category(c) != 'Mn'
    )
    return texto

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

app = Flask(__name__)
CORS(app)

bot = telebot.TeleBot(BOT_TOKEN)
message_handlers = RestaurantMessageHandlers(bot)
db = DatabaseManager()

chat_sessions = {}

# ==================== AGREGAR ESTAS FUNCIONES AL INICIO (después de los imports) ====================

def obtener_info_horarios(restaurante_id):
    """Obtener horarios dinámicos desde la BD"""
    from database.database_multirestaurante import get_db_cursor
    
    with get_db_cursor() as (cursor, conn):
        cursor.execute("SELECT horarios FROM restaurantes WHERE id = %s", (restaurante_id,))
        result = cursor.fetchone()
    
    if not result or not result['horarios']:
        # Fallback a config.py si no hay horarios configurados
        return None
    
    try:
        horarios = json.loads(result['horarios']) if isinstance(result['horarios'], str) else result['horarios']
        return horarios
    except:
        return None


def generar_texto_horarios(restaurante_id):
    """Generar texto de horarios para mostrar en el chat"""
    horarios = obtener_info_horarios(restaurante_id)
    
    if not horarios:
        # Fallback al config.py
        return f"""🕐 HORARIOS DE SERVICIO

📅 Lunes a Viernes: {RESTAURANT_CONFIG['horario']['lunes_viernes']}
📅 Sábado: {RESTAURANT_CONFIG['horario']['sabado']}
📅 Domingo: {RESTAURANT_CONFIG['horario']['domingo']}

🚗 Delivery: Mismo horario del restaurante
⏰ Última orden: 30 minutos antes del cierre

¡Te esperamos!"""
    
    # Construir texto desde BD
    dias_nombres = {
        'lunes': 'Lunes',
        'martes': 'Martes',
        'miercoles': 'Miércoles',
        'jueves': 'Jueves',
        'viernes': 'Viernes',
        'sabado': 'Sábado',
        'domingo': 'Domingo'
    }
    
    texto = "🕐 HORARIOS DE ATENCIÓN\n\n"
    
    for dia_key, dia_nombre in dias_nombres.items():
        if dia_key in horarios:
            horario = horarios[dia_key]
            
            if not horario.get('activo', False):
                texto += f"📅 {dia_nombre}: Cerrado\n"
            elif horario.get('24h', False):
                texto += f"📅 {dia_nombre}: Abierto 24 horas\n"
            else:
                apertura = horario.get('apertura', '09:00')
                cierre = horario.get('cierre', '22:00')
                texto += f"📅 {dia_nombre}: {apertura} - {cierre}\n"
    
    # Verificar si está abierto ahora
    from datetime import datetime
    now = datetime.now()
    dia_actual = ['lunes', 'martes', 'miercoles', 'jueves', 'viernes', 'sabado', 'domingo'][now.weekday()]
    
    if dia_actual in horarios:
        horario_hoy = horarios[dia_actual]
        if horario_hoy.get('activo', False):
            if horario_hoy.get('24h', False):
                texto += f"\n🟢 Abierto ahora (24 horas)"
            else:
                hora_actual = now.time()
                try:
                    from datetime import time
                    apertura = datetime.strptime(horario_hoy['apertura'], '%H:%M').time()
                    cierre = datetime.strptime(horario_hoy['cierre'], '%H:%M').time()
                    
                    if apertura <= hora_actual <= cierre:
                        texto += f"\n🟢 Abierto ahora (hasta las {horario_hoy['cierre']})"
                    elif hora_actual < apertura:
                        texto += f"\n🔴 Cerrado (Abre a las {horario_hoy['apertura']})"
                    else:
                        texto += f"\n🔴 Cerrado (Cierra a las {horario_hoy['cierre']})"
                except:
                    pass
        else:
            texto += f"\n🔴 Cerrado hoy"
    
    texto += "\n\n¡Te esperamos!"
    return texto


def obtener_info_delivery(restaurante_id):
    """Obtener configuración de delivery desde la BD"""
    from database.database_multirestaurante import get_db_cursor
    
    with get_db_cursor() as (cursor, conn):
        cursor.execute("SELECT config_delivery FROM restaurantes WHERE id = %s", (restaurante_id,))
        result = cursor.fetchone()
    
    if not result or not result['config_delivery']:
        return None
    
    try:
        config = json.loads(result['config_delivery']) if isinstance(result['config_delivery'], str) else result['config_delivery']
        return config
    except:
        return None


def generar_texto_delivery(restaurante_id):
    """Generar texto de delivery para mostrar en el chat"""
    config = obtener_info_delivery(restaurante_id)
    
    if not config:
        # Fallback al config.py
        return f"""🚗 SERVICIO DE DELIVERY

📍 Cobertura: {RESTAURANT_CONFIG['delivery']['zona_cobertura']}
⏱ Tiempo: {RESTAURANT_CONFIG['delivery']['tiempo_estimado']}
💰 Costo de envío: ${RESTAURANT_CONFIG['delivery']['costo_envio']}
🛒 Pedido mínimo: ${RESTAURANT_CONFIG['delivery']['pedido_minimo']}

📞 Contacto: {RESTAURANT_CONFIG['contacto']['telefono']}

Escribe "menú" para hacer tu pedido."""
    
    # Construir texto desde BD
    texto = "🚗 INFORMACIÓN DE DELIVERY\n\n"
    
    if not config.get('activo', True):
        texto += "🚫 Delivery no disponible en este momento.\n"
        texto += "Puedes hacer tu pedido para recoger en el local.\n\n"
        texto += "Escribe 'menú' para ver nuestras opciones."
        return texto
    
    texto += f"💰 Costo de envío: ${config.get('costo_envio_base', 35):.2f}\n"
    texto += f"🛒 Pedido mínimo: ${config.get('pedido_minimo', 150):.2f}\n"
    
    if config.get('envio_gratis_desde', 0) > 0:
        texto += f"🎁 Envío GRATIS desde: ${config['envio_gratis_desde']:.2f}\n"
    
    texto += f"⏱ Tiempo estimado: {config.get('tiempo_entrega', '30-45 minutos')}\n"
    
    # Zonas de cobertura
    zonas = config.get('zonas_cobertura', [])
    if zonas:
        texto += f"\n📍 Zonas de cobertura:\n"
        for zona in zonas:
            if zona.strip():  # Evitar líneas vacías
                texto += f"   • {zona}\n"
    
    texto += "\nEscribe 'menú' para hacer tu pedido."
    return texto


def calcular_costo_envio_dinamico(restaurante_id, subtotal):
    """Calcular costo de envío según configuración de la BD"""
    config = obtener_info_delivery(restaurante_id)
    
    if not config:
        # Fallback
        return RESTAURANT_CONFIG['delivery']['costo_envio'], RESTAURANT_CONFIG['delivery']['pedido_minimo']
    
    if not config.get('activo', True):
        return 0, 0
    
    pedido_minimo = config.get('pedido_minimo', 150)
    
    # Verificar envío gratis
    envio_gratis_desde = config.get('envio_gratis_desde', 0)
    if envio_gratis_desde > 0 and subtotal >= envio_gratis_desde:
        return 0, pedido_minimo
    
    # Costo normal
    costo_envio = config.get('costo_envio_base', 35)
    return costo_envio, pedido_minimo


class WebChatSession:
    """Simular una sesión de chat para usuarios web"""
    def __init__(self, session_id, restaurante_id):
        self.session_id = session_id
        self.restaurante_id = restaurante_id
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
        
        self.reservation_step = None
        self.reservation_date = None
        self.reservation_time = None
        self.reservation_people = None
        self.reservation_occasion = None
        self.reservation_notes = None
    
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
            
        elif notification_type == "new_reservation":
            reservacion = data['reservacion']
            
            message = f"""🎯 NUEVA RESERVACIÓN WEB

👤 Cliente: {session.customer_name}
📱 Teléfono: {session.customer_phone}
🆔 Código: {reservacion['codigo_reservacion']}

📅 Fecha: {data['fecha']}
⏰ Hora: {data['hora']}
👥 Personas: {data['personas']}"""
            
            if data.get('ocasion'):
                message += f"\n🎉 Ocasión: {data['ocasion']}"
            
            if data.get('notas'):
                message += f"\n📝 Notas: {data['notas']}"
            
            message += f"""

🌐 Origen: Interfaz Web
⏰ Registrado: {datetime.now().strftime('%d/%m/%Y %H:%M')}
✅ Estado: Pendiente de confirmación"""
            
            bot.send_message(target_chat, message)
            print(f"✅ Reservación notificada al grupo: {target_chat}")
            
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

def process_reservacion_flow(session, text_lower, text):
    """Procesar el flujo de reservaciones"""
    
    if any(word in text_lower for word in ['reservar', 'reserva', 'reservación', 'mesa', 'apartar']):
        if not session.is_registered:
            return "Para hacer una reservación, primero necesito que te registres. Escribe cualquier cosa para comenzar."
        
        session.reservation_step = "waiting_date"
        return f"""🎯 ¡Perfecto! Vamos a hacer tu reservación.

📅 ¿Para qué fecha deseas reservar?
(Formato: DD/MM/AAAA o escribe 'hoy' o 'mañana')

Ejemplo: 25/10/2025"""
    
    if hasattr(session, 'reservation_step'):
        
        if session.reservation_step == "waiting_date":
            from datetime import datetime, timedelta
            
            fecha = None
            if text_lower == 'hoy':
                fecha = datetime.now().date()
            elif text_lower in ['mañana', 'manana']:
                fecha = (datetime.now() + timedelta(days=1)).date()
            else:
                try:
                    fecha = datetime.strptime(text, '%d/%m/%Y').date()
                except:
                    return "❌ Formato de fecha incorrecto. Por favor usa DD/MM/AAAA\nEjemplo: 25/10/2025"
            
            if fecha < datetime.now().date():
                return "❌ No puedes reservar para una fecha pasada. Por favor elige una fecha futura."
            
            session.reservation_date = fecha
            session.reservation_step = "waiting_time"
            
            return f"""✅ Fecha: {fecha.strftime('%d/%m/%Y')}

⏰ ¿A qué hora?
(Formato: HH:MM - horario de 24 horas)

Ejemplo: 19:00 o 20:30"""
        
        elif session.reservation_step == "waiting_time":
            try:
                from datetime import datetime
                hora_obj = datetime.strptime(text, '%H:%M').time()
                
                session.reservation_time = hora_obj
                session.reservation_step = "waiting_people"
                
                return f"""✅ Hora: {hora_obj.strftime('%H:%M')}

👥 ¿Para cuántas personas?
(Escribe un número entre 1 y 20)

Ejemplo: 4"""
            except:
                return "❌ Formato de hora incorrecto. Por favor usa HH:MM\nEjemplo: 19:00"
        
        elif session.reservation_step == "waiting_people":
            try:
                personas = int(text)
                if personas < 1 or personas > 20:
                    return "❌ El número de personas debe estar entre 1 y 20."
                
                session.reservation_people = personas
                session.reservation_step = "waiting_occasion"
                
                return f"""✅ Mesa para {personas} personas

🎉 ¿Es una ocasión especial? (opcional)
Elige una opción o escribe 'ninguna':

1. Cumpleaños
2. Aniversario
3. Cita romántica
4. Reunión de negocios
5. Celebración
6. Ninguna"""
            except:
                return "❌ Por favor escribe solo el número de personas.\nEjemplo: 4"
        
        elif session.reservation_step == "waiting_occasion":
            ocasiones = {
                '1': 'Cumpleaños',
                '2': 'Aniversario', 
                '3': 'Cita romántica',
                '4': 'Reunión de negocios',
                '5': 'Celebración',
                '6': 'Ninguna',
                'ninguna': 'Ninguna'
            }
            
            ocasion = ocasiones.get(text_lower, text if len(text) < 50 else 'Ninguna')
            session.reservation_occasion = None if ocasion == 'Ninguna' else ocasion
            session.reservation_step = "waiting_notes"
            
            return f"""✅ Ocasión: {ocasion}

📝 ¿Alguna nota especial?
(Alergias, preferencias de mesa, etc.)

Escribe 'no' si no tienes notas especiales."""
        
        elif session.reservation_step == "waiting_notes":
            notas = None if text_lower in ['no', 'ninguna', 'nada'] else text
            session.reservation_notes = notas
            session.reservation_step = "confirm"
            
            from datetime import datetime
            fecha_formato = session.reservation_date.strftime('%d/%m/%Y')
            hora_formato = session.reservation_time.strftime('%H:%M')
            
            resumen = f"""📋 RESUMEN DE TU RESERVACIÓN

👤 Nombre: {session.customer_name}
📱 Teléfono: {session.customer_phone}
📅 Fecha: {fecha_formato}
⏰ Hora: {hora_formato}
👥 Personas: {session.reservation_people}"""
            
            if session.reservation_occasion:
                resumen += f"\n🎉 Ocasión: {session.reservation_occasion}"
            
            if notas:
                resumen += f"\n📝 Notas: {notas}"
            
            resumen += "\n\n✅ Escribe 'confirmar' para completar la reservación"
            resumen += "\n❌ Escribe 'cancelar' para empezar de nuevo"
            
            return resumen
        
        elif session.reservation_step == "confirm":
            if 'confirmar' in text_lower:
                fecha_guardada = session.reservation_date
                hora_guardada = session.reservation_time
                personas_guardadas = session.reservation_people
                ocasion_guardada = session.reservation_occasion
                notas_guardadas = session.reservation_notes
        
                reservacion = db.crear_reservacion(
                    restaurante_id=session.restaurante_id,
                    cliente_id=session.cliente_id,
                    nombre=session.customer_name,
                    telefono=session.customer_phone,
                    fecha=fecha_guardada,
                    hora=hora_guardada,
                    personas=personas_guardadas,
                    origen='web'
                )
        
                if reservacion:
                    if ocasion_guardada or notas_guardadas:
                        from database.database_multirestaurante import get_db_cursor
                        with get_db_cursor() as (cursor, conn):
                            cursor.execute("""
                                UPDATE reservaciones 
                                SET ocasion_especial = %s, notas_especiales = %s
                                WHERE id = %s
                            """, (ocasion_guardada, notas_guardadas, reservacion['id']))
                            conn.commit()
            
                    send_notification_to_group("new_reservation", {
                        'reservacion': reservacion,
                        'fecha': fecha_guardada.strftime('%d/%m/%Y'),
                        'hora': hora_guardada.strftime('%H:%M'),
                        'personas': personas_guardadas,
                        'ocasion': ocasion_guardada,
                        'notas': notas_guardadas
                    }, session)
            
                    mensaje_confirmacion = f"""✅ ¡RESERVACIÓN CONFIRMADA!

🎫 Código: {reservacion['codigo_reservacion']}

📅 {fecha_guardada.strftime('%d/%m/%Y')} a las {hora_guardada.strftime('%H:%M')}
👥 Mesa para {personas_guardadas} personas
👤 A nombre de: {session.customer_name}
📱 Teléfono: {session.customer_phone}"""

                    if ocasion_guardada:
                        mensaje_confirmacion += f"\n🎉 Ocasión: {ocasion_guardada}"
            
                    if notas_guardadas:
                        mensaje_confirmacion += f"\n📝 Notas: {notas_guardadas}"

                    mensaje_confirmacion += """

📞 CONFIRMACIÓN:
Te contactaremos al número registrado para confirmar tu reservación.

⚠️ IMPORTANTE:
• Llega 10 minutos antes de tu hora
• Tiempo de tolerancia: 15 minutos
• Si no puedes asistir, avísanos con anticipación

¡Te esperamos! 🍽️

Escribe 'menú' para hacer un pedido
Escribe 'reservar' para hacer otra reservación"""
            
                    delattr(session, 'reservation_step')
                    delattr(session, 'reservation_date')
                    delattr(session, 'reservation_time')
                    delattr(session, 'reservation_people')
                    delattr(session, 'reservation_occasion')
                    delattr(session, 'reservation_notes')
            
                    return mensaje_confirmacion
                else:
                    if hasattr(session, 'reservation_step'):
                        delattr(session, 'reservation_step')
                    return "❌ Error al crear la reservación. Por favor intenta de nuevo o contáctanos directamente."
    
            elif 'cancelar' in text_lower:
                if hasattr(session, 'reservation_step'):
                    delattr(session, 'reservation_step')
                    if hasattr(session, 'reservation_date'):
                        delattr(session, 'reservation_date')
                    if hasattr(session, 'reservation_time'):
                        delattr(session, 'reservation_time')
                    if hasattr(session, 'reservation_people'):
                        delattr(session, 'reservation_people')
                    if hasattr(session, 'reservation_occasion'):
                        delattr(session, 'reservation_occasion')
                    if hasattr(session, 'reservation_notes'):
                        delattr(session, 'reservation_notes')
        
                return "❌ Reservación cancelada.\n\nEscribe 'reservar' para intentar de nuevo."
    
    return None

@app.route('/')
def home():
    """Redirigir al primer restaurante o mostrar mensaje"""
    from flask import redirect
    from database.database_multirestaurante import get_db_cursor
    
    with get_db_cursor() as (cursor, conn):
        cursor.execute("""
            SELECT slug FROM restaurantes 
            WHERE estado = 'activo' 
            ORDER BY id ASC LIMIT 1
        """)
        restaurante = cursor.fetchone()
    
    if restaurante:
        return redirect(f"/{restaurante['slug']}/")
    
    return "<h1>Acceso no autorizado</h1>", 403

@app.route('/<slug>/')
def index(slug):
    """Chat del restaurante según su slug"""
    restaurante = db.get_restaurante_por_slug(slug)
    
    if not restaurante:
        return """
        <h1>❌ Restaurante no encontrado</h1>
        <p>El restaurante que buscas no existe o está inactivo.</p>
        <p><a href="http://localhost:5001/register">¿Quieres registrar tu restaurante?</a></p>
        """, 404
    
    return render_template('public/chat.html', restaurante=restaurante)

@app.route('/api/send_message', methods=['POST'])
def send_message():
    try:
        data = request.json
        message_text = data.get('message', '')
        session_id = data.get('session_id', 'default')
        
        # ✅ Obtener slug del restaurante
        restaurante_slug = data.get('restaurante_slug')
        
        if not restaurante_slug:
            return jsonify({"error": "Falta restaurante_slug"}), 400
        
        # Obtener restaurante por slug
        restaurante = db.get_restaurante_por_slug(restaurante_slug)
        
        if not restaurante:
            return jsonify({"error": "Restaurante no encontrado"}), 404
        
        restaurante_id = restaurante['id']
        
        if not message_text:
            return jsonify({"error": "Mensaje vacío"}), 400
        
        # Crear o recuperar sesión con restaurante_id
        if session_id not in chat_sessions:
            chat_sessions[session_id] = WebChatSession(session_id, restaurante_id)
        
        session = chat_sessions[session_id]
        session.add_message(message_text, is_user=True)
        
        mock_message = MockMessage(
            text=message_text,
            chat_id=session.user_id,
            user_id=session.user_id
        )
        
        # Obtener respuesta del bot (PASAR restaurante_id)
        bot_response = process_bot_message(mock_message, session, restaurante_id)
        session.add_message(bot_response, is_user=False)
        
        # Registrar interacción
        if session.cliente_id:
            db.registrar_interaccion(
                cliente_id=session.cliente_id,
                mensaje=message_text,
                respuesta=bot_response,
                tipo='web',
                restaurante_id=restaurante_id
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

def generar_respuesta_dinamica(session, text_lower, restaurante_id):
    """Generar respuestas dinámicas desde la base de datos"""
    
    if any(word in text_lower for word in ['menu', 'menú', 'carta', 'comida', 'platillos']):
        menu_completo = db.get_menu_completo_display(restaurante_id)
        
        if not menu_completo:
            return "❌ Lo siento, no hay menú disponible en este momento."
        
        restaurante = db.get_restaurante_por_slug(session.restaurante_id) if hasattr(session, 'restaurante_id') else None
        nombre_restaurante = restaurante['nombre_restaurante'] if restaurante else "Nuestro Restaurante"
        
        respuesta = f"🍽 ¡Bienvenido a {nombre_restaurante}!\n\nEstas son nuestras categorías disponibles:\n\n"
        
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
    
    if any(word in text_lower for word in ['quiero', 'pedir', 'ordenar', 'me gustaría']):
        palabras_remover = ['quiero', 'pedir', 'ordenar', 'me gustaría', 'me gustaria', 'dame', 'un', 'una', 'el', 'la', 'los', 'las']
        texto_busqueda = text_lower
        for palabra in palabras_remover:
            texto_busqueda = texto_busqueda.replace(palabra, '')
        texto_busqueda = texto_busqueda.strip()

        items_encontrados = db.buscar_items_por_texto(restaurante_id, texto_busqueda)
    
        if not items_encontrados:
            return "🤔 No logré identificar ese platillo.\n\nPor favor, escribe 'menú' para ver todas las opciones disponibles."
    
        item = items_encontrados[0]
    
        if not item['disponible']:
            return f"😔 Lo siento, *{item['nombre']}* está temporalmente agotado.\n\nEscribe 'menú' para ver otras opciones."
    
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
        
        # Usar función dinámica para obtener costo de envío
        costo_envio, pedido_minimo = calcular_costo_envio_dinamico(restaurante_id, 0)
        respuesta += f"\n🚗 Delivery: ${costo_envio}"
        respuesta += f" (pedido mínimo ${pedido_minimo})\n\n"
        respuesta += "Escribe 'menú' para ver el menú completo con todos los detalles."
        
        return respuesta
    
    return None

def process_bot_message(mock_message, session, restaurante_id):
    """Procesar mensaje y obtener respuesta del bot"""
    try:
        text = mock_message.text.strip()
        text_lower = text.lower()
        
        if session.is_registered:
            reservacion_response = process_reservacion_flow(session, text_lower, text)
            if reservacion_response:
                return reservacion_response
        
        reservacion_response = process_reservacion_flow(session, text_lower, text)
        if reservacion_response:
            return reservacion_response
        
        if not session.is_registered:
            
            if session.registration_step == "needs_name":
                session.registration_step = "waiting_name"
                
                restaurante = None
                from database.database_multirestaurante import get_db_cursor
                with get_db_cursor() as (cursor, conn):
                    cursor.execute("SELECT nombre_restaurante FROM restaurantes WHERE id = %s", (restaurante_id,))
                    result = cursor.fetchone()
                    if result:
                        restaurante = result
                
                nombre_rest = restaurante['nombre_restaurante'] if restaurante else "nuestro restaurante"
                
                return f"""¡Hola! Bienvenido a {nombre_rest} 🍽

Antes de empezar, necesito conocerte un poco mejor.

👤 Por favor, dime tu nombre completo:"""
            
            elif session.registration_step == "waiting_name":
                if len(text) < 3:
                    return "❌ Por favor ingresa un nombre válido (mínimo 3 caracteres)"
                
                session.customer_name = text
                session.registration_step = "waiting_phone"
                return f"""Mucho gusto, {session.customer_name}! 😊

📱 Ahora, ¿cuál es tu número de teléfono?
(Ejemplo: 9611234567)"""
            
            elif session.registration_step == "waiting_phone":
                phone_clean = text.replace(" ", "").replace("-", "")
                if not phone_clean.isdigit() or len(phone_clean) < 10:
                    return "❌ Por favor ingresa un número de teléfono válido (10 dígitos)"
                
                session.customer_phone = phone_clean
                session.registration_step = "waiting_address"
                return """Perfecto! 📞

📍 ¿Cuál es tu dirección de entrega?
(Calle, número, colonia)"""
            
            elif session.registration_step == "waiting_address":
                if len(text) < 10:
                    return "❌ Por favor proporciona una dirección más completa"
                
                session.customer_address = text
                
                cliente = db.get_or_create_cliente(
                    web_session_id=session.session_id,
                    nombre=session.customer_name,
                    restaurante_id=restaurante_id,
                    origen="web"
                )
                
                if cliente:
                    session.cliente_id = cliente['id']
                    
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
        
        respuesta_dinamica = generar_respuesta_dinamica(session, text_lower, restaurante_id)
        if respuesta_dinamica:
            return respuesta_dinamica

        # ==================== REEMPLAZAR ESTAS SECCIONES EN process_bot_message() ====================

        elif any(word in text_lower for word in ['delivery', 'domicilio', 'entregar', 'llevar', 'envio', 'envío']):
            return generar_texto_delivery(restaurante_id)

        elif any(word in text_lower for word in ['horario', 'horarios', 'abierto', 'cerrado', 'hora', 'abren', 'cierran']):
            return generar_texto_horarios(restaurante_id)

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

        elif 'confirmar' in text_lower and 'pedido' in text_lower:
            if len(session.cart) == 0:
                return """🛒 Tu carrito está vacío
        
Aún no has agregado ningún platillo a tu pedido.

Escribe "menú" para ver nuestras opciones."""
            
            try:
                # ==================== ACTUALIZAR CÁLCULO DE TOTAL EN CONFIRMAR PEDIDO ====================
                
                # Calcular subtotal
                subtotal = sum(item['precio'] * item.get('cantidad', 1) for item in session.cart)
                
                # Calcular costo de envío dinámicamente
                costo_envio, pedido_minimo = calcular_costo_envio_dinamico(restaurante_id, subtotal)
                
                # Validar pedido mínimo
                if subtotal < pedido_minimo:
                    faltante = pedido_minimo - subtotal
                    return f"""❌ PEDIDO MÍNIMO NO ALCANZADO

💰 Subtotal: ${subtotal:.2f}
🛒 Pedido mínimo: ${pedido_minimo:.2f}
❗ Te faltan: ${faltante:.2f}

Escribe 'menú' para agregar más items."""
                
                # Calcular total con envío
                total = subtotal + costo_envio
                
                resultado_pedido = db.crear_pedido_simple(restaurante_id, session.cliente_id, 'delivery', 'web')
                if not resultado_pedido or 'pedido_id' not in resultado_pedido:
                    return "❌ Error al crear el pedido. Por favor intenta de nuevo."
                
                pedido_id = resultado_pedido['pedido_id']
                numero_pedido = resultado_pedido['numero_pedido']
                session.pedido_id = pedido_id
                
                print(f"✅ Pedido creado - ID: {pedido_id}, Número: {numero_pedido}")
                
                items_agregados = 0
                for item in session.cart:
                    success = db.agregar_item_pedido(pedido_id, item['id'], item.get('cantidad', 1), float(item['precio']))
                    if success:
                        items_agregados += 1
                        print(f"✅ Item agregado: {item['nombre']}")
                    else:
                        print(f"⚠ No se pudo agregar: {item['nombre']}")
                
                if items_agregados == 0:
                    return "❌ No se pudieron agregar los items al pedido. Por favor intenta de nuevo."
                
                # Actualizar total del pedido con envío
                from database.database_multirestaurante import get_db_cursor
                with get_db_cursor() as (cursor, conn):
                    cursor.execute("""
                        UPDATE pedidos 
                        SET total = %s, costo_envio = %s
                        WHERE id = %s
                    """, (total, costo_envio, pedido_id))
                    conn.commit()
                
                db.actualizar_estado_pedido(pedido_id, 'confirmado')
                
                pedido_final = db.get_pedido(pedido_id)
                detalles = db.get_detalle_pedido(pedido_id)
                
                if not pedido_final or not detalles:
                    print("⚠ No se pudieron obtener los detalles finales del pedido")
                    order_summary = "\n".join([
                        f"• {item['nombre']} x{item.get('cantidad', 1)} - ${item['precio'] * item.get('cantidad', 1)}" 
                        for item in session.cart
                    ])
                else:
                    order_summary = "\n".join([
                        f"• {d['item_nombre']} x{d['cantidad']} - ${d['subtotal']}" 
                        for d in detalles
                    ])
                
                # Mensaje de costo con desglose
                mensaje_costo = f"""💵 DESGLOSE:
🍽️ Subtotal: ${subtotal:.2f}
🚗 Envío: ${costo_envio:.2f}"""
                
                if costo_envio == 0 and subtotal >= obtener_info_delivery(restaurante_id).get('envio_gratis_desde', 999999):
                    mensaje_costo += " ¡GRATIS! 🎉"
                
                mensaje_costo += f"\n💰 TOTAL: ${total:.2f}"
                
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

{mensaje_costo}

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

        elif 'cancelar' in text_lower and 'pedido' in text_lower:
            session.cart = []
            return """🗑 Pedido cancelado

Tu carrito ha sido limpiado.

¿Deseas empezar un nuevo pedido?
Escribe "menú" para ver nuestras opciones."""

        elif 'carrito' in text_lower or 'pedido actual' in text_lower:
            if len(session.cart) == 0:
                return """🛒 Tu carrito está vacío

Aún no has agregado productos.

Escribe "menú" para ver nuestras opciones."""
            
            total = sum(item['precio'] * item.get('cantidad', 1) for item in session.cart)
            
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

        elif any(word in text_lower for word in ['hola', 'buenas', 'hi', 'hello', 'buenos días', 'buenas tardes', 'buenas noches', 'buen día']):
            saludos = [
                f"¡Bienvenido a {RESTAURANT_CONFIG['nombre']}! ¿Listo para una experiencia culinaria única?",
                f"¡Buen día! Me da mucho gusto saludarte. ¿Qué se te antoja hoy?",
                "¡Has llegado al lugar correcto para disfrutar de deliciosa comida!"
            ]
            return random.choice(saludos) + "\n\nEscribe 'menu' para ver todas nuestras opciones."

        elif any(word in text_lower for word in ['gracias', 'excelente', 'perfecto', 'buenísimo', 'delicioso', 'rico']):
            return """¡Muchas gracias!

Nos hace muy felices poder ayudarte. Tu satisfacción es nuestra mayor recompensa.

¿Hay algo más en lo que pueda asistirte?
Escribe "menú" para ver nuestras opciones."""

        elif any(word in text_lower for word in ['adios', 'adiós', 'bye', 'hasta luego', 'nos vemos', 'chao']):
            despedidas = [
                f"¡Adiós! Esperamos verte pronto en {RESTAURANT_CONFIG['nombre']}!",
                "¡Hasta pronto! Que tengas un día delicioso",
                "¡Chao! Gracias por visitarnos. Te esperamos con los brazos abiertos!"
            ]
            return random.choice(despedidas)

        else:
            return """¿Te puedo ayudar con algo específico?

Puedo ayudarte con:
• Ver el menú (escribe "menú")
• Consultar precios
• Información de delivery y horarios
• Ver tu carrito actual
• Hacer una reservación (escribe "reservar")

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
    print("🔗 Servidor: http://localhost:5000/<slug>/")
    print("🤖 Bot de Telegram conectado")
    print("🗄 Base de datos MySQL conectada")
    print(f"📱 Grupo notificaciones: {CHAT_IDS.get('cocina', CHAT_IDS.get('admin', 'No configurado'))}")
    print("✅ Listo para recibir mensajes desde la web")
    print("🎯 MODO MULTI-RESTAURANTE: Dinámico por slug")
    print("📅 SISTEMA DE RESERVACIONES INTEGRADO")
    print("🕐 HORARIOS Y DELIVERY DINÁMICOS DESDE BD")
    print("=" * 60)
    
    run_flask_server()