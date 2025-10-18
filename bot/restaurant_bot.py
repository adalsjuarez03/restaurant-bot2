
"""
Bot de Telegram para Restaurante Giants
Sistema completo de menú, pedidos, reservaciones y atención al cliente
"""

import telebot
import time
import threading
import schedule
from datetime import datetime
from config import BOT_TOKEN, RESTAURANT_CONFIG, CHAT_IDS
from bot.restaurant_message_handlers import RestaurantMessageHandlers

class RestaurantBot:
    def __init__(self):
        """Inicializar el bot del restaurante"""
        try:
            self.bot = telebot.TeleBot(BOT_TOKEN)
            self.message_handlers = RestaurantMessageHandlers(self.bot)
            self.is_running = False
            self.stats = {
                "messages_received": 0,
                "orders_started": 0,
                "reservations_started": 0,
                "complaints_received": 0,
                "start_time": datetime.now()
            }
            print("✅ Bot inicializado correctamente")
        except Exception as e:
            print(f"❌ Error al inicializar el bot: {e}")
            raise
    
    def start_bot(self):
        """Iniciar el bot con manejo de errores mejorado"""
        try:
            # Obtener información del bot
            bot_info = self.bot.get_me()
            self.print_startup_info(bot_info)
            
            # Configurar tareas programadas
            self.setup_scheduled_tasks()
            
            # Iniciar hilo para tareas programadas
            schedule_thread = threading.Thread(target=self.run_scheduled_tasks)
            schedule_thread.daemon = True
            schedule_thread.start()
            
            self.is_running = True
            
            # Notificar inicio a administradores
            self.notify_bot_start(bot_info)
            
            print("🚀 Bot ejecutándose... Presiona Ctrl+C para detener")
            print("-" * 60)
            
            # Iniciar el bot con polling mejorado
            self.bot.infinity_polling(
                timeout=20,
                long_polling_timeout=15,
                none_stop=True,
                interval=2
            )
            
        except KeyboardInterrupt:
            print("\n⏹️ Bot detenido por el usuario")
            self.stop_bot()
        except Exception as e:
            print(f"❌ Error crítico en el bot: {e}")
            self.handle_critical_error(e)
    
    def print_startup_info(self, bot_info):
        """Imprimir información de inicio del bot"""
        print("=" * 60)
        print("🍽️  RESTAURANTE GIANTS - BOT TELEGRAM  🇮🇹")
        print("=" * 60)
        print(f"✅ Bot iniciado correctamente!")
        print(f"🤖 Nombre: {bot_info.first_name}")
        print(f"🆔 Username: @{bot_info.username}")
        print(f"📱 ID: {bot_info.id}")
        print(f"🏪 Restaurante: {RESTAURANT_CONFIG['nombre']}")
        print(f"⏰ Horario: {RESTAURANT_CONFIG['horario']['lunes_viernes']}")
        print(f"📍 Ubicación: {RESTAURANT_CONFIG['contacto']['direccion']}")
        print("-" * 60)
        print("🔧 FUNCIONALIDADES DISPONIBLES:")
        print("   • 🍽️  Sistema de Menú Interactivo")
        print("   • 🛒 Procesamiento de Pedidos")
        print("   • 🪑 Sistema de Reservaciones")
        print("   • 💬 Manejo de Quejas y Sugerencias")
        print("   • 🤖 IA Conversacional para Ventas")
        print("   • 📊 Estadísticas en Tiempo Real")
        print("   • ⏰ Notificaciones Programadas")
        print("-" * 60)
    
    def setup_scheduled_tasks(self):
        """Configurar tareas programadas"""
        # Menú del día
        schedule.every().day.at("08:00").do(self.send_daily_menu)
        
        # Promociones
        schedule.every().monday.at("10:00").do(self.send_weekly_promotion)
        
        # Estadísticas diarias
        schedule.every().day.at("23:00").do(self.send_daily_stats)
        
        # Recordatorio de cierre
        schedule.every().day.at("21:30").do(self.send_closing_reminder)
        
        print("⏰ Tareas programadas configuradas")
    
    def run_scheduled_tasks(self):
        """Ejecutar tareas programadas en hilo separado"""
        while self.is_running:
            try:
                schedule.run_pending()
                time.sleep(60)  # Revisar cada minuto
            except Exception as e:
                print(f"⚠️ Error en tarea programada: {e}")
    
    def notify_bot_start(self, bot_info):
        """Notificar inicio del bot a administradores"""
        try:
            if "admin" in CHAT_IDS:
                # SIN parse_mode para evitar errores
                start_message = f"""🚀 Bot Iniciado

🤖 {bot_info.first_name} (@{bot_info.username})
🕐 Hora: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
🏪 Restaurante: {RESTAURANT_CONFIG['nombre']}

✅ Sistemas activos:
• Menú interactivo
• Procesamiento de pedidos  
• Reservaciones
• Atención al cliente IA

Bot listo para recibir clientes"""

                self.bot.send_message(CHAT_IDS["admin"], start_message)
                print(f"✅ Notificación enviada a admin: {CHAT_IDS['admin']}")
                
        except Exception as e:
            print(f"⚠️ No se pudo notificar inicio: {e}")
    
    def send_daily_menu(self):
        """Enviar menú del día (tarea programada)"""
        try:
            daily_message = f"""🌅 ¡Buenos días!

🍽️ Menú Especial de Hoy - {datetime.now().strftime('%d/%m/%Y')}

⭐ Plato del Día: Ossobuco alla Milanese
💰 Precio especial: $350 (precio regular $380)

🍝 Pasta Fresca del Día: Ravioli de Ricotta y Espinaca
🥗 Ensalada Especial: Ensalada de Arúgula con Peras

¡Ven a disfrutar de la auténtica cocina italiana!

📞 Reserva: {RESTAURANT_CONFIG['contacto']['telefono']}"""

            # Enviar a grupo si está configurado
            if "grupo_restaurante" in CHAT_IDS:
                self.bot.send_message(CHAT_IDS["grupo_restaurante"], daily_message)
        except Exception as e:
            print(f"⚠️ Error enviando menú diario: {e}")
    
    def send_weekly_promotion(self):
        """Enviar promoción semanal"""
        try:
            promo_message = f"""🎉 ¡PROMOCIÓN DE LA SEMANA!

💝 Lunes de Parejas
2x1 en postres italianos para parejas
Válido en consumo en restaurante

🍝 Martes de Pasta
20% de descuento en todos los platos de pasta

🍷 Miércoles de Vinos
Copa de vino gratis con plato principal

¡No te pierdas nuestras promociones especiales!

📱 Reserva ya: {RESTAURANT_CONFIG['contacto']['whatsapp']}"""

            if "grupo_restaurante" in CHAT_IDS:
                self.bot.send_message(CHAT_IDS["grupo_restaurante"], promo_message)
        except Exception as e:
            print(f"⚠️ Error enviando promoción semanal: {e}")
    
    def send_daily_stats(self):
        """Enviar estadísticas diarias a administradores"""
        try:
            if "admin" in CHAT_IDS:
                uptime = datetime.now() - self.stats["start_time"]
                
                stats_message = f"""📊 Estadísticas Diarias
                
📅 Fecha: {datetime.now().strftime('%d/%m/%Y')}
⏱️ Tiempo activo: {str(uptime).split('.')[0]}

📈 Actividad del bot:
• Mensajes recibidos: {self.stats['messages_received']}
• Pedidos iniciados: {self.stats['orders_started']}
• Reservaciones solicitadas: {self.stats['reservations_started']}
• Quejas/sugerencias: {self.stats['complaints_received']}

🤖 Estado: Operacional ✅"""

                self.bot.send_message(CHAT_IDS["admin"], stats_message)
        except Exception as e:
            print(f"⚠️ Error enviando estadísticas: {e}")
    
    def send_closing_reminder(self):
        """Recordatorio de cierre del restaurante"""
        try:
            closing_message = f"""⏰ Recordatorio de Cierre

🍽️ {RESTAURANT_CONFIG['nombre']}

Cerramos en 30 minutos ({RESTAURANT_CONFIG['horario']['lunes_viernes'].split(' - ')[1]})

🏃‍♂️ Último pedido para delivery: ¡Ordena ahora!
🪑 Últimas reservaciones: Disponibles hasta las 21:00

¡Gracias por elegirnos hoy! 🇮🇹"""

            if "grupo_restaurante" in CHAT_IDS:
                self.bot.send_message(CHAT_IDS["grupo_restaurante"], closing_message)
        except Exception as e:
            print(f"⚠️ Error enviando recordatorio de cierre: {e}")
    
    def handle_critical_error(self, error):
        """Manejar errores críticos del bot"""
        try:
            error_message = f"""🚨 ERROR CRÍTICO DEL BOT

⏰ Tiempo: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
❌ Error: {str(error)}
🤖 Bot: Restaurante Giants

Acciones tomadas:
• Bot detenido temporalmente
• Registrando error para análisis
• Se requiere intervención manual

Estado: Requiere atención 🔧"""

            if "admin" in CHAT_IDS:
                self.bot.send_message(CHAT_IDS["admin"], error_message)
        except:
            pass  # Si falla el envío del error, no hacer nada
        
        # Intentar reinicio automático después de 30 segundos
        print("🔄 Intentando reinicio automático en 30 segundos...")
        time.sleep(30)
        self.attempt_restart()
    
    def attempt_restart(self):
        """Intentar reiniciar el bot automáticamente"""
        try:
            print("🔄 Reiniciando bot...")
            self.is_running = False
            time.sleep(5)
            self.start_bot()
        except Exception as e:
            print(f"❌ Error en reinicio automático: {e}")
            self.stop_bot()
    
    def stop_bot(self):
        """Detener el bot de forma segura"""
        if self.is_running:
            print("🔄 Deteniendo el bot...")
            self.is_running = False
            
            try:
                # Notificar parada a administradores
                if "admin" in CHAT_IDS:
                    stop_message = f"""⏹️ Bot Detenido

🕐 Hora: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
🤖 Bot: Restaurante Giants

Estadísticas de sesión:
• Mensajes procesados: {self.stats['messages_received']}
• Tiempo activo: {str(datetime.now() - self.stats['start_time']).split('.')[0]}

Bot desconectado ❌"""
                    
                    self.bot.send_message(CHAT_IDS["admin"], stop_message)
            except:
                pass
            
            self.bot.stop_polling()
            print("✅ Bot detenido correctamente")
        else:
            print("ℹ️ El bot ya estaba detenido")
    
    def update_stats(self, stat_type):
        """Actualizar estadísticas del bot"""
        if stat_type in self.stats:
            self.stats[stat_type] += 1
    
    def get_bot_status(self):
        """Obtener estado actual del bot"""
        uptime = datetime.now() - self.stats["start_time"]
        
        status = {
            "running": self.is_running,
            "uptime": str(uptime).split('.')[0],
            "stats": self.stats.copy(),
            "config": RESTAURANT_CONFIG['nombre']
        }
        
        return status
    
    def send_test_message(self, chat_id, message):
        """Enviar mensaje de prueba"""
        try:
            result = self.bot.send_message(chat_id, message)
            print(f"✅ Mensaje de prueba enviado a {chat_id}: {message}")
            return result
        except Exception as e:
            print(f"❌ Error enviando mensaje de prueba: {e}")
            return None
    
    def get_bot_info(self):
        """Obtener información completa del bot"""
        try:
            me = self.bot.get_me()
            info = {
                "id": me.id,
                "username": me.username,
                "first_name": me.first_name,
                "is_bot": me.is_bot,
                "restaurant": RESTAURANT_CONFIG['nombre'],
                "status": "running" if self.is_running else "stopped"
            }
            
            info_text = f"""🤖 Información del Bot

Bot: {me.first_name} (@{me.username})
ID: {me.id}
Restaurante: {RESTAURANT_CONFIG['nombre']}
Estado: {'✅ Funcionando' if self.is_running else '❌ Detenido'}

¡Listo para atender a nuestros clientes! 🍽️"""
            
            print(info_text)
            return info
        except Exception as e:
            print(f"❌ Error obteniendo información del bot: {e}")
            return None

def main():
    """Función principal"""
    print("🍽️ Iniciando Bot de Restaurante Giants...")
    print("=" * 60)
    
    try:
        # Crear instancia del bot
        restaurant_bot = RestaurantBot()
        
        # Obtener información inicial
        restaurant_bot.get_bot_info()
        
        # Iniciar el bot
        restaurant_bot.start_bot()
        
    except Exception as e:
        print(f"❌ Error fatal al iniciar el bot: {e}")
        print("🔧 Verificar:")
        print("   • Token de bot válido")
        print("   • Conexión a internet")
        print("   • Permisos del bot")

if __name__ == "__main__":
    main()