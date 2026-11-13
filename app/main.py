import os
from datetime import date, datetime, time, timedelta
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import engine, Base, get_db
from app.models import Device, SyslogEvent, Incident, AuditLog, User, UserSession
from app.schemas import (DeviceCreate, DeviceUpdate, DeviceResponse,
                         SyslogIn, SyslogEventResponse,
                         IncidentCreate, IncidentUpdate, IncidentResponse,
                         ConsoleIn, ConsoleOut, AuditResponse, LoginIn, MeOut)
from app.ingest import guardar_evento
from app.configs import generar_config, VENDORS
from app.console import ejecutar_comando
from app.config import SESSION_HOURS, MAX_FAILED_LOGINS, LOCK_MINUTES
from app.security import hash_password, verify_password, new_token, hash_token
from app.auth import (COOKIE_NAME, COOKIE_SECURE, now_naive, auditar,
                      current_user, require_roles)
from app.approvals import router as approvals_router

# Crear las tablas en la base de datos si no existen
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="NOC Syslog Inteligente - API",
    version="1.0.0-dev",
    description="Sistema de Monitoreo NOC y Gestión de Syslog para Redes"
)

ESTADOS_INCIDENTE = ("Abierto", "En Progreso", "Cerrado")
SEVERIDADES_INCIDENTE = ("Crítica", "Alta", "Media", "Baja")

# Permisos por rol (denegar por defecto):
#   admin    -> todo
#   operador -> ver, incidentes, consola de solo lectura, ingesta simulada
#   auditor  -> solo lectura, incluida la auditoría
SOLO_ADMIN = require_roles("admin")
OPERAR = require_roles("admin", "operador")
VER_AUDITORIA = require_roles("admin", "auditor")

# Hash falso: se verifica cuando el usuario no existe para que la respuesta
# tarde lo mismo y no se pueda averiguar qué usuarios existen.
DUMMY_HASH = hash_password("clave-inexistente-solo-para-igualar-tiempos")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(BASE_DIR, "static")


@app.middleware("http")
async def cabeceras_seguras(request: Request, call_next):
    """Cabeceras básicas de seguridad; la API nunca se guarda en caché."""
    respuesta = await call_next(request)
    respuesta.headers["X-Content-Type-Options"] = "nosniff"
    respuesta.headers["X-Frame-Options"] = "DENY"
    respuesta.headers["Referrer-Policy"] = "no-referrer"
    if request.url.path.startswith("/api/"):
        respuesta.headers["Cache-Control"] = "no-store"
    return respuesta


@app.get("/", include_in_schema=False)
def root():
    if os.path.isdir(STATIC_DIR):
        return RedirectResponse(url="/ui/")
    return {"message": "API del NOC Syslog Inteligente - ver /docs"}


# --- AUTENTICACIÓN ---

@app.post("/api/auth/login", response_model=MeOut, tags=["Autenticación"])
def login(entry: LoginIn, response: Response, db: Session = Depends(get_db)):
    """Inicia sesión. Mensaje genérico en los fallos; bloqueo temporal tras varios intentos."""
    ahora = now_naive()
    nombre = entry.username.strip().lower()
    user = db.query(User).filter(User.username == nombre).first()

    # Cuenta bloqueada: se rechaza sin comprobar la contraseña
    if user and user.locked_until and user.locked_until > ahora:
        verify_password(entry.password, DUMMY_HASH)
        auditar(db, user.username, "LOGIN_BLOQUEADO", "intento con la cuenta bloqueada", "DENEGADO")
        raise HTTPException(status_code=429, detail="Demasiados intentos fallidos. Intenta más tarde.")

    correcta = verify_password(entry.password, user.password_hash if user else DUMMY_HASH)
    if not user or not user.active or not correcta:
        if user:
            user.failed_attempts = (user.failed_attempts or 0) + 1
            if user.failed_attempts >= MAX_FAILED_LOGINS:
                user.locked_until = ahora + timedelta(minutes=LOCK_MINUTES)
                user.failed_attempts = 0
            db.commit()
        auditar(db, user.username if user else nombre[:30], "LOGIN_FALLIDO",
                "usuario o contraseña incorrectos", "DENEGADO")
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")

    # Éxito: limpiar contadores, borrar sesiones vencidas y crear la sesión
    user.failed_attempts = 0
    user.locked_until = None
    db.query(UserSession).filter(UserSession.expires_at < ahora).delete()
    token = new_token()
    db.add(UserSession(token_hash=hash_token(token), user_id=user.id,
                       expires_at=ahora + timedelta(hours=SESSION_HOURS)))
    db.commit()
    response.set_cookie(COOKIE_NAME, token, httponly=True, samesite="strict",
                        secure=COOKIE_SECURE, max_age=SESSION_HOURS * 3600, path="/")
    auditar(db, user.username, "LOGIN_OK", f"rol {user.role}", "OK")
    return {"username": user.username, "role": user.role}


