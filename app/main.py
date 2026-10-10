from typing import List
from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import engine, Base, get_db
from app.models import Device
from app.schemas import DeviceCreate, DeviceUpdate, DeviceResponse

# Crear las tablas en la base de datos si no existen
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="NOC Syslog Inteligente - API",
    version="0.2.0",
    description="Sistema de Monitoreo NOC y Gestión de Syslog para Redes"
)

@app.get("/", tags=["General"])
def root():
    return {"message": "Bienvenido a la API del NOC Syslog Inteligente v0.2.0"}

# --- ENDPOINTS CRUD DE DISPOSITIVOS ---

@app.post("/api/devices/", response_model=DeviceResponse, status_code=status.HTTP_201_CREATED, tags=["Dispositivos"])
def create_device(device: DeviceCreate, db: Session = Depends(get_db)):
    """Registrar un nuevo dispositivo de red en el inventario."""
    db_device = db.query(Device).filter(Device.ip_address == device.ip_address).first()
    if db_device:
        raise HTTPException(
            status_code=400, 
            detail=f"Ya existe un dispositivo registrado con la IP {device.ip_address}"
        )
    
    new_device = Device(**device.model_dump())
    db.add(new_device)
    db.commit()
    db.refresh(new_device)
    return new_device

@app.get("/api/devices/", response_model=List[DeviceResponse], tags=["Dispositivos"])
def list_devices(db: Session = Depends(get_db)):
    """Obtener el inventario completo de dispositivos de red."""
    return db.query(Device).all()

@app.get("/api/devices/{device_id}", response_model=DeviceResponse, tags=["Dispositivos"])
def get_device(device_id: int, db: Session = Depends(get_db)):
    """Obtener los detalles de un dispositivo específico por ID."""
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Dispositivo no encontrado")
    return device

@app.put("/api/devices/{device_id}", response_model=DeviceResponse, tags=["Dispositivos"])
def update_device(device_id: int, device_update: DeviceUpdate, db: Session = Depends(get_db)):
    """Actualizar la información de un dispositivo registrado."""
    db_device = db.query(Device).filter(Device.id == device_id).first()
    if not db_device:
        raise HTTPException(status_code=404, detail="Dispositivo no encontrado")
    
    update_data = device_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_device, key, value)
    
    db.commit()
    db.refresh(db_device)
    return db_device

@app.delete("/api/devices/{device_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Dispositivos"])
def delete_device(device_id: int, db: Session = Depends(get_db)):
    """Eliminar un dispositivo del inventario."""
    db_device = db.query(Device).filter(Device.id == device_id).first()
    if not db_device:
        raise HTTPException(status_code=404, detail="Dispositivo no encontrado")
    
    db.delete(db_device)
    db.commit()
    return None