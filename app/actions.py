"""Catálogo cerrado de acciones del flujo de aprobación (ejecución SIMULADA).

Una acción es una plantilla: la persona elige la acción y el valor de sus
parámetros, nunca escribe un comando libre. Cada parámetro se valida con una
expresión regular estricta (fullmatch), así que nada permite encadenar otro comando.

Los comandos de cada fabricante son una referencia: verificar con la guía oficial
y probar en laboratorio antes de usarlos en un equipo real.
"""
import re
from typing import Dict, List

ACCIONES: Dict[str, dict] = {
    "apagar_interfaz": {
        "descripcion": "Apagar (shutdown) una interfaz para aislar un puerto",
        "riesgo": "cambio",
        "parametros": {
            "interfaz": "Interfaz: Gi1/0/5 (Cisco), GigabitEthernet0/0/5 (Huawei) o port5 (Fortinet)",
        },
    },
    "encender_interfaz": {
        "descripcion": "Encender (no shutdown) una interfaz apagada",
        "riesgo": "cambio",
        "parametros": {
            "interfaz": "Interfaz: Gi1/0/5 (Cisco), GigabitEthernet0/0/5 (Huawei) o port5 (Fortinet)",
        },
    },
}

# Formato válido del nombre de interfaz por fabricante
INTERFAZ = {
    "cisco": re.compile(r"(?:Gi|Te|Fa|GigabitEthernet|TenGigabitEthernet|FastEthernet)\d{1,2}(?:/\d{1,3}){1,3}"),
    "huawei": re.compile(r"(?:GigabitEthernet|XGigabitEthernet|Ethernet)\d{1,2}(?:/\d{1,2}){2}"),
    "fortinet": re.compile(r"(?:port|wan|lan|dmz|internal)\d{0,2}"),
}

PLANTILLAS = {
    "cisco": {
        "apagar_interfaz": ["configure terminal", "interface {interfaz}", "shutdown", "end"],
        "encender_interfaz": ["configure terminal", "interface {interfaz}", "no shutdown", "end"],
    },
    "fortinet": {
        "apagar_interfaz": ["config system interface", "edit {interfaz}", "set status down", "next", "end"],
        "encender_interfaz": ["config system interface", "edit {interfaz}", "set status up", "next", "end"],
    },
    "huawei": {
        "apagar_interfaz": ["system-view", "interface {interfaz}", "shutdown", "quit", "return"],
        "encender_interfaz": ["system-view", "interface {interfaz}", "undo shutdown", "quit", "return"],
    },
}


def fabricantes_de(accion: str) -> List[str]:
    """Fabricantes para los que existe la acción."""
    return [v for v in PLANTILLAS if accion in PLANTILLAS[v]]


def construir_comandos(vendor: str, accion: str, params: Dict[str, str]) -> List[str]:
    """Valida la acción y sus parámetros y devuelve los comandos que se aplicarían.

    Lanza ValueError con un mensaje claro si algo no cumple.
    """
    v = (vendor or "").lower()
    if accion not in ACCIONES:
        raise ValueError("Acción no permitida: no está en el catálogo")
    plantilla = PLANTILLAS.get(v, {}).get(accion)
    if plantilla is None:
        raise ValueError(f"La acción no está disponible para el fabricante {vendor}")

    esperados = set(ACCIONES[accion]["parametros"])
    if set(params) != esperados:
        raise ValueError("Parámetros inválidos: se esperan " + ", ".join(sorted(esperados)))

    valores = {}
    for nombre in esperados:
        valor = str(params[nombre]).strip()
        if nombre == "interfaz" and not INTERFAZ[v].fullmatch(valor):
            raise ValueError(f"Nombre de interfaz inválido para {vendor}")
        valores[nombre] = valor
    return [linea.format(**valores) for linea in plantilla]


def simular_ejecucion(host: str, comandos: List[str]) -> str:
    """Salida SIMULADA: no se toca ningún equipo real."""
    lineas = [f"[SIMULADO] {host}: no se tocó ningún equipo real. Se habrían aplicado:"]
    lineas += [f"  {host}# {c}" for c in comandos]
    lineas.append("[SIMULADO] Resultado: cambio aplicado correctamente.")
    return "\n".join(lineas)