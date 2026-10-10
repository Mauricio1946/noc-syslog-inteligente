"""Constantes del protocolo Syslog (RFC 5424, sección 6.2.1)."""

# Las 24 facilities: número -> nombre
FACILITIES = {
    0: "kern", 1: "user", 2: "mail", 3: "daemon",
    4: "auth", 5: "syslog", 6: "lpr", 7: "news",
    8: "uucp", 9: "cron", 10: "authpriv", 11: "ftp",
    12: "ntp", 13: "audit", 14: "alert", 15: "clock",
    16: "local0", 17: "local1", 18: "local2", 19: "local3",
    20: "local4", 21: "local5", 22: "local6", 23: "local7",
}

# Las 8 severidades: número -> nombre (0 es la más grave)
SEVERITIES = {
    0: "Emergency", 1: "Alert", 2: "Critical", 3: "Error",
    4: "Warning", 5: "Notice", 6: "Informational", 7: "Debug",
}

def decode_pri(pri: int) -> tuple[int, int]:
    """Separa el valor PRI en (facility, severity).

    Lanza ValueError si el PRI está fuera del rango válido (0 a 191).
    """
    if not 0 <= pri <= 191:
        raise ValueError(f"PRI fuera de rango: {pri}")
    facility = pri // 8   # división entera
    severity = pri % 8    # residuo
    return facility, severity