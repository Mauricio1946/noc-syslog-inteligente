"""Flujo de aprobación humana para acciones sobre equipos (ejecución SIMULADA).

Flujo: solicitud -> revisión humana (otra persona) -> aprobación -> ejecución
autorizada -> verificación -> auditoría.

Reglas:
 - Nadie aprueba su propia solicitud (separación de funciones).
 - Las solicitudes vencen si nadie las revisa.
 - Hay un tope de solicitudes pendientes por usuario (contra inundación de peticiones).
 - Solo existen las acciones del catálogo (app/actions.py): no hay comandos libres.
 - Antes de ejecutar se vuelve a validar la acción (defensa en profundidad).
"""
import json
import os
from datetime import timedelta
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Session

from app import config  # noqa: F401  (carga el archivo .env)
from app.actions import ACCIONES, construir_comandos, fabricantes_de, simular_ejecucion
from app.auth import auditar, current_user, now_naive, require_roles
from app.executor import ejecutar
from app.database import Base, get_db
from app.models import Device, User

VENCE_MINUTOS = int(os.getenv("APPROVAL_MINUTES", "30"))        # tiempo para revisar una solicitud
MAX_PENDIENTES = int(os.getenv("MAX_PENDING_PER_USER", "5"))    # pendientes por usuario

PROPONER = require_roles("admin", "operador")
REVISAR = require_roles("admin", "operador")

router = APIRouter(tags=["Aprobaciones"])


