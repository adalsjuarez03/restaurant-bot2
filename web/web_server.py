"""
Servidor Web para interactuar con el Bot de Telegram
Conecta la interfaz web con el bot de Telegram y la base de datos
VERSIÓN MULTI-RESTAURANTE - Dinámico por Slug
"""
import sys
import os
import unicodedata
import json
import re  # ✅ AGREGAR IMPORT
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
# ✅ NO importar bot global - usaremos bots dinámicos por restaurante
# Solo importar RESTAURANT_CONFIG como fallback para info básica
from config import RESTAURANT_CONFIG
from bot.restaurant_message_handlers import RestaurantMessageHandlers
from database.database_multirestaurante import DatabaseManager
import threading
import time
import random
from database.payment_manager import payment_manager

BASE_URL = os.getenv('BASE_URL', 'http://localhost:5000')

app = Flask(__name__)
CORS(app)

# ✅ NO crear bot global aquí - se creará dinámicamente por restaurante
db = DatabaseManager()

chat_sessions = {}

# ==================== AGREGAR FUNCIÓN DE VERIFICACIÓN DE TIEMPOS ====================

def verificar_tiempos_bd(restaurante_id):
    """Verificar que todos los items tengan tiempo_preparacion"""
    from database.database_multirestaurante import get_db_cursor
    
    with get_db_cursor() as (cursor, conn):
        cursor.execute("""
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN tiempo_preparacion IS NULL THEN 1 ELSE 0 END) as sin_tiempo
            FROM items_menu 
            WHERE restaurante_id = %s
        """, (restaurante_id,))
        result = cursor.fetchone()
    
    if result and result['sin_tiempo'] > 0:
        print(f"⚠️ ADVERTENCIA: {result['sin_tiempo']} items sin tiempo_preparacion")
        print(f"   Ejecuta: UPDATE items_menu SET tiempo_preparacion = '15-20 min' WHERE tiempo_preparacion IS NULL AND restaurante_id = {restaurante_id}")
    else:
        print(f"✅ Todos los items tienen tiempo_preparacion definido")

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


def obtener_info_contacto(restaurante_id):
    """Obtener información de contacto desde la BD"""
    from database.database_multirestaurante import get_db_cursor
    
    with get_db_cursor() as (cursor, conn):
        cursor.execute("""
            SELECT nombre_restaurante, telefono, email, direccion, ciudad, estado_republica
            FROM restaurantes WHERE id = %s
        """, (restaurante_id,))
        return cursor.fetchone()


# ==================== NUEVAS FUNCIONES PARA MENÚ PRINCIPAL ====================

def mostrar_menu_principal(session):
    """Mostrar menú principal con 4 opciones"""
    restaurante_info = obtener_info_contacto(session.restaurante_id)
    nombre_rest = restaurante_info['nombre_restaurante'] if restaurante_info else "Nuestro Restaurante"
    
    return f"""🍽️ ¡Bienvenido a {nombre_rest}!

¿Cómo deseas disfrutar hoy?

1️⃣ 🏪 COMER EN LOCAL
   • Pedido directo a tu mesa
   • Pago en efectivo o terminal

2️⃣ 🚶 PARA LLEVAR
   • Listo para recoger
   • Pago en línea con PayPal

3️⃣ 🚗 DELIVERY A DOMICILIO
   • Te lo llevamos hasta tu puerta
   • Pago en línea con PayPal

4️⃣ ℹ️ INFORMACIÓN
   • Horarios, ubicación, menú, precios

💡 Escribe el número de la opción que prefieras (1, 2, 3 o 4)"""


def procesar_seleccion_tipo_pedido(session, opcion):
    """Procesar la selección del tipo de pedido"""
    
    if opcion in ['1', 'local', 'comer aqui', 'comer aquí', 'en local']:
        session.tipo_pedido_seleccionado = 'restaurant'
        session.registration_step = 'restaurant_name'
        
        return """🏪 ¡PERFECTO! Comer en Local

Para procesar tu pedido, necesito algunos datos:

👤 ¿Cuál es tu nombre completo?"""
    
    elif opcion in ['2', 'llevar', 'para llevar', 'takeaway', 'recoger']:
        session.tipo_pedido_seleccionado = 'takeaway'
        session.registration_step = 'takeaway_name'
        
        return """🚶 ¡EXCELENTE! Para Llevar

Te prepararemos tu pedido para que lo recojas.

👤 ¿Cuál es tu nombre completo?"""
    
    elif opcion in ['3', 'delivery', 'domicilio', 'envio', 'envío']:
        session.tipo_pedido_seleccionado = 'delivery'
        session.registration_step = 'delivery_name'
        
        return """🚗 ¡GENIAL! Delivery a Domicilio

Te llevaremos tu pedido hasta tu puerta.

👤 ¿Cuál es tu nombre completo?"""
    
    elif opcion in ['4', 'informacion', 'información', 'info']:
        return mostrar_menu_informacion(session.restaurante_id)
    
    else:
        return """❌ Opción no válida

Por favor, escribe el número de la opción que deseas:
1 - Comer en Local
2 - Para Llevar
3 - Delivery
4 - Información"""


def mostrar_menu_informacion(restaurante_id):
    """Mostrar menú de información"""
    return """ℹ️ INFORMACIÓN DEL RESTAURANTE

¿Qué información necesitas?

1️⃣ 🕐 Horarios de atención
2️⃣ 📍 Ubicación y contacto
3️⃣ 💵 Precios del menú
4️⃣ 🚗 Zonas de delivery y costos
5️⃣ 🔙 Volver al menú principal

💡 Escribe el número de la opción"""


def procesar_menu_informacion(session, opcion, restaurante_id):
    """Procesar selección del menú de información"""
    
    if opcion in ['1', 'horarios', 'horario']:
        return generar_texto_horarios(restaurante_id)
    
    elif opcion in ['2', 'ubicacion', 'ubicación', 'contacto', 'direccion', 'dirección']:
        info = obtener_info_contacto(restaurante_id)
        
        if info:
            return f"""📍 UBICACIÓN Y CONTACTO

🏨 {info['nombre_restaurante']}

📍 Dirección:
{info['direccion']}
{info['ciudad']}, {info['estado_republica']}

📱 Teléfono: {info['telefono']}
📧 Email: {info['email']}

¡Estamos aquí para servirte!

Escribe '0' para volver al menú de información"""
        else:
            return "❌ No se pudo obtener la información de contacto"
    
    elif opcion in ['3', 'precios', 'precio', 'menu', 'menú']:
        return generar_respuesta_dinamica(session, 'precios', restaurante_id)
    
    elif opcion in ['4', 'delivery', 'envio', 'envío', 'cobertura']:
        return generar_texto_delivery(restaurante_id)
    
    elif opcion in ['5', '0', 'volver', 'atras', 'atrás', 'menu principal', 'menú principal']:
        session.en_menu_informacion = False
        return mostrar_menu_principal(session)
    
    else:
        return """❌ Opción no válida

Por favor, escribe el número correcto:
1 - Horarios
2 - Ubicación
3 - Precios
4 - Delivery
5 - Volver"""


# ==================== FUNCIONES PARA CANTIDADES E INGREDIENTES ====================

# ==================== CORRECCIÓN 1: MEJORAR BÚSQUEDA DE ITEMS ====================

