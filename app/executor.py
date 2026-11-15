"""Ejecutor de acciones aprobadas. Modo SIMULADO (no toca equipos reales).

Controles antes de ejecutar:
 - El equipo debe estar en estado Activo.
 - Si existe SSH_ALLOWED_HOSTS (IPs separadas por coma), el equipo debe estar en esa lista.
 - Solo se admite EXEC_MODE=simulado. El modo SSH real queda PREPARADO pero no
   implementado en esta versión: requiere un equipo de laboratorio para probarlo.
"""
import os

from app import config  # noqa: F401  (carga el archivo .env)
from app.actions import simular_ejecucion


def hosts_permitidos() -> set:
    crudo = os.getenv("SSH_ALLOWED_HOSTS", "")
    return {h.strip() for h in crudo.split(",") if h.strip()}


def ejecutar(device, comandos) -> str:
    """Devuelve la salida de la ejecución o lanza ValueError si el ejecutor se niega."""
    if device.status != "Activo":
        raise ValueError(f"El equipo está en estado {device.status}: no se ejecutan acciones")
    permitidos = hosts_permitidos()
    if permitidos and device.ip_address not in permitidos:
        raise ValueError("El equipo no está en la lista de hosts permitidos")
    if os.getenv("EXEC_MODE", "simulado") != "simulado":
        raise ValueError("El modo de ejecución real no está habilitado en esta versión")
    return simular_ejecucion(device.hostname, comandos)