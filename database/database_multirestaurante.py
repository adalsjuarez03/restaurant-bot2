"""
Módulo de conexión y operaciones con la base de datos MySQL
VERSIÓN MULTI-RESTAURANTE
"""

import mysql.connector
from mysql.connector import Error, pooling
from contextlib import contextmanager
from datetime import datetime, date, time as dt_time
import os
from dotenv import load_dotenv
import bcrypt
import random
import string


load_dotenv()

# Configuración de la base de datos
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
    'database': os.getenv('DB_NAME', 'sistema_restaurantes'),
    'port': int(os.getenv('DB_PORT', 3306)),
    'charset': 'utf8mb4',
    'collation': 'utf8mb4_unicode_ci'
}

# Pool de conexiones
connection_pool = None

def init_connection_pool():
    """Inicializar el pool de conexiones"""
    global connection_pool
    try:
        connection_pool = pooling.MySQLConnectionPool(
            pool_name="restaurant_pool",
            pool_size=5,
            pool_reset_session=True,
            **DB_CONFIG
        )
        print("✅ Pool de conexiones inicializado")
        return True
    except Error as e:
        print(f"❌ Error inicializando pool: {e}")
        return False

@contextmanager
def get_db_connection():
    """Context manager para obtener conexión"""
    connection = None
    try:
        if connection_pool is None:
            init_connection_pool()
        
        connection = connection_pool.get_connection()
        yield connection
    except Error as e:
        print(f"❌ Error de conexión: {e}")
        raise
    finally:
        if connection and connection.is_connected():
            connection.close()

@contextmanager
def get_db_cursor(dictionary=True):
    """Context manager para obtener cursor"""
    with get_db_connection() as connection:
        cursor = connection.cursor(dictionary=dictionary)
        try:
            yield cursor, connection
        finally:
            cursor.close()


