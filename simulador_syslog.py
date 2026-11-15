"""Simulador de equipos de red: envía mensajes Syslog de PRUEBA (SIMULADOS) por UDP al receptor.

Uso:  python simulador_syslog.py <escenario>

Escenarios:
  nombre     un equipo dice ser otro               -> alerta HOSTNAME_NO_COINCIDE
  fuerza     5 fallos de autenticación seguidos    -> alerta POSIBLE_FUERZA_BRUTA
  cambio     cambio de configuración               -> alerta solo si es fuera de horario
  normal     un mensaje normal                     -> sin alerta
  repetido   5 mensajes idénticos                  -> deduplicación (un evento, contador 5)
  tormenta   150 mensajes distintos                -> control de tormentas

El receptor (python udp_receiver.py) debe estar corriendo. Todo el contenido es SIMULADO.
"""
import socket
import sys

DESTINO = ("127.0.0.1", 5514)


def mensajes(nombre):
    if nombre == "nombre":
        return ["<189>Nov 13 10:00:00 SW-CORE-SIMULADO-01 %LINK-3-UPDOWN: Interface Gi1/0/31, changed state to down"]
    if nombre == "fuerza":
        return [f"<35>Nov 13 10:01:00 LAB-LOCAL-SIMULADO sshd[412]: Failed password for admin attempt {i}"
                for i in range(5)]
    if nombre == "cambio":
        return ["<189>Nov 13 10:02:00 LAB-LOCAL-SIMULADO %SYS-5-CONFIG_I: Configured from console by admin"]
    if nombre == "normal":
        return ["<190>Nov 13 10:04:00 LAB-LOCAL-SIMULADO %LINEPROTO-6-UPDOWN: Line protocol on Interface Gi1/0/2, changed state to up"]
    if nombre == "repetido":
        return ["<187>Nov 13 10:05:00 LAB-LOCAL-SIMULADO %LINK-3-UPDOWN: Interface Gi1/0/9, changed state to down"] * 5
    if nombre == "tormenta":
        return [f"<187>Nov 13 10:06:00 LAB-LOCAL-SIMULADO test: mensaje numero {i}" for i in range(150)]
    return None


def main():
    lista = mensajes(sys.argv[1]) if len(sys.argv) == 2 else None
    if lista is None:
        print(__doc__)
        return 1
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    for m in lista:
        s.sendto(m.encode("utf-8"), DESTINO)
    print(f"Enviados {len(lista)} mensaje(s) SIMULADOS a {DESTINO[0]}:{DESTINO[1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())