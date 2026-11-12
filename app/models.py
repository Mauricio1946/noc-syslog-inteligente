from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database import Base


def utcnow():
    """Hora actual en UTC (forma moderna, sin advertencias)."""
    return datetime.now(timezone.utc)


class Device(Base):
    """Modelo de Inventario de Dispositivos de Red."""
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    hostname = Column(String(100), nullable=False)
    ip_address = Column(String(45), unique=True, nullable=False, index=True)
    vendor = Column(String(50), nullable=False)  # Cisco, Fortinet, Huawei
    model = Column(String(50), nullable=False)
    os_version = Column(String(50), nullable=False)
    location = Column(String(100), nullable=False)
    status = Column(String(20), default="Activo")  # Activo, Inactivo, Mantenimiento
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    logs = relationship("SyslogEvent", back_populates="device", cascade="all, delete-orphan")
    incidents = relationship("Incident", back_populates="device", cascade="all, delete-orphan")


class SyslogEvent(Base):
    """Evento Syslog. El contenido es DATO no confiable, nunca una instrucción."""
    __tablename__ = "syslog_events"

    id = Column(Integer, primary_key=True, index=True)
    # nullable=True: puede llegar un log de un equipo que no está en el inventario
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=True)
    source_ip = Column(String(45), nullable=False, index=True)       # IP real del emisor
    hostname_reported = Column(String(100), nullable=True)           # nombre que dice tener
    facility = Column(Integer, nullable=False)
    severity = Column(Integer, nullable=False, index=True)           # 0 (Emergency) a 7 (Debug)
    timestamp = Column(DateTime, default=utcnow, index=True)         # hora de recepción (UTC)
    repeat_count = Column(Integer, nullable=False, default=1)        # veces que se repitió
    last_seen = Column(DateTime, default=utcnow, index=True)         # última vez que llegó
    parsed_program = Column(String(50), nullable=True)
    message = Column(Text, nullable=True)                            # texto ya separado
    raw_message = Column(Text, nullable=False)                       # cadena original
    origin = Column(String(10), nullable=False, default="SIMULADO")  # SIMULADO, REAL o SISTEMA

    device = relationship("Device", back_populates="logs")


class Incident(Base):
    """Gestión de incidentes: creación, asignación, seguimiento y cierre."""
    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(150), nullable=False)
    description = Column(Text, nullable=False)
    severity = Column(String(20), nullable=False)  # Crítica, Alta, Media, Baja
    status = Column(String(20), default="Abierto")  # Abierto, En Progreso, Cerrado
    assigned_to = Column(String(100), default="Sin asignar")
    created_at = Column(DateTime, default=utcnow)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False)

    device = relationship("Device", back_populates="incidents")


class AuditLog(Base):
    """Auditoría: quién hizo qué, cuándo y con qué resultado."""
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=utcnow, index=True)
    actor = Column(String(100), nullable=False)    # usuario autenticado
    action = Column(String(50), nullable=False)    # INCIDENTE_CREADO, CONSOLA, ...
    detail = Column(Text, nullable=True)
    result = Column(String(20), nullable=False)    # OK, PERMITIDO, BLOQUEADO, DENEGADO


class User(Base):
    """Usuario del NOC. La contraseña NUNCA se guarda: solo su hash scrypt."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(30), unique=True, nullable=False, index=True)
    password_hash = Column(String(300), nullable=False)
    role = Column(String(20), nullable=False)            # admin, operador, auditor
    active = Column(Integer, nullable=False, default=1)  # 1 = activo, 0 = deshabilitado
    failed_attempts = Column(Integer, nullable=False, default=0)
    locked_until = Column(DateTime, nullable=True)       # bloqueo temporal por intentos fallidos
    created_at = Column(DateTime, default=utcnow)


class UserSession(Base):
    """Sesión iniciada. Se guarda el hash del token, no el token."""
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    token_hash = Column(String(64), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=utcnow)
    expires_at = Column(DateTime, nullable=False)

    user = relationship("User")