"""Configuración leída desde variables de entorno y el archivo .env.

El archivo .env NO se sube a GitHub (está en .gitignore): ahí van los secretos.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _cargar_env():
    """Lector mínimo de .env (líneas CLAVE=valor). No pisa variables ya definidas."""
    ruta = BASE_DIR / ".env"
    if not ruta.exists():
        return
    for linea in ruta.read_text(encoding="utf-8-sig").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        os.environ.setdefault(clave.strip(), valor.strip().strip('"').strip("'"))


_cargar_env()

SESSION_HOURS = int(os.getenv("SESSION_HOURS", "8"))        # duración de la sesión
MAX_FAILED_LOGINS = int(os.getenv("MAX_FAILED_LOGINS", "5"))  # intentos antes de bloquear
LOCK_MINUTES = int(os.getenv("LOCK_MINUTES", "15"))          # minutos de bloqueo
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")