from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field

# --- ESQUEMAS PARA DISPOSITIVOS ---

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

    class Config:
        from_attributes = True