def buscar_items_mejorada(restaurante_id, texto_busqueda):
    """Búsqueda mejorada de items con múltiples estrategias"""
    import unicodedata
    
    def normalizar(texto):
        texto = texto.lower()
        return ''.join(
            c for c in unicodedata.normalize('NFD', texto)
            if unicodedata.category(c) != 'Mn'
        )
    
    # Normalizar texto de búsqueda
    texto_normalizado = normalizar(texto_busqueda)
    
    # Buscar en la base de datos
    items_encontrados = db.buscar_items_por_texto(restaurante_id, texto_normalizado)
    
    # Debug mejorado
    if items_encontrados:
        print(f"✅ Búsqueda '{texto_busqueda}' encontró {len(items_encontrados)} resultados")
        for idx, item in enumerate(items_encontrados[:3], 1):
            print(f"   {idx}. {item['nombre']} (score: {item.get('score', 0)})")
    else:
        print(f"❌ Búsqueda '{texto_busqueda}' sin resultados")
    
    if items_encontrados:
        return items_encontrados
    
    # Si no encuentra, intentar búsqueda por palabras clave
    palabras_clave = texto_normalizado.split()
    
    # Buscar por cada palabra clave
    for palabra in palabras_clave:
        if len(palabra) > 2:  # Solo palabras de más de 2 letras
            items_parciales = db.buscar_items_por_texto(restaurante_id, palabra)
            if items_parciales:
                return items_parciales
    
    return []


def procesar_agregado_item_con_cantidad(session, texto_busqueda, restaurante_id):
    """
    Buscar item y preguntar cantidad ANTES de agregar al carrito - VERSIÓN MEJORADA
    """
    import unicodedata
    
    # Normalizar texto
    def normalizar(texto):
        texto = texto.lower()
        return ''.join(
            c for c in unicodedata.normalize('NFD', texto)
            if unicodedata.category(c) != 'Mn'
        )
    
    # Limpiar texto de búsqueda de forma más inteligente
    palabras_remover = ['quiero', 'pedir', 'ordenar', 'me gustaría', 'me gustaria', 
                       'dame', 'un', 'una', 'el', 'la', 'los', 'las', 'de', 'por', 'favor']
    texto_normalizado = normalizar(texto_busqueda)
    
    for palabra in palabras_remover:
        # Usar regex para reemplazar palabras completas
        texto_normalizado = re.sub(r'\b' + palabra + r'\b', '', texto_normalizado)
    
    texto_normalizado = texto_normalizado.strip()
    
    # Si el texto está muy vacío después de limpiar, usar el original
    if len(texto_normalizado) < 3:
        texto_normalizado = normalizar(texto_busqueda)
    
    # Buscar items con búsqueda mejorada
    items_encontrados = buscar_items_mejorada(restaurante_id, texto_normalizado)
    
    if not items_encontrados:
        return "🤔 No logré identificar ese platillo.\n\nEscribe 'menú' para ver todas las opciones."
    
    item = items_encontrados[0]
    
    # Verificar disponibilidad
    if not item['disponible']:
        return f"😔 Lo siento, *{item['nombre']}* está temporalmente agotado.\n\nEscribe 'menú' para ver otras opciones."
    
    # Guardar item pendiente y activar flujo de cantidad
    session.item_pendiente = {
        'id': item['id'],
        'codigo': item['codigo'],
        'nombre': item['nombre'],
        'descripcion': item.get('descripcion', ''),
        'precio': float(item['precio']),
        'categoria': item['categoria_nombre']
    }
    
    session.esperando_cantidad = True
    
    # Obtener ingredientes si existen
    ingredientes = db.get_ingredientes_item(item['id'])
    session.item_pendiente['ingredientes'] = ingredientes
    
    # Mensaje de cantidad
    vegano_emoji = " 🌱" if item.get('vegano') else ""
    
    return f"""✨ Has seleccionado:

🍽️ **{item['nombre']}**{vegano_emoji}
📝 {item.get('descripcion', 'Deliciosa opción')}
💰 Precio unitario: ${item['precio']}

❓ ¿Cuántas unidades deseas ordenar?

[1]  [2]  [3]  [4]  [5+]

💡 Escribe el número o presiona un botón"""


def procesar_cantidad_seleccionada(session, texto):
    """Procesar la cantidad ingresada por el usuario"""
    try:
        cantidad = int(texto)
        
        if cantidad < 1:
            return "❌ La cantidad debe ser al menos 1"
        
        if cantidad > 20:
            return "❌ La cantidad máxima es 20 unidades. Si necesitas más, contáctanos directamente."
        
        # Guardar cantidad
        session.item_pendiente['cantidad'] = cantidad
        session.esperando_cantidad = False
        
        # Verificar si tiene ingredientes personalizables
        ingredientes = session.item_pendiente.get('ingredientes', [])
        
        if ingredientes and len(ingredientes) > 0:
            # Preguntar por ingredientes
            session.esperando_ingredientes = True
            
            ingredientes_lista = "\n".join([f"✅ {ing}" for ing in ingredientes])
            
            return f"""✅ Cantidad: {cantidad} unidad(es)

🍽️ {session.item_pendiente['nombre']} x{cantidad}

🧀 **Ingredientes incluidos:**
{ingredientes_lista}

❓ ¿Deseas quitar algún ingrediente?

💡 Opciones:
• Escribe "sin [ingrediente]" (Ej: sin cebolla)
• Escribe "sin [ing1], sin [ing2]" para quitar varios
• Escribe "todo bien" o "ninguno" si está perfecto así"""
        
        else:
            # No tiene ingredientes, agregar directamente
            return agregar_item_al_carrito_final(session)
    
    except ValueError:
        return "❌ Por favor escribe solo un número.\nEjemplo: 2"


# ==================== CORRECCIÓN 2: MEJORAR DETECCIÓN DE INGREDIENTES ====================

def procesar_modificacion_ingredientes(session, texto):
    """
    Procesar modificación de ingredientes - VERSIÓN MEJORADA CON DETECCIÓN INTELIGENTE
    """
    texto_lower = texto.lower()
    
    # Si no quiere quitar nada
    if any(word in texto_lower for word in ['todo bien', 'ninguno', 'nada', 'asi esta bien', 'está bien', 'ok', 'perfecto', 'no quitar']):
        session.item_pendiente['ingredientes_quitados'] = []
        session.esperando_ingredientes = False
        return agregar_item_al_carrito_final(session)
    
    # Extraer ingredientes a quitar con búsqueda más inteligente
    import unicodedata
    
    def normalizar(texto):
        texto = texto.lower()
        return ''.join(
            c for c in unicodedata.normalize('NFD', texto)
            if unicodedata.category(c) != 'Mn'
        )
    
    texto_normalizado = normalizar(texto_lower)
    
    # ✅ OBTENER INGREDIENTES COMO LISTA (NO COMO STRING)
    ingredientes_disponibles = session.item_pendiente.get('ingredientes', [])
    
    # ✅ ASEGURAR QUE SEA UNA LISTA
    if isinstance(ingredientes_disponibles, str):
        # Si por error viene como string, convertirlo a lista
        ingredientes_disponibles = [ing.strip() for ing in ingredientes_disponibles.split(',') if ing.strip()]
    
    ingredientes_quitados = []
    
    print(f"🔍 Texto del usuario: {texto}")
    print(f"🔍 Ingredientes disponibles: {ingredientes_disponibles}")
    
    # Buscar patrones "sin X"
    patron_sin = re.findall(r'sin\s+(\w+(?:\s+\w+)?)', texto_normalizado)
    
    print(f"🔍 Patrones 'sin' encontrados: {patron_sin}")
    
    for palabra in patron_sin:
        for ingrediente in ingredientes_disponibles:
            ing_normalizado = normalizar(ingrediente)
            palabra_normalizada = normalizar(palabra)
            
            # ✅ BÚSQUEDA MÁS PRECISA
            # Verificar si la palabra está contenida en el ingrediente O viceversa
            if (palabra_normalizada in ing_normalizado or 
                ing_normalizado in palabra_normalizada or
                # También verificar coincidencia de palabras completas
                palabra_normalizada == ing_normalizado.split()[0] if ing_normalizado else False):
                
                if ingrediente not in ingredientes_quitados:
                    ingredientes_quitados.append(ingrediente)
                    print(f"✅ Match encontrado: '{palabra}' → '{ingrediente}'")
    
    # Si no se encontraron con "sin", buscar palabras directamente en ingredientes
    if not ingredientes_quitados:
        # Separar texto en palabras individuales
        palabras_texto = [p.strip() for p in texto_normalizado.replace('sin', '').replace(',', ' ').split() if len(p.strip()) > 2]
        
        print(f"🔍 Palabras a buscar: {palabras_texto}")
        
        for palabra in palabras_texto:
            for ingrediente in ingredientes_disponibles:
                ing_normalizado = normalizar(ingrediente)
                
                # Buscar coincidencia en cualquier palabra del ingrediente
                palabras_ingrediente = ing_normalizado.split()
                
                for palabra_ing in palabras_ingrediente:
                    if (palabra in palabra_ing or palabra_ing in palabra):
                        if ingrediente not in ingredientes_quitados:
                            ingredientes_quitados.append(ingrediente)
                            print(f"✅ Match directo: '{palabra}' → '{ingrediente}'")
                            break
    
    # Si aún no se encontraron, mostrar ayuda específica
    if not ingredientes_quitados:
        ingredientes_lista = "\n".join([f"• {ing}" for ing in ingredientes_disponibles])
        
        return f'''🤔 No identifiqué los ingredientes a quitar.

🧀 **Ingredientes disponibles:**
{ingredientes_lista}

💡 **Por favor intenta de nuevo:**
- Escribe "sin [ingrediente]" (Ej: sin cebolla)
- Escribe "sin [ing1], sin [ing2]" para quitar varios
- Escribe "todo bien" si no quieres quitar nada

📝 **Ejemplos válidos:**
- sin cebolla
- sin tomate, sin lechuga
- no quiero cebolla
- quitar mayonesa'''
    
    # Guardar modificación
    session.item_pendiente['ingredientes_quitados'] = ingredientes_quitados
    session.esperando_ingredientes = False
    
    print(f"✅ Ingredientes a quitar: {ingredientes_quitados}")
    
    return agregar_item_al_carrito_final(session)


