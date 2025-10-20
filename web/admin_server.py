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

# ==================== RUTAS DE AUTENTICACIÓN ====================

@app.route('/')
def index():
    """Página principal - redirige según autenticación"""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

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
    with get_db_cursor() as (cursor, conn):
        cursor.execute("""
            SELECT * FROM reservaciones 
            WHERE id = %s AND restaurante_id = %s
        """, (reservacion_id, user['restaurante_id']))
        reservacion = cursor.fetchone()
    
    if not reservacion:
        return jsonify({'success': False, 'message': 'Reservación no encontrada'}), 404
    
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

@app.template_filter('format_time')
def format_time(value):
    """Formatear solo hora"""
    if isinstance(value, str):
        try:
            value = datetime.strptime(value, '%H:%M:%S').time()
        except:
            pass
    return value.strftime('%H:%M')

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