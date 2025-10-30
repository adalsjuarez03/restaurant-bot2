"""
Panel de Administración Web para Sistema Multi-Restaurante
Servidor Flask con autenticación y gestión completa
"""

import sys
import os

# ✅ AGREGAR ESTO AL INICIO - Agregar la carpeta raíz del proyecto al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from flask_cors import CORS
from functools import wraps
from datetime import datetime, timedelta
import json

# Importar el nuevo DatabaseManager
from database.database_multirestaurante import DatabaseManager

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'tu_clave_secreta_super_segura_cambiar_en_produccion')
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
CORS(app)

db = DatabaseManager()

# ==================== DECORADORES ====================

def login_required(f):
    """Decorador para rutas que requieren autenticación"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor inicia sesión', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def get_current_user():
    """Obtener usuario actual de la sesión"""
    if 'user_id' in session:
        return {
            'id': session['user_id'],
            'email': session['email'],
            'nombre': session['nombre'],
            'restaurante_id': session['restaurante_id'],
            'restaurante_nombre': session['restaurante_nombre'],
            'rol': session['rol']
        }
    return None

# ==================== RUTAS DE REGISTRO PÚBLICO ====================
# Agregar estas rutas en admin_server.py ANTES de @app.route('/login')
# Aproximadamente después de la línea 50, antes de las rutas de autenticación

@app.route('/register')
def register_page():
    """Página pública de registro de restaurantes"""
    return render_template('public/register.html')


@app.route('/api/register-restaurant', methods=['POST'])
def register_restaurant():
    """API para registrar un nuevo restaurante"""
    try:
        data = request.get_json()
        
        # ✅ Validaciones básicas
        if not data.get('nombre_restaurante') or not data.get('slug'):
            return jsonify({
                'success': False, 
                'message': 'Nombre y slug son requeridos'
            }), 400
        
        if not data.get('admin_email') or not data.get('password'):
            return jsonify({
                'success': False, 
                'message': 'Email y contraseña del admin son requeridos'
            }), 400
        
        if not data.get('nombre_completo'):
            return jsonify({
                'success': False, 
                'message': 'Nombre completo del administrador es requerido'
            }), 400
        
        # ✅ Verificar que las contraseñas coincidan
        if data.get('password') != data.get('password_confirm'):
            return jsonify({
                'success': False, 
                'message': 'Las contraseñas no coinciden'
            }), 400
        
        # ✅ Verificar que el slug no exista
        restaurante_existente = db.get_restaurante_por_slug(data['slug'])
        if restaurante_existente:
            return jsonify({
                'success': False, 
                'message': 'Esa URL ya está en uso. Por favor elige otra.'
            }), 400
        
        # ✅ Verificar que el email no exista
        from database.database_multirestaurante import get_db_cursor
        with get_db_cursor() as (cursor, conn):
            cursor.execute("SELECT id FROM usuarios_admin WHERE email = %s", (data['admin_email'],))
            if cursor.fetchone():
                return jsonify({
                    'success': False, 
                    'message': 'Ese email ya está registrado'
                }), 400
        
        # 1️⃣ Crear el restaurante
        print(f"🏪 Creando restaurante: {data['nombre_restaurante']}")
        
        datos_restaurante = {
            'slug': data['slug'].lower().strip(),
            'nombre_restaurante': data['nombre_restaurante'].strip(),
            'descripcion': data.get('descripcion', '').strip() if data.get('descripcion') else None,
            'telefono': data.get('telefono', '').strip() if data.get('telefono') else None,
            'email': data.get('email', '').strip() if data.get('email') else None,
            'direccion': data.get('direccion', '').strip() if data.get('direccion') else None,
            'ciudad': data.get('ciudad', '').strip() if data.get('ciudad') else None,
            'estado_republica': data.get('estado_republica', '').strip() if data.get('estado_republica') else None,
            'plan': data.get('plan', 'gratis')
        }
        
        restaurante_id = db.crear_restaurante(datos_restaurante)
        
        if not restaurante_id:
            return jsonify({
                'success': False, 
                'message': 'Error al crear el restaurante. Por favor intenta de nuevo.'
            }), 500
        
        print(f"✅ Restaurante creado con ID: {restaurante_id}")
        
        # 2️⃣ Crear usuario administrador
        print(f"👤 Creando usuario administrador...")
        
        usuario_id = db.crear_usuario_admin(
            restaurante_id=restaurante_id,
            email=data['admin_email'].strip(),
            password=data['password'],
            nombre_completo=data['nombre_completo'].strip(),
            rol='owner'  # owner tiene todos los permisos
        )
        
        if not usuario_id:
            # ❌ Si falla, eliminar el restaurante creado (rollback manual)
            print(f"❌ Error creando usuario, eliminando restaurante...")
            with get_db_cursor() as (cursor, conn):
                cursor.execute("DELETE FROM restaurantes WHERE id = %s", (restaurante_id,))
                conn.commit()
            
            return jsonify({
                'success': False, 
                'message': 'Error al crear el usuario administrador'
            }), 500
        
        print(f"✅ Usuario creado con ID: {usuario_id}")
        
        # 3️⃣ Crear categorías por defecto (opcional pero recomendado)
        print(f"📂 Creando categorías por defecto...")
        
        categorias_default = [
            {
                'nombre': 'entradas', 
                'nombre_display': 'Entradas', 
                'icono': '🥗', 
                'orden': 1,
                'descripcion': 'Platos de entrada y aperitivos'
            },
            {
                'nombre': 'platos_fuertes', 
                'nombre_display': 'Platos Fuertes', 
                'icono': '🍽️', 
                'orden': 2,
                'descripcion': 'Platos principales'
            },
            {
                'nombre': 'bebidas', 
                'nombre_display': 'Bebidas', 
                'icono': '🥤', 
                'orden': 3,
                'descripcion': 'Bebidas frías y calientes'
            },
            {
                'nombre': 'postres', 
                'nombre_display': 'Postres', 
                'icono': '🍰', 
                'orden': 4,
                'descripcion': 'Postres y dulces'
            }
        ]
        
        categorias_creadas = 0
        for cat in categorias_default:
            cat_id = db.crear_categoria(
                restaurante_id=restaurante_id,
                nombre=cat['nombre'],
                nombre_display=cat['nombre_display'],
                descripcion=cat['descripcion'],
                icono=cat['icono'],
                orden=cat['orden']
            )
            if cat_id:
                categorias_creadas += 1
        
        print(f"✅ {categorias_creadas} categorías creadas")
        
        # 4️⃣ TODO: Enviar email de bienvenida (implementar después)
        # send_welcome_email(data['admin_email'], data['nombre_restaurante'])
        
        # ✅ REGISTRO EXITOSO
        print("=" * 60)
        print(f"🎉 RESTAURANTE REGISTRADO EXITOSAMENTE")
        print(f"   Restaurante: {datos_restaurante['nombre_restaurante']} (ID: {restaurante_id})")
        print(f"   Usuario: {data['admin_email']} (ID: {usuario_id})")
        print(f"   Slug: {datos_restaurante['slug']}")
        print(f"   Plan: {datos_restaurante['plan']}")
        print("=" * 60)
        
        return jsonify({
            'success': True,
            'message': 'Restaurante registrado exitosamente',
            'data': {
                'restaurante_id': restaurante_id,
                'usuario_id': usuario_id,
                'slug': datos_restaurante['slug'],
                'nombre_restaurante': datos_restaurante['nombre_restaurante']
            }
        }), 201
        
    except Exception as e:
        print(f"❌ ERROR EN REGISTRO: {e}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            'success': False, 
            'message': f'Error interno del servidor: {str(e)}'
        }), 500


@app.route('/api/check-slug/<slug>')
def check_slug_availability(slug):
    """Verificar si un slug está disponible (AJAX)"""
    try:
        # Validar formato del slug
        import re
        if not re.match(r'^[a-z0-9-]+$', slug):
            return jsonify({
                'available': False,
                'message': 'Solo letras minúsculas, números y guiones'
            })
        
        restaurante = db.get_restaurante_por_slug(slug)
        
        return jsonify({
            'available': restaurante is None,
            'message': '✓ Disponible' if restaurante is None else '✗ Ya está en uso'
        })
    except Exception as e:
        print(f"Error verificando slug: {e}")
        return jsonify({
            'success': False, 
            'message': str(e)
        }), 500


@app.route('/api/check-email/<email>')
def check_email_availability(email):
    """Verificar si un email está disponible (AJAX)"""
    try:
        # Validar formato básico de email
        import re
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            return jsonify({
                'available': False,
                'message': 'Formato de email inválido'
            })
        
        from database.database_multirestaurante import get_db_cursor
        with get_db_cursor() as (cursor, conn):
            cursor.execute("SELECT id FROM usuarios_admin WHERE email = %s", (email,))
            exists = cursor.fetchone() is not None
        
        return jsonify({
            'available': not exists,
            'message': '✓ Disponible' if not exists else '✗ Ya está registrado'
        })
    except Exception as e:
        print(f"Error verificando email: {e}")
        return jsonify({
            'success': False, 
            'message': str(e)
        }), 500


# ==================== FIN DE RUTAS DE REGISTRO ====================
# ==================== RUTAS DE AUTENTICACIÓN ====================

@app.route('/')
def index():
    """Página principal - landing page pública"""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('public/landing.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Página de login"""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        data = request.get_json() if request.is_json else request.form
        email = data.get('email', '').strip()
        password = data.get('password', '')
        
        if not email or not password:
            if request.is_json:
                return jsonify({'success': False, 'message': 'Email y contraseña son requeridos'}), 400
            flash('Email y contraseña son requeridos', 'danger')
            return redirect(url_for('login'))
        
        # Verificar credenciales
        usuario = db.verificar_login_admin(email, password)
        
        if usuario:
            # Crear sesión
            session.permanent = True
            session['user_id'] = usuario['id']
            session['email'] = usuario['email']
            session['nombre'] = usuario['nombre_completo']
            session['restaurante_id'] = usuario['restaurante_id']
            session['restaurante_nombre'] = usuario['nombre_restaurante']
            session['rol'] = usuario['rol']
            
            if request.is_json:
                return jsonify({
                    'success': True, 
                    'message': 'Login exitoso',
                    'redirect': url_for('dashboard')
                })
            
            flash(f'Bienvenido {usuario["nombre_completo"]}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            if request.is_json:
                return jsonify({'success': False, 'message': 'Credenciales inválidas'}), 401
            flash('Credenciales inválidas', 'danger')
            return redirect(url_for('login'))
    
    return render_template('admin/login.html')

@app.route('/logout')
def logout():
    """Cerrar sesión"""
    nombre = session.get('nombre', 'Usuario')
    session.clear()
    flash(f'Hasta luego {nombre}!', 'info')
    return redirect(url_for('login'))

# ==================== DASHBOARD ====================

@app.route('/dashboard')
@login_required
def dashboard():
    """Dashboard principal del administrador"""
    user = get_current_user()
    restaurante_id = user['restaurante_id']
    
    # Obtener estadísticas
    stats = db.get_estadisticas_hoy(restaurante_id)
    
    # Pedidos recientes
    pedidos_recientes = db.get_pedidos_restaurante(restaurante_id, limit=10)
    
    # Reservaciones recientes
    reservaciones_recientes = db.get_reservaciones_restaurante(restaurante_id, limit=10)
    
    return render_template('admin/dashboard.html',
                         user=user,
                         stats=stats,
                         pedidos=pedidos_recientes,
                         reservaciones=reservaciones_recientes)

# ==================== GESTIÓN DE MENÚ ====================

@app.route('/menu')
@login_required
def menu():
    """Página de gestión del menú"""
    user = get_current_user()
    restaurante_id = user['restaurante_id']
    
    # Obtener categorías
    categorias = db.get_categorias_menu(restaurante_id)
    
    # Obtener items agrupados por categoría
    menu_completo = []
    for categoria in categorias:
        items = db.get_items_por_categoria(restaurante_id, categoria['id'])
        menu_completo.append({
            'categoria': categoria,
            'items': items
        })
    
    return render_template('admin/menu.html',
                         user=user,
                         menu=menu_completo)

@app.route('/menu/categorias', methods=['GET', 'POST'])
@login_required
def gestionar_categorias():
    """Gestión de categorías del menú"""
    user = get_current_user()
    restaurante_id = user['restaurante_id']
    
    if request.method == 'POST':
        data = request.get_json()
        action = data.get('action')
        
        if action == 'crear':
            categoria_id = db.crear_categoria(
                restaurante_id,
                data['nombre'],
                data['nombre_display'],
                data.get('descripcion'),
                data.get('icono'),
                data.get('orden', 0)
            )
            
            if categoria_id:
                return jsonify({'success': True, 'message': 'Categoría creada', 'id': categoria_id})
            return jsonify({'success': False, 'message': 'Error al crear categoría'}), 500
        
        elif action == 'actualizar':
            success = db.actualizar_categoria(data['id'], data)
            if success:
                return jsonify({'success': True, 'message': 'Categoría actualizada'})
            return jsonify({'success': False, 'message': 'Error al actualizar'}), 500
        
        elif action == 'eliminar':
            success = db.eliminar_categoria(data['id'])
            if success:
                return jsonify({'success': True, 'message': 'Categoría eliminada'})
            return jsonify({'success': False, 'message': 'Error al eliminar'}), 500
    
    # GET
    categorias = db.get_categorias_menu(restaurante_id)
    return jsonify({'success': True, 'categorias': categorias})

@app.route('/menu/items', methods=['GET', 'POST', 'PUT', 'DELETE'])
@login_required
def gestionar_items():
    """Gestión de items del menú"""
    user = get_current_user()
    restaurante_id = user['restaurante_id']
    
    if request.method == 'POST':
        data = request.get_json()
        
        # Crear nuevo item
        item_id = db.crear_item_menu(restaurante_id, data)
        
        if item_id:
            # Agregar ingredientes si existen
            if 'ingredientes' in data and data['ingredientes']:
                for idx, ing in enumerate(data['ingredientes']):
                    db.agregar_ingrediente(item_id, ing, False, idx)
            
            return jsonify({'success': True, 'message': 'Item creado', 'id': item_id})
        return jsonify({'success': False, 'message': 'Error al crear item'}), 500
    
    elif request.method == 'PUT':
        data = request.get_json()
        item_id = data.get('id')
        
        success = db.actualizar_item_menu(item_id, data)
        if success:
            return jsonify({'success': True, 'message': 'Item actualizado'})
        return jsonify({'success': False, 'message': 'Error al actualizar'}), 500
    
    elif request.method == 'DELETE':
        item_id = request.args.get('id')
        success = db.eliminar_item_menu(item_id)
        if success:
            return jsonify({'success': True, 'message': 'Item eliminado'})
        return jsonify({'success': False, 'message': 'Error al eliminar'}), 500
    
    # GET - obtener items
    categoria_id = request.args.get('categoria_id')
    if categoria_id:
        items = db.get_items_por_categoria(restaurante_id, categoria_id)
    else:
        # Obtener todos los items
        categorias = db.get_categorias_menu(restaurante_id)
        items = []
        for cat in categorias:
            items.extend(db.get_items_por_categoria(restaurante_id, cat['id']))
    
    return jsonify({'success': True, 'items': items})

@app.route('/api/categoria/<int:categoria_id>', methods=['GET'])
@login_required
def get_categoria(categoria_id):
    """Obtener datos de una categoría específica"""
    categoria = db.get_categoria_by_id(categoria_id)
    
    if categoria:
        return jsonify({'success': True, 'categoria': categoria})
    return jsonify({'success': False, 'message': 'Categoría no encontrada'}), 404

@app.route('/api/item/<int:item_id>', methods=['GET'])
@login_required
def get_item(item_id):
    """Obtener datos de un item específico"""
    item = db.get_item_by_id(item_id)
    
    if item:
        # Obtener ingredientes también
        ingredientes = db.get_ingredientes_item(item_id)
        item['ingredientes'] = ingredientes
        return jsonify({'success': True, 'item': item})
    return jsonify({'success': False, 'message': 'Item no encontrado'}), 404

# ==================== GESTIÓN DE PEDIDOS ====================

@app.route('/pedidos')
@login_required
def pedidos():
    """Página de gestión de pedidos"""
    user = get_current_user()
    restaurante_id = user['restaurante_id']
    
    # Filtros
    estado = request.args.get('estado')
    fecha = request.args.get('fecha')
    
    # Obtener pedidos (por ahora todos los recientes)
    pedidos_lista = db.get_pedidos_restaurante(restaurante_id, limit=50)
    
    # Obtener estadísticas desde la base de datos
    stats = db.get_estadisticas_hoy(restaurante_id)
    
    # Asegurar que stats tenga los campos necesarios para pedidos
    if 'pendientes' not in stats:
        stats['pendientes'] = sum(1 for p in pedidos_lista if p.get('estado') in ['pendiente', 'confirmado'])
        stats['en_proceso'] = sum(1 for p in pedidos_lista if p.get('estado') in ['preparando', 'en_camino'])
        stats['completados'] = sum(1 for p in pedidos_lista if p.get('estado') in ['entregado', 'listo'])
        stats['total'] = len(pedidos_lista)
    
    return render_template('admin/pedidos.html',
                         user=user,
                         pedidos=pedidos_lista,
                         stats=stats)

@app.route('/pedidos/<int:pedido_id>')
@login_required
def ver_pedido(pedido_id):
    """Ver detalle de un pedido"""
    user = get_current_user()
    
    pedido = db.get_pedido(pedido_id)
    
    if not pedido or pedido['restaurante_id'] != user['restaurante_id']:
        flash('Pedido no encontrado', 'danger')
        return redirect(url_for('pedidos'))
    
    detalle = db.get_detalle_pedido(pedido_id)
    
    return render_template('admin/pedido_detalle.html',
                         user=user,
                         pedido=pedido,
                         detalle=detalle)

# ==================== GESTIÓN DE RESERVACIONES ====================

@app.route('/reservaciones', methods=['GET', 'POST'])
@login_required
def reservaciones():
    """Página de gestión de reservaciones"""
    user = get_current_user()
    restaurante_id = user['restaurante_id']
    
    if request.method == 'POST':
        # Crear nueva reservación desde el panel admin
        data = request.get_json()
        
        # Primero crear o buscar cliente
        cliente = db.get_or_create_cliente(
            restaurante_id=restaurante_id,
            nombre=data['nombre_cliente'],
            origen='admin'
        )
        
        if not cliente:
            return jsonify({'success': False, 'message': 'Error al crear cliente'}), 500
        
        # Crear reservación
        reservacion = db.crear_reservacion(
            restaurante_id=restaurante_id,
            cliente_id=cliente['id'],
            nombre=data['nombre_cliente'],
            telefono=data['telefono'],
            fecha=data['fecha_reservacion'],
            hora=data['hora_reservacion'],
            personas=data['numero_personas'],
            origen='admin'
        )
        
        if reservacion:
            return jsonify({'success': True, 'message': 'Reservación creada', 'id': reservacion['id']})
        return jsonify({'success': False, 'message': 'Error al crear reservación'}), 500
    
    # GET - Obtener reservaciones
    reservaciones_lista = db.get_reservaciones_restaurante(restaurante_id, limit=50)
    
    # Calcular estadísticas de reservaciones
    from datetime import date
    hoy = date.today()
    
    stats = {
        'hoy': sum(1 for r in reservaciones_lista if r.get('fecha_reservacion') == hoy),
        'pendientes': sum(1 for r in reservaciones_lista if r.get('estado') == 'pendiente'),
        'confirmadas': sum(1 for r in reservaciones_lista if r.get('estado') == 'confirmada'),
        'personas_hoy': sum(r.get('numero_personas', 0) for r in reservaciones_lista if r.get('fecha_reservacion') == hoy)
    }
    
    return render_template('admin/reservaciones.html',
                         user=user,
                         reservaciones=reservaciones_lista,
                         stats=stats)

@app.route('/reservaciones/<int:reservacion_id>', methods=['GET'])
@login_required
def ver_reservacion(reservacion_id):
    """Ver detalle de una reservación"""
    user = get_current_user()
    
    # Obtener reservación
    from database.database_multirestaurante import get_db_cursor
    from datetime import timedelta, date
    
    with get_db_cursor() as (cursor, conn):
        cursor.execute("""
            SELECT * FROM reservaciones 
            WHERE id = %s AND restaurante_id = %s
        """, (reservacion_id, user['restaurante_id']))
        reservacion = cursor.fetchone()
    
    if not reservacion:
        return jsonify({'success': False, 'message': 'Reservación no encontrada'}), 404
    
    # Convertir timedelta a string para JSON
    if reservacion.get('hora_reservacion') and isinstance(reservacion['hora_reservacion'], timedelta):
        td = reservacion['hora_reservacion']
        total_seconds = int(td.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        reservacion['hora_reservacion'] = f"{hours:02d}:{minutes:02d}"
    
    # Convertir date a string si es necesario
    if reservacion.get('fecha_reservacion') and isinstance(reservacion['fecha_reservacion'], date):
        reservacion['fecha_reservacion'] = reservacion['fecha_reservacion'].strftime('%Y-%m-%d')
    
    return jsonify({'success': True, 'reservacion': reservacion})

@app.route('/reservaciones/<int:reservacion_id>/estado', methods=['PUT'])
@login_required
def actualizar_estado_reservacion(reservacion_id):
    """Actualizar estado de una reservación"""
    user = get_current_user()
    data = request.get_json()
    nuevo_estado = data.get('estado')
    
    # Actualizar estado
    from database.database_multirestaurante import get_db_cursor
    with get_db_cursor() as (cursor, conn):
        cursor.execute("""
            UPDATE reservaciones 
            SET estado = %s 
            WHERE id = %s AND restaurante_id = %s
        """, (nuevo_estado, reservacion_id, user['restaurante_id']))
        conn.commit()
    
    return jsonify({'success': True, 'message': 'Estado actualizado'})

# ==================== CONFIGURACIÓN DEL RESTAURANTE ====================

@app.route('/configuracion', methods=['GET', 'POST'])
@login_required
def configuracion():
    """Página de configuración del restaurante"""
    user = get_current_user()
    restaurante_id = user['restaurante_id']
    
    if request.method == 'POST':
        data = request.get_json() if request.is_json else request.form.to_dict()
        
        # Actualizar configuración
        success = db.actualizar_restaurante(restaurante_id, data)
        
        if success:
            # Actualizar nombre en sesión si cambió
            if 'nombre_restaurante' in data:
                session['restaurante_nombre'] = data['nombre_restaurante']
            
            if request.is_json:
                return jsonify({'success': True, 'message': 'Configuración actualizada'})
            flash('Configuración actualizada correctamente', 'success')
            return redirect(url_for('configuracion'))
        else:
            if request.is_json:
                return jsonify({'success': False, 'message': 'Error al actualizar'}), 500
            flash('Error al actualizar la configuración', 'danger')
    
    # GET
    restaurante = db.get_restaurante_por_slug(session.get('restaurante_slug', ''))
    if not restaurante:
        # Obtener por ID si no hay slug en sesión
        from database.database_multirestaurante import get_db_cursor
        with get_db_cursor() as (cursor, conn):
            cursor.execute("SELECT * FROM restaurantes WHERE id = %s", (restaurante_id,))
            restaurante = cursor.fetchone()
    
    return render_template('admin/configuracion.html',
                         user=user,
                         restaurante=restaurante)

# ==================== AGREGAR ESTA RUTA EN admin_server.py ====================

@app.route('/api/restaurante/config')
@login_required
def get_restaurante_config():
    """API: Obtener configuración completa del restaurante"""
    try:
        user = get_current_user()
        restaurante_id = user['restaurante_id']
        
        from database.database_multirestaurante import get_db_cursor
        import json
        
        with get_db_cursor() as (cursor, conn):
            cursor.execute("""
                SELECT 
                    slug, nombre_restaurante, descripcion, telefono, email, direccion,
                    ciudad, estado_republica, codigo_postal, logo_url, banner_url,
                    config_delivery, horarios, bot_token, telegram_admin_id, 
                    telegram_group_id, config_notificaciones, plan, estado
                FROM restaurantes 
                WHERE id = %s
            """, (restaurante_id,))
            restaurante = cursor.fetchone()
        
        if not restaurante:
            return jsonify({'success': False, 'message': 'Restaurante no encontrado'}), 404
        
        # Parsear JSONs
        if restaurante.get('config_delivery') and isinstance(restaurante['config_delivery'], str):
            restaurante['config_delivery'] = json.loads(restaurante['config_delivery'])
        
        if restaurante.get('horarios') and isinstance(restaurante['horarios'], str):
            restaurante['horarios'] = json.loads(restaurante['horarios'])
        
        # ✅ Parsear config_notificaciones
        if restaurante.get('config_notificaciones') and isinstance(restaurante['config_notificaciones'], str):
            restaurante['config_notificaciones'] = json.loads(restaurante['config_notificaciones'])
        
        print(f"📤 Enviando configuración: bot_token={bool(restaurante.get('bot_token'))}, admin_id={restaurante.get('telegram_admin_id')}, group_id={restaurante.get('telegram_group_id')}")
        
        return jsonify({
            'success': True,
            'restaurante': restaurante
        })
        
    except Exception as e:
        print(f"❌ Error obteniendo config: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500
    
# ==================== RUTAS DE CONFIGURACIÓN ====================

@app.route('/configuracion/general', methods=['PUT'])
@login_required
def actualizar_configuracion_general():
    """Actualizar configuración general del restaurante"""
    try:
        user = get_current_user()
        restaurante_id = user['restaurante_id']
        data = request.get_json()
        
        success = db.actualizar_restaurante(restaurante_id, data)
        
        if success:
            # Actualizar nombre en sesión si cambió
            if 'nombre_restaurante' in data:
                session['restaurante_nombre'] = data['nombre_restaurante']
            
            return jsonify({'success': True, 'message': 'Configuración actualizada correctamente'})
        else:
            return jsonify({'success': False, 'message': 'Error al actualizar'}), 500
            
    except Exception as e:
        print(f"❌ Error actualizando configuración: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500


@app.route('/configuracion/delivery', methods=['PUT'])
@login_required
def actualizar_configuracion_delivery():
    """Actualizar configuración de delivery"""
    try:
        user = get_current_user()
        restaurante_id = user['restaurante_id']
        data = request.get_json()
        
        # Construir JSON de configuración de delivery
        config_delivery = {
            'activo': data.get('delivery_activo', 'false') == 'true',
            'costo_envio_base': float(data.get('costo_envio_base', 0)),
            'pedido_minimo': float(data.get('pedido_minimo', 0)),
            'envio_gratis_desde': float(data.get('envio_gratis_desde', 0)),
            'radio_cobertura': float(data.get('radio_cobertura', 5)),
            'tiempo_entrega': data.get('tiempo_entrega', '30-45 minutos'),
            'zonas_cobertura': data.get('zonas_cobertura', '').split('\n') if data.get('zonas_cobertura') else []
        }
        
        # Actualizar en la BD
        success = db.actualizar_restaurante(restaurante_id, {
            'config_delivery': json.dumps(config_delivery)
        })
        
        if success:
            return jsonify({'success': True, 'message': 'Configuración de delivery actualizada'})
        else:
            return jsonify({'success': False, 'message': 'Error al actualizar'}), 500
            
    except Exception as e:
        print(f"❌ Error actualizando delivery: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500


@app.route('/configuracion/horarios', methods=['PUT'])
@login_required
def actualizar_configuracion_horarios():
    """Actualizar horarios del restaurante"""
    try:
        user = get_current_user()
        restaurante_id = user['restaurante_id']
        data = request.get_json()
        
        # Construir JSON de horarios
        dias = ['lunes', 'martes', 'miercoles', 'jueves', 'viernes', 'sabado', 'domingo']
        horarios = {}
        
        for dia in dias:
            activo = data.get(f'activo_{dia}') == 'on'
            es_24h = data.get(f'24h_{dia}') == 'on'
            
            if activo:
                if es_24h:
                    horarios[dia] = {
                        'activo': True,
                        'apertura': '00:00',
                        'cierre': '23:59',
                        '24h': True
                    }
                else:
                    horarios[dia] = {
                        'activo': True,
                        'apertura': data.get(f'apertura_{dia}', '09:00'),
                        'cierre': data.get(f'cierre_{dia}', '22:00'),
                        '24h': False
                    }
            else:
                horarios[dia] = {
                    'activo': False
                }
        
        # Actualizar en la BD
        success = db.actualizar_restaurante(restaurante_id, {
            'horarios': json.dumps(horarios)
        })
        
        if success:
            return jsonify({'success': True, 'message': 'Horarios actualizados correctamente'})
        else:
            return jsonify({'success': False, 'message': 'Error al actualizar'}), 500
            
    except Exception as e:
        print(f"❌ Error actualizando horarios: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500


@app.route('/configuracion/telegram', methods=['PUT'])
@login_required
def actualizar_configuracion_telegram():
    """Actualizar configuración de Telegram"""
    try:
        user = get_current_user()
        restaurante_id = user['restaurante_id']
        data = request.get_json()
        
        print(f"📥 Datos recibidos: {data}")  # Debug
        
        # Construir datos de telegram
        datos_telegram = {}
        
        # Bot Token
        if data.get('bot_token'):
            datos_telegram['bot_token'] = data['bot_token'].strip()
        
        # Admin ID (convertir a número)
        if data.get('telegram_admin_id'):
            try:
                datos_telegram['telegram_admin_id'] = int(data['telegram_admin_id'].strip())
            except ValueError:
                return jsonify({'success': False, 'message': 'Admin ID debe ser un número'}), 400
        
        # Group ID (convertir a número)
        if data.get('telegram_group_id'):
            try:
                datos_telegram['telegram_group_id'] = int(data['telegram_group_id'].strip())
            except ValueError:
                return jsonify({'success': False, 'message': 'Group ID debe ser un número'}), 400
        
        # Guardar configuración de notificaciones como JSON
        config_notificaciones = {
            'notificar_pedidos': data.get('notificar_pedidos') == True or data.get('notificar_pedidos') == 'on',
            'notificar_reservaciones': data.get('notificar_reservaciones') == True or data.get('notificar_reservaciones') == 'on'
        }
        datos_telegram['config_notificaciones'] = json.dumps(config_notificaciones)
        
        print(f"💾 Guardando: {datos_telegram}")  # Debug
        
        # Actualizar en la BD
        success = db.actualizar_restaurante(restaurante_id, datos_telegram)
        
        if success:
            print(f"✅ Configuración guardada correctamente")
            return jsonify({'success': True, 'message': 'Configuración de Telegram actualizada'})
        else:
            print(f"❌ Error al guardar en BD")
            return jsonify({'success': False, 'message': 'Error al actualizar en base de datos'}), 500
            
    except Exception as e:
        print(f"❌ Error actualizando Telegram: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500

@app.route('/telegram/test')
@login_required
def test_telegram_bot():
    """Probar conexión con el bot de Telegram"""
    try:
        user = get_current_user()
        restaurante_id = user['restaurante_id']
        
        # Obtener el bot token del restaurante
        from database.database_multirestaurante import get_db_cursor
        with get_db_cursor() as (cursor, conn):
            cursor.execute("SELECT bot_token FROM restaurantes WHERE id = %s", (restaurante_id,))
            result = cursor.fetchone()
        
        if not result or not result['bot_token']:
            return jsonify({'success': False, 'message': 'No hay bot token configurado'})
        
        bot_token = result['bot_token']
        
        # Intentar obtener info del bot
        import requests
        response = requests.get(f'https://api.telegram.org/bot{bot_token}/getMe', timeout=5)
        
        if response.status_code == 200:
            bot_info = response.json()
            if bot_info.get('ok'):
                return jsonify({
                    'success': True, 
                    'message': f'Bot conectado: @{bot_info["result"]["username"]}'
                })
        
        return jsonify({'success': False, 'message': 'Token inválido o bot no accesible'})
        
    except Exception as e:
        print(f"❌ Error probando bot: {e}")
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500


@app.route('/usuarios', methods=['GET', 'POST'])
@login_required
def gestionar_usuarios():
    """Gestionar usuarios del restaurante"""
    user = get_current_user()
    restaurante_id = user['restaurante_id']
    
    if request.method == 'POST':
        try:
            data = request.get_json()
            
            # Crear nuevo usuario
            usuario_id = db.crear_usuario_admin(
                restaurante_id=restaurante_id,
                email=data['email'],
                password=data['password'],
                nombre_completo=data['nombre_completo'],
                rol=data.get('rol', 'staff')
            )
            
            if usuario_id:
                # Agregar teléfono si se proporcionó
                if data.get('telefono'):
                    from database.database_multirestaurante import get_db_cursor
                    with get_db_cursor() as (cursor, conn):
                        cursor.execute("""
                            UPDATE usuarios_admin 
                            SET telefono = %s 
                            WHERE id = %s
                        """, (data['telefono'], usuario_id))
                        conn.commit()
                
                return jsonify({'success': True, 'message': 'Usuario creado', 'id': usuario_id})
            else:
                return jsonify({'success': False, 'message': 'Error al crear usuario'}), 500
                
        except Exception as e:
            print(f"❌ Error creando usuario: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500
    
    # GET - listar usuarios
    from database.database_multirestaurante import get_db_cursor
    with get_db_cursor() as (cursor, conn):
        cursor.execute("""
            SELECT id, email, nombre_completo, rol, telefono, activo, ultimo_acceso, created_at
            FROM usuarios_admin
            WHERE restaurante_id = %s
            ORDER BY created_at DESC
        """, (restaurante_id,))
        usuarios = cursor.fetchall()
    
    return jsonify({'success': True, 'usuarios': usuarios})


@app.route('/usuarios/<int:usuario_id>', methods=['DELETE'])
@login_required
def eliminar_usuario(usuario_id):
    """Eliminar (desactivar) un usuario"""
    try:
        user = get_current_user()
        
        # No permitir que se elimine a sí mismo
        if usuario_id == user['id']:
            return jsonify({'success': False, 'message': 'No puedes eliminarte a ti mismo'}), 400
        
        # Desactivar usuario
        from database.database_multirestaurante import get_db_cursor
        with get_db_cursor() as (cursor, conn):
            cursor.execute("""
                UPDATE usuarios_admin 
                SET activo = FALSE 
                WHERE id = %s AND restaurante_id = %s
            """, (usuario_id, user['restaurante_id']))
            conn.commit()
        
        return jsonify({'success': True, 'message': 'Usuario eliminado'})
        
    except Exception as e:
        print(f"❌ Error eliminando usuario: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


# ==================== FIN DE RUTAS DE CONFIGURACIÓN ====================
# ==================== API ENDPOINTS ====================

@app.route('/api/stats')
@login_required
def api_stats():
    """API: Obtener estadísticas del restaurante"""
    user = get_current_user()
    restaurante_id = user['restaurante_id']
    
    stats = db.get_estadisticas_hoy(restaurante_id)
    
    return jsonify({
        'success': True,
        'stats': stats
    })

@app.route('/api/pedidos/recientes')
@login_required
def api_pedidos_recientes():
    """API: Obtener pedidos recientes para actualización automática"""
    try:
        user = get_current_user()
        restaurante_id = user['restaurante_id']
        
        pedidos = db.get_pedidos_restaurante(restaurante_id, limit=50)
        
        # Convertir datetime a string para JSON
        for pedido in pedidos:
            if pedido.get('fecha_pedido'):
                pedido['fecha_pedido'] = pedido['fecha_pedido'].isoformat()
        
        return jsonify({
            'success': True,
            'pedidos': pedidos
        })
    except Exception as e:
        print(f"❌ Error obteniendo pedidos: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500
    
@app.route('/api/dashboard/datos')
@login_required
def api_dashboard_datos():
    """API: Obtener datos del dashboard para actualización automática"""
    try:
        user = get_current_user()
        restaurante_id = user['restaurante_id']
        
        # Obtener estadísticas
        stats = db.get_estadisticas_hoy(restaurante_id)
        
        # Pedidos recientes
        pedidos = db.get_pedidos_restaurante(restaurante_id, limit=10)
        
        # Convertir datetime a string
        for pedido in pedidos:
            if pedido.get('fecha_pedido'):
                pedido['fecha_pedido'] = pedido['fecha_pedido'].isoformat()
        
        # Reservaciones recientes
        reservaciones = db.get_reservaciones_restaurante(restaurante_id, limit=10)
        
        # Convertir hora_reservacion (timedelta) a string
        from datetime import timedelta
        for reservacion in reservaciones:
            if reservacion.get('hora_reservacion'):
                if isinstance(reservacion['hora_reservacion'], timedelta):
                    td = reservacion['hora_reservacion']
                    total_seconds = int(td.total_seconds())
                    hours = total_seconds // 3600
                    minutes = (total_seconds % 3600) // 60
                    reservacion['hora_reservacion'] = f"{hours:02d}:{minutes:02d}"
        
        return jsonify({
            'success': True,
            'stats': stats,
            'pedidos': pedidos,
            'reservaciones': reservaciones
        })
    except Exception as e:
        print(f"❌ Error obteniendo datos dashboard: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500
# ==================== MANEJADORES DE ERRORES ====================

@app.errorhandler(404)
def not_found(error):
    return render_template('admin/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('admin/500.html'), 500

# ==================== FILTROS DE PLANTILLAS ====================

@app.template_filter('format_currency')
def format_currency(value):
    """Formatear como moneda"""
    try:
        return f"${float(value):,.2f}"
    except:
        return "$0.00"

@app.template_filter('format_datetime')
def format_datetime(value):
    """Formatear fecha y hora"""
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    return value.strftime('%d/%m/%Y %H:%M')

@app.template_filter('format_date')
def format_date(value):
    """Formatear solo fecha"""
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    return value.strftime('%d/%m/%Y')

# Agregar este filtro después de los otros filtros en admin_server.py
# Busca la sección "FILTROS DE PLANTILLAS" y agrega esto:

@app.template_filter('format_time')
def format_time(value):
    """Formatear solo hora - Compatible con time y timedelta"""
    from datetime import timedelta, time
    
    if value is None:
        return "N/A"
    
    # Si es un string, intentar parsearlo
    if isinstance(value, str):
        try:
            from datetime import datetime
            value = datetime.strptime(value, '%H:%M:%S').time()
        except:
            return value
    
    # Si es timedelta (duración), convertir a hora
    if isinstance(value, timedelta):
        total_seconds = int(value.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        return f"{hours:02d}:{minutes:02d}"
    
    # Si es time normal
    if isinstance(value, time):
        return value.strftime('%H:%M')
    
    return str(value)

@app.template_filter('estado_badge')
def estado_badge(estado):
    """Generar badge HTML según estado"""
    badges = {
        'pendiente': 'warning',
        'confirmado': 'info',
        'preparando': 'primary',
        'listo': 'success',
        'en_camino': 'info',
        'entregado': 'success',
        'cancelado': 'danger',
        'confirmada': 'success',
        'en_curso': 'primary',
        'completada': 'success',
        'no_show': 'danger'
    }
    color = badges.get(estado, 'secondary')
    return f'<span class="badge bg-{color}">{estado.replace("_", " ").title()}</span>'

# ==================== FUNCIÓN PRINCIPAL ====================

def main():
    """Iniciar servidor de administración"""
    print("=" * 60)
    print("🍽️  PANEL DE ADMINISTRACIÓN - SISTEMA MULTI-RESTAURANTE")
    print("=" * 60)
    print("🌐 URL: http://localhost:5001")
    print("🔐 Asegúrate de tener un usuario admin creado en la BD")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=5001, debug=True)

if __name__ == '__main__':
    main()