def agregar_item_al_carrito_final(session):
    """Agregar item al carrito con todos los detalles"""
    item = session.item_pendiente
    cantidad = item.get('cantidad', 1)
    precio_unitario = item['precio']
    subtotal_item = precio_unitario * cantidad
    
    # Crear objeto para el carrito
    item_carrito = {
        'id': item['id'],
        'codigo': item['codigo'],
        'nombre': item['nombre'],
        'precio': precio_unitario,
        'cantidad': cantidad,
        'subtotal': subtotal_item,
        'categoria': item['categoria']
    }
    
    # Agregar modificaciones si existen
    ingredientes_quitados = item.get('ingredientes_quitados', [])
    if ingredientes_quitados:
        item_carrito['sin_ingredientes'] = ingredientes_quitados
    
    # Agregar al carrito
    session.cart.append(item_carrito)
    
    # Calcular totales
    total_items = len(session.cart)
    subtotal_carrito = sum(i['subtotal'] for i in session.cart)
    
    # Mensaje de confirmación
    mensaje = f"""✅ ¡Agregado al pedido!

📦 **{item['nombre']}** x{cantidad}"""
    
    if ingredientes_quitados:
        mensaje += f"\n   🚫 Sin: {', '.join(ingredientes_quitados)}"
    
    mensaje += f"\n💰 Subtotal: ${subtotal_item:.2f}"
    
    mensaje += f"""

🛒 **Resumen del carrito** ({total_items} items):
"""
    
    for i in session.cart:
        mensaje += f"\n• {i['nombre']} x{i['cantidad']} - ${i['subtotal']:.2f}"
        if i.get('sin_ingredientes'):
            mensaje += f"\n  🚫 Sin: {', '.join(i['sin_ingredientes'])}"
    
    mensaje += f"""

💵 **Subtotal actual:** ${subtotal_carrito:.2f}

¿Qué deseas hacer?
• Escribe "menú" para agregar más items
• Escribe "confirmar pedido" para finalizar
• Escribe "ver carrito" para revisar tu pedido"""
    
    # Limpiar item pendiente
    session.item_pendiente = None
    
    return mensaje


def formatear_resumen_carrito(session):
    """Generar resumen formateado del carrito"""
    if not session.cart:
        return "🛒 Tu carrito está vacío"
    
    mensaje = f"🛒 **Tu Carrito** ({len(session.cart)} items)\n\n"
    
    for item in session.cart:
        mensaje += f"• {item['nombre']} x{item['cantidad']} - ${item['subtotal']:.2f}\n"
        
        if item.get('sin_ingredientes'):
            mensaje += f"  🚫 Sin: {', '.join(item['sin_ingredientes'])}\n"
    
    subtotal = sum(i['subtotal'] for i in session.cart)
    mensaje += f"\n💵 **Subtotal:** ${subtotal:.2f}"
    
    return mensaje


# ==================== CORRECCIÓN 3: MEJORAR CONFIRMACIÓN DE PEDIDO ====================

