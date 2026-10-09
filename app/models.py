from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database import Base

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
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relación con Logs e Incidentes
    logs = relationship("SyslogEvent", back_populates="device", cascade="all, delete-orphan")
    incidents = relationship("Incident", back_populates="device", cascade="all, delete-orphan")

class SyslogEvent(Base):
    """Modelo para Eventos de Syslog (Tratados estrictamente como datos no confiables)."""
    __tablename__ = "syslog_events"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=True)
    facility = Column(Integer, nullable=False)
    severity = Column(Integer, nullable=False, index=True)  # 0 (Emergency) a 7 (Debug)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    raw_message = Column(Text, nullable=False)  # Cadena original recibida
    parsed_program = Column(String(50), nullable=True)

    device = relationship("Device", back_populates="logs")

class Incident(Base):
    """Modelo para Gestión de Incidentes y Auditoría Humana."""
    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(150), nullable=False)
    description = Column(Text, nullable=False)
    severity = Column(String(20), nullable=False)  # Alta, Media, Baja, Crítica
    status = Column(String(20), default="Abierto")  # Abierto, En Progreso, Cerrado
    assigned_to = Column(String(100), default="Sin asignar")
    created_at = Column(DateTime, default=datetime.utcnow)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False)

    device = relationship("Device", back_populates="incidents")