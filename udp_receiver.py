"""Receptor Syslog por UDP.

Escucha en un puerto, recibe mensajes y los guarda con la lógica compartida.
Se ejecuta como un programa APARTE del servidor web.

Uso:  python udp_receiver.py
"""
import socket

from app.database import SessionLocal, Base, engine
from app.ingest import guardar_evento
import app.models  # noqa: F401  (registra las tablas)

HOST = "0.0.0.0"     # escucha en todas las interfaces de este equipo
PUERTO = 5514        # el estándar es 514 (requiere administrador)
MAX_BYTES = 2048     # descartar paquetes más grandes


def main():
    Base.metadata.create_all(bind=engine)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # SOCK_DGRAM = UDP
    sock.bind((HOST, PUERTO))
    print(f"Receptor Syslog UDP escuchando en el puerto {PUERTO} (Ctrl+C para salir)")

    recibidos = rechazados = 0
    try:
        while True:
            datos, (ip_origen, _puerto) = sock.recvfrom(MAX_BYTES + 1)

            if len(datos) > MAX_BYTES:
                rechazados += 1
                print(f"[DESCARTADO] paquete demasiado grande desde {ip_origen}")
                continue

            # Los bytes son dato no confiable: decodificar sin romper nunca
            texto = datos.decode("utf-8", errors="replace").strip()

            db = SessionLocal()
            try:
                evento = guardar_evento(db, texto, ip_origen, origin="REAL")
                recibidos += 1
                estado = "conocida" if evento.device_id else "DESCONOCIDA"
                print(f"[OK] id={evento.id} sev={evento.severity} "
                      f"desde {ip_origen} (fuente {estado})")
            except ValueError as e:
                rechazados += 1
                print(f"[RECHAZADO] {ip_origen}: {e}")
            finally:
                db.close()
    except KeyboardInterrupt:
        print(f"\nCerrado. Guardados: {recibidos}, rechazados: {rechazados}")
    finally:
        sock.close()


if __name__ == "__main__":
    main()