def confirmar_pedido_mejorado(session, restaurante_id):
    """
    Confirmar pedido con validaciones específicas según tipo - VERSIÓN MEJORADA
    """
    
    # Validar que hay items
    if len(session.cart) == 0:
        return """🛒 Tu carrito está vacío

Aún no has agregado ningún platillo.

Escribe "menú" para ver nuestras opciones."""
    
    # Calcular subtotal
    subtotal = sum(item['subtotal'] for item in session.cart)
    
    # Obtener tipo de pedido
    tipo_pedido = session.tipo_pedido_seleccionado or 'delivery'
    
    # ==================== VALIDACIONES POR TIPO ====================
    
    if tipo_pedido == 'restaurant':
        # ✅ COMER EN LOCAL: No requiere validación de mínimo
        costo_envio = 0
        metodo_pago = "💳 Efectivo o Tarjeta en el local"
        
    elif tipo_pedido == 'takeaway':
        # ✅ PARA LLEVAR: Validar pedido mínimo (opcional)
        costo_envio = 0
        metodo_pago = "💳 Pago en línea con PayPal"
        
        # Pedido mínimo para takeaway (configuración)
        pedido_minimo_takeaway = 100  # Puedes hacerlo dinámico desde BD
        
        if subtotal < pedido_minimo_takeaway:
            faltante = pedido_minimo_takeaway - subtotal
            return f"""❌ PEDIDO MÍNIMO NO ALCANZADO (Para Llevar)

💰 Subtotal: ${subtotal:.2f}
🛒 Pedido mínimo: ${pedido_minimo_takeaway:.2f}
❗ Te faltan: ${faltante:.2f}

Escribe 'menú' para agregar más items."""
        
    elif tipo_pedido == 'delivery':
        # ✅ DELIVERY: Validar pedido mínimo y calcular envío
        costo_envio, pedido_minimo = calcular_costo_envio_dinamico(restaurante_id, subtotal)
        metodo_pago = "💳 Pago en línea con PayPal"
        
        if subtotal < pedido_minimo:
            faltante = pedido_minimo - subtotal
            return f"""❌ PEDIDO MÍNIMO NO ALCANZADO (Delivery)

💰 Subtotal: ${subtotal:.2f}
🛒 Pedido mínimo: ${pedido_minimo:.2f}
❗ Te faltan: ${faltante:.2f}

Escribe 'menú' para agregar más items."""
    
    else:
        # Fallback
        costo_envio = 0
        metodo_pago = "💳 A definir"
    
    # Calcular total
    total = subtotal + costo_envio

    # ==================== ✅ AGREGAR ESTO AQUÍ ====================
    # Calcular tiempo estimado desde BD
    detalles_temp = []
    for item_cart in session.cart:
        item_bd = db.get_item_by_id(item_cart['id'])
        if item_bd:
            detalles_temp.append(item_bd)

    tiempos = []
    for item_bd in detalles_temp:
        if item_bd and item_bd.get('tiempo_preparacion'):
            tiempo_str = item_bd['tiempo_preparacion']
            numeros = re.findall(r'\d+', tiempo_str)
            if numeros:
                tiempos.append(int(numeros[-1]))

    # Calcular tiempo estimado
    if tiempos:
        tiempo_max = max(tiempos)
        tiempo_estimado = f"{tiempo_max}-{tiempo_max + 5} minutos"
    else:
        # Tiempos por defecto según tipo
        if tipo_pedido == 'restaurant':
            tiempo_estimado = "15-20 minutos"
        elif tipo_pedido == 'takeaway':
            tiempo_estimado = "20-30 minutos"
        else:  # delivery
            delivery_config = obtener_info_delivery(restaurante_id)
            tiempo_estimado = delivery_config.get('tiempo_entrega', '30-45 minutos') if delivery_config else '30-45 minutos'

    print(f"⏱ Tiempo estimado calculado: {tiempo_estimado}")
    # ==================== FIN DE CÓDIGO AGREGADO ====================

    # ==================== CREAR PEDIDO EN BD ====================
    try:
        resultado_pedido = db.crear_pedido_simple(
            restaurante_id, 
            session.cliente_id, 
            tipo_pedido,  # ✅ Ahora usamos el tipo correcto
            'web'
        )
        
        if not resultado_pedido or 'pedido_id' not in resultado_pedido:
            return "❌ Error al crear el pedido. Por favor intenta de nuevo."
        
        pedido_id = resultado_pedido['pedido_id']
        numero_pedido = resultado_pedido['numero_pedido']
        session.pedido_id = pedido_id
        
        print(f"✅ Pedido creado - ID: {pedido_id}, Número: {numero_pedido}, Tipo: {tipo_pedido}")
        
        # Agregar items con detalles
        items_agregados = 0
        for item in session.cart:
            # Agregar notas sobre ingredientes quitados
            notas_item = None
            if item.get('sin_ingredientes'):
                notas_item = f"Sin: {', '.join(item['sin_ingredientes'])}"
            
            success = db.agregar_item_pedido(
                pedido_id, 
                item['id'], 
                item.get('cantidad', 1), 
                float(item['precio'])
            )
            
            # Si hay notas, actualizar
            if success and notas_item:
                from database.database_multirestaurante import get_db_cursor
                with get_db_cursor() as (cursor, conn):
                    cursor.execute("""
                        UPDATE detalle_pedidos 
                        SET notas_item = %s 
                        WHERE pedido_id = %s AND item_id = %s
                        ORDER BY id DESC LIMIT 1
                    """, (notas_item, pedido_id, item['id']))
                    conn.commit()
            
            if success:
                items_agregados += 1
                print(f"✅ Item agregado: {item['nombre']} x{item.get('cantidad', 1)}")
        
        if items_agregados == 0:
            return "❌ No se pudieron agregar los items. Intenta de nuevo."
        
        # Actualizar totales en BD
        from database.database_multirestaurante import get_db_cursor
        with get_db_cursor() as (cursor, conn):
            # Guardar datos específicos según tipo
            if tipo_pedido == 'restaurant':
                cursor.execute("""
                    UPDATE pedidos 
                    SET total = %s, 
                        subtotal = %s,
                        costo_envio = 0,
                        direccion_entrega = %s,
                        notas = %s
                    WHERE id = %s
                """, (
                    total, 
                    subtotal, 
                    f"Mesa {session.numero_mesa}",
                    f"Comensales: {session.numero_comensales or 'No especificado'}",
                    pedido_id
                ))
            else:
                cursor.execute("""
                    UPDATE pedidos 
                    SET total = %s, 
                        subtotal = %s,
                        costo_envio = %s
                    WHERE id = %s
                """, (total, subtotal, costo_envio, pedido_id))
            
            conn.commit()
        
        # Actualizar estado
        db.actualizar_estado_pedido(pedido_id, 'confirmado')
        
        # Obtener detalles finales
        pedido_final = db.get_pedido(pedido_id)
        detalles = db.get_detalle_pedido(pedido_id)
        
        # Generar resumen de items
        if detalles:
            order_summary = "\n".join([
                f"• {d['item_nombre']} x{d['cantidad']} - ${d['subtotal']:.2f}"
                + (f"\n  🚫 {d['notas_item']}" if d.get('notas_item') else "")
                for d in detalles
            ])
        else:
            order_summary = "\n".join([
                f"• {item['nombre']} x{item.get('cantidad', 1)} - ${item['subtotal']:.2f}" 
                + (f"\n  🚫 Sin: {', '.join(item['sin_ingredientes'])}" if item.get('sin_ingredientes') else "")
                for item in session.cart
            ])
        
        # ==================== MENSAJE SEGÚN TIPO ====================
        
        if tipo_pedido == 'restaurant':
            # MENSAJE PARA COMER EN LOCAL
            mensaje_confirmacion = f"""✅ ¡PEDIDO CONFIRMADO!

🎫 Número de orden: {numero_pedido}
🏪 Tipo: Comer en Local

👤 Cliente: {session.customer_name}
🪑 Mesa: {session.numero_mesa}
👥 Comensales: {session.numero_comensales or 'No especificado'}"""
            
            if session.customer_phone:
                mensaje_confirmacion += f"\n📱 Teléfono: {session.customer_phone}"
            
            mensaje_confirmacion += f"""

📋 Tu pedido:
{order_summary}

💵 TOTAL: ${total:.2f}
💳 Pago: Efectivo o Tarjeta en el local

⏱ Tiempo estimado: {tiempo_estimado}

✅ Tu pedido está siendo procesado
🍽️ Te lo llevaremos a tu mesa

¡Gracias por tu preferencia!

Escribe "menú" para hacer otro pedido."""
        
        elif tipo_pedido == 'takeaway':
            # MENSAJE PARA LLEVAR
            mensaje_confirmacion = f"""✅ ¡PEDIDO CONFIRMADO!

🎫 Número de orden: {numero_pedido}
🚶 Tipo: Para Llevar

👤 Cliente: {session.customer_name}
📱 Teléfono: {session.customer_phone}
📧 Email: {session.customer_email}

📋 Tu pedido:
{order_summary}

💵 TOTAL: ${total:.2f}
💳 Pago: PayPal (requerido)

⏱ Tiempo estimado: {tiempo_estimado}

📞 Próximos pasos:
1️⃣ Realiza el pago con PayPal (botón abajo)
2️⃣ Te avisaremos cuando esté listo
3️⃣ Recoge tu pedido en el restaurante

✅ Pedido guardado en base de datos

Escribe "menú" para hacer otro pedido."""
        
        elif tipo_pedido == 'delivery':
            # MENSAJE PARA DELIVERY
            mensaje_costo = f"""💵 DESGLOSE:
🍽️ Subtotal: ${subtotal:.2f}
🚗 Envío: ${costo_envio:.2f}"""
            
            if costo_envio == 0 and delivery_config and subtotal >= delivery_config.get('envio_gratis_desde', 999999):
                mensaje_costo += " ¡GRATIS! 🎉"
            
            mensaje_costo += f"\n💰 TOTAL: ${total:.2f}"
            
            mensaje_confirmacion = f"""✅ ¡PEDIDO CONFIRMADO!

🎫 Número de orden: {numero_pedido}
🚗 Tipo: Delivery a Domicilio

👤 Cliente: {session.customer_name}
📱 Teléfono: {session.customer_phone}
📍 Dirección: {session.customer_address}
📧 Email: {session.customer_email}

📋 Tu pedido:
{order_summary}

{mensaje_costo}

⏱ Tiempo estimado: {tiempo_estimado}

📞 Próximos pasos:
1️⃣ Realiza el pago con PayPal (botón abajo)
2️⃣ Prepararemos tu pedido
3️⃣ Te notificaremos cuando esté en camino
4️⃣ ¡Disfruta en casa!

✅ Pedido guardado en base de datos

Escribe "menú" para hacer otro pedido."""
        
        else:
            # Mensaje genérico
            mensaje_confirmacion = f"""✅ ¡PEDIDO CONFIRMADO!

🎫 Número: {numero_pedido}

Total: ${total:.2f}

Escribe "menú" para hacer otro pedido."""
        
        # Enviar notificación a Telegram
        send_notification_to_group("new_order", {
            "items": detalles if detalles else session.cart,
            "total": total,
            "order_number": numero_pedido
        }, session)
        
        # Limpiar carrito
        session.cart = []
        
        return mensaje_confirmacion
        
    except Exception as e:
        print(f"❌ Error confirmando pedido: {e}")
        import traceback
        traceback.print_exc()
        return "❌ Hubo un error al confirmar tu pedido. Por favor contacta al restaurante."


