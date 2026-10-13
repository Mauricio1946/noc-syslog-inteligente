import os
from datetime import date, datetime, time
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException, Query, status
from fastapi.responses import PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import engine, Base, get_db
from app.models import Device, SyslogEvent, Incident, AuditLog
from app.schemas import (DeviceCreate, DeviceUpdate, DeviceResponse,
                         SyslogIn, SyslogEventResponse,
                         IncidentCreate, IncidentUpdate, IncidentResponse,
                         ConsoleIn, ConsoleOut, AuditResponse)
from app.ingest import guardar_evento
from app.configs import generar_config, VENDORS
from app.console import ejecutar_comando

# Crear las tablas en la base de datos si no existen
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="NOC Syslog Inteligente - API",
    version="0.2.0",
    description="Sistema de Monitoreo NOC y Gestión de Syslog para Redes"
)

ACTOR = "estudiante"   # sin login en el MVP; roles y autenticación quedan para el Corte 3
ESTADOS_INCIDENTE = ("Abierto", "En Progreso", "Cerrado")
SEVERIDADES_INCIDENTE = ("Crítica", "Alta", "Media", "Baja")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(BASE_DIR, "static")


def auditar(db: Session, accion: str, detalle: str, resultado: str = "OK"):
    """Registra una acción en la auditoría (quién, qué, cuándo, resultado)."""
    db.add(AuditLog(actor=ACTOR, action=accion, detail=detalle[:500], result=resultado))
    db.commit()


@app.get("/", include_in_schema=False)
def root():
    if os.path.isdir(STATIC_DIR):
        return RedirectResponse(url="/ui/")
    return {"message": "API del NOC Syslog Inteligente v0.2.0 - ver /docs"}


# --- DISPOSITIVOS (INVENTARIO) ---

@app.post("/api/devices/", response_model=DeviceResponse,
          status_code=status.HTTP_201_CREATED, tags=["Dispositivos"])
def create_device(device: DeviceCreate, db: Session = Depends(get_db)):
    """Registrar un nuevo dispositivo en el inventario (IP única)."""
    if db.query(Device).filter(Device.ip_address == device.ip_address).first():
        raise HTTPException(status_code=400,
                            detail=f"Ya existe un dispositivo registrado con la IP {device.ip_address}")
    new_device = Device(**device.model_dump())
    db.add(new_device)
    db.commit()
    db.refresh(new_device)
    auditar(db, "DISPOSITIVO_CREADO", f"{new_device.hostname} ({new_device.ip_address})")
    return new_device


@app.get("/api/devices/", response_model=List[DeviceResponse], tags=["Dispositivos"])
def list_devices(db: Session = Depends(get_db)):
    return db.query(Device).all()


@app.get("/api/devices/{device_id}", response_model=DeviceResponse, tags=["Dispositivos"])
def get_device(device_id: int, db: Session = Depends(get_db)):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Dispositivo no encontrado")
    return device


@app.put("/api/devices/{device_id}", response_model=DeviceResponse, tags=["Dispositivos"])
def update_device(device_id: int, device_update: DeviceUpdate, db: Session = Depends(get_db)):
    db_device = db.query(Device).filter(Device.id == device_id).first()
    if not db_device:
        raise HTTPException(status_code=404, detail="Dispositivo no encontrado")
    for key, value in device_update.model_dump(exclude_unset=True).items():
        setattr(db_device, key, value)
    db.commit()
    db.refresh(db_device)
    auditar(db, "DISPOSITIVO_EDITADO", f"{db_device.hostname}")
    return db_device


@app.delete("/api/devices/{device_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Dispositivos"])
def delete_device(device_id: int, db: Session = Depends(get_db)):
    db_device = db.query(Device).filter(Device.id == device_id).first()
    if not db_device:
        raise HTTPException(status_code=404, detail="Dispositivo no encontrado")
    nombre = db_device.hostname
    db.delete(db_device)
    db.commit()
    auditar(db, "DISPOSITIVO_ELIMINADO", nombre)
    return None


# --- SYSLOG ---

@app.post("/api/syslog/", response_model=SyslogEventResponse,
          status_code=status.HTTP_201_CREATED, tags=["Syslog"])
def ingest_syslog(entry: SyslogIn, db: Session = Depends(get_db)):
    """Recibe un mensaje Syslog (SIMULADO), lo parsea y lo guarda."""
    try:
        return guardar_evento(db, entry.raw_message, entry.source_ip, "SIMULADO")
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.get("/api/syslog/", response_model=List[SyslogEventResponse], tags=["Syslog"])
def list_syslog(severity: Optional[int] = Query(None, ge=0, le=7),
                max_severity: Optional[int] = Query(None, ge=0, le=7),
                device_id: Optional[int] = None,
                vendor: Optional[str] = None,
                date_from: Optional[date] = None,
                date_to: Optional[date] = None,
                limit: int = Query(100, ge=1, le=500),
                db: Session = Depends(get_db)):
    """Lista eventos (más recientes primero) con filtros opcionales.

    severity = exacta; max_severity = esa severidad o más grave (0 a N).
    """
    q = db.query(SyslogEvent)
    if vendor:
        q = q.join(Device, SyslogEvent.device_id == Device.id).filter(
            func.lower(Device.vendor) == vendor.lower())
    if severity is not None:
        q = q.filter(SyslogEvent.severity == severity)
    if max_severity is not None:
        q = q.filter(SyslogEvent.severity <= max_severity)
    if device_id is not None:
        q = q.filter(SyslogEvent.device_id == device_id)
    if date_from:
        q = q.filter(SyslogEvent.timestamp >= datetime.combine(date_from, time.min))
    if date_to:
        q = q.filter(SyslogEvent.timestamp <= datetime.combine(date_to, time.max))
    return q.order_by(SyslogEvent.id.desc()).limit(limit).all()


