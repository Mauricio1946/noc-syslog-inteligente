"""Límite de frecuencia por IP de origen (control de tormentas de eventos).

Guarda en memoria los instantes de los últimos mensajes de cada IP.
Si una IP supera el máximo dentro de la ventana, se limita.
"""
import time
from collections import deque


class LimitadorFrecuencia:
    def __init__(self, maximo: int = 100, ventana: int = 60):
        self.maximo = maximo            # mensajes permitidos por ventana
        self.ventana = ventana          # segundos
        self.registros = {}             # ip -> cola de instantes
        self.avisados = set()           # IPs ya avisadas en esta tormenta

    def revisar(self, ip: str) -> str:
        """Devuelve 'ok', 'primer_exceso' o 'excedido'."""
        ahora = time.monotonic()
        cola = self.registros.setdefault(ip, deque())

        # Olvidar los mensajes que ya salieron de la ventana
        while cola and ahora - cola[0] > self.ventana:
            cola.popleft()

        if len(cola) >= self.maximo:
            if ip not in self.avisados:
                self.avisados.add(ip)
                return "primer_exceso"   # aquí se genera la alerta, una sola vez
            return "excedido"

        cola.append(ahora)
        self.avisados.discard(ip)        # volvió a la normalidad
        return "ok"