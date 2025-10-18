import bcrypt

password = "admin123"
hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
print(f"\n✅ Hash generado correctamente:")
print(f"{hashed.decode('utf-8')}")
print(f"\nAhora ejecuta este SQL:\n")
print(f"UPDATE usuarios_admin")
print(f"SET password_hash = '{hashed.decode('utf-8')}'")
print(f"WHERE email = 'admin@giants.com';")