# ==================== REEMPLAZAR send_notification_to_group() EN web_server.py ====================

def send_notification_to_group(notification_type, data, session):
    """
    Enviar notificación al grupo de Telegram - DINÁMICO Y DIFERENCIADO POR TIPO
    """
    try:
        # Obtener configuración de Telegram del restaurante
        from database.database_multirestaurante import get_db_cursor
        
        with get_db_cursor() as (cursor, conn):
            cursor.execute("""
                SELECT bot_token, telegram_admin_id, telegram_group_id, config_notificaciones
                FROM restaurantes 
                WHERE id = %s
            """, (session.restaurante_id,))
            config = cursor.fetchone()
        
        if not config or not config.get('bot_token'):
            print(f"⚠️ No hay bot_token configurado para restaurante {session.restaurante_id}")
            return
        
        # Parsear config_notificaciones
        config_notif = {'notificar_pedidos': True, 'notificar_reservaciones': True}
        
        if config.get('config_notificaciones'):
            try:
                if isinstance(config['config_notificaciones'], str):
                    config_notif = json.loads(config['config_notificaciones'])
                else:
                    config_notif = config['config_notificaciones']
            except Exception as e:
                print(f"⚠️ Error parseando config_notificaciones: {e}")
        
        # Verificar si está activo
        if notification_type == "new_order" and not config_notif.get('notificar_pedidos', True):
            print(f"ℹ️ Notificaciones de pedidos desactivadas")
            return
        
        if notification_type == "new_reservation" and not config_notif.get('notificar_reservaciones', True):
            print(f"ℹ️ Notificaciones de reservaciones desactivadas")
            return
        
        # Determinar chat destino
        target_chat = config.get('telegram_group_id') or config.get('telegram_admin_id')
        
        if not target_chat:
            print(f"⚠️ No hay chat configurado")
            return
        
        # Crear bot dinámico
        import telebot
        bot_restaurante = telebot.TeleBot(config['bot_token'])
        
        # ==================== CONSTRUIR MENSAJE SEGÚN TIPO ====================
        message = ""
        
        if notification_type == "new_order":
            # Obtener tipo de pedido
            tipo_pedido = session.tipo_pedido_seleccionado or 'delivery'
            
            # Formatear items
            if data['items'] and isinstance(data['items'][0], dict) and 'item_nombre' in data['items'][0]:
                items_text = "\n".join([
                    f"• {item['item_nombre']} x{item['cantidad']} - ${item['subtotal']}"
                    + (f"\n  🚫 {item['notas_item']}" if item.get('notas_item') else "")
                    for item in data['items']
                ])
            else:
                items_text = "\n".join([
                    f"• {item['nombre']} x{item.get('cantidad', 1)} - ${item.get('subtotal', item['precio'])}"
                    + (f"\n  🚫 Sin: {', '.join(item['sin_ingredientes'])}" if item.get('sin_ingredientes') else "")
                    for item in data['items']
                ])
            
            # ==================== MENSAJE DIFERENCIADO POR TIPO ====================
            
            if tipo_pedido == 'restaurant':
                # 🏪 PEDIDO EN LOCAL
                message = f"""🏪 NUEVO PEDIDO EN LOCAL

👤 Cliente: {session.customer_name}
🪑 Mesa: {session.numero_mesa}
👥 Comensales: {session.numero_comensales or 'No especificado'}"""
                
                if session.customer_phone:
                    message += f"\n📱 Teléfono: {session.customer_phone}"
                
                message += f"""
🌐 Origen: Interfaz Web
🆔 Session: {session.session_id[:8]}
📋 Pedido: #{data.get('order_number', 'N/A')}

🍽 PEDIDO:
{items_text}

💰 Total: ${data['total']:.2f}
💳 Pago: Efectivo o Tarjeta en el local
⏰ Hora: {datetime.now().strftime('%d/%m/%Y %H:%M')}

⚡ URGENTE - Cliente esperando en mesa
✅ Pedido confirmado en base de datos"""
            
            elif tipo_pedido == 'takeaway':
                # 🚶 PARA LLEVAR
                message = f"""🚶 NUEVO PEDIDO PARA LLEVAR

👤 Cliente: {session.customer_name}
📱 Teléfono: {session.customer_phone}
📧 Email: {session.customer_email or 'No proporcionado'}
🌐 Origen: Interfaz Web
🆔 Session: {session.session_id[:8]}
📋 Pedido: #{data.get('order_number', 'N/A')}

🍽 PEDIDO:
{items_text}

💰 Total: ${data['total']:.2f}
💳 Pago: PayPal (REQUERIDO)
⏰ Hora: {datetime.now().strftime('%d/%m/%Y %H:%M')}
⏱ Listo en: 20-30 minutos

📞 AVISAR al cliente cuando esté listo:
{session.customer_phone}

✅ Pedido confirmado en base de datos"""
            
            elif tipo_pedido == 'delivery':
                # 🚗 DELIVERY
                message = f"""🚗 NUEVO PEDIDO DELIVERY

👤 Cliente: {session.customer_name}
📱 Teléfono: {session.customer_phone}
📧 Email: {session.customer_email or 'No proporcionado'}
📍 Dirección: {session.customer_address}
🌐 Origen: Interfaz Web
🆔 Session: {session.session_id[:8]}
📋 Pedido: #{data.get('order_number', 'N/A')}

🍽 PEDIDO:
{items_text}

💰 Total: ${data['total']:.2f}
💳 Pago: PayPal (REQUERIDO)
⏰ Hora: {datetime.now().strftime('%d/%m/%Y %H:%M')}
⏱ Entregar en: 30-45 minutos

🚗 Coordinar repartidor
📞 Contacto: {session.customer_phone}

✅ Pedido confirmado en base de datos"""
            
            else:
                # Mensaje genérico (fallback)
                message = f"""🆕 NUEVO PEDIDO WEB

👤 Cliente: {session.customer_name}
📱 Teléfono: {session.customer_phone}
📧 Email: {session.customer_email or 'No proporcionado'}
📍 Dirección: {session.customer_address or 'N/A'}
🌐 Origen: Interfaz Web
📋 Pedido: #{data.get('order_number', 'N/A')}

🍽 PEDIDO:
{items_text}

💰 Total: ${data['total']}
⏰ Hora: {datetime.now().strftime('%d/%m/%Y %H:%M')}

✅ Pedido guardado en base de datos"""
        
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
✅ Estado: Pendiente de confirmación

📞 LLAMAR para confirmar"""
        
        elif notification_type == "payment_confirmed":
            message = f"""💰 PAGO CONFIRMADO - PAYPAL

🎫 Pedido: #{data.get('numero_pedido', 'N/A')}
💳 Transacción: {data['transaction_id']}
💵 Monto: ${data['total']}

👤 Cliente: {session.customer_name}
📱 Teléfono: {session.customer_phone}

✅ Estado: PAGADO
🕐 {datetime.now().strftime('%d/%m/%Y %H:%M')}

🔔 ¡Pedido listo para preparar!"""
        
        elif notification_type == "new_message":
            message = f"""💬 MENSAJE DEL CHAT WEB

