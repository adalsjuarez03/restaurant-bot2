# ARCHIVO: restaurant_message_handlers.py
# Agregar estos imports al inicio del archivo (después de los imports existentes)
from database.database_multirestaurante import DatabaseManager
from telebot import types
from datetime import datetime
from bot.restaurant_menu_system import RestaurantMenuSystem


class RestaurantMessageHandlers:
    def __init__(self, bot):
        self.bot = bot
        self.menu_system = RestaurantMenuSystem()
        self.waiting_for_input = {}
        self.db = DatabaseManager()  # Base de datos
        self.setup_handlers()

    def setup_handlers(self):
        """Configurar todos los manejadores de mensajes y callbacks del bot"""
        
        # ==================== COMANDOS ====================
        
        @self.bot.message_handler(commands=['start', 'inicio'])
        def send_welcome(message):
            """Comando /start - Mensaje de bienvenida"""
            user_id = message.from_user.id
            user_name = message.from_user.first_name
            
            self.menu_system.set_user_state(user_id, "inicio")
            
            welcome_text = self.menu_system.format_welcome_message()
            markup = self.menu_system.get_main_menu()
            
            self.bot.send_message(
                message.chat.id,
                welcome_text,
                reply_markup=markup,
                parse_mode='Markdown'
            )
        
        @self.bot.message_handler(commands=['menu', 'carta'])
        def show_menu(message):
            """Comando /menu - Mostrar menú"""
            markup = self.menu_system.get_menu_categories()
            self.bot.send_message(
                message.chat.id,
                "🍽️ **MENÚ RESTAURANTE GIANTS**\n\nSelecciona una categoría:",
                reply_markup=markup,
                parse_mode='Markdown'
            )
        
        @self.bot.message_handler(commands=['ayuda', 'help'])
        def show_help(message):
            """Comando /ayuda"""
            help_text = """ℹ️ **AYUDA - COMANDOS DISPONIBLES**

📋 **Comandos:**
/start - Menú principal
/menu - Ver menú completo
/pedido - Hacer un pedido
/reservacion - Hacer reservación
/contacto - Información de contacto
/ayuda - Ver esta ayuda

💬 **Navegación:**
• Usa los botones interactivos
• Escribe directamente lo que necesites
• El bot entiende lenguaje natural

❓ **¿Necesitas ayuda?**
Contacta: +52 961 123 4567"""

            self.bot.send_message(
                message.chat.id,
                help_text,
                parse_mode='Markdown'
            )
        
        @self.bot.message_handler(commands=['pedido'])
        def start_order(message):
            """Comando /pedido - Iniciar pedido"""
            user_id = message.from_user.id
            self.menu_system.set_user_state(user_id, "selecting_order_type")
            
            markup = self.menu_system.get_order_type_menu()
            self.bot.send_message(
                message.chat.id,
                "🛍️ **HACER PEDIDO**\n\n¿Cómo deseas recibir tu pedido?",
                reply_markup=markup,
                parse_mode='Markdown'
            )
        
        @self.bot.message_handler(commands=['reservacion', 'reservar'])
        def start_reservation(message):
            """Comando /reservacion"""
            markup = self.menu_system.get_reservations_menu()
            self.bot.send_message(
                message.chat.id,
                "🪑 **RESERVACIONES**\n\n¿Qué deseas hacer?",
                reply_markup=markup,
                parse_mode='Markdown'
            )
        
        @self.bot.message_handler(commands=['contacto'])
        def show_contact(message):
            """Comando /contacto"""
            from config import RESTAURANT_CONFIG
            
            contact_text = f"""📞 **CONTACTO**

🏨 {RESTAURANT_CONFIG['nombre']}

📍 Dirección:
{RESTAURANT_CONFIG['contacto']['direccion']}

📱 Teléfono: {RESTAURANT_CONFIG['contacto']['telefono']}
💬 WhatsApp: {RESTAURANT_CONFIG['contacto']['whatsapp']}
📧 Email: {RESTAURANT_CONFIG['contacto']['email']}

🕐 Horario:
Lun-Vie: {RESTAURANT_CONFIG['horario']['lunes_viernes']}
Sábado: {RESTAURANT_CONFIG['horario']['sabado']}
Domingo: {RESTAURANT_CONFIG['horario']['domingo']}"""

            markup = self.menu_system.get_main_menu()
            self.bot.send_message(
                message.chat.id,
                contact_text,
                reply_markup=markup,
                parse_mode='Markdown'
            )
        
        # ==================== CALLBACKS ====================
        
        @self.bot.callback_query_handler(func=lambda call: True)
        def callback_handler(call):
            """Manejador principal de callbacks"""
            try:
                user_id = call.from_user.id
                data = call.data
                
                # Menú principal
                if data == "menu_principal":
                    self.process_main_menu(call)
                
                # Ver menú
                elif data == "ver_menu":
                    self.process_view_menu(call)
                
                # Categorías del menú
                elif data.startswith("menu_"):
                    categoria = data.replace("menu_", "")
                    self.process_category_view(call, categoria)
                
                # Items del menú
                elif data.startswith("item_"):
                    parts = data.split("_")
                    categoria = parts[1]
                    item = parts[2]
                    self.process_item_detail(call, categoria, item)
                
                # Hacer pedido
                elif data == "hacer_pedido":
                    self.process_start_order(call)
                
                # Tipo de pedido
                elif data.startswith("order_type_"):
                    order_type = data.replace("order_type_", "")
                    self.process_order_type_selection(call, order_type)
                
                # Agregar al pedido
                elif data.startswith("add_to_order_"):
                    parts = data.split("_")
                    categoria = parts[3]
                    item = parts[4]
                    cantidad = parts[5]
                    self.process_add_to_order(call, categoria, item, cantidad)
                
                # Categorías para ordenar
                elif data.startswith("order_"):
                    categoria = data.replace("order_", "")
                    self.process_order_category(call, categoria)
                
                # Ver resumen del pedido
                elif data == "ver_pedido":
                    self.process_view_order(call)
                
                # Finalizar pedido
                elif data == "finalizar_pedido":
                    self.finish_order_process(call)
                
                # Reservaciones
                elif data == "reservaciones":
                    self.process_reservations_menu(call)
                
                elif data == "new_reservation":
                    self.process_new_reservation(call)
                
                elif data == "check_reservation":
                    self.process_check_reservation(call)
                
                # Quejas y sugerencias
                elif data == "quejas":
                    self.process_complaints_menu(call)
                
                elif data.startswith("complaint_") or data.startswith("suggestion_"):
                    self.process_complaint_type(call, data)
                
                # Contacto
                elif data == "contacto":
                    self.process_contact(call)
                
                # Ayuda
                elif data == "ayuda":
                    self.process_help(call)
                
                # Responder al callback
                self.bot.answer_callback_query(call.id)
                
            except Exception as e:
                print(f"❌ Error en callback: {e}")
                import traceback
                traceback.print_exc()
                self.bot.answer_callback_query(call.id, "Error procesando acción")
        
        # ==================== MENSAJES DE TEXTO ====================
        
        @self.bot.message_handler(func=lambda message: True)
        def handle_text_messages(message):
            """Manejador de mensajes de texto"""
            user_id = message.from_user.id
            text = message.text.lower().strip()
            
            # Verificar si estamos esperando input
            if user_id in self.waiting_for_input:
                input_type = self.waiting_for_input[user_id]["type"]
                
                if input_type == "reservation_name":
                    self.process_reservation_name(message)
                elif input_type == "reservation_phone":
                    self.process_reservation_phone(message)
                elif input_type == "reservation_date":
                    self.process_reservation_date(message)
                elif input_type == "reservation_time":
                    self.process_reservation_time(message)
                elif input_type == "reservation_people":
                    self.process_reservation_people(message)
                elif input_type == "complaint_description":
                    self.process_complaint_description(message)
                
                return
            
            # Respuestas a palabras clave
            if any(word in text for word in ['hola', 'buenas', 'hi', 'buenos días']):
                markup = self.menu_system.get_main_menu()
                self.bot.reply_to(
                    message,
                    f"¡Hola {message.from_user.first_name}! ¿En qué puedo ayudarte hoy?",
                    reply_markup=markup
                )
            
            elif any(word in text for word in ['menu', 'menú', 'carta']):
                markup = self.menu_system.get_menu_categories()
                self.bot.reply_to(
                    message,
                    "🍽️ Aquí está nuestro menú:",
                    reply_markup=markup
                )
            
            elif any(word in text for word in ['pedido', 'ordenar', 'pedir']):
                markup = self.menu_system.get_order_type_menu()
                self.bot.reply_to(
                    message,
                    "🛍️ ¿Cómo deseas recibir tu pedido?",
                    reply_markup=markup
                )
            
            else:
                markup = self.menu_system.get_main_menu()
                self.bot.reply_to(
                    message,
                    "🤔 No entendí tu mensaje. ¿En qué puedo ayudarte?",
                    reply_markup=markup
                )

        print("✅ Manejadores configurados correctamente")

    # ==================== MÉTODOS DE PROCESAMIENTO ====================
    
    def process_order_type_selection(self, call, order_type):
        """Procesar selección de tipo de pedido"""
        user_id = call.from_user.id
        
        # Iniciar pedido en la base de datos
        pedido = self.menu_system.iniciar_pedido(user_id, order_type, origen="telegram")
        
        if not pedido:
            self.bot.answer_callback_query(call.id, "❌ Error al crear el pedido")
            return
        
        # Guardar tipo de pedido
        self.menu_system.set_user_state(user_id, f"ordering_{order_type}")
        
        order_messages = {
            "takeaway": "🏠 Para Llevar - ¡Perfetto!\n\nTu pedido estará listo en 20-25 minutos.",
            "delivery": f"🚗 Delivery - ¡Excelente!\n\nEnvío: $35 | Pedido mínimo: $150",
            "restaurant": "🍽️ En Restaurante - ¡Buena elección!\n\nTe prepararemos una mesa especial."
        }
        
        message = order_messages.get(order_type, "¡Excelente elección!")
        message += f"\n\n📋 Pedido #{pedido['numero_pedido']}"
        message += "\n\n🍽️ Ahora selecciona tus platillos favoritos:"
        
        markup = self.menu_system.get_menu_categories("order")
        
        self.bot.edit_message_text(
            message,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup
        )

    def finish_order_process(self, call):
        """Finalizar proceso de pedido"""
        user_id = call.from_user.id
        
        if user_id not in self.menu_system.user_orders or 'pedido_id' not in self.menu_system.user_orders[user_id]:
            self.bot.answer_callback_query(call.id, "❌ No tienes productos en tu pedido")
            return
        
        pedido_id = self.menu_system.user_orders[user_id]['pedido_id']
        numero_pedido = self.menu_system.user_orders[user_id]['numero_pedido']
        
        # Actualizar estado del pedido en la base de datos
        self.db.actualizar_estado_pedido(pedido_id, 'confirmado')
        
        order_text, total = self.menu_system.get_order_summary(user_id)
        
        confirmation_text = f"""✅ ¡Pedido Confirmado!

{order_text}

🎉 ¡Gracias por tu pedido!

📋 Número de pedido: #{numero_pedido}

Próximos pasos:
1️⃣ Te contactaremos para confirmar detalles
2️⃣ Coordinaremos el método de pago  
3️⃣ Prepararemos tu deliciosa comida
4️⃣ ¡Te notificaremos cuando esté listo!

📞 Contacto: +52 961 123 4567

¡Que disfrutes tu experiencia italiana!"""
        
        # Limpiar pedido temporal del usuario
        self.menu_system.limpiar_pedido(user_id)
        
        markup = self.menu_system.get_main_menu()
        
        self.bot.edit_message_text(
            confirmation_text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup
        )
        
        # Notificar a la cocina/administrador
        self.notify_new_order_db(pedido_id, call.from_user)

    def notify_new_order_db(self, pedido_id, user_info):
        """Notificar nuevo pedido usando datos de la base de datos"""
        try:
            from config import CHAT_IDS
            
            # Obtener datos del pedido
            pedido = self.db.get_pedido(pedido_id)
            detalles = self.db.get_detalle_pedido(pedido_id)
            
            if not pedido:
                return
            
            # Construir lista de items
            items_text = ""
            for detalle in detalles:
                items_text += f"• {detalle['item_nombre']} x{detalle['cantidad']} - ${detalle['subtotal']}\n"
            
            admin_message = f"""🆕 NUEVO PEDIDO TELEGRAM

📋 Pedido: #{pedido['numero_pedido']}
👤 Cliente: {user_info.first_name} {user_info.last_name or ''}
📱 Username: @{user_info.username or 'N/A'}

🍽️ PEDIDO:
{items_text}

💰 Total: ${pedido['total']}
📦 Tipo: {pedido['tipo_pedido']}
⏰ Hora: {pedido['fecha_pedido'].strftime('%d/%m/%Y %H:%M')}
🎯 Estado: {pedido['estado']}
📱 Origen: Bot de Telegram"""

            if "cocina" in CHAT_IDS:
                self.bot.send_message(CHAT_IDS["cocina"], admin_message)
            elif "admin" in CHAT_IDS:
                self.bot.send_message(CHAT_IDS["admin"], admin_message)
                    
        except Exception as e:
            print(f"⚠️ Error notificando pedido: {e}")
            import traceback
            traceback.print_exc()

    def process_reservation_people(self, message):
        """Procesar número de personas"""
        user_id = message.from_user.id
        
        try:
            people_count = int(message.text.strip())
        except ValueError:
            self.bot.reply_to(message, "Por favor, ingresa un número válido de personas")
            self.waiting_for_input[user_id] = {"type": "reservation_people", "step": "people"}
            return
        
        if people_count < 1 or people_count > 8:
            self.bot.reply_to(message, "El número de personas debe ser entre 1 y 8")
            self.waiting_for_input[user_id] = {"type": "reservation_people", "step": "people"}
            return
        
        # Guardar número de personas
        self.menu_system.user_reservations[user_id]["people"] = people_count
        
        # Crear reservación en la base de datos
        reservacion_data = self.menu_system.user_reservations[user_id]
        
        reservacion = self.menu_system.crear_reservacion_db(
            user_id=user_id,
            nombre=reservacion_data['name'],
            telefono=reservacion_data['phone'],
            fecha=reservacion_data['date'].date(),
            hora=reservacion_data['time'],
            personas=people_count,
            origen="telegram"
        )
        
        if not reservacion:
            self.bot.reply_to(message, "❌ Error al crear la reservación. Por favor intenta de nuevo.")
            return
        
        confirmation_text = f"""✅ ¡Reservación Confirmada!

🎫 Código: {reservacion['codigo_reservacion']}
👤 Nombre: {reservacion['nombre_cliente']}
📱 Teléfono: {reservacion['telefono']}
📅 Fecha: {reservacion['fecha_reservacion'].strftime('%d/%m/%Y')}
🕐 Hora: {reservacion['hora_reservacion'].strftime('%H:%M')}
👥 Personas: {people_count}

Información importante:
• Llega 10 minutos antes de tu reservación
• Presenta este código al llegar
• Tolerancia máxima: 15 minutos
• Para cambios, contacta: +52 961 123 4567

¡Te esperamos en Giants! 🇮🇹"""
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("🏠 Menú Principal", callback_data="menu_principal"),
            types.InlineKeyboardButton("🍽️ Ver Menú", callback_data="ver_menu")
        )
        
        self.bot.reply_to(message, confirmation_text, reply_markup=markup)
        
        # Notificar al restaurante
        self.notify_new_reservation_db(reservacion)
        
        # Limpiar estado de espera
        if user_id in self.waiting_for_input:
            del self.waiting_for_input[user_id]
        if user_id in self.menu_system.user_reservations:
            del self.menu_system.user_reservations[user_id]

    def notify_new_reservation_db(self, reservacion):
        """Notificar nueva reservación usando datos de la base de datos"""
        try:
            from config import CHAT_IDS
            
            admin_message = f"""🪑 NUEVA RESERVACIÓN

🎫 Código: {reservacion['codigo_reservacion']}
👤 Cliente: {reservacion['nombre_cliente']}
📱 Teléfono: {reservacion['telefono']}
📅 Fecha: {reservacion['fecha_reservacion'].strftime('%d/%m/%Y')}
🕐 Hora: {reservacion['hora_reservacion'].strftime('%H:%M')}
👥 Personas: {reservacion['numero_personas']}

⏰ Creada: {reservacion['created_at'].strftime('%d/%m/%Y %H:%M')}
✅ Estado: {reservacion['estado']}"""

            if "cocina" in CHAT_IDS:
                self.bot.send_message(CHAT_IDS["cocina"], admin_message)
            elif "admin" in CHAT_IDS:
                self.bot.send_message(CHAT_IDS["admin"], admin_message)
                    
        except Exception as e:
            print(f"⚠️ Error notificando reservación: {e}")

    def process_complaint_description(self, message):
        """Procesar descripción de la queja"""
        user_id = message.from_user.id
        complaint_text = message.text.strip()
        
        if len(complaint_text) < 10:
            self.bot.reply_to(message, "Por favor, proporciona más detalles (mínimo 10 caracteres)")
            return
        
        complaint_type = self.waiting_for_input[user_id]["complaint_type"]
        
        # Crear queja en la base de datos
        complaint_id = self.menu_system.crear_queja_db(
            user_id=user_id,
            tipo=complaint_type,
            descripcion=complaint_text,
            origen="telegram"
        )
        
        if not complaint_id:
            self.bot.reply_to(message, "❌ Error al registrar tu comentario. Por favor intenta de nuevo.")
            return
        
        response_text = f"""✅ ¡Comentario Recibido!

🎫 ID: {complaint_id}
🔖 Tipo: {complaint_type}

¡Gracias por tu retroalimentación!

Tu opinión nos ayuda a mejorar cada día. Nuestro equipo revisará tu comentario y si es necesario, nos pondremos en contacto contigo.

🎁 Como disculpa, tienes 15% de descuento en tu próxima visita.
Solo menciona el código: FELIZ15

📞 Contacto directo: +52 961 123 4567"""
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("🏠 Menú Principal", callback_data="menu_principal"),
            types.InlineKeyboardButton("🛒 Hacer Pedido", callback_data="hacer_pedido")
        )
        
        self.bot.reply_to(message, response_text, reply_markup=markup)
        
        # Notificar al administrador
        self.notify_new_complaint_db(complaint_id, complaint_type, complaint_text, message.from_user)
        
        # Limpiar estado
        if user_id in self.waiting_for_input:
            del self.waiting_for_input[user_id]

    def notify_new_complaint_db(self, complaint_id, complaint_type, complaint_text, user_info):
        """Notificar nueva queja"""
        try:
            from config import CHAT_IDS
            
            admin_message = f"""💬 NUEVA QUEJA/SUGERENCIA

🎫 ID: {complaint_id}
👤 Cliente: {user_info.first_name} {user_info.last_name or ''}
📱 Username: @{user_info.username or 'N/A'}

🔖 Tipo: {complaint_type}

Descripción:
{complaint_text}

⏰ Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}
⚠️ Requiere atención"""

            if "cocina" in CHAT_IDS:
                self.bot.send_message(CHAT_IDS["cocina"], admin_message)
            elif "admin" in CHAT_IDS:
                self.bot.send_message(CHAT_IDS["admin"], admin_message)
                    
        except Exception as e:
            print(f"⚠️ Error notificando queja: {e}")

    def process_main_menu(self, call):
        """Mostrar menú principal"""
        user_id = call.from_user.id
        self.menu_system.set_user_state(user_id, "inicio")
        
        welcome_text = self.menu_system.format_welcome_message()
        markup = self.menu_system.get_main_menu()
        
        self.bot.edit_message_text(
            welcome_text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode='Markdown'
        )

    def process_view_menu(self, call):
        """Mostrar categorías del menú"""
        markup = self.menu_system.get_menu_categories()
        self.bot.edit_message_text(
            "🍽️ **MENÚ RESTAURANTE GIANTS**\n\nSelecciona una categoría:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode='Markdown'
        )

    def process_category_view(self, call, categoria):
        """Mostrar items de una categoría"""
        items_text = self.menu_system.format_category_items(categoria)
        markup = self.menu_system.get_category_items_menu(categoria)
        
        self.bot.edit_message_text(
            items_text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode='Markdown'
        )

    def process_item_detail(self, call, categoria, item):
        """Mostrar detalle de un item"""
        item_data = self.menu_system.get_item_data(categoria, item)
        
        if not item_data:
            self.bot.answer_callback_query(call.id, "❌ Item no encontrado")
            return
        
        detail_text = f"""🍽️ **{item_data['nombre']}**

📝 {item_data['descripcion']}

💰 Precio: ${item_data['precio']}"""

        if item_data.get('ingredientes'):
            detail_text += f"\n\n🥗 Ingredientes:\n{item_data['ingredientes']}"

        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton(
                f"🔙 Volver a {categoria.title()}", 
                callback_data=f"menu_{categoria}"
            ),
            types.InlineKeyboardButton("🏠 Menú Principal", callback_data="menu_principal")
        )
        
        self.bot.edit_message_text(
            detail_text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode='Markdown'
        )

    def process_start_order(self, call):
        """Iniciar proceso de pedido"""
        user_id = call.from_user.id
        self.menu_system.set_user_state(user_id, "selecting_order_type")
        
        markup = self.menu_system.get_order_type_menu()
        self.bot.edit_message_text(
            "🛍️ **HACER PEDIDO**\n\n¿Cómo deseas recibir tu pedido?",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode='Markdown'
        )

    def process_order_category(self, call, categoria):
        """Mostrar items de una categoría para ordenar"""
        user_id = call.from_user.id
        
        items_text = self.menu_system.format_category_items(categoria, for_order=True)
        markup = self.menu_system.get_order_items_menu(categoria)
        
        # Agregar botón para ver pedido actual si hay items
        if user_id in self.menu_system.user_orders and self.menu_system.user_orders[user_id].get('items'):
            order_text, total = self.menu_system.get_order_summary(user_id)
            items_text += f"\n\n📋 **Tu pedido actual:**\n{order_text}"
        
        self.bot.edit_message_text(
            items_text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode='Markdown'
        )

    def process_add_to_order(self, call, categoria, item, cantidad):
        """Agregar item al pedido"""
        user_id = call.from_user.id
        cantidad = int(cantidad)
        
        # Verificar que el usuario tenga un pedido iniciado
        if user_id not in self.menu_system.user_orders or 'pedido_id' not in self.menu_system.user_orders[user_id]:
            self.bot.answer_callback_query(call.id, "❌ Primero selecciona el tipo de pedido")
            return
        
        # Agregar item al pedido
        success = self.menu_system.add_item_to_order(user_id, categoria, item, cantidad)
        
        if success:
            item_data = self.menu_system.get_item_data(categoria, item)
            self.bot.answer_callback_query(
                call.id, 
                f"✅ {cantidad}x {item_data['nombre']} agregado"
            )
            
            # Actualizar vista
            self.process_order_category(call, categoria)
        else:
            self.bot.answer_callback_query(call.id, "❌ Error al agregar item")

    def process_view_order(self, call):
        """Ver resumen del pedido actual"""
        user_id = call.from_user.id
        
        if user_id not in self.menu_system.user_orders or not self.menu_system.user_orders[user_id].get('items'):
            self.bot.answer_callback_query(call.id, "❌ No tienes items en tu pedido")
            return
        
        order_text, total = self.menu_system.get_order_summary(user_id)
        numero_pedido = self.menu_system.user_orders[user_id].get('numero_pedido', 'N/A')
        
        summary_text = f"""📋 **RESUMEN DE TU PEDIDO**

Pedido #{numero_pedido}

{order_text}

¿Deseas finalizar tu pedido?"""
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("✅ Finalizar Pedido", callback_data="finalizar_pedido"),
            types.InlineKeyboardButton("➕ Agregar más items", callback_data="hacer_pedido"),
            types.InlineKeyboardButton("🗑️ Cancelar Pedido", callback_data="cancelar_pedido"),
            types.InlineKeyboardButton("🏠 Menú Principal", callback_data="menu_principal")
        )
        
        self.bot.edit_message_text(
            summary_text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode='Markdown'
        )

    def process_reservations_menu(self, call):
        """Mostrar menú de reservaciones"""
        markup = self.menu_system.get_reservations_menu()
        self.bot.edit_message_text(
            "🪑 **RESERVACIONES**\n\n¿Qué deseas hacer?",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode='Markdown'
        )

    def process_new_reservation(self, call):
        """Iniciar proceso de nueva reservación"""
        user_id = call.from_user.id
        
        # Inicializar reservación
        self.menu_system.user_reservations[user_id] = {}
        
        # Pedir nombre
        self.waiting_for_input[user_id] = {"type": "reservation_name", "step": "name"}
        
        self.bot.edit_message_text(
            "🪑 **NUEVA RESERVACIÓN**\n\n👤 Por favor, ingresa tu nombre completo:",
            call.message.chat.id,
            call.message.message_id
        )

    def process_reservation_name(self, message):
        """Procesar nombre de la reservación"""
        user_id = message.from_user.id
        name = message.text.strip()
        
        if len(name) < 3:
            self.bot.reply_to(message, "❌ Por favor ingresa un nombre válido (mínimo 3 caracteres)")
            return
        
        self.menu_system.user_reservations[user_id]["name"] = name
        self.waiting_for_input[user_id] = {"type": "reservation_phone", "step": "phone"}
        
        self.bot.reply_to(message, "📱 Ahora ingresa tu número de teléfono (10 dígitos):")

    def process_reservation_phone(self, message):
        """Procesar teléfono de la reservación"""
        user_id = message.from_user.id
        phone = message.text.strip()
        
        # Validar teléfono (10 dígitos)
        if not phone.isdigit() or len(phone) != 10:
            self.bot.reply_to(message, "❌ Por favor ingresa un número válido de 10 dígitos")
            return
        
        self.menu_system.user_reservations[user_id]["phone"] = phone
        self.waiting_for_input[user_id] = {"type": "reservation_date", "step": "date"}
        
        self.bot.reply_to(
            message, 
            "📅 Ingresa la fecha de tu reservación (formato: DD/MM/YYYY)\nEjemplo: 25/12/2024"
        )

    def process_reservation_date(self, message):
        """Procesar fecha de la reservación"""
        user_id = message.from_user.id
        date_str = message.text.strip()
        
        try:
            from datetime import datetime
            date = datetime.strptime(date_str, "%d/%m/%Y")
            
            # Validar que sea fecha futura
            if date.date() < datetime.now().date():
                self.bot.reply_to(message, "❌ La fecha debe ser futura")
                return
            
            self.menu_system.user_reservations[user_id]["date"] = date
            self.waiting_for_input[user_id] = {"type": "reservation_time", "step": "time"}
            
            self.bot.reply_to(
                message,
                "🕐 Ingresa la hora de tu reservación (formato 24h: HH:MM)\nEjemplo: 19:30"
            )
            
        except ValueError:
            self.bot.reply_to(message, "❌ Formato de fecha incorrecto. Usa: DD/MM/YYYY")

    def process_reservation_time(self, message):
        """Procesar hora de la reservación"""
        user_id = message.from_user.id
        time_str = message.text.strip()
        
        try:
            from datetime import datetime
            time_obj = datetime.strptime(time_str, "%H:%M").time()
            
            # Validar horario de restaurante (ejemplo: 12:00 - 23:00)
            if time_obj.hour < 12 or time_obj.hour > 23:
                self.bot.reply_to(
                    message, 
                    "❌ Horario no disponible. Horario: 12:00 - 23:00"
                )
                return
            
            self.menu_system.user_reservations[user_id]["time"] = time_obj
            self.waiting_for_input[user_id] = {"type": "reservation_people", "step": "people"}
            
            self.bot.reply_to(message, "👥 ¿Para cuántas personas? (1-8)")
            
        except ValueError:
            self.bot.reply_to(message, "❌ Formato de hora incorrecto. Usa: HH:MM (ejemplo: 19:30)")

    def process_check_reservation(self, call):
        """Consultar estado de reservación"""
        self.bot.edit_message_text(
            "🔍 **CONSULTAR RESERVACIÓN**\n\nPor favor, envía tu código de reservación:",
            call.message.chat.id,
            call.message.message_id
        )
        
        user_id = call.from_user.id
        self.waiting_for_input[user_id] = {"type": "check_reservation"}

    def process_complaints_menu(self, call):
        """Mostrar menú de quejas y sugerencias"""
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("😞 Tengo una queja", callback_data="complaint_queja"),
            types.InlineKeyboardButton("💡 Tengo una sugerencia", callback_data="suggestion_sugerencia"),
            types.InlineKeyboardButton("📝 Comentario general", callback_data="complaint_comentario"),
            types.InlineKeyboardButton("🔙 Menú Principal", callback_data="menu_principal")
        )
        
        self.bot.edit_message_text(
            "💬 **QUEJAS Y SUGERENCIAS**\n\nTu opinión es muy importante para nosotros.\n¿Qué deseas compartir?",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode='Markdown'
        )

    def process_complaint_type(self, call, complaint_type):
        """Procesar tipo de queja/sugerencia"""
        user_id = call.from_user.id
        
        # Extraer el tipo
        if complaint_type.startswith("complaint_"):
            tipo = complaint_type.replace("complaint_", "")
        else:
            tipo = complaint_type.replace("suggestion_", "")
        
        self.waiting_for_input[user_id] = {
            "type": "complaint_description",
            "complaint_type": tipo
        }
        
        messages = {
            "queja": "😞 Lamentamos que hayas tenido una mala experiencia.\n\nPor favor, descríbenos qué sucedió:",
            "sugerencia": "💡 ¡Nos encanta recibir sugerencias!\n\nCuéntanos tu idea:",
            "comentario": "📝 Gracias por compartir tu opinión.\n\nEscribe tu comentario:"
        }
        
        self.bot.edit_message_text(
            messages.get(tipo, "Por favor, describe tu comentario:"),
            call.message.chat.id,
            call.message.message_id
        )

    def process_contact(self, call):
        """Mostrar información de contacto"""
        from config import RESTAURANT_CONFIG
        
        contact_text = f"""📞 **CONTACTO**

🏨 {RESTAURANT_CONFIG['nombre']}

📍 Dirección:
{RESTAURANT_CONFIG['contacto']['direccion']}

📱 Teléfono: {RESTAURANT_CONFIG['contacto']['telefono']}
💬 WhatsApp: {RESTAURANT_CONFIG['contacto']['whatsapp']}
📧 Email: {RESTAURANT_CONFIG['contacto']['email']}

🕐 Horario:
Lun-Vie: {RESTAURANT_CONFIG['horario']['lunes_viernes']}
Sábado: {RESTAURANT_CONFIG['horario']['sabado']}
Domingo: {RESTAURANT_CONFIG['horario']['domingo']}"""

        markup = self.menu_system.get_main_menu()
        
        self.bot.edit_message_text(
            contact_text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode='Markdown'
        )

    def process_help(self, call):
        """Mostrar ayuda"""
        help_text = """ℹ️ **AYUDA - COMANDOS DISPONIBLES**

📋 **Comandos:**
/start - Menú principal
/menu - Ver menú completo
/pedido - Hacer un pedido
/reservacion - Hacer reservación
/contacto - Información de contacto
/ayuda - Ver esta ayuda

💬 **Navegación:**
• Usa los botones interactivos
• Escribe directamente lo que necesites
• El bot entiende lenguaje natural

❓ **¿Necesitas ayuda?**
Contacta: +52 961 123 4567"""

        markup = self.menu_system.get_main_menu()
        
        self.bot.edit_message_text(
            help_text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode='Markdown'
        )