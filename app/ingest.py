"""Lógica compartida de ingesta de eventos Syslog.

La usan tanto el endpoint HTTP como el receptor UDP.
Regla de seguridad: el mensaje es un DATO no confiable; solo se extraen campos.
Defensa: los mensajes repetidos se agrupan (deduplicación), no se descartan.
"""
from datetime import timedelta
from sqlalchemy.orm import Session
from app.models import Device, SyslogEvent, utcnow
from app.syslog_parser import parse_rfc3164

# Ventana de deduplicación: mismo mensaje dentro de este tiempo = repetido
VENTANA_SEGUNDOS = 60


def guardar_evento(db: Session, raw_message: str, source_ip: str,
                   origin: str = "SIMULADO") -> SyslogEvent:
    """Parsea un mensaje y lo guarda (o suma al contador si es repetido).

    Lanza ValueError si el formato es inválido.
    """
    # 1. Parsear (si no cumple el formato, lanza ValueError)
    parsed = parse_rfc3164(raw_message)
    programa = (parsed["programa"] or "")[:50] or None

    # 2. ¿Es repetido? Mismo origen y contenido dentro de la ventana
    limite = (utcnow() - timedelta(seconds=VENTANA_SEGUNDOS)).replace(tzinfo=None)
    repetido = (
        db.query(SyslogEvent)
        .filter(SyslogEvent.source_ip == source_ip,
                SyslogEvent.facility == parsed["facility"],
                SyslogEvent.severity == parsed["severity"],
                SyslogEvent.parsed_program == programa,
                SyslogEvent.message == parsed["mensaje"],
                SyslogEvent.last_seen >= limite)
        .order_by(SyslogEvent.id.desc())
        .first()
    )
    if repetido:
        repetido.repeat_count += 1
        repetido.last_seen = utcnow()
        db.commit()
        db.refresh(repetido)
        return repetido

    # 3. No es repetido: ¿la IP está en el inventario? Si no, fuente desconocida
    device = db.query(Device).filter(Device.ip_address == source_ip).first()

    # 4. Guardar el evento nuevo
    event = SyslogEvent(
        device_id=device.id if device else None,
        source_ip=source_ip,
        hostname_reported=parsed["hostname"][:100],
        facility=parsed["facility"],
        severity=parsed["severity"],
        parsed_program=programa,
        message=parsed["mensaje"],
        raw_message=parsed["raw"],
        origin=origin,
        repeat_count=1,
        last_seen=utcnow(),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def guardar_alerta_tormenta(db: Session, source_ip: str,
                            maximo: int, ventana: int) -> SyslogEvent:
    """Guarda UN evento que avisa que una IP superó el límite de frecuencia."""
    device = db.query(Device).filter(Device.ip_address == source_ip).first()
    texto = (f"Tormenta de eventos: {source_ip} superó {maximo} mensajes "
             f"en {ventana} s. Se descartan los mensajes adicionales.")
    event = SyslogEvent(
        device_id=device.id if device else None,
        source_ip=source_ip,
        facility=5,                      # syslog (generado por el propio sistema)
        severity=1,                      # Alert
        parsed_program="noc-ratelimit",
        message=texto,
        raw_message=texto,
        origin="SISTEMA",
        repeat_count=1,
        last_seen=utcnow(),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event