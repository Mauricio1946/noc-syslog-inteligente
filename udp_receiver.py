"""Receptor Syslog por UDP, con límite de frecuencia por fuente.

Se ejecuta como un programa APARTE del servidor web.
Uso:  python udp_receiver.py
"""
import socket

from app.database import SessionLocal, Base, engine
from app.ingest import guardar_evento, guardar_alerta_tormenta
from app.ratelimit import LimitadorFrecuencia
import app.models  # noqa: F401  (registra las tablas)

HOST = "0.0.0.0"     # escucha en todas las interfaces de este equipo
PUERTO = 5514        # el estándar es 514 (requiere administrador)
MAX_BYTES = 2048     # descartar paquetes más grandes
MAX_POR_VENTANA = 100
VENTANA_SEGUNDOS = 60


def main():
    Base.metadata.create_all(bind=engine)
    limitador = LimitadorFrecuencia(MAX_POR_VENTANA, VENTANA_SEGUNDOS)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # SOCK_DGRAM = UDP
    sock.bind((HOST, PUERTO))
    sock.settimeout(1.0)  # despertar cada 1 s para poder atender Ctrl+C en Windows
    print(f"Receptor Syslog UDP escuchando en el puerto {PUERTO} (Ctrl+C para salir)")
    print(f"Límite: {MAX_POR_VENTANA} mensajes por {VENTANA_SEGUNDOS} s por IP")

    recibidos = rechazados = limitados = 0
    try:
        while True:
            try:
                datos, (ip_origen, _puerto) = sock.recvfrom(MAX_BYTES + 1)
            except socket.timeout:
                continue  # nada llegó en 1 s: volver a esperar

            if len(datos) > MAX_BYTES:
                rechazados += 1
                print(f"[DESCARTADO] paquete demasiado grande desde {ip_origen}")
                continue

            # Control de tormentas: se revisa ANTES de procesar el mensaje
            veredicto = limitador.revisar(ip_origen)
            if veredicto != "ok":
                limitados += 1
                if veredicto == "primer_exceso":
                    db = SessionLocal()
                    try:
                        guardar_alerta_tormenta(db, ip_origen,
                                                MAX_POR_VENTANA, VENTANA_SEGUNDOS)
                    finally:
                        db.close()
                    print(f"[TORMENTA] {ip_origen} superó el límite; alerta guardada")
                continue

            # Los bytes son dato no confiable: decodificar sin romper nunca
            texto = datos.decode("utf-8", errors="replace").strip()

            db = SessionLocal()
            try:
                evento = guardar_evento(db, texto, ip_origen, origin="REAL")
                recibidos += 1
                estado = "conocida" if evento.device_id else "DESCONOCIDA"
                if evento.repeat_count > 1:
                    print(f"[REPETIDO x{evento.repeat_count}] id={evento.id} desde {ip_origen}")
                else:
                    print(f"[OK] id={evento.id} sev={evento.severity} "
                          f"desde {ip_origen} (fuente {estado})")
            except ValueError as e:
                rechazados += 1
                print(f"[RECHAZADO] {ip_origen}: {e}")
            finally:
                db.close()
    except KeyboardInterrupt:
        print(f"\nCerrado. Guardados: {recibidos}, rechazados: {rechazados}, "
              f"limitados: {limitados}")
    finally:
        sock.close()


if __name__ == "__main__":
    main()