@app.post("/api/auth/logout", tags=["Autenticación"])
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    """Cierra la sesión: borra el token del servidor y la cookie del navegador."""
    token = request.cookies.get(COOKIE_NAME)
    if token:
        db.query(UserSession).filter(UserSession.token_hash == hash_token(token)).delete()
        db.commit()
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


@app.get("/api/auth/me", response_model=MeOut, tags=["Autenticación"])
def me(user: User = Depends(current_user)):
    return {"username": user.username, "role": user.role}


# --- DISPOSITIVOS (INVENTARIO) ---

@app.post("/api/devices/", response_model=DeviceResponse,
          status_code=status.HTTP_201_CREATED, tags=["Dispositivos"])
def create_device(device: DeviceCreate, db: Session = Depends(get_db),
                  user: User = Depends(SOLO_ADMIN)):
    """Registrar un nuevo dispositivo en el inventario (IP única). Solo admin."""
    if db.query(Device).filter(Device.ip_address == device.ip_address).first():
        raise HTTPException(status_code=400,
                            detail=f"Ya existe un dispositivo registrado con la IP {device.ip_address}")
    new_device = Device(**device.model_dump())
    db.add(new_device)
    db.commit()
    db.refresh(new_device)
    auditar(db, user.username, "DISPOSITIVO_CREADO", f"{new_device.hostname} ({new_device.ip_address})")
    return new_device


@app.get("/api/devices/", response_model=List[DeviceResponse], tags=["Dispositivos"],
         dependencies=[Depends(current_user)])
def list_devices(db: Session = Depends(get_db)):
    return db.query(Device).all()


@app.get("/api/devices/{device_id}", response_model=DeviceResponse, tags=["Dispositivos"],
         dependencies=[Depends(current_user)])
def get_device(device_id: int, db: Session = Depends(get_db)):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Dispositivo no encontrado")
    return device


@app.put("/api/devices/{device_id}", response_model=DeviceResponse, tags=["Dispositivos"])
def update_device(device_id: int, device_update: DeviceUpdate, db: Session = Depends(get_db),
                  user: User = Depends(SOLO_ADMIN)):
    db_device = db.query(Device).filter(Device.id == device_id).first()
    if not db_device:
        raise HTTPException(status_code=404, detail="Dispositivo no encontrado")
    for key, value in device_update.model_dump(exclude_unset=True).items():
        setattr(db_device, key, value)
    db.commit()
    db.refresh(db_device)
    auditar(db, user.username, "DISPOSITIVO_EDITADO", f"{db_device.hostname}")
    return db_device


@app.delete("/api/devices/{device_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Dispositivos"])
def delete_device(device_id: int, db: Session = Depends(get_db),
                  user: User = Depends(SOLO_ADMIN)):
    db_device = db.query(Device).filter(Device.id == device_id).first()
    if not db_device:
        raise HTTPException(status_code=404, detail="Dispositivo no encontrado")
    nombre = db_device.hostname
    db.delete(db_device)
    db.commit()
    auditar(db, user.username, "DISPOSITIVO_ELIMINADO", nombre)
    return None


# --- SYSLOG ---

@app.post("/api/syslog/", response_model=SyslogEventResponse,
          status_code=status.HTTP_201_CREATED, tags=["Syslog"])