👤 Usuario: {session.customer_name or 'Sin registrar'}
💬 Mensaje: {data['message']}
⏰ {datetime.now().strftime('%H:%M')}"""
        
        else:
            print(f"⚠️ Tipo de notificación no reconocido: {notification_type}")
            return
        
        # Enviar mensaje
        bot_restaurante.send_message(target_chat, message)
        print(f"✅ Notificación '{notification_type}' enviada a {target_chat}")
        
    except Exception as e:
        print(f"❌ Error enviando notificación: {e}")
        import traceback
        traceback.print_exc()


# ==================== MODIFICAR CLASE WebChatSession ====================

class WebChatSession:
    """Simular una sesión de chat para usuarios web - ACTUALIZADA"""
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
        self.registration_step = "needs_initial_selection"  # ✅ CAMBIO AQUÍ
        self.is_registered = False
        
        # ✅ NUEVOS ATRIBUTOS
        self.tipo_pedido_seleccionado = None  # 'restaurant', 'takeaway', 'delivery'
        self.numero_mesa = None
        self.numero_comensales = None
        self.en_menu_informacion = False
        
        # Reservaciones
        self.reservation_step = None
        self.reservation_date = None
        self.reservation_time = None
        self.reservation_people = None
        self.reservation_occasion = None
        self.reservation_notes = None
        
        # ✅ NUEVO: Sistema de cantidades e ingredientes
        self.item_pendiente = None  # Item que está siendo agregado
        self.esperando_cantidad = False
        self.esperando_ingredientes = False
    
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
        return procesar_agregado_item_con_cantidad(session, text_lower, restaurante_id)
    
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
    """Procesar mensaje - VERSIÓN CON CANTIDADES E INGREDIENTES"""
    try:
        text = mock_message.text.strip()
        text_lower = text.lower()
        
        # ==================== FLUJO DE CANTIDADES E INGREDIENTES ====================
        # (Ejecutar ANTES de cualquier otra cosa si están activos)
        
        if session.esperando_cantidad:
            return procesar_cantidad_seleccionada(session, text)
        
        if session.esperando_ingredientes:
            return procesar_modificacion_ingredientes(session, text)
        
        # ==================== USUARIOS REGISTRADOS ====================
        if session.is_registered:
            
            # Detección de intención de ordenar (MEJORADA)
            if any(word in text_lower for word in ['quiero', 'pedir', 'ordenar', 'me gustaría', 'dame']):
                return procesar_agregado_item_con_cantidad(session, text_lower, restaurante_id)
            
            # Menú de información
            if session.en_menu_informacion:
                resultado = procesar_menu_informacion(session, text_lower, restaurante_id)
                if '0' in text_lower or 'volver' in text_lower:
                    session.en_menu_informacion = False
                return resultado
            
            # Reservaciones
            reservacion_response = process_reservacion_flow(session, text_lower, text)
            if reservacion_response:
                return reservacion_response
        
        # ==================== PRIORIDAD 2: FLUJO DE REGISTRO ====================
        if not session.is_registered:
            
            # ===== PASO 0: MOSTRAR MENÚ INICIAL =====
            if session.registration_step == "needs_initial_selection":
                session.registration_step = "waiting_initial_selection"
                return mostrar_menu_principal(session)
            
            # ===== PASO 1: PROCESAR SELECCIÓN DE TIPO =====
            elif session.registration_step == "waiting_initial_selection":
                resultado = procesar_seleccion_tipo_pedido(session, text_lower)
                
                # Si eligió información, activar flag
                if '1️⃣ 🕐' in resultado:  # Es el menú de información
                    session.en_menu_informacion = True
                
                return resultado
            
            # ===== FLUJO: COMER EN LOCAL =====
            elif session.registration_step == "restaurant_name":
                if len(text) < 3:
                    return "❌ Por favor ingresa un nombre válido (mínimo 3 caracteres)"
                
                session.customer_name = text
                session.registration_step = "restaurant_table"
                
                return f"""Perfecto, {session.customer_name}! 😊

🪑 ¿En qué número de mesa estás?
(Ej: 5, 12, 15)"""
            
            elif session.registration_step == "restaurant_table":
                # Validar que sea un número
                if not text.isdigit():
                    return "❌ Por favor ingresa solo el número de mesa (Ej: 5)"
                
                numero_mesa = int(text)
                
                # TODO: Aquí podrías validar contra la tabla 'mesas' en la BD
                if numero_mesa < 1 or numero_mesa > 50:
                    return "❌ Número de mesa no válido. Intenta de nuevo."
                
                session.numero_mesa = numero_mesa
                session.registration_step = "restaurant_diners"
                
                return f"""✅ Mesa {numero_mesa} registrada

👥 ¿Cuántas personas son?
(Opcional - presiona 'saltar' si no quieres compartirlo)"""
            
            elif session.registration_step == "restaurant_diners":
                if 'saltar' in text_lower or 'skip' in text_lower:
                    session.numero_comensales = None
                    comensales_texto = "No especificado"
                else:
                    if not text.isdigit():
                        return "❌ Por favor ingresa solo números o escribe 'saltar'"
                    
                    session.numero_comensales = int(text)
                    comensales_texto = f"{session.numero_comensales} personas"
                
                session.registration_step = "restaurant_phone"
                
                return f"""👥 Comensales: {comensales_texto}

📱 ¿Cuál es tu número de teléfono?
(Opcional - presiona 'saltar' si no quieres proporcionarlo)
Ejemplo: 9611234567"""
            
            elif session.registration_step == "restaurant_phone":
                if 'saltar' in text_lower or 'skip' in text_lower:
                    session.customer_phone = None
                    telefono = "No proporcionado"
                else:
                    phone_clean = text.replace(" ", "").replace("-", "")
                    if not phone_clean.isdigit() or len(phone_clean) < 10:
                        return "❌ Teléfono inválido. Escribe 10 dígitos o 'saltar'"
                    
                    session.customer_phone = phone_clean
                    telefono = phone_clean
                
                # COMPLETAR REGISTRO PARA LOCAL
                cliente = db.get_or_create_cliente(
                    web_session_id=session.session_id,
                    nombre=session.customer_name,
                    restaurante_id=restaurante_id,
                    origen="web"
                )
                
                if cliente:
                    session.cliente_id = cliente['id']
                    
                    if session.customer_phone:
                        db.actualizar_cliente(
                            session.cliente_id,
                            telefono=session.customer_phone
                        )
                    
                    session.is_registered = True
                    session.registration_step = "completed"
                    
                    return f"""✅ ¡REGISTRO COMPLETADO!

🏪 Tipo: Comer en Local
👤 Nombre: {session.customer_name}
🪑 Mesa: {session.numero_mesa}
👥 Comensales: {session.numero_comensales or 'No especificado'}
📱 Teléfono: {telefono}

💳 Método de pago: Efectivo o Tarjeta en el local

🎉 ¡Perfecto! Ahora puedes hacer tu pedido.

Escribe "menú" para ver nuestras opciones 🍽️"""
                else:
                    return "❌ Error al registrar. Intenta de nuevo."
            
            # ===== FLUJO: PARA LLEVAR =====
            elif session.registration_step == "takeaway_name":
                if len(text) < 3:
                    return "❌ Nombre inválido (mínimo 3 caracteres)"
                
                session.customer_name = text
                session.registration_step = "takeaway_phone"
                
                return f"""Mucho gusto, {session.customer_name}! 😊

📱 ¿Cuál es tu número de teléfono?
(Para avisarte cuando esté listo)
Ejemplo: 9611234567"""
            
            elif session.registration_step == "takeaway_phone":
                phone_clean = text.replace(" ", "").replace("-", "")
                if not phone_clean.isdigit() or len(phone_clean) < 10:
                    return "❌ Teléfono inválido (10 dígitos)"
                
                session.customer_phone = phone_clean
                session.registration_step = "takeaway_email"
                
                return """✅ Teléfono guardado!

