"""Módulo de defensa: detecta señales sospechosas en los eventos y genera alertas.

Las reglas puras están en app/defense_rules.py. Aquí: la tabla de alertas, el registro
con deduplicación, el análisis de cada evento nuevo y la API para consultarlas.
Si este módulo falla, la ingesta de eventos NO se detiene.
"""
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Column, DateTime, Integer, String, func
from sqlalchemy.orm import Session

from app import notify
from app.auth import auditar, current_user, now_naive, require_roles
from app.database import Base, get_db
from app.defense_rules import (UMBRAL_FALLOS_AUTH, VENTANA_AUTH_MIN, HORA_INICIO, HORA_FIN,
                               clasificar_origen, es_cambio_config, es_fallo_auth, fuera_de_horario)
from app.models import Device, SyslogEvent, User

VENTANA_DEDUP_MIN = 60      # una alerta igual (tipo + IP) en 60 min solo suma al contador

router = APIRouter(tags=["Alertas de seguridad"])


class SecurityAlert(Base):
    """Alerta generada por las reglas de defensa."""
    __tablename__ = "security_alerts"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, nullable=False)
    last_seen = Column(DateTime, nullable=False)
    kind = Column(String(30), nullable=False, index=True)
    severity = Column(String(10), nullable=False)          # Crítica, Alta, Media
    source_ip = Column(String(45), nullable=False, index=True)
    device_id = Column(Integer, nullable=True)
    detail = Column(String(300), nullable=True)
    count = Column(Integer, nullable=False, default=1)
    status = Column(String(12), nullable=False, default="ABIERTA", index=True)   # ABIERTA, RECONOCIDA
    notified = Column(String(10), nullable=True)           # TELEGRAM, SIMULADA o ERROR
    acknowledged_by = Column(String(30), nullable=True)


def registrar_alerta(db: Session, tipo: str, severidad: str, source_ip: str,
                     device_id: Optional[int], detalle: str) -> SecurityAlert:
    """Crea la alerta (y avisa) o, si ya hay una igual abierta, solo suma al contador."""
    ahora = now_naive()
    previa = (db.query(SecurityAlert)
              .filter(SecurityAlert.kind == tipo, SecurityAlert.source_ip == source_ip,
                      SecurityAlert.status == "ABIERTA",
                      SecurityAlert.last_seen >= ahora - timedelta(minutes=VENTANA_DEDUP_MIN))
              .order_by(SecurityAlert.id.desc()).first())
    if previa:
        previa.count += 1
        previa.last_seen = ahora
        db.commit()
        return previa

    alerta = SecurityAlert(created_at=ahora, last_seen=ahora, kind=tipo, severity=severidad,
                           source_ip=source_ip, device_id=device_id,
                           detail=(detalle or "")[:300], count=1, status="ABIERTA")
    db.add(alerta)
    db.commit()
    db.refresh(alerta)
    alerta.notified = notify.enviar(f"[NOC] {severidad} · {tipo} · origen {source_ip} · {detalle}")
    db.commit()
    auditar(db, "sistema", "ALERTA_SEGURIDAD", f"{tipo} desde {source_ip}: {detalle}"[:500], "OK")
    return alerta


def analizar_evento(db: Session, evento: SyslogEvent, device: Optional[Device]) -> None:
    """Aplica las reglas a un evento NUEVO. Nunca interrumpe la ingesta."""
    try:
        ip = evento.source_ip
        dev_id = device.id if device else None

        # 1. Origen: nombre del mensaje contra el inventario
        nombre_en_otra_ip = False
        if device is None and evento.hostname_reported:
            nombre_en_otra_ip = db.query(Device).filter(
                func.lower(Device.hostname) == evento.hostname_reported.lower()).first() is not None
        r = clasificar_origen(device.hostname if device else None,
                              evento.hostname_reported, nombre_en_otra_ip)
        if r:
            registrar_alerta(db, r[0], r[1], ip, dev_id, r[2])

        # 2. Cambio de configuración fuera de horario (hora de recepción, Bogotá)
        if es_cambio_config(evento.parsed_program, evento.message) and fuera_de_horario(now_naive()):
            registrar_alerta(db, "CAMBIO_FUERA_DE_HORARIO", "Alta", ip, dev_id,
                             f"cambio de configuración fuera de {HORA_INICIO}:00-{HORA_FIN}:00 (hora Bogotá)")

        # 3. Fallos de autenticación repetidos desde la misma IP
        if es_fallo_auth(evento.parsed_program, evento.message):
            desde = now_naive() - timedelta(minutes=VENTANA_AUTH_MIN)
            recientes = (db.query(SyslogEvent)
                         .filter(SyslogEvent.source_ip == ip, SyslogEvent.last_seen >= desde)
                         .limit(200).all())
            total = sum((e.repeat_count or 1) for e in recientes
                        if es_fallo_auth(e.parsed_program, e.message))
            if total >= UMBRAL_FALLOS_AUTH:
                registrar_alerta(db, "POSIBLE_FUERZA_BRUTA", "Crítica", ip, dev_id,
                                 f"{total} fallos de autenticación en {VENTANA_AUTH_MIN} min")
    except Exception as e:      # la defensa nunca debe tumbar la ingesta
        db.rollback()
        print(f"[DEFENSA] Error al analizar el evento (la ingesta continúa): {type(e).__name__}: {e}")


def _salida(a: SecurityAlert) -> dict:
    return {"id": a.id, "created_at": a.created_at, "last_seen": a.last_seen, "kind": a.kind,
            "severity": a.severity, "source_ip": a.source_ip, "device_id": a.device_id,
            "detail": a.detail, "count": a.count, "status": a.status,
            "notified": a.notified, "acknowledged_by": a.acknowledged_by}


@router.get("/api/alerts/", dependencies=[Depends(current_user)])
def listar_alertas(estado: Optional[str] = Query(None, alias="status"),
                   limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db)):
    q = db.query(SecurityAlert)
    if estado:
        q = q.filter(SecurityAlert.status == estado)
    return [_salida(a) for a in q.order_by(SecurityAlert.last_seen.desc()).limit(limit).all()]


@router.post("/api/alerts/{alert_id}/ack")
def reconocer(alert_id: int, db: Session = Depends(get_db),
              user: User = Depends(require_roles("admin", "operador"))):
    """Marca la alerta como reconocida por una persona."""
    a = db.query(SecurityAlert).filter(SecurityAlert.id == alert_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Alerta no encontrada")
    a.status = "RECONOCIDA"
    a.acknowledged_by = user.username
    db.commit()
    db.refresh(a)
    auditar(db, user.username, "ALERTA_RECONOCIDA", f"#{a.id} {a.kind} desde {a.source_ip}")
    return _salida(a)