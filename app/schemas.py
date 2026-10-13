from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict

# --- DISPOSITIVOS ---

class DeviceBase(BaseModel):
    hostname: str = Field(..., example="SW-CORE-01")
    ip_address: str = Field(..., example="192.168.1.1")
    vendor: str = Field(..., example="Cisco")  # Cisco, Fortinet, Huawei
    model: str = Field(..., example="Catalyst 9300")
    os_version: str = Field(..., example="17.03.04a")
    location: str = Field(..., example="Data Center - Rack 02")
    status: Optional[str] = "Activo"

class DeviceCreate(DeviceBase):
    pass

class DeviceUpdate(BaseModel):
    hostname: Optional[str] = None
    ip_address: Optional[str] = None
    vendor: Optional[str] = None
    model: Optional[str] = None
    os_version: Optional[str] = None
    location: Optional[str] = None
    status: Optional[str] = None

class DeviceResponse(DeviceBase):
    id: int
    updated_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


# --- SYSLOG ---

class SyslogIn(BaseModel):
    """Mensaje Syslog entrante (SIMULADO por Swagger)."""
    raw_message: str = Field(..., max_length=2048,
        example="<189>Oct 10 01:03:31 SW-CORE-SIMULADO-01 %LINK-3-UPDOWN: Interface Gi1/0/1, changed state to down")
    source_ip: str = Field(..., example="10.0.0.1")

class SyslogEventResponse(BaseModel):
    id: int
    device_id: Optional[int] = None   # None = fuente desconocida
    source_ip: str
    hostname_reported: Optional[str] = None
    facility: int
    severity: int
    timestamp: Optional[datetime] = None
    parsed_program: Optional[str] = None
    message: Optional[str] = None
    origin: str
    repeat_count: int = 1
    last_seen: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


# --- INCIDENTES ---

class IncidentCreate(BaseModel):
    title: str = Field(..., max_length=150, example="Interfaz caída en SW-CORE (SIMULADO)")
    description: str = Field(..., example="Evento Syslog severidad 5 en Gi1/0/1")
    severity: str = Field(..., example="Alta")  # Crítica, Alta, Media, Baja
    device_id: int
    assigned_to: Optional[str] = "Sin asignar"

class IncidentUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    severity: Optional[str] = None
    status: Optional[str] = None       # Abierto, En Progreso, Cerrado
    assigned_to: Optional[str] = None

class IncidentResponse(BaseModel):
    id: int
    title: str
    description: str
    severity: str
    status: str
    assigned_to: str
    created_at: Optional[datetime] = None
    device_id: int
    model_config = ConfigDict(from_attributes=True)


# --- CONSOLA SIMULADA Y AUDITORÍA ---

class ConsoleIn(BaseModel):
    device_id: int
    command: str = Field(..., max_length=200, example="show version")

class ConsoleOut(BaseModel):
    allowed: bool
    output: str

class AuditResponse(BaseModel):
    id: int
    timestamp: Optional[datetime] = None
    actor: str
    action: str
    detail: Optional[str] = None
    result: str
    model_config = ConfigDict(from_attributes=True)