"""Parser de mensajes Syslog formato RFC 3164.

Regla de seguridad: el mensaje es un DATO no confiable.
Aquí solo se extraen campos; nunca se ejecuta su contenido.
"""
import re
from app.syslog_constants import decode_pri, FACILITIES, SEVERITIES

# RFC 3164 limita el mensaje a 1024 bytes
MAX_LEN = 1024

# Parte 1: <PRI> TIMESTAMP HOSTNAME resto
PATRON_3164 = re.compile(
    r"^<(?P<pri>\d{1,3})>"
    r"(?P<timestamp>[A-Z][a-z]{2}\s+\d{1,2}\s\d{2}:\d{2}:\d{2})\s"
    r"(?P<hostname>\S+)\s"
    r"(?P<resto>.*)$",
    re.DOTALL,
)

# Parte 2: el "resto" se separa en TAG: mensaje
PATRON_TAG = re.compile(
    r"^(?P<programa>[^\s:\[]+)(?:\[(?P<pid>\d+)\])?:\s?(?P<mensaje>.*)$",
    re.DOTALL,
)

def parse_rfc3164(raw: str) -> dict:
    """Convierte un mensaje Syslog (texto) en un diccionario de campos.

    Lanza ValueError si el mensaje no cumple el formato.
    """
    raw = raw[:MAX_LEN]  # limitar tamaño

    m = PATRON_3164.match(raw)
    if not m:
        raise ValueError("El mensaje no cumple el formato RFC 3164")

    facility, severity = decode_pri(int(m["pri"]))

    # Separar el tag del texto; si no hay tag, todo es mensaje
    resto = m["resto"]
    t = PATRON_TAG.match(resto)
    programa = t["programa"] if t else None
    mensaje = t["mensaje"] if t else resto

    return {
        "facility": facility,
        "facility_name": FACILITIES[facility],
        "severity": severity,
        "severity_name": SEVERITIES[severity],
        "timestamp_text": m["timestamp"],
        "hostname": m["hostname"],
        "programa": programa,
        "mensaje": mensaje,
        "raw": raw,
    }