📧 ¿Cuál es tu correo electrónico?
(Necesario para enviarte el recibo de PayPal)
Ejemplo: tucorreo@gmail.com"""
            
            elif session.registration_step == "takeaway_email":
                import re
                email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
                
                if not re.match(email_pattern, text):
                    return "❌ Email inválido. Ej: tucorreo@gmail.com"
                
                session.customer_email = text
                
                # COMPLETAR REGISTRO PARA LLEVAR
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
                        email=session.customer_email
                    )
                    
                    session.is_registered = True
                    session.registration_step = "completed"
                    
                    return f"""✅ ¡REGISTRO COMPLETADO!

🚶 Tipo: Para Llevar
👤 Nombre: {session.customer_name}
📱 Teléfono: {session.customer_phone}
📧 Email: {session.customer_email}

💳 Pago: PayPal (al confirmar pedido)
⏱ Tiempo estimado: 20-30 minutos

🎉 ¡Listo! Ahora puedes hacer tu pedido.

Escribe "menú" para ver nuestras opciones 🍽️"""
                else:
                    return "❌ Error al registrar. Intenta de nuevo."
            
            # ===== FLUJO: DELIVERY (Mantener existente + email) =====
            elif session.registration_step == "delivery_name":
                if len(text) < 3:
                    return "❌ Nombre inválido (mínimo 3 caracteres)"
                
                session.customer_name = text
                session.registration_step = "delivery_phone"
                
                return f"""Mucho gusto, {session.customer_name}! 😊

📱 ¿Cuál es tu número de teléfono?
Ejemplo: 9611234567"""
            
            elif session.registration_step == "delivery_phone":
                phone_clean = text.replace(" ", "").replace("-", "")
                if not phone_clean.isdigit() or len(phone_clean) < 10:
                    return "❌ Teléfono inválido (10 dígitos)"
                
                session.customer_phone = phone_clean
                session.registration_step = "delivery_address"
                
                return """Perfecto! 📞

📍 ¿Cuál es tu dirección completa de entrega?
(Calle, número, colonia, referencias)"""
            
            elif session.registration_step == "delivery_address":
                if len(text) < 10:
                    return "❌ Dirección muy corta. Sé más específico"
                
                session.customer_address = text
                session.registration_step = "delivery_email"
                
                return """✅ Dirección guardada!

📧 ¿Cuál es tu correo electrónico?
(Necesario para enviarte el recibo de PayPal)
Ejemplo: tucorreo@gmail.com"""
            
            elif session.registration_step == "delivery_email":
                import re
                email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
                
                if not re.match(email_pattern, text):
                    return "❌ Email inválido. Ej: tucorreo@gmail.com"
                
                session.customer_email = text
                
                # COMPLETAR REGISTRO DELIVERY
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
                        direccion=session.customer_address,
                        email=session.customer_email
                    )
                    
                    session.is_registered = True
                    session.registration_step = "completed"
                    
                    delivery_config = obtener_info_delivery(restaurante_id)
                    tiempo = delivery_config.get('tiempo_entrega', '30-45 minutos') if delivery_config else '30-45 minutos'
                    
                    return f"""✅ ¡REGISTRO COMPLETADO!

🚗 Tipo: Delivery a Domicilio
👤 Nombre: {session.customer_name}
📱 Teléfono: {session.customer_phone}
📍 Dirección: {session.customer_address}
📧 Email: {session.customer_email}

💳 Pago: PayPal (al confirmar pedido)
⏱ Tiempo estimado: {tiempo}

🎉 ¡Perfecto! Ahora puedes hacer tu pedido.

Escribe "menú" para ver nuestras opciones 🍽️"""
                else:
                    return "❌ Error al registrar. Intenta de nuevo."
        
        # ==================== RESTO DEL CÓDIGO EXISTENTE ====================
        respuesta_dinamica = generar_respuesta_dinamica(session, text_lower, restaurante_id)
        if respuesta_dinamica:
            return respuesta_dinamica

        # ==================== ACTUALIZAR ESTAS SECCIONES EN process_bot_message() ====================

        elif any(word in text_lower for word in ['delivery', 'domicilio', 'entregar', 'llevar', 'envio', 'envío']):
            return generar_texto_delivery(restaurante_id)

        elif any(word in text_lower for word in ['horario', 'horarios', 'abierto', 'cerrado', 'hora', 'abren', 'cierran']):
            return generar_texto_horarios(restaurante_id)

        elif any(word in text_lower for word in ['donde', 'dirección', 'direccion', 'ubicación', 'ubicacion', 'telefono', 'teléfono', 'contacto', 'llamar']):
            info = obtener_info_contacto(restaurante_id)
            
            if info:
                return f"""📞 INFORMACIÓN DE CONTACTO

🏨 {info['nombre_restaurante']}

📍 Dirección:
{info['direccion']}, {info['ciudad']}, {info['estado_republica']}

📱 Teléfono: {info['telefono']}
📧 Email: {info['email']}

¡Estamos aquí para servirte!"""
            else:
                # Fallback a config.py
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
            return confirmar_pedido_mejorado(session, restaurante_id)

        elif 'cancelar' in text_lower and 'pedido' in text_lower:
            session.cart = []
            return """🗑 Pedido cancelado

Tu carrito ha sido limpiado.

