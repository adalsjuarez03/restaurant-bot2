import bcrypt
import sys
sys.path.insert(0, '.')

from database.database_multirestaurante import DatabaseManager

db = DatabaseManager()

# Verificar el login
usuario = db.verificar_login_admin('admin@giants.com', 'admin123')

if usuario:
    print("✅ Login EXITOSO!")
    print(f"Usuario: {usuario['nombre_completo']}")
    print(f"Restaurante: {usuario['nombre_restaurante']}")
    print(f"Rol: {usuario['rol']}")
else:
    print("❌ Login FALLÓ - Credenciales inválidas")
    print("Revisa el hash de la contraseña")