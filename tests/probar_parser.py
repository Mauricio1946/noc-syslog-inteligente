"""Prueba manual del parser. Todos los mensajes son SIMULADOS."""
from app.syslog_parser import parse_rfc3164

MENSAJES = [
    "<189>Oct 10 01:03:31 SW-CORE-SIMULADO-01 %LINK-3-UPDOWN: Interface Gi1/0/1, changed state to down",
    "<34>Oct 10 01:05:00 FW-SIMULADO-01 sshd[412]: Failed password for admin",
    "<999>Oct 10 01:06:00 EQUIPO-X test: PRI invalido",
    "esto no es syslog",
]

for texto in MENSAJES:
    print("ENTRADA:", texto)
    try:
        resultado = parse_rfc3164(texto)
        for campo, valor in resultado.items():
            if campo != "raw":
                print(f"   {campo}: {valor}")
    except ValueError as e:
        print("   RECHAZADO:", e)
    print()