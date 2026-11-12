"""Crea un usuario del NOC pidiendo la contraseña por teclado (no queda en historial).

Uso:  python create_user.py
"""
import getpass
import re

from app.database import SessionLocal, Base, engine
import app.models  # noqa: F401  (registra las tablas)
from app.models import User
from app.security import hash_password, ROLES


def main():
    Base.metadata.create_all(bind=engine)

    username = input("Usuario (3-30 caracteres: letras, números, . _ -): ").strip().lower()
    if not re.fullmatch(r"[a-z0-9._-]{3,30}", username):
        print("Usuario inválido.")
        return
    rol = input(f"Rol {ROLES}: ").strip().lower()
    if rol not in ROLES:
        print("Rol inválido.")
        return

    clave = getpass.getpass("Contraseña (mínimo 10 caracteres): ")
    if len(clave) < 10 or clave.lower() == username:
        print("Contraseña débil: usa al menos 10 caracteres y que no sea el usuario.")
        return
    if clave != getpass.getpass("Repite la contraseña: "):
        print("Las contraseñas no coinciden.")
        return

    db = SessionLocal()
    try:
        if db.query(User).filter(User.username == username).first():
            print("Ese usuario ya existe.")
            return
        db.add(User(username=username, password_hash=hash_password(clave), role=rol))
        db.commit()
        print(f"Usuario '{username}' creado con rol {rol}.")
    finally:
        db.close()


if __name__ == "__main__":
    main()