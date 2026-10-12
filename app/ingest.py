"""Lógica compartida de ingesta de eventos Syslog.

La usan tanto el endpoint HTTP como el receptor UDP.
Regla de seguridad: el mensaje es un DATO no confiable; solo se extraen campos.
"""
from sqlalchemy.orm import Session
from app.models import Device, SyslogEvent
from app.syslog_parser import parse_rfc3164


def guardar_evento(db: Session, raw_message: str, source_ip: str,
                   origin: str = "SIMULADO") -> SyslogEvent:
    """Parsea un mensaje y lo guarda. Lanza ValueError si el formato es inválido."""
    # 1. Parsear (si no cumple el formato, lanza ValueError)
    parsed = parse_rfc3164(raw_message)

    # 2. ¿La IP de origen está en el inventario? Si no, es fuente desconocida.
    device = db.query(Device).filter(Device.ip_address == source_ip).first()

    # 3. Guardar el evento
    event = SyslogEvent(
        device_id=device.id if device else None,
        source_ip=source_ip,
        hostname_reported=parsed["hostname"][:100],
        facility=parsed["facility"],
        severity=parsed["severity"],
        parsed_program=(parsed["programa"] or "")[:50] or None,
        message=parsed["mensaje"],
        raw_message=parsed["raw"],
        origin=origin,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event