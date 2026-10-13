"""Generador de configuraciones Syslog comentadas (PLANTILLAS).

Direcciones de ejemplo del rango de documentación RFC 5737 (192.0.2.0/24):
NO son IPs reales. Verificar cada comando contra la guía oficial del
fabricante y probar en laboratorio antes de aplicar en un equipo real.
"""

VENDORS = ("cisco", "fortinet", "huawei")

SERVIDOR_EJEMPLO = "192.0.2.10"   # servidor NOC (ejemplo)
NTP_EJEMPLO = "192.0.2.11"        # servidor NTP (ejemplo)

NIVEL_CISCO = {0: "emergencies", 1: "alerts", 2: "critical", 3: "errors",
               4: "warnings", 5: "notifications", 6: "informational", 7: "debugging"}
NIVEL_FORTI = {0: "emergency", 1: "alert", 2: "critical", 3: "error",
               4: "warning", 5: "notification", 6: "information", 7: "debug"}
NIVEL_HUAWEI = {0: "emergencies", 1: "alert", 2: "critical", 3: "error",
                4: "warning", 5: "notification", 6: "informational", 7: "debugging"}


def generar_config(vendor: str, severity: int = 6,
                   servidor: str = SERVIDOR_EJEMPLO, puerto: int = 514) -> str:
    """Devuelve la plantilla de Syslog del fabricante indicado."""
    if vendor == "cisco":
        nivel = NIVEL_CISCO[severity]
        return f"""! === Syslog para Cisco IOS / IOS-XE (PLANTILLA) ===
! Verificar con la guia oficial "System Message Logging" antes de aplicar.

! 1. Hora sincronizada por NTP: sin hora correcta los logs no se pueden correlacionar
ntp server {NTP_EJEMPLO}

! 2. Marcas de tiempo con milisegundos y zona horaria
service timestamps log datetime msec localtime show-timezone

! 3. Enviar los logs al servidor NOC por UDP
logging host {servidor} transport udp port {puerto}

! 4. Nivel minimo a enviar: severidad {severity} ({nivel}) y mas graves
logging trap {nivel}

! 5. Facility con la que salen los mensajes
logging facility local7

! 6. Origen estable de los mensajes (la IP identifica al equipo en el NOC)
logging source-interface Loopback0
"""
    if vendor == "fortinet":
        nivel = NIVEL_FORTI[severity]
        return f"""# === Syslog para FortiGate / FortiOS (PLANTILLA) ===
# Verificar con "FortiGate CLI Reference: log syslogd setting / filter".

# 1. Destino de los logs (servidor NOC)
config log syslogd setting
    set status enable
    set server "{servidor}"
    set mode udp
    set port {puerto}
    # 2. Facility con la que salen los mensajes
    set facility local7
    set format default
end

# 3. Nivel minimo a enviar: severidad {severity} ({nivel}) y mas graves
config log syslogd filter
    set severity {nivel}
end

# 4. La hora debe sincronizarse por NTP (config system ntp) para correlacionar eventos
"""
    # huawei
    nivel = NIVEL_HUAWEI[severity]
    return f"""# === Syslog para Huawei VRP (PLANTILLA) ===
# Verificar con "Command Reference: info-center loghost".

system-view
 # 1. Hora sincronizada por NTP
 ntp-service unicast-server {NTP_EJEMPLO}

 # 2. Activar el centro de informacion y sellar los logs con fecha
 info-center enable
 info-center timestamp log date

 # 3. Destino de los logs (servidor NOC) y facility
 info-center loghost {servidor} facility local7 port {puerto}

 # 4. Nivel minimo a enviar: severidad {severity} ({nivel}) y mas graves
 info-center source default channel loghost log level {nivel}
return
"""