¿Deseas empezar un nuevo pedido?
Escribe "menú" para ver nuestras opciones."""

        elif 'carrito' in text_lower or 'pedido actual' in text_lower:
            return formatear_resumen_carrito(session)

        elif any(word in text_lower for word in ['hola', 'buenas', 'hi', 'hello', 'buenos días', 'buenas tardes', 'buenas noches', 'buen día']):
            restaurante_info = obtener_info_contacto(restaurante_id)
            nombre_rest = restaurante_info['nombre_restaurante'] if restaurante_info else RESTAURANT_CONFIG['nombre']
            
            saludos = [
                f"¡Bienvenido a {nombre_rest}! ¿Listo para una experiencia culinaria única?",
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
            restaurante_info = obtener_info_contacto(restaurante_id)
            nombre_rest = restaurante_info['nombre_restaurante'] if restaurante_info else RESTAURANT_CONFIG['nombre']
            
            despedidas = [
                f"¡Adiós! Esperamos verte pronto en {nombre_rest}!",
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

@app.route('/api/create-payment', methods=['POST'])
def create_payment():
    """Crear pago en PayPal"""
    try:
        data = request.json
        session_id = data.get('session_id')
        
        if session_id not in chat_sessions:
            return jsonify({'success': False, 'error': 'Sesión no encontrada'}), 404
        
        session = chat_sessions[session_id]
        
        # Verificar que haya un pedido
        if not session.pedido_id:
            return jsonify({'success': False, 'error': 'No hay pedido activo'}), 400
        
        # Obtener datos del pedido desde la BD
        pedido = db.get_pedido(session.pedido_id)
        detalles = db.get_detalle_pedido(session.pedido_id)
        
        if not pedido or not detalles:
            return jsonify({'success': False, 'error': 'Error obteniendo datos del pedido'}), 500
        
        # Construir datos para PayPal
        items_list = []
        for detalle in detalles:
            items_list.append({
                'nombre': detalle['item_nombre'],
                'codigo': f"ITEM-{detalle['item_id']}",
                'cantidad': detalle['cantidad'],
                'precio': float(detalle['precio_unitario'])
            })
        
        pedido_data = {
            'numero_pedido': pedido['numero_pedido'],
            'items': items_list,
            'subtotal': float(pedido['subtotal']),
            'costo_envio': float(pedido.get('costo_envio', 0)),
            'total': float(pedido['total']),
            'moneda': 'MXN',
            'restaurante_nombre': pedido['nombre_restaurante']
        }
        
        # URLs de retorno
        restaurante_slug = data.get('restaurante_slug')
        return_url = f"{BASE_URL}/{restaurante_slug}/payment-success?session_id={session_id}"
        cancel_url = f"{BASE_URL}/{restaurante_slug}/payment-cancel?session_id={session_id}"
        
        # Crear pago en PayPal
        resultado = payment_manager.crear_pago(pedido_data, return_url, cancel_url)
        
        if resultado['success']:
            # Guardar payment_id en la sesión y en la BD
            session.payment_id = resultado['payment_id']
            
            from database.database_multirestaurante import get_db_cursor
            with get_db_cursor() as (cursor, conn):
                cursor.execute("""
                    UPDATE pedidos 
                    SET payment_id = %s, estado = 'pendiente_pago'
                    WHERE id = %s
                """, (resultado['payment_id'], session.pedido_id))
                conn.commit()
            
            return jsonify({
                'success': True,
                'approval_url': resultado['approval_url'],
                'payment_id': resultado['payment_id']
            })
        else:
            return jsonify({
                'success': False,
                'error': resultado.get('error', 'Error desconocido')
            }), 500
            
    except Exception as e:
        print(f"❌ Error en create-payment: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/<slug>/payment-success')
def payment_success(slug):
    """Página de éxito del pago"""
    try:
        session_id = request.args.get('session_id')
        payment_id = request.args.get('paymentId')
        payer_id = request.args.get('PayerID')
        
        if not session_id or not payment_id or not payer_id:
            return "<h1>❌ Datos de pago incompletos</h1>", 400
        
        session_obj = chat_sessions.get(session_id)
        if not session_obj:
            return "<h1>❌ Sesión no encontrada</h1>", 404
        
        # Ejecutar el pago
        resultado = payment_manager.ejecutar_pago(payment_id, payer_id)
        
        if resultado['success']:
            # Actualizar estado del pedido en la BD
            from database.database_multirestaurante import get_db_cursor
            with get_db_cursor() as (cursor, conn):
                cursor.execute("""
                    UPDATE pedidos 
                    SET estado = 'pagado', 
                        transaction_id = %s,
                        fecha_pago = NOW()
                    WHERE id = %s
                """, (resultado['transaction_id'], session_obj.pedido_id))
                conn.commit()
            
            # Obtener datos del pedido para la notificación
            pedido = db.get_pedido(session_obj.pedido_id)
            
            # Notificar a Telegram
            send_notification_to_group("payment_confirmed", {
                'numero_pedido': pedido['numero_pedido'],
                'transaction_id': resultado['transaction_id'],
                'total': pedido['total']
            }, session_obj)
            
            # ==================== NUEVO: ENVIAR MENSAJE AL CHAT ====================
            # Obtener tiempo estimado dinámicamente
            delivery_config = obtener_info_delivery(session_obj.restaurante_id)
            tiempo_estimado = delivery_config.get('tiempo_entrega', '30-45 minutos') if delivery_config else '30-45 minutos'
            
            mensaje_confirmacion = f"""✅ ¡PAGO CONFIRMADO!

🎫 Pedido: #{pedido['numero_pedido']}
💳 Transacción: {resultado['transaction_id']}
💰 Total pagado: ${pedido['total']}

📦 ESTADO DE TU PEDIDO:
🟢 Pago recibido
⏳ En preparación

📱 Te notificaremos por teléfono cuando:
- Tu pedido esté listo
- El repartidor esté en camino
- Llegue a tu dirección

📍 Dirección de entrega:
{session_obj.customer_address}

⏱ Tiempo estimado: {tiempo_estimado}

¡Gracias por tu compra! 🍽️"""

            session_obj.add_message(mensaje_confirmacion, is_user=False)
            
            # ==================== NUEVO: LIMPIAR SESIÓN ====================
            session_obj.cart = []
            session_obj.pedido_id = None
            session_obj.payment_id = None
            
            # Generar factura (opcional)
            cliente_data = {
                'nombre': session_obj.customer_name,
                'email': session_obj.customer_email or '',
                'telefono': session_obj.customer_phone,
                'direccion': session_obj.customer_address,
                'ciudad': '',
                'estado': '',
                'codigo_postal': ''
            }
            
            detalles = db.get_detalle_pedido(session_obj.pedido_id)
            items_list = []
            for detalle in detalles:
                items_list.append({
                    'nombre': detalle['item_nombre'],
                    'cantidad': detalle['cantidad'],
                    'precio': float(detalle['precio_unitario'])
                })
            
            pedido_data = {
                'numero_pedido': pedido['numero_pedido'],
                'items': items_list,
                'subtotal': float(pedido['subtotal']),
                'costo_envio': float(pedido.get('costo_envio', 0)),
                'total': float(pedido['total']),
                'moneda': 'MXN',
                'restaurante_nombre': pedido['nombre_restaurante']
            }
            
            factura_result = payment_manager.generar_factura(pedido_data, cliente_data)
            if factura_result['success']:
                print(f"✅ Factura generada: {factura_result.get('invoice_id')}")
            
            return render_template('public/payment_success.html', 
                                 transaction_id=resultado['transaction_id'],
                                 pedido_numero=pedido['numero_pedido'],
                                 total=pedido['total'],
                                 slug=slug,
                                 session_id=session_id)
        else:
            return f"<h1>❌ Error procesando pago</h1><p>{resultado.get('error')}</p>", 500
            
    except Exception as e:
        print(f"❌ Error en payment-success: {e}")
        import traceback
        traceback.print_exc()
        return f"<h1>❌ Error</h1><p>{str(e)}</p>", 500


@app.route('/<slug>/payment-cancel')
def payment_cancel(slug):
    """Página de cancelación del pago"""
    session_id = request.args.get('session_id')
    
    if session_id and session_id in chat_sessions:
        session = chat_sessions[session_id]
        
        # Actualizar estado del pedido
        if session.pedido_id:
            from database.database_multirestaurante import get_db_cursor
            with get_db_cursor() as (cursor, conn):
                cursor.execute("""
                    UPDATE pedidos 
                    SET estado = 'cancelado_pago'
                    WHERE id = %s
                """, (session.pedido_id,))
                conn.commit()
    
    return render_template('public/payment_cancel.html')

if __name__ == "__main__":
    print("=" * 60)
    print("🌐 Iniciando Servidor Web para Bot de Restaurante")
    
    # ✅ AGREGAR VERIFICACIÓN DE TIEMPOS
    from database.database_multirestaurante import get_db_cursor
    with get_db_cursor() as (cursor, conn):
        cursor.execute("SELECT id FROM restaurantes WHERE estado = 'activo'")
        restaurantes = cursor.fetchall()
    
    for rest in restaurantes:
        verificar_tiempos_bd(rest['id'])
    
    print("=" * 60)
    print("🔗 Servidor: http://localhost:5000/<slug>/")
    print("🤖 Bot de Telegram conectado")
    print("🗄 Base de datos MySQL conectada")
    print("✅ Listo para recibir mensajes desde la web")
    print("🎯 MODO MULTI-RESTAURANTE: Dinámico por slug")
    print("📅 SISTEMA DE RESERVACIONES INTEGRADO")
    print("🕐 HORARIOS Y DELIVERY DINÁMICOS DESDE BD")
    print("🤖 NOTIFICACIONES TELEGRAM DINÁMICAS POR RESTAURANTE")
    print("💰 SISTEMA DE PAGOS PAYPAL INTEGRADO")
    print("🍽️ SISTEMA DE CANTIDADES E INGREDIENTES MEJORADO")
    print("🏪 3 TIPOS DE PEDIDO: Local, Para Llevar, Delivery")
    print("🔍 BÚSQUEDA MEJORADA DE ITEMS E INGREDIENTES")
    print("⏱ SISTEMA DE TIEMPOS ESTIMADOS DINÁMICOS")
    print("=" * 60)
    
    run_flask_server()