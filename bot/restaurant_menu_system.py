from telebot import types
import random
from datetime import datetime, timedelta
from database.database_multirestaurante import DatabaseManager

class RestaurantMenuSystem:
    def __init__(self, restaurante_id=1):
        """
        Inicializar sistema de menú para un restaurante específico
        Args:
            restaurante_id: ID del restaurante en la base de datos
        """
        self.restaurante_id = restaurante_id  # ← AGREGADO
        self.user_states = {}
        self.user_orders = {}  # Ahora guardará el pedido_id temporal
        self.user_reservations = {}
        self.db = DatabaseManager()
        
        # Cargar menú desde la base de datos
        self.menu = self._load_menu_from_db()
        
        # Frases motivacionales del AI
        self.sales_phrases = {
            "bienvenida": [
                "¡Bienvenido a una experiencia culinaria única! 🌟",
                "¡Qué alegría tenerte aquí! Prepárate para saborear Giants",
                "¡Perfecto! Estás a punto de vivir la auténtica experiencia italiana 🇮🇹"
            ],
            "recomendaciones": [
                "¡Excelente elección! Este platillo es uno de nuestros favoritos 👨‍🍳",
                "¡Tienes buen gusto! Nuestros clientes lo califican con 5 estrellas ⭐",
                "¡Perfecta elección! Este es el plato que más recomiendan nuestros chefs 🔥"
            ],
            "upselling": [
                "¿Te gustaría acompañarlo con algo especial? 🥂",
                "Para completar la experiencia, te recomiendo... ✨",
                "¡Qué tal si lo acompañas con...! Harán la combinación perfecta 👌"
            ],
            "urgencia": [
                "¡Solo quedan pocas porciones de este platillo hoy! ⏰",
                "¡Este es nuestro último Ossobuco del día! 🔥",
                "¡La promoción termina pronto, no te la pierdas! ⚡"
            ]
        }

    def _load_menu_from_db(self):
        """Cargar menú desde la base de datos"""
        menu = {}
        
        try:
            # ← USAR restaurante_id
            categorias = self.db.get_categorias_menu(self.restaurante_id)
            
            for categoria in categorias:
                cat_codigo = categoria['nombre']
                menu[cat_codigo] = {
                    "nombre": categoria['nombre_display'],
                    "items": {}
                }
                
                # ← USAR restaurante_id
                items = self.db.get_items_por_categoria(self.restaurante_id, categoria['id'])
                
                for item in items:
                    # Cargar ingredientes
                    ingredientes = self.db.get_ingredientes_item(item['id'])
                    
                    menu[cat_codigo]["items"][item['codigo']] = {
                        "id": item['id'],
                        "nombre": item['nombre'],
                        "precio": float(item['precio']),
                        "descripcion": item['descripcion'],
                        "tiempo": item['tiempo_preparacion'],
                        "ingredientes": ingredientes,
                        "disponible": bool(item['disponible']),
                        "vegano": bool(item['vegano'])
                    }
            
            print(f"✅ Menú cargado para restaurante {self.restaurante_id}: {len(menu)} categorías")
            return menu
            
        except Exception as e:
            print(f"❌ Error cargando menú: {e}")
            import traceback
            traceback.print_exc()
            return {}

    def get_user_state(self, user_id):
        return self.user_states.get(user_id, "inicio")
    
    def set_user_state(self, user_id, state):
        self.user_states[user_id] = state
    
    def get_random_phrase(self, category):
        return random.choice(self.sales_phrases.get(category, ["¡Excelente!"]))
    
    # MENÚS DE NAVEGACIÓN
    def get_main_menu(self):
        """Menú principal del restaurante"""
        markup = types.InlineKeyboardMarkup(row_width=2)
        
        markup.add(
            types.InlineKeyboardButton("🍽️ Ver Menú", callback_data="ver_menu"),
            types.InlineKeyboardButton("🛒 Hacer Pedido", callback_data="hacer_pedido")
        )
        markup.add(
            types.InlineKeyboardButton("🪑 Reservaciones", callback_data="reservaciones"),
            types.InlineKeyboardButton("💬 Quejas y Sugerencias", callback_data="quejas")
        )
        markup.add(
            types.InlineKeyboardButton("📞 Contacto", callback_data="contacto"),
            types.InlineKeyboardButton("❓ Ayuda", callback_data="ayuda")
        )
        
        return markup
    
    def get_menu_categories(self, action_prefix="menu"):
        """Menú de categorías de comida"""
        markup = types.InlineKeyboardMarkup(row_width=2)
        
        for cat_key, cat_info in self.menu.items():
            btn = types.InlineKeyboardButton(
                cat_info["nombre"], 
                callback_data=f"{action_prefix}_{cat_key}"
            )
            markup.add(btn)
        
        markup.add(types.InlineKeyboardButton("🏠 Menú Principal", callback_data="menu_principal"))
        return markup
    
    def get_category_items(self, categoria, action_prefix="item"):
        """Menú de items de una categoría"""
        if categoria not in self.menu:
            return None
            
        markup = types.InlineKeyboardMarkup(row_width=1)
        
        for item_key, item_info in self.menu[categoria]["items"].items():
            disponible = "✅" if item_info["disponible"] else "❌"
            vegano = "🌱" if item_info.get("vegano", False) else ""
            
            btn_text = f"{disponible} {item_info['nombre']} - ${item_info['precio']} {vegano}"
            
            btn = types.InlineKeyboardButton(
                btn_text, 
                callback_data=f"{action_prefix}_{categoria}_{item_key}"
            )
            markup.add(btn)
        
        markup.add(
            types.InlineKeyboardButton("⬅️ Categorías", callback_data="ver_menu"),
            types.InlineKeyboardButton("🏠 Inicio", callback_data="menu_principal")
        )
        
        return markup
    
    def get_item_detail_menu(self, categoria, item, action_prefix="add_to_order"):
        """Menú de detalles de un item específico"""
        if categoria not in self.menu or item not in self.menu[categoria]["items"]:
            return None
            
        markup = types.InlineKeyboardMarkup(row_width=2)
        item_info = self.menu[categoria]["items"][item]
        
        if item_info["disponible"]:
            markup.add(
                types.InlineKeyboardButton("1️⃣ Cantidad: 1", callback_data=f"{action_prefix}_{categoria}_{item}_1"),
                types.InlineKeyboardButton("2️⃣ Cantidad: 2", callback_data=f"{action_prefix}_{categoria}_{item}_2")
            )
            markup.add(
                types.InlineKeyboardButton("3️⃣ Cantidad: 3", callback_data=f"{action_prefix}_{categoria}_{item}_3"),
                types.InlineKeyboardButton("4️⃣ Cantidad: 4", callback_data=f"{action_prefix}_{categoria}_{item}_4")
            )
        
        markup.add(
            types.InlineKeyboardButton("⬅️ Regresar", callback_data=f"menu_{categoria}"),
            types.InlineKeyboardButton("🏠 Inicio", callback_data="menu_principal")
        )
        
        return markup
    
    def get_order_type_menu(self):
        """Menú para seleccionar tipo de pedido"""
        markup = types.InlineKeyboardMarkup(row_width=1)
        
        markup.add(
            types.InlineKeyboardButton("🏠 Para Llevar", callback_data="order_type_takeaway"),
            types.InlineKeyboardButton("🚗 Delivery a Domicilio", callback_data="order_type_delivery"),
            types.InlineKeyboardButton("🍽️ Consumir en Restaurante", callback_data="order_type_restaurant")
        )
        
        markup.add(types.InlineKeyboardButton("🏠 Menú Principal", callback_data="menu_principal"))
        return markup
    
    def get_reservations_menu(self):
        """Menú principal de reservaciones"""
        markup = types.InlineKeyboardMarkup(row_width=2)
        
        markup.add(
            types.InlineKeyboardButton("📅 Nueva Reservación", callback_data="new_reservation"),
            types.InlineKeyboardButton("🔍 Consultar Reservación", callback_data="check_reservation")
        )
        markup.add(
            types.InlineKeyboardButton("✏️ Modificar Reservación", callback_data="modify_reservation"),
            types.InlineKeyboardButton("❌ Cancelar Reservación", callback_data="cancel_reservation")
        )
        
        markup.add(types.InlineKeyboardButton("🏠 Menú Principal", callback_data="menu_principal"))
        return markup
    
    def get_complaints_menu(self):
        """Menú de quejas y sugerencias"""
        markup = types.InlineKeyboardMarkup(row_width=2)
        
        markup.add(
            types.InlineKeyboardButton("🍽️ Calidad de Comida", callback_data="complaint_food"),
            types.InlineKeyboardButton("👥 Atención al Cliente", callback_data="complaint_service")
        )
        markup.add(
            types.InlineKeyboardButton("⏰ Tiempo de Espera", callback_data="complaint_time"),
            types.InlineKeyboardButton("🧹 Limpieza e Higiene", callback_data="complaint_hygiene")
        )
        markup.add(
            types.InlineKeyboardButton("💰 Precios", callback_data="complaint_price"),
            types.InlineKeyboardButton("🏢 Instalaciones", callback_data="complaint_facilities")
        )
        markup.add(
            types.InlineKeyboardButton("💡 Sugerencia General", callback_data="suggestion_general")
        )
        
        markup.add(types.InlineKeyboardButton("🏠 Menú Principal", callback_data="menu_principal"))
        return markup
    
    # FORMATEO DE MENSAJES
    def format_welcome_message(self):
        """Mensaje de bienvenida principal"""
        bienvenida = self.get_random_phrase("bienvenida")
        
        return f"""{bienvenida}

🍽️ **¡Bienvenido a Restaurante Giants!**

Auténtica cocina italiana con ingredientes frescos y recetas tradicionales de la nonna.

✨ **¿Qué te apetece hoy?**
• Ver nuestro delicioso menú
• Realizar un pedido
• Hacer una reservación
• O simplemente conocer más sobre nosotros

¡Estamos aquí para ofrecerte la mejor experiencia culinaria! 🇮🇹"""

    def format_category_message(self, categoria):
        """Mensaje de una categoría específica"""
        if categoria not in self.menu:
            return "Categoría no encontrada"
            
        cat_info = self.menu[categoria]
        message = f"**{cat_info['nombre']}**\n\n"
        
        descriptions = {
            "entradas": "Para abrir el apetito con sabores auténticos 🥗",
            "principales": "Nuestros platos estrella, preparados con amor 🍝",
            "postres": "El final perfecto para tu comida 🍰",
            "bebidas": "Para acompañar tu experiencia ☕",
            "especialidades": "Lo mejor de nuestra casa, platos únicos ⭐"
        }
        
        if categoria in descriptions:
            message += f"*{descriptions[categoria]}*\n\n"
        
        message += "**Selecciona un platillo:**\n\n"
        
        for item_key, item_info in cat_info["items"].items():
            estado = "✅" if item_info["disponible"] else "❌ AGOTADO"
            vegano = " 🌱" if item_info.get("vegano", False) else ""
            
            message += f"{estado} **{item_info['nombre']}**{vegano}\n"
            message += f"   💰 ${item_info['precio']} • ⏱️ {item_info['tiempo']}\n"
            message += f"   _{item_info['descripcion']}_\n\n"
        
        return message
    
    def format_item_detail_message(self, categoria, item):
        """Mensaje detallado de un item"""
        if categoria not in self.menu or item not in self.menu[categoria]["items"]:
            return "Producto no encontrado"
            
        item_info = self.menu[categoria]["items"][item]
        recomendacion = self.get_random_phrase("recomendaciones")
        
        message = f"**{item_info['nombre']}** ⭐\n\n"
        message += f"💰 **Precio:** ${item_info['precio']}\n"
        message += f"⏱️ **Tiempo de preparación:** {item_info['tiempo']}\n"
        message += f"🍽️ **Descripción:** {item_info['descripcion']}\n\n"
        
        if item_info.get("ingredientes"):
            message += "🧄 **Ingredientes principales:**\n"
            for ingrediente in item_info['ingredientes']:
                message += f"• {ingrediente}\n"
        
        message += f"\n{recomendacion}\n\n"
        
        if item_info["disponible"]:
            message += "¿Cuántas porciones deseas agregar? 👇"
        else:
            message += "❌ **Temporalmente agotado**\nPero tenemos otras deliciosas opciones disponibles 😊"
            
        return message

    # SISTEMA DE PEDIDOS CON BASE DE DATOS
    def iniciar_pedido(self, user_id, tipo_pedido, origen="telegram"):
        """Iniciar un nuevo pedido en la base de datos"""
        try:
            print(f"🔄 Iniciando pedido para user_id: {user_id}, tipo: {tipo_pedido}")
            
            # Obtener o crear cliente CON restaurante_id
            cliente = self.db.get_or_create_cliente(
                restaurante_id=self.restaurante_id,  # ← AGREGAR restaurante_id
                telegram_user_id=user_id if origen == "telegram" else None,
                web_session_id=str(user_id) if origen == "web" else None,
                nombre="Cliente",
                origen=origen
            )
            
            if not cliente:
                print("❌ No se pudo crear/obtener cliente")
                return None
            
            print(f"✅ Cliente obtenido/creado: ID {cliente['id']}")
            
            # Crear pedido CON restaurante_id
            pedido = self.db.crear_pedido_simple(
                self.restaurante_id,  # ← AGREGAR restaurante_id
                cliente['id'], 
                tipo_pedido, 
                origen
            )
            
            if pedido:
                # Guardar el pedido_id temporalmente
                self.user_orders[user_id] = {
                    'pedido_id': pedido['pedido_id'],
                    'numero_pedido': pedido['numero_pedido'],
                    'tipo_pedido': tipo_pedido,
                    'items': []  # Para mostrar en la interfaz
                }
                print(f"✅ Pedido creado exitosamente: {pedido['numero_pedido']}")
                return pedido
            
            print("❌ No se pudo crear el pedido")
            return None
            
        except Exception as e:
            print(f"❌ Error iniciando pedido: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def add_to_order(self, user_id, categoria, item, cantidad):
        """Agregar item al pedido del usuario"""
        if categoria not in self.menu or item not in self.menu[categoria]["items"]:
            return "Error: Producto no encontrado"
        
        item_info = self.menu[categoria]["items"][item]
        
        if not item_info["disponible"]:
            return "❌ Este producto está temporalmente agotado"
        
        cantidad = int(cantidad)
        precio_total = item_info["precio"] * cantidad
        
        # Verificar si hay un pedido activo
        if user_id not in self.user_orders or 'pedido_id' not in self.user_orders[user_id]:
            return "❌ Error: No hay un pedido activo. Inicia un pedido primero."
        
        pedido_id = self.user_orders[user_id]['pedido_id']
        
        # Agregar item a la base de datos usando el ID del item
        success = self.db.agregar_item_pedido(
            pedido_id, 
            item_info['id'],  # ← USAR ID en lugar de código
            cantidad,
            item_info['precio']
        )
        
        if not success:
            return "❌ Error al agregar el producto al pedido"
        
        # Agregar también a la lista temporal para mostrar
        order_item = {
            "categoria": categoria,
            "item": item,
            "nombre": item_info["nombre"],
            "precio_unitario": item_info["precio"],
            "cantidad": cantidad,
            "precio_total": precio_total
        }
        
        self.user_orders[user_id]['items'].append(order_item)
        
        upsell = self.get_random_phrase("upselling")
        
        message = f"✅ **¡Agregado al pedido!**\n\n"
        message += f"📦 **{item_info['nombre']}** x{cantidad}\n"
        message += f"💰 Subtotal: ${precio_total}\n\n"
        message += f"{upsell}\n\n"
        
        # Sugerencias inteligentes
        suggestions = self.get_smart_suggestions(categoria, item)
        if suggestions:
            message += "**Te recomendamos también:**\n"
            message += suggestions + "\n"
        
        message += "¿Qué más te gustaría agregar? 🛒"
        
        return message
    
    def get_smart_suggestions(self, categoria, item):
        """Sugerencias inteligentes basadas en el item agregado"""
        suggestions_map = {
            "carbonara": "🥗 Una Ensalada Caprese para equilibrar",
            "margherita": "🍷 Una copa de Chianti para maridar",
            "tiramisu": "☕ Un Espresso para acompañar",
            "bruschetta": "🍝 Continúa con una Carbonara",
            "espresso": "🍰 ¿Qué tal un Tiramisú para endulzar?"
        }
        
        return suggestions_map.get(item, "")
    
    def get_order_summary(self, user_id):
        """Resumen del pedido del usuario desde la base de datos"""
        if user_id not in self.user_orders or 'pedido_id' not in self.user_orders[user_id]:
            return "No tienes productos en tu pedido", 0
        
        pedido_id = self.user_orders[user_id]['pedido_id']
        
        # Obtener pedido de la base de datos
        pedido = self.db.get_pedido(pedido_id)
        detalles = self.db.get_detalle_pedido(pedido_id)
        
        if not pedido or not detalles:
            return "No tienes productos en tu pedido", 0
        
        message = "🛒 **Resumen de tu Pedido:**\n\n"
        
        for detalle in detalles:
            message += f"• **{detalle['item_nombre']}** x{detalle['cantidad']}\n"
            message += f"  ${detalle['subtotal']}\n\n"
        
        message += f"💰 **Total:** ${pedido['total']}\n"
        message += f"⏱️ **Tiempo estimado:** 25-35 minutos\n\n"
        message += "¿Deseas confirmar tu pedido? 🍽️"
        
        return message, float(pedido['total'])
    
    def limpiar_pedido(self, user_id):
        """Limpiar el pedido temporal del usuario"""
        if user_id in self.user_orders:
            del self.user_orders[user_id]
    
    # SISTEMA DE RESERVACIONES CON BASE DE DATOS
    def crear_reservacion_db(self, user_id, nombre, telefono, fecha, hora, personas, origen="telegram"):
        """Crear reservación en la base de datos"""
        try:
            # Obtener o crear cliente CON restaurante_id
            cliente = self.db.get_or_create_cliente(
                restaurante_id=self.restaurante_id,  # ← AGREGAR restaurante_id
                telegram_user_id=user_id if origen == "telegram" else None,
                web_session_id=str(user_id) if origen == "web" else None,
                nombre=nombre,
                origen=origen
            )
            
            if not cliente:
                return None
            
            # Actualizar teléfono del cliente
            self.db.actualizar_cliente(cliente['id'], telefono=telefono)
            
            # Crear reservación CON restaurante_id
            reservacion = self.db.crear_reservacion(
                self.restaurante_id,  # ← AGREGAR restaurante_id
                cliente['id'], 
                nombre, 
                telefono, 
                fecha, 
                hora, 
                personas, 
                origen
            )
            
            return reservacion
            
        except Exception as e:
            print(f"❌ Error creando reservación: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def buscar_reservacion_db(self, codigo=None, telefono=None):
        """Buscar reservación en la base de datos"""
        return self.db.buscar_reservacion(codigo, telefono)
    
    def cancelar_reservacion_db(self, reservacion_id):
        """Cancelar una reservación"""
        return self.db.actualizar_estado_reservacion(reservacion_id, 'cancelada')
    
    # SISTEMA DE QUEJAS CON BASE DE DATOS
    def crear_queja_db(self, user_id, tipo, descripcion, origen="telegram"):
        """Crear queja en la base de datos"""
        try:
            # Obtener o crear cliente CON restaurante_id
            cliente = self.db.get_or_create_cliente(
                restaurante_id=self.restaurante_id,  # ← AGREGAR restaurante_id
                telegram_user_id=user_id if origen == "telegram" else None,
                web_session_id=str(user_id) if origen == "web" else None,
                nombre="Cliente",
                origen=origen
            )
            
            if not cliente:
                return None
            
            # Crear queja
            codigo = self.db.crear_queja(cliente['id'], tipo, descripcion, origen)
            return codigo
            
        except Exception as e:
            print(f"❌ Error creando queja: {e}")
            import traceback
            traceback.print_exc()
            return None