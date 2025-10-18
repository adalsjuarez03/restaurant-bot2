"""
Configuración del Bot de Restaurante
"""

# Token del bot de Telegram
BOT_TOKEN = "8377389753:AAHboV1A22knoR9k0I2qo4fn8trH7jfHTbo"  # ← CAMBIA ESTO

# IDs de Telegram importantes
CHAT_IDS = {
    "admin": 6310703683,           # Tu ID personal
    "cocina": -1003157157792,      # ID del grupo (tu grupo)
    "grupo_restaurante": -1003157157792  # Mismo grupo
}

# Configuración del restaurante
RESTAURANT_CONFIG = {
    "nombre": "Restaurante Giants",
    "descripcion": "Auténtica cocina italiana con ingredientes frescos",
    "contacto": {
        "telefono": "+52 961 123 4567",
        "whatsapp": "+52 961 123 4567",
        "email": "contacto@giants.com",
        "direccion": "Av. Central Norte 123, Tuxtla Gutiérrez, Chiapas"
    },
    "horario": {
        "lunes_viernes": "11:00 AM - 10:00 PM",
        "sabado": "12:00 PM - 11:00 PM",
        "domingo": "12:00 PM - 9:00 PM"
    },
    "horarios_reservacion": [
        "13:00", "14:00", "15:00",
        "19:00", "20:00", "21:00"
    ],
    "delivery": {
        "zona_cobertura": "Tuxtla Gutiérrez centro y alrededores",
        "tiempo_estimado": "30-45 minutos",
        "costo_envio": 35,
        "pedido_minimo": 150
    }
}