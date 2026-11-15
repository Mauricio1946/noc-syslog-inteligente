"""Reglas puras de defensa (sin base de datos): fáciles de probar.

Regla de oro: los logs son datos NO confiables. Aquí solo se LEEN campos y se
comparan con el inventario y con umbrales; nada del texto de un log se
interpreta como instrucción.
"""
import os
import re
from datetime import timedelta
from typing import Optional, Tuple

from app import config  # noqa: F401  (carga el archivo .env)

# Horario laboral en hora de Bogotá (UTC-5, sin horario de verano)
HORA_INICIO = int(os.getenv("WORK_HOURS_START", "7"))
HORA_FIN = int(os.getenv("WORK_HOURS_END", "19"))
UTC_OFFSET_HORAS = -5

UMBRAL_FALLOS_AUTH = int(os.getenv("AUTH_FAIL_THRESHOLD", "5"))   # fallos para alertar
VENTANA_AUTH_MIN = 10                                             # minutos de observación

PATRON_CAMBIO = re.compile(
    r"CONFIG_I|Configured from|Policy \d+ changed|configuration (?:changed|saved)", re.I)
PATRON_FALLO_AUTH = re.compile(
    r"Failed password|Failed login|login failed|authentication failure", re.I)


def es_cambio_config(programa: Optional[str], mensaje: Optional[str]) -> bool:
    """¿El evento describe un cambio de configuración?"""
    return bool(PATRON_CAMBIO.search(f"{programa or ''} {mensaje or ''}"))


def es_fallo_auth(programa: Optional[str], mensaje: Optional[str]) -> bool:
    """¿El evento describe un fallo de autenticación?"""
    return bool(PATRON_FALLO_AUTH.search(f"{programa or ''} {mensaje or ''}"))


def fuera_de_horario(utc_naive, inicio: Optional[int] = None, fin: Optional[int] = None) -> bool:
    """True si la hora local (Bogotá) está fuera de [inicio, fin).

    Se usa la hora de RECEPCIÓN, no la que dice el mensaje (esa no es confiable).
    """
    inicio = HORA_INICIO if inicio is None else inicio
    fin = HORA_FIN if fin is None else fin
    hora_local = (utc_naive + timedelta(hours=UTC_OFFSET_HORAS)).hour
    return not (inicio <= hora_local < fin)


def clasificar_origen(hostname_equipo: Optional[str], hostname_reportado: Optional[str],
                      nombre_en_otra_ip: bool) -> Optional[Tuple[str, str, str]]:
    """Contrasta el nombre que dice tener el mensaje con el inventario.

    La IP de origen es la referencia (sale de la conexión); el nombre del mensaje no.
    Devuelve (tipo, severidad, detalle) o None si todo es normal.
    """
    reportado = (hostname_reportado or "").strip()
    if hostname_equipo is not None:
        if reportado.lower() != hostname_equipo.lower():
            return ("HOSTNAME_NO_COINCIDE", "Media",
                    f"la IP pertenece a {hostname_equipo} pero el mensaje dice ser {reportado[:60]}")
        return None
    if nombre_en_otra_ip:
        return ("POSIBLE_SUPLANTACION", "Alta",
                f"IP no registrada usa el nombre de un equipo del inventario: {reportado[:60]}")
    return ("FUENTE_DESCONOCIDA", "Media", "IP no registrada en el inventario")