# --- INCIDENTES ---

@app.post("/api/incidents/", response_model=IncidentResponse,
          status_code=status.HTTP_201_CREATED, tags=["Incidentes"])
def create_incident(entry: IncidentCreate, db: Session = Depends(get_db)):
    if entry.severity not in SEVERIDADES_INCIDENTE:
        raise HTTPException(status_code=422, detail=f"Severidad válida: {SEVERIDADES_INCIDENTE}")
    if not db.query(Device).filter(Device.id == entry.device_id).first():
        raise HTTPException(status_code=404, detail="Dispositivo no encontrado")
    incident = Incident(**entry.model_dump())
    db.add(incident)
    db.commit()
    db.refresh(incident)
    auditar(db, "INCIDENTE_CREADO", f"#{incident.id} {incident.title}")
    return incident


@app.get("/api/incidents/", response_model=List[IncidentResponse], tags=["Incidentes"])
def list_incidents(estado: Optional[str] = Query(None, alias="status"),
                   db: Session = Depends(get_db)):
    q = db.query(Incident)
    if estado:
        q = q.filter(Incident.status == estado)
    return q.order_by(Incident.id.desc()).all()


@app.put("/api/incidents/{incident_id}", response_model=IncidentResponse, tags=["Incidentes"])
def update_incident(incident_id: int, entry: IncidentUpdate, db: Session = Depends(get_db)):
    """Asignar, dar seguimiento (estado) o cerrar un incidente."""
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incidente no encontrado")
    datos = entry.model_dump(exclude_unset=True)
    if "status" in datos and datos["status"] not in ESTADOS_INCIDENTE:
        raise HTTPException(status_code=422, detail=f"Estado válido: {ESTADOS_INCIDENTE}")
    if "severity" in datos and datos["severity"] not in SEVERIDADES_INCIDENTE:
        raise HTTPException(status_code=422, detail=f"Severidad válida: {SEVERIDADES_INCIDENTE}")
    for key, value in datos.items():
        setattr(incident, key, value)
    db.commit()
    db.refresh(incident)
    auditar(db, "INCIDENTE_ACTUALIZADO", f"#{incident.id} -> {datos}")
    return incident


# --- DASHBOARD ---

@app.get("/api/dashboard/", tags=["Dashboard"])
def dashboard(db: Session = Depends(get_db)):
    """Resumen para el panel principal."""
    dispositivos = dict(db.query(Device.status, func.count(Device.id)).group_by(Device.status).all())
    por_severidad = dict(db.query(SyslogEvent.severity, func.count(SyslogEvent.id))
                         .group_by(SyslogEvent.severity).all())
    return {
        "dispositivos": dispositivos,
        "total_dispositivos": db.query(func.count(Device.id)).scalar(),
        "total_eventos": db.query(func.count(SyslogEvent.id)).scalar(),
        "eventos_por_severidad": por_severidad,
        "eventos_criticos": db.query(func.count(SyslogEvent.id)).filter(SyslogEvent.severity <= 2).scalar(),
        "eventos_fuente_desconocida": db.query(func.count(SyslogEvent.id)).filter(SyslogEvent.device_id.is_(None)).scalar(),
        "incidentes_abiertos": db.query(func.count(Incident.id)).filter(Incident.status != "Cerrado").scalar(),
        "incidentes_total": db.query(func.count(Incident.id)).scalar(),
    }


# --- CONFIGURACIONES SYSLOG ---

@app.get("/api/configs/{vendor}", response_class=PlainTextResponse, tags=["Configuraciones"])
def get_config(vendor: str, severity: int = Query(6, ge=0, le=7)):
    """Plantilla Syslog comentada para cisco, fortinet o huawei."""
    v = vendor.lower()
    if v not in VENDORS:
        raise HTTPException(status_code=404, detail=f"Fabricante válido: {VENDORS}")
    return generar_config(v, severity=severity)


# --- CONSOLA SIMULADA (SOLO LECTURA) ---

@app.post("/api/console/", response_model=ConsoleOut, tags=["Consola"])
def console(entry: ConsoleIn, db: Session = Depends(get_db)):
    """Ejecuta un comando SIMULADO. Solo la allowlist pasa; todo se audita."""
    device = db.query(Device).filter(Device.id == entry.device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Dispositivo no encontrado")
    permitido, salida = ejecutar_comando(device.vendor, device.hostname, entry.command)
    auditar(db, "CONSOLA", f"{device.hostname}: {entry.command[:200]}",
            "PERMITIDO" if permitido else "BLOQUEADO")
    return {"allowed": permitido, "output": salida}


# --- AUDITORÍA ---

@app.get("/api/audit/", response_model=List[AuditResponse], tags=["Auditoría"])
def list_audit(limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db)):
    return db.query(AuditLog).order_by(AuditLog.id.desc()).limit(limit).all()


# --- INTERFAZ WEB (carpeta static/, se crea en el paso B) ---
if os.path.isdir(STATIC_DIR):
    app.mount("/ui", StaticFiles(directory=STATIC_DIR, html=True), name="ui")