def ingest_syslog(entry: SyslogIn, db: Session = Depends(get_db),
                  user: User = Depends(OPERAR)):
    """Recibe un mensaje Syslog (SIMULADO), lo parsea y lo guarda."""
    try:
        return guardar_evento(db, entry.raw_message, entry.source_ip, "SIMULADO")
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.get("/api/syslog/", response_model=List[SyslogEventResponse], tags=["Syslog"],
         dependencies=[Depends(current_user)])
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
def create_incident(entry: IncidentCreate, db: Session = Depends(get_db),
                    user: User = Depends(OPERAR)):
    if entry.severity not in SEVERIDADES_INCIDENTE:
        raise HTTPException(status_code=422, detail=f"Severidad válida: {SEVERIDADES_INCIDENTE}")
    if not db.query(Device).filter(Device.id == entry.device_id).first():
        raise HTTPException(status_code=404, detail="Dispositivo no encontrado")
    incident = Incident(**entry.model_dump())
    db.add(incident)
    db.commit()
    db.refresh(incident)
    auditar(db, user.username, "INCIDENTE_CREADO", f"#{incident.id} {incident.title}")
    return incident


@app.get("/api/incidents/", response_model=List[IncidentResponse], tags=["Incidentes"],
         dependencies=[Depends(current_user)])
def list_incidents(estado: Optional[str] = Query(None, alias="status"),
                   db: Session = Depends(get_db)):
    q = db.query(Incident)
    if estado:
        q = q.filter(Incident.status == estado)
    return q.order_by(Incident.id.desc()).all()


@app.put("/api/incidents/{incident_id}", response_model=IncidentResponse, tags=["Incidentes"])
def update_incident(incident_id: int, entry: IncidentUpdate, db: Session = Depends(get_db),
                    user: User = Depends(OPERAR)):
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
    auditar(db, user.username, "INCIDENTE_ACTUALIZADO", f"#{incident.id} -> {datos}")
    return incident


# --- DASHBOARD ---

@app.get("/api/dashboard/", tags=["Dashboard"], dependencies=[Depends(current_user)])
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

@app.get("/api/configs/{vendor}", response_class=PlainTextResponse, tags=["Configuraciones"],
         dependencies=[Depends(current_user)])
def get_config(vendor: str, severity: int = Query(6, ge=0, le=7)):
    """Plantilla Syslog comentada para cisco, fortinet o huawei."""
    v = vendor.lower()
    if v not in VENDORS:
        raise HTTPException(status_code=404, detail=f"Fabricante válido: {VENDORS}")
    return generar_config(v, severity=severity)


# --- CONSOLA SIMULADA (SOLO LECTURA) ---

@app.post("/api/console/", response_model=ConsoleOut, tags=["Consola"])
def console(entry: ConsoleIn, db: Session = Depends(get_db), user: User = Depends(OPERAR)):
    """Ejecuta un comando SIMULADO. Solo la allowlist pasa; todo se audita."""
    device = db.query(Device).filter(Device.id == entry.device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Dispositivo no encontrado")
    permitido, salida = ejecutar_comando(device.vendor, device.hostname, entry.command)
    auditar(db, user.username, "CONSOLA", f"{device.hostname}: {entry.command[:200]}",
            "PERMITIDO" if permitido else "BLOQUEADO")
    return {"allowed": permitido, "output": salida}


# --- AUDITORÍA ---

@app.get("/api/audit/", response_model=List[AuditResponse], tags=["Auditoría"],
         dependencies=[Depends(VER_AUDITORIA)])
def list_audit(limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db)):
    return db.query(AuditLog).order_by(AuditLog.id.desc()).limit(limit).all()


# --- APROBACIÓN HUMANA DE ACCIONES (app/approvals.py) ---
app.include_router(approvals_router)


# --- INTERFAZ WEB (carpeta static/): la página es pública, los datos exigen login ---
if os.path.isdir(STATIC_DIR):
    app.mount("/ui", StaticFiles(directory=STATIC_DIR, html=True), name="ui")