class DatabaseManager:
    """Clase para manejar todas las operaciones de base de datos"""
    
    # ==================== RESTAURANTES ====================
    
    @staticmethod
    def get_restaurante_por_slug(slug):
        """Obtener información de un restaurante por su slug"""
        try:
            with get_db_cursor() as (cursor, conn):
                cursor.execute("""
                    SELECT * FROM restaurantes 
                    WHERE slug = %s AND estado = 'activo'
                """, (slug,))
                return cursor.fetchone()
        except Error as e:
            print(f"❌ Error obteniendo restaurante: {e}")
            return None
    
    @staticmethod
    def get_restaurante_por_bot_token(bot_token):
        """Obtener restaurante por su token de bot de Telegram"""
        try:
            with get_db_cursor() as (cursor, conn):
                cursor.execute("""
                    SELECT * FROM restaurantes 
                    WHERE bot_token = %s AND estado = 'activo'
                """, (bot_token,))
                return cursor.fetchone()
        except Error as e:
            print(f"❌ Error obteniendo restaurante por token: {e}")
            return None
    
    @staticmethod
    def crear_restaurante(data):
        """Crear un nuevo restaurante"""
        try:
            with get_db_cursor() as (cursor, conn):
                cursor.execute("""
                    INSERT INTO restaurantes 
                    (slug, nombre_restaurante, descripcion, telefono, email, 
                     direccion, ciudad, estado_republica, plan)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    data['slug'], data['nombre_restaurante'], data.get('descripcion'),
                    data.get('telefono'), data.get('email'), data.get('direccion'),
                    data.get('ciudad'), data.get('estado_republica'), 
                    data.get('plan', 'gratis')
                ))
                conn.commit()
                return cursor.lastrowid
        except Error as e:
            print(f"❌ Error creando restaurante: {e}")
            return None
    
    @staticmethod
    def actualizar_restaurante(restaurante_id, data):
        """Actualizar información del restaurante"""
        try:
            with get_db_cursor() as (cursor, conn):
                updates = []
                params = []
                
                campos_permitidos = [
                    'nombre_restaurante', 'descripcion', 'telefono', 'email',
                    'direccion', 'ciudad', 'estado_republica', 'logo_url',
                    'banner_url', 'color_primario', 'color_secundario',
                    'horarios', 'config_delivery', 'bot_token'
                ]
                
                for campo in campos_permitidos:
                    if campo in data:
                        updates.append(f"{campo} = %s")
                        params.append(data[campo])
                
                if not updates:
                    return True
                
                params.append(restaurante_id)
                query = f"UPDATE restaurantes SET {', '.join(updates)} WHERE id = %s"
                
                cursor.execute(query, params)
                conn.commit()
                return True
        except Error as e:
            print(f"❌ Error actualizando restaurante: {e}")
            return False
    
    # ==================== USUARIOS ADMIN ====================
    
    @staticmethod
    def crear_usuario_admin(restaurante_id, email, password, nombre_completo, rol='admin'):
        """Crear un usuario administrador"""
        try:
            with get_db_cursor() as (cursor, conn):
                # Hash de la contraseña
                password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                
                cursor.execute("""
                    INSERT INTO usuarios_admin 
                    (restaurante_id, email, password_hash, nombre_completo, rol)
                    VALUES (%s, %s, %s, %s, %s)
                """, (restaurante_id, email, password_hash, nombre_completo, rol))
                
                conn.commit()
                return cursor.lastrowid
        except Error as e:
            print(f"❌ Error creando usuario admin: {e}")
            return None
    
    @staticmethod
    def verificar_login_admin(email, password):
        """Verificar credenciales de administrador"""
        try:
            with get_db_cursor() as (cursor, conn):
                cursor.execute("""
                    SELECT u.*, r.nombre_restaurante, r.slug, r.estado as estado_restaurante
                    FROM usuarios_admin u
                    INNER JOIN restaurantes r ON u.restaurante_id = r.id
                    WHERE u.email = %s AND u.activo = TRUE
                """, (email,))
                
                usuario = cursor.fetchone()
                
                if not usuario:
                    return None
                
                # Verificar contraseña
                if bcrypt.checkpw(password.encode('utf-8'), usuario['password_hash'].encode('utf-8')):
                    # Actualizar último acceso
                    cursor.execute("""
                        UPDATE usuarios_admin 
                        SET ultimo_acceso = NOW() 
                        WHERE id = %s
                    """, (usuario['id'],))
                    conn.commit()
                    
                    return usuario
                
                return None
        except Error as e:
            print(f"❌ Error verificando login: {e}")
            return None
    
    # ==================== CATEGORÍAS MENÚ ====================
    
    @staticmethod
    def get_categorias_menu(restaurante_id):
        """Obtener categorías del menú de un restaurante"""
        try:
            with get_db_cursor() as (cursor, conn):
                cursor.execute("""
                    SELECT * FROM categorias_menu 
                    WHERE restaurante_id = %s AND activo = TRUE 
                    ORDER BY orden
                """, (restaurante_id,))
                return cursor.fetchall()
        except Error as e:
            print(f"❌ Error obteniendo categorías: {e}")
            return []
    
    @staticmethod
    def crear_categoria(restaurante_id, nombre, nombre_display, descripcion=None, icono=None, orden=0):
        """Crear una categoría de menú"""
        try:
            with get_db_cursor() as (cursor, conn):
                cursor.execute("""
                    INSERT INTO categorias_menu 
                    (restaurante_id, nombre, nombre_display, descripcion, icono, orden)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (restaurante_id, nombre, nombre_display, descripcion, icono, orden))
                
                conn.commit()
                return cursor.lastrowid
        except Error as e:
            print(f"❌ Error creando categoría: {e}")
            return None
    
    @staticmethod
    def actualizar_categoria(categoria_id, data):
        """Actualizar una categoría"""
        try:
            with get_db_cursor() as (cursor, conn):
                updates = []
                params = []
                
                for campo in ['nombre', 'nombre_display', 'descripcion', 'icono', 'orden', 'activo']:
                    if campo in data:
                        updates.append(f"{campo} = %s")
                        params.append(data[campo])
                
                if not updates:
                    return True
                
                params.append(categoria_id)
                query = f"UPDATE categorias_menu SET {', '.join(updates)} WHERE id = %s"
                
                cursor.execute(query, params)
                conn.commit()
                return True
        except Error as e:
            print(f"❌ Error actualizando categoría: {e}")
            return False
    
    @staticmethod
    def eliminar_categoria(categoria_id):
        """Eliminar (desactivar) una categoría"""
        try:
            with get_db_cursor() as (cursor, conn):
                cursor.execute("""
                    UPDATE categorias_menu 
                    SET activo = FALSE 
                    WHERE id = %s
                """, (categoria_id,))
                conn.commit()
                return True
        except Error as e:
            print(f"❌ Error eliminando categoría: {e}")
            return False
    
    # ==================== ITEMS MENÚ ====================
    
    @staticmethod
    def get_items_por_categoria(restaurante_id, categoria_id):
        """Obtener items de una categoría de un restaurante específico"""
        try:
            with get_db_cursor() as (cursor, conn):
                cursor.execute("""
                    SELECT * FROM items_menu 
                    WHERE restaurante_id = %s AND categoria_id = %s
                    ORDER BY nombre
                """, (restaurante_id, categoria_id))
                return cursor.fetchall()
        except Error as e:
            print(f"❌ Error obteniendo items: {e}")
            return []
    
    @staticmethod
    def get_item_por_codigo(restaurante_id, codigo):
        """Obtener un item por su código en un restaurante específico"""
        try:
            with get_db_cursor() as (cursor, conn):
                cursor.execute("""
                    SELECT i.*, c.nombre as categoria_nombre
                    FROM items_menu i
                    INNER JOIN categorias_menu c ON i.categoria_id = c.id
                    WHERE i.restaurante_id = %s AND i.codigo = %s
                """, (restaurante_id, codigo))
                return cursor.fetchone()
        except Error as e:
            print(f"❌ Error obteniendo item: {e}")
            return None
    
    @staticmethod
    def crear_item_menu(restaurante_id, data):
        """Crear un item del menú"""
        try:
            with get_db_cursor() as (cursor, conn):
                cursor.execute("""
                    INSERT INTO items_menu 
                    (restaurante_id, categoria_id, codigo, nombre, descripcion, precio,
                     tiempo_preparacion, disponible, vegano, vegetariano, sin_gluten, picante)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    restaurante_id, data['categoria_id'], data['codigo'], 
                    data['nombre'], data['descripcion'], data['precio'],
                    data.get('tiempo_preparacion'), data.get('disponible', True),
                    data.get('vegano', False), data.get('vegetariano', False),
                    data.get('sin_gluten', False), data.get('picante', False)
                ))
                
                conn.commit()
                return cursor.lastrowid
        except Error as e:
            print(f"❌ Error creando item: {e}")
            return None
    
    @staticmethod
    def actualizar_item_menu(item_id, data):
        """Actualizar un item del menú"""
        try:
            with get_db_cursor() as (cursor, conn):
                updates = []
                params = []
                
                campos_permitidos = [
                    'categoria_id', 'codigo', 'nombre', 'descripcion', 'precio',
                    'precio_oferta', 'tiempo_preparacion', 'disponible', 'destacado',
                    'vegano', 'vegetariano', 'sin_gluten', 'picante', 'imagen_url'
                ]
                
                for campo in campos_permitidos:
                    if campo in data:
                        updates.append(f"{campo} = %s")
                        params.append(data[campo])
                
                if not updates:
                    return True
                
                params.append(item_id)
                query = f"UPDATE items_menu SET {', '.join(updates)} WHERE id = %s"
                
                cursor.execute(query, params)
                conn.commit()
                return True
        except Error as e:
            print(f"❌ Error actualizando item: {e}")
            return False
    
    @staticmethod
    def eliminar_item_menu(item_id):
        """Eliminar (desactivar) un item del menú"""
        try:
            with get_db_cursor() as (cursor, conn):
                cursor.execute("""
                    UPDATE items_menu 
                    SET disponible = FALSE 
                    WHERE id = %s
                """, (item_id,))
                conn.commit()
                return True
        except Error as e:
            print(f"❌ Error eliminando item: {e}")
            return False
    
    @staticmethod
    def get_ingredientes_item(item_id):
        """Obtener ingredientes de un item"""
        try:
            with get_db_cursor() as (cursor, conn):
                cursor.execute("""
                    SELECT nombre FROM ingredientes 
                    WHERE item_id = %s 
                    ORDER BY orden
                """, (item_id,))
                return [row['nombre'] for row in cursor.fetchall()]
        except Error as e:
            print(f"❌ Error obteniendo ingredientes: {e}")
            return []
    
    @staticmethod
    def agregar_ingrediente(item_id, nombre, alergeno=False, orden=0):
        """Agregar un ingrediente a un item"""
        try:
            with get_db_cursor() as (cursor, conn):
                cursor.execute("""
                    INSERT INTO ingredientes 
                    (item_id, nombre, alergeno, orden)
                    VALUES (%s, %s, %s, %s)
                """, (item_id, nombre, alergeno, orden))
                
                conn.commit()
                return cursor.lastrowid
        except Error as e:
            print(f"❌ Error agregando ingrediente: {e}")
            return None
    
    # ==================== NUEVOS MÉTODOS DINÁMICOS ====================
    
    @staticmethod
    def buscar_items_por_texto(restaurante_id, texto_busqueda):
        """Buscar items del menú por palabras clave - Búsqueda flexible sin tildes"""
        try:
            import unicodedata
        
            # Normalizar texto de búsqueda (eliminar tildes)
            def normalizar(texto):
                texto = texto.lower()
                return ''.join(
                    c for c in unicodedata.normalize('NFD', texto)
                    if unicodedata.category(c) != 'Mn'
                )
        
            texto_normalizado = normalizar(texto_busqueda)
        
            with get_db_cursor() as (cursor, conn):
                # Obtener todos los items disponibles del restaurante
                cursor.execute("""
                    SELECT i.*, c.nombre as categoria_nombre
                    FROM items_menu i
                    INNER JOIN categorias_menu c ON i.categoria_id = c.id
                    WHERE i.restaurante_id = %s 
                    AND i.disponible = TRUE
                """, (restaurante_id,))
            
                items = cursor.fetchall()
            
                # Buscar manualmente comparando textos normalizados
                resultados = []
                for item in items:
                    nombre_normalizado = normalizar(item['nombre'])
                    descripcion_normalizada = normalizar(item.get('descripcion', ''))
                
                    # Buscar cada palabra del texto en el nombre o descripción
                    palabras_busqueda = texto_normalizado.split()
                    coincidencias = sum(
                        1 for palabra in palabras_busqueda 
                        if palabra in nombre_normalizado or palabra in descripcion_normalizada
                    )
                
                    # Si encuentra al menos una coincidencia, agregarlo
                    if coincidencias > 0:
                        item['score'] = coincidencias
                        resultados.append(item)
            
                # Ordenar por número de coincidencias (más relevante primero)
                resultados.sort(key=lambda x: x['score'], reverse=True)
            
                return resultados[:5]
        except Error as e:
            print(f"❌ Error buscando items: {e}")
            return []
    
    @staticmethod
    def get_menu_completo_display(restaurante_id):
        """Obtener menú completo formateado para mostrar"""
        try:
            with get_db_cursor() as (cursor, conn):
                cursor.execute("""
                    SELECT 
                        c.id as categoria_id,
                        c.nombre as categoria_codigo,
                        c.nombre_display,
                        c.descripcion as cat_descripcion,
                        c.icono,
                        c.orden
                    FROM categorias_menu c
                    WHERE c.restaurante_id = %s AND c.activo = TRUE
                    ORDER BY c.orden
                """, (restaurante_id,))
                categorias = cursor.fetchall()
                
                menu_display = []
                for cat in categorias:
                    cursor.execute("""
                        SELECT 
                            id, codigo, nombre, descripcion, precio, 
                            tiempo_preparacion, vegano, vegetariano,
                            sin_gluten, disponible
                        FROM items_menu
                        WHERE restaurante_id = %s 
                        AND categoria_id = %s
                        ORDER BY nombre
                    """, (restaurante_id, cat['categoria_id']))
                    
                    items = cursor.fetchall()
                    
                    menu_display.append({
                        'categoria': cat,
                        'items': items
                    })
                
                return menu_display
        except Error as e:
            print(f"❌ Error obteniendo menú display: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    # ==================== CLIENTES ====================
    
    @staticmethod
    def get_or_create_cliente(restaurante_id, telegram_user_id=None, web_session_id=None, nombre="Cliente", origen="telegram"):
        """Obtener o crear un cliente - CORREGIDO CON restaurante_id"""
        try:
            with get_db_cursor() as (cursor, conn):
                # Buscar cliente existente
                if telegram_user_id:
                    cursor.execute("""
                        SELECT * FROM clientes 
                        WHERE restaurante_id = %s AND telegram_user_id = %s
                    """, (restaurante_id, telegram_user_id))
                elif web_session_id:
                    cursor.execute("""
                        SELECT * FROM clientes 
                        WHERE restaurante_id = %s AND web_session_id = %s
                    """, (restaurante_id, web_session_id))
                else:
                    print("⚠️ Advertencia: No se proporcionó telegram_user_id ni web_session_id")
                    return None
                
                cliente = cursor.fetchone()
                
                if cliente:
                    print(f"✅ Cliente existente encontrado: ID {cliente['id']}")
                    return cliente
                
                # Crear nuevo cliente CON restaurante_id
                print(f"🆕 Creando nuevo cliente para restaurante_id: {restaurante_id}")
                cursor.execute("""
                    INSERT INTO clientes 
                    (restaurante_id, telegram_user_id, web_session_id, nombre, origen)
                    VALUES (%s, %s, %s, %s, %s)
                """, (restaurante_id, telegram_user_id, web_session_id, nombre, origen))
                
                conn.commit()
                cliente_id = cursor.lastrowid
                
                print(f"✅ Cliente creado exitosamente: ID {cliente_id}")
                
                # Retornar el cliente creado
                cursor.execute("SELECT * FROM clientes WHERE id = %s", (cliente_id,))
                return cursor.fetchone()
                
        except Error as e:
            print(f"❌ Error en get_or_create_cliente: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    @staticmethod
    def actualizar_cliente(cliente_id, telefono=None, direccion=None, email=None):
        """Actualizar información del cliente"""
        try:
            with get_db_cursor() as (cursor, conn):
                updates = []
                params = []
                
                if telefono:
                    updates.append("telefono = %s")
                    params.append(telefono)
                if direccion:
                    updates.append("direccion = %s")
                    params.append(direccion)
                if email:
                    updates.append("email = %s")
                    params.append(email)
                
                if not updates:
                    return True
                
                params.append(cliente_id)
                query = f"UPDATE clientes SET {', '.join(updates)} WHERE id = %s"
                
                cursor.execute(query, params)
                conn.commit()
                return True
                
        except Error as e:
            print(f"❌ Error actualizando cliente: {e}")
            return False
    
    # ==================== INTERACCIONES ====================
    
    @staticmethod
    def registrar_interaccion(cliente_id, mensaje, respuesta, tipo='web', restaurante_id=None):
        """Registrar una interacción del cliente con el bot"""
        try:
            with get_db_cursor() as (cursor, conn):
                cursor.execute("""
                    INSERT INTO interacciones 
                    (cliente_id, restaurante_id, mensaje, respuesta, tipo, fecha_interaccion)
                    VALUES (%s, %s, %s, %s, %s, NOW())
                """, (cliente_id, restaurante_id, mensaje, respuesta, tipo))
                
                conn.commit()
                return cursor.lastrowid
        except Error as e:
            print(f"❌ Error registrando interacción: {e}")
            return None
    
    # ==================== PEDIDOS ====================
    
    @staticmethod
    def crear_pedido_simple(restaurante_id, cliente_id, tipo_pedido, origen):
        """Crear pedido sin usar stored procedure"""
        try:
            with get_db_cursor() as (cursor, conn):
                # Generar número de pedido único
                numero_pedido = f"PED-{datetime.now().strftime('%Y%m%d%H%M%S')}-{random.randint(100, 999)}"
                
                cursor.execute("""
                    INSERT INTO pedidos 
                    (restaurante_id, cliente_id, numero_pedido, tipo_pedido, origen, estado, total, subtotal)
                    VALUES (%s, %s, %s, %s, %s, 'pendiente', 0, 0)
                """, (restaurante_id, cliente_id, numero_pedido, tipo_pedido, origen))
                
                conn.commit()
                pedido_id = cursor.lastrowid
                
                print(f"✅ Pedido insertado - ID: {pedido_id}, Número: {numero_pedido}")
                
                return {
                    'pedido_id': pedido_id,
                    'numero_pedido': numero_pedido
                }
        except Error as e:
            print(f"❌ Error creando pedido simple: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    @staticmethod
    def agregar_item_pedido(pedido_id, item_id, cantidad, precio_unitario):
        """Agregar un item al pedido"""
        try:
            with get_db_cursor() as (cursor, conn):
                subtotal = cantidad * precio_unitario
                
                cursor.execute("""
                    INSERT INTO detalle_pedidos 
                    (pedido_id, item_id, cantidad, precio_unitario, subtotal)
                    VALUES (%s, %s, %s, %s, %s)
                """, (pedido_id, item_id, cantidad, precio_unitario, subtotal))
                
                # Actualizar total del pedido
                cursor.execute("""
                    UPDATE pedidos 
                    SET subtotal = subtotal + %s,
                        total = total + %s
                    WHERE id = %s
                """, (subtotal, subtotal, pedido_id))
                
                conn.commit()
                return True
                
        except Error as e:
            print(f"❌ Error agregando item a pedido: {e}")
            return False
    
    @staticmethod
    def get_pedido(pedido_id):
        """Obtener información de un pedido"""
        try:
            with get_db_cursor() as (cursor, conn):
                cursor.execute("""
                    SELECT p.*, c.nombre as cliente_nombre, c.telefono as cliente_telefono,
                           r.nombre_restaurante
                    FROM pedidos p
                    INNER JOIN clientes c ON p.cliente_id = c.id
                    INNER JOIN restaurantes r ON p.restaurante_id = r.id
                    WHERE p.id = %s
                """, (pedido_id,))
                return cursor.fetchone()
        except Error as e:
            print(f"❌ Error obteniendo pedido: {e}")
            return None
    
    @staticmethod
    def get_detalle_pedido(pedido_id):
        """Obtener detalles (items) de un pedido"""
        try:
            with get_db_cursor() as (cursor, conn):
                cursor.execute("""
                    SELECT dp.*, i.nombre as item_nombre
                    FROM detalle_pedidos dp
                    INNER JOIN items_menu i ON dp.item_id = i.id
                    WHERE dp.pedido_id = %s
                """, (pedido_id,))
                return cursor.fetchall()
        except Error as e:
            print(f"❌ Error obteniendo detalle: {e}")
            return []
    
    @staticmethod
    def actualizar_estado_pedido(pedido_id, nuevo_estado):
        """Actualizar el estado de un pedido"""
        try:
            with get_db_cursor() as (cursor, conn):
                cursor.execute("""
                    UPDATE pedidos 
                    SET estado = %s 
                    WHERE id = %s
                """, (nuevo_estado, pedido_id))
                conn.commit()
                return True
        except Error as e:
            print(f"❌ Error actualizando estado: {e}")
            return False
    
    @staticmethod
    def get_pedidos_restaurante(restaurante_id, limit=20):
        """Obtener pedidos recientes de un restaurante"""
        try:
            with get_db_cursor() as (cursor, conn):
                cursor.execute("""
                    SELECT p.*, c.nombre as nombre_cliente
                    FROM pedidos p
                    LEFT JOIN clientes c ON p.cliente_id = c.id
                    WHERE p.restaurante_id = %s
                    ORDER BY p.fecha_pedido DESC
                    LIMIT %s
                """, (restaurante_id, limit))
                return cursor.fetchall()
        except Error as e:
            print(f"❌ Error obteniendo pedidos: {e}")
            return []
    
    # ==================== RESERVACIONES ====================
    
    @staticmethod
    def crear_reservacion(restaurante_id, cliente_id, nombre, telefono, fecha, hora, personas, origen):
        """Crear una nueva reservación"""
        try:
            with get_db_cursor() as (cursor, conn):
                # Generar código de reservación
                letters = ''.join(random.choices(string.ascii_uppercase, k=3))
                numbers = ''.join(random.choices(string.digits, k=3))
                codigo = f"RES-{letters}{numbers}"
                
                cursor.execute("""
                    INSERT INTO reservaciones 
                    (restaurante_id, cliente_id, codigo_reservacion, nombre_cliente, telefono, 
                     fecha_reservacion, hora_reservacion, numero_personas, origen)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (restaurante_id, cliente_id, codigo, nombre, telefono, fecha, hora, personas, origen))
                
                conn.commit()
                reservacion_id = cursor.lastrowid
                
                # Retornar la reservación creada
                cursor.execute("""
                    SELECT * FROM reservaciones WHERE id = %s
                """, (reservacion_id,))
                return cursor.fetchone()
                
        except Error as e:
            print(f"❌ Error creando reservación: {e}")
            return None
    
    @staticmethod
    def get_reservaciones_restaurante(restaurante_id, limit=20):
        """Obtener reservaciones recientes de un restaurante"""
        try:
            with get_db_cursor() as (cursor, conn):
                cursor.execute("""
                    SELECT * FROM reservaciones
                    WHERE restaurante_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                """, (restaurante_id, limit))
                return cursor.fetchall()
        except Error as e:
            print(f"❌ Error obteniendo reservaciones: {e}")
            return []
    
    # ==================== ESTADÍSTICAS ====================
    
    @staticmethod
    def get_estadisticas_hoy(restaurante_id):
        """Obtener estadísticas del día actual para un restaurante"""
        try:
            with get_db_cursor() as (cursor, conn):
                hoy = date.today()
                
                # Pedidos hoy
                cursor.execute("""
                    SELECT COUNT(*) as total, COALESCE(SUM(total), 0) as suma
                    FROM pedidos
                    WHERE restaurante_id = %s AND DATE(fecha_pedido) = %s
                """, (restaurante_id, hoy))
                pedidos_data = cursor.fetchone()
                
                # Reservaciones hoy
                cursor.execute("""
                    SELECT COUNT(*) as total
                    FROM reservaciones
                    WHERE restaurante_id = %s AND DATE(fecha_reservacion) = %s
                """, (restaurante_id, hoy))
                reservaciones_data = cursor.fetchone()
                
                return {
                    'pedidos_hoy': pedidos_data['total'] if pedidos_data else 0,
                    'total_hoy': float(pedidos_data['suma']) if pedidos_data else 0,
                    'reservaciones_hoy': reservaciones_data['total'] if reservaciones_data else 0
                }
        except Error as e:
            print(f"❌ Error obteniendo estadísticas: {e}")
            return {
                'pedidos_hoy': 0,
                'total_hoy': 0, 
                'reservaciones_hoy': 0
            }


# Inicializar el pool al importar el módulo
init_connection_pool()