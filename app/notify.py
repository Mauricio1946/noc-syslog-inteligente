"""Notificaciones de alertas: Telegram si hay credenciales; si no, modo SIMULADO.

El token vive SOLO en el archivo .env (que no se sube a GitHub): nunca en el
código, en la base de datos ni en los mensajes de error.
"""
import json
import os
import urllib.request

from app import config  # noqa: F401  (carga el archivo .env)

TIMEOUT_SEGUNDOS = 4


def modo() -> str:
    """'TELEGRAM' si hay token y chat configurados; 'SIMULADA' en caso contrario."""
    if os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"):
        return "TELEGRAM"
    return "SIMULADA"


def enviar(texto: str) -> str:
    """Envía la alerta. Devuelve 'TELEGRAM', 'SIMULADA' o 'ERROR'. Nunca lanza excepciones."""
    texto = " ".join(str(texto).split())[:400]    # una sola línea y con tope de tamaño
    if modo() == "SIMULADA":
        print(f"[ALERTA SIMULADA] {texto}")
        return "SIMULADA"
    try:
        token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        datos = json.dumps({"chat_id": os.getenv("TELEGRAM_CHAT_ID", ""), "text": texto,
                            "disable_web_page_preview": True}).encode("utf-8")
        peticion = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage", data=datos,
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(peticion, timeout=TIMEOUT_SEGUNDOS) as r:
            return "TELEGRAM" if r.status == 200 else "ERROR"
    except Exception as e:
        # Solo el tipo de error: el mensaje podría incluir la URL, que contiene el token
        print(f"[ALERTA] No se pudo enviar a Telegram ({type(e).__name__})")
        return "ERROR"
