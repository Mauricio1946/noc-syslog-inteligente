"""Consola simulada de SOLO LECTURA.

Política: lista permitida (allowlist) por fabricante, con coincidencia EXACTA.
Todo lo que no esté en la lista se BLOQUEA (denegar por defecto). Así, un
comando como "show version; reload" no pasa. Nada se ejecuta en equipos
reales: las salidas son texto simulado.
"""

PALABRAS_PELIGROSAS = ("configure", "conf t", "config", "reload", "reboot",
                       "write", "erase", "delete", "format", "shutdown",
                       "system-view", "save", "undo", "reset", "execute",
                       "set ", "copy", "no ")


def _catalogo(host: str) -> dict:
    return {
        "cisco": {
            "show version": f"[SIMULADO] Cisco IOS XE Software, Version 17.03.04a\nHostname: {host}\nUptime: 42 days, 3 hours",
            "show ip interface brief": "[SIMULADO]\nInterface              IP-Address   Status  Protocol\nGigabitEthernet1/0/1   unassigned   down    down\nGigabitEthernet1/0/2   unassigned   up      up",
            "show logging": "[SIMULADO] Syslog logging: enabled\n  Logging to 192.0.2.10 (udp port 514)\n  Trap logging: level informational",
            "show clock": "[SIMULADO] 12:00:00.000 UTC Tue Oct 13 2026",
        },
        "fortinet": {
            "get system status": f"[SIMULADO] Version: FortiGate v7.2\nHostname: {host}\nOperation Mode: NAT",
            "get system performance status": "[SIMULADO] CPU states: 3% user 2% system 95% idle\nMemory: 41% used",
            "get system interface physical": "[SIMULADO]\nport1: up, speed 1000\nport2: down",
        },
        "huawei": {
            "display version": f"[SIMULADO] Huawei Versatile Routing Platform Software\nVRP (R) software, Version 8.150\nHostname: {host}",
            "display ip interface brief": "[SIMULADO]\nInterface             IP Address   Physical  Protocol\nGigabitEthernet0/0/1  unassigned   down      down\nGigabitEthernet0/0/2  unassigned   up        up",
            "display clock": "[SIMULADO] 2026-10-13 12:00:00 UTC",
            "display logbuffer": "[SIMULADO] Logging buffer configuration and contents: enabled",
        },
    }


def ejecutar_comando(vendor: str, host: str, comando: str):
    """Devuelve (permitido, salida). Nunca toca un equipo real."""
    cmd = " ".join(comando.strip().lower().split())   # normalizar espacios y mayúsculas
    catalogo = _catalogo(host).get(vendor.lower())

    if catalogo is None:
        return False, f"[BLOQUEADO] Fabricante sin catalogo de comandos: {vendor}"

    if cmd in catalogo:
        return True, catalogo[cmd]

    if any(p in cmd for p in PALABRAS_PELIGROSAS):
        return False, "[BLOQUEADO] Comando de modificacion: la consola es de solo lectura."
    return False, "[BLOQUEADO] Comando no incluido en la lista permitida (allowlist)."