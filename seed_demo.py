"""Carga datos de DEMOSTRACION. TODO es SIMULADO (no hay equipos reales).

Hace tres cosas:
  1. Borra los eventos de prueba de la tormenta (programa "test").
  2. Registra equipos de ejemplo Fortinet y Huawei si no existen.
  3. Carga eventos Syslog variados, marcados con origin = SIMULADO.

Uso:  python seed_demo.py
"""
from app.database import SessionLocal, Base, engine
import app.models  # noqa: F401  (registra las tablas)
from app.models import Device, SyslogEvent
from app.ingest import guardar_evento

# IPs de equipos de ejemplo. Las IPs "externas" usan el rango de
# documentacion 192.0.2.0/24 (RFC 5737): no son direcciones reales.
EQUIPOS = [
    dict(hostname="FW-PERIMETRO-SIMULADO", ip_address="10.0.0.2", vendor="Fortinet",
         model="FortiGate 60F", os_version="7.2.5", location="Perimetro (SIMULADO)",
         status="Activo"),
    dict(hostname="RT-BORDE-SIMULADO", ip_address="10.0.0.3", vendor="Huawei",
         model="AR6140", os_version="V800R021", location="Sala de comunicaciones (SIMULADO)",
         status="Mantenimiento"),
]

# (IP de origen, mensaje Syslog RFC 3164). PRI = facility*8 + severidad
EVENTOS = [
    # --- Cisco (10.0.0.1), local7 = 184 + severidad ---
    ("10.0.0.1", "<186>Oct 13 09:00:00 SW-CORE-SIMULADO-01 %PLATFORM-2-PS_FAIL: Power supply 2 failed"),
    ("10.0.0.1", "<187>Oct 13 09:01:10 SW-CORE-SIMULADO-01 %LINK-3-UPDOWN: Interface Gi1/0/7, changed state to down"),
    ("10.0.0.1", "<188>Oct 13 09:02:20 SW-CORE-SIMULADO-01 %SPANTREE-4-BLOCK_PVID_LOCAL: Blocking Gi1/0/5 on VLAN0010"),
    ("10.0.0.1", "<189>Oct 13 09:03:30 SW-CORE-SIMULADO-01 %SYS-5-CONFIG_I: Configured from console by admin"),
    ("10.0.0.1", "<190>Oct 13 09:04:40 SW-CORE-SIMULADO-01 %LINEPROTO-6-UPDOWN: Line protocol on Interface Gi1/0/2, changed state to up"),
    ("10.0.0.1", "<35>Oct 13 09:05:50 SW-CORE-SIMULADO-01 sshd[312]: Failed password for admin from 192.0.2.99"),
    ("10.0.0.1", "<37>Oct 13 09:06:00 SW-CORE-SIMULADO-01 sshd[311]: Accepted publickey for admin from 192.0.2.50"),
    # --- Fortinet (10.0.0.2) ---
    ("10.0.0.2", "<185>Oct 13 09:10:00 FW-PERIMETRO-SIMULADO fortigate: Admin login failed 5 times from 192.0.2.99"),
    ("10.0.0.2", "<186>Oct 13 09:11:00 FW-PERIMETRO-SIMULADO fortigate: HA member lost heartbeat"),
    ("10.0.0.2", "<188>Oct 13 09:12:00 FW-PERIMETRO-SIMULADO fortigate: CPU usage high 91 percent"),
    ("10.0.0.2", "<189>Oct 13 09:13:00 FW-PERIMETRO-SIMULADO fortigate: Policy 12 changed by admin"),
    ("10.0.0.2", "<190>Oct 13 09:14:00 FW-PERIMETRO-SIMULADO fortigate: Session closed policyid=12"),
    # --- Huawei (10.0.0.3) ---
    ("10.0.0.3", "<187>Oct 13 09:20:00 RT-BORDE-SIMULADO ifnet: Interface GigabitEthernet0/0/1 changed to Down"),
    ("10.0.0.3", "<188>Oct 13 09:21:00 RT-BORDE-SIMULADO ospf: Neighbor 192.0.2.1 state changed from Full to Down"),
    ("10.0.0.3", "<189>Oct 13 09:22:00 RT-BORDE-SIMULADO cli: Command display version executed by admin"),
    ("10.0.0.3", "<190>Oct 13 09:23:00 RT-BORDE-SIMULADO ssh: User admin logged in from 192.0.2.50"),
    ("10.0.0.3", "<35>Oct 13 09:24:00 RT-BORDE-SIMULADO ssh: Failed login for admin from 192.0.2.99"),
    # --- Fuente desconocida (IP que no esta en el inventario) ---
    ("10.9.9.9", "<34>Oct 13 09:30:00 FW-DESCONOCIDO sshd[500]: Failed password for root from 192.0.2.99"),
]


def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        borrados = (db.query(SyslogEvent)
                    .filter(SyslogEvent.parsed_program == "test")
                    .delete(synchronize_session=False))
        db.commit()
        print(f"Eventos de prueba de tormenta borrados: {borrados}")

        for e in EQUIPOS:
            if not db.query(Device).filter(Device.ip_address == e["ip_address"]).first():
                db.add(Device(**e))
                print(f"Equipo creado: {e['hostname']}")
        db.commit()

        n = 0
        for ip, texto in EVENTOS:
            guardar_evento(db, texto, ip, origin="SIMULADO")
            n += 1
        print(f"Eventos SIMULADOS cargados: {n}")
    finally:
        db.close()


if __name__ == "__main__":
    main()