class CommandRequest(Base):
    """Solicitud de una acción sobre un equipo, pendiente de aprobación humana."""
    __tablename__ = "command_requests"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False)
    action = Column(String(40), nullable=False)
    params = Column(Text, nullable=False, default="{}")
    commands = Column(Text, nullable=False)                 # comandos ya construidos, uno por línea
    requested_by = Column(String(30), nullable=False, index=True)
    status = Column(String(12), nullable=False, default="PENDIENTE", index=True)
    created_at = Column(DateTime, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    decided_by = Column(String(30), nullable=True)
    decided_at = Column(DateTime, nullable=True)
    decision_note = Column(String(200), nullable=True)
    executed_at = Column(DateTime, nullable=True)
    output = Column(Text, nullable=True)
    verified_by = Column(String(30), nullable=True)
    verified_at = Column(DateTime, nullable=True)
    verify_note = Column(String(200), nullable=True)


class RequestIn(BaseModel):
    device_id: int
    action: str = Field(..., max_length=40, examples=["apagar_interfaz"])
    params: Dict[str, str] = Field(default_factory=dict, examples=[{"interfaz": "Gi1/0/5"}])


class DecisionIn(BaseModel):
    note: Optional[str] = Field(None, max_length=200)


def _salida(r: CommandRequest) -> dict:
    return {
        "id": r.id, "device_id": r.device_id, "action": r.action,
        "params": json.loads(r.params or "{}"), "commands": r.commands.split("\n"),
        "requested_by": r.requested_by, "status": r.status,
        "created_at": r.created_at, "expires_at": r.expires_at,
        "decided_by": r.decided_by, "decided_at": r.decided_at, "decision_note": r.decision_note,
        "executed_at": r.executed_at, "output": r.output,
        "verified_by": r.verified_by, "verified_at": r.verified_at, "verify_note": r.verify_note,
    }


def _obtener(db: Session, req_id: int) -> CommandRequest:
    r = db.query(CommandRequest).filter(CommandRequest.id == req_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    return r


def _pendiente(db: Session, req_id: int, user: User) -> CommandRequest:
    """Devuelve la solicitud si sigue PENDIENTE y vigente; si venció, la marca."""
    r = _obtener(db, req_id)
    if r.status != "PENDIENTE":
        raise HTTPException(status_code=409, detail=f"La solicitud ya está {r.status}")
    if r.expires_at < now_naive():
        r.status = "EXPIRADA"
        db.commit()
        auditar(db, user.username, "SOLICITUD_EXPIRADA", f"#{r.id}", "DENEGADO")
        raise HTTPException(status_code=409, detail="La solicitud venció sin ser revisada")
    return r


@router.get("/api/actions/", dependencies=[Depends(current_user)])
def catalogo():
    """Acciones disponibles, sus parámetros y los fabricantes donde aplican."""
    return [{"action": nombre, "descripcion": a["descripcion"], "riesgo": a["riesgo"],
             "parametros": a["parametros"], "fabricantes": fabricantes_de(nombre)}
            for nombre, a in ACCIONES.items()]


@router.post("/api/requests/", status_code=201)
def crear(entry: RequestIn, db: Session = Depends(get_db), user: User = Depends(PROPONER)):
    """Propone una acción. Queda PENDIENTE hasta que OTRA persona la revise."""
    device = db.query(Device).filter(Device.id == entry.device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Dispositivo no encontrado")
    try:
        comandos = construir_comandos(device.vendor, entry.action, entry.params)
    except ValueError as e:
        auditar(db, user.username, "SOLICITUD_BLOQUEADA",
                f"{device.hostname}: {entry.action} {entry.params} -> {e}", "BLOQUEADO")
        raise HTTPException(status_code=422, detail=str(e))

    ahora = now_naive()
    pendientes = (db.query(CommandRequest)
                  .filter(CommandRequest.requested_by == user.username,
                          CommandRequest.status == "PENDIENTE",
                          CommandRequest.expires_at > ahora).count())
    if pendientes >= MAX_PENDIENTES:
        auditar(db, user.username, "SOLICITUD_BLOQUEADA",
                f"tope de {MAX_PENDIENTES} pendientes por usuario", "DENEGADO")
        raise HTTPException(status_code=429, detail="Tienes demasiadas solicitudes pendientes")

    r = CommandRequest(device_id=device.id, action=entry.action,
                       params=json.dumps(entry.params), commands="\n".join(comandos),
                       requested_by=user.username, status="PENDIENTE",
                       created_at=ahora, expires_at=ahora + timedelta(minutes=VENCE_MINUTOS))
    db.add(r)
    db.commit()
    db.refresh(r)
    auditar(db, user.username, "SOLICITUD_CREADA",
            f"#{r.id} {entry.action} {entry.params} en {device.hostname}")
    return _salida(r)


@router.get("/api/requests/", dependencies=[Depends(current_user)])
def listar(estado: Optional[str] = Query(None, alias="status"),
           limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db)):
    """Lista las solicitudes (las vencidas se marcan EXPIRADA)."""
    db.query(CommandRequest).filter(CommandRequest.status == "PENDIENTE",
                                    CommandRequest.expires_at < now_naive()
                                    ).update({"status": "EXPIRADA"}, synchronize_session=False)
    db.commit()
    q = db.query(CommandRequest)
    if estado:
        q = q.filter(CommandRequest.status == estado)
    return [_salida(r) for r in q.order_by(CommandRequest.id.desc()).limit(limit).all()]


@router.post("/api/requests/{req_id}/approve")
def aprobar(req_id: int, entry: DecisionIn, db: Session = Depends(get_db),
            user: User = Depends(REVISAR)):
    """Aprueba y ejecuta (SIMULADO). La persona que propuso NO puede aprobar."""
    r = _pendiente(db, req_id, user)
    if r.requested_by == user.username:
        auditar(db, user.username, "AUTOAPROBACION_DENEGADA", f"solicitud #{r.id}", "DENEGADO")
        raise HTTPException(status_code=403,
                            detail="No puedes aprobar tu propia solicitud: debe hacerlo otra persona")

    ahora = now_naive()
    r.decided_by, r.decided_at, r.decision_note = user.username, ahora, entry.note
    device = db.query(Device).filter(Device.id == r.device_id).first()
    try:
        if not device:
            raise ValueError("el equipo ya no existe")
        comandos = construir_comandos(device.vendor, r.action, json.loads(r.params))
    except ValueError as e:      # revalidación antes de ejecutar
        r.status = "RECHAZADA"
        r.decision_note = f"Revalidación fallida: {e}"[:200]
        db.commit()
        auditar(db, user.username, "SOLICITUD_RECHAZADA", f"#{r.id} {e}", "BLOQUEADO")
        raise HTTPException(status_code=409, detail="La solicitud ya no es válida y se rechazó")

    try:
        r.output = ejecutar(device, comandos)
    except ValueError as e:      # el ejecutor puede negarse (equipo inactivo, host no permitido)
        r.status = "RECHAZADA"
        r.decision_note = f"Ejecución denegada: {e}"[:200]
        db.commit()
        auditar(db, user.username, "EJECUCION_DENEGADA", f"#{r.id} {e}", "BLOQUEADO")
        raise HTTPException(status_code=409, detail=str(e))
    r.executed_at = ahora
    r.status = "EJECUTADA"
    db.commit()
    db.refresh(r)
    auditar(db, user.username, "SOLICITUD_APROBADA", f"#{r.id} (propuesta por {r.requested_by})")
    auditar(db, user.username, "EJECUCION_SIMULADA", f"#{r.id} {device.hostname}: {'; '.join(comandos)}")
    return _salida(r)


@router.post("/api/requests/{req_id}/reject")
def rechazar(req_id: int, entry: DecisionIn, db: Session = Depends(get_db),
             user: User = Depends(REVISAR)):
    """Rechaza una solicitud pendiente (también sirve para retirar la propia)."""
    r = _pendiente(db, req_id, user)
    r.status = "RECHAZADA"
    r.decided_by, r.decided_at, r.decision_note = user.username, now_naive(), entry.note
    db.commit()
    db.refresh(r)
    auditar(db, user.username, "SOLICITUD_RECHAZADA", f"#{r.id} (propuesta por {r.requested_by})")
    return _salida(r)


@router.post("/api/requests/{req_id}/verify")
def verificar(req_id: int, entry: DecisionIn, db: Session = Depends(get_db),
              user: User = Depends(PROPONER)):
    """Verificación: quien propuso (o un admin) confirma que el resultado es el esperado."""
    r = _obtener(db, req_id)
    if r.status != "EJECUTADA":
        raise HTTPException(status_code=409, detail="Solo se verifican solicitudes ejecutadas")
    if user.username != r.requested_by and user.role != "admin":
        auditar(db, user.username, "VERIFICACION_DENEGADA", f"solicitud #{r.id}", "DENEGADO")
        raise HTTPException(status_code=403, detail="Solo quien propuso la acción (o un admin) puede verificarla")
    r.status = "VERIFICADA"
    r.verified_by, r.verified_at, r.verify_note = user.username, now_naive(), entry.note
    db.commit()
    db.refresh(r)
    auditar(db, user.username, "SOLICITUD_VERIFICADA", f"#{r.id}")
    return _salida(r)