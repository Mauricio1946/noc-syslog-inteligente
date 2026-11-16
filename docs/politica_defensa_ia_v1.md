# Política de defensa frente a acciones de agentes de IA · v1.0.0

NOC Syslog Inteligente · Administración y Gestión de Redes · Periodo 2026-2
Estudiante: Mauricio Ramirez · Docente: Ing. John Harold Pérez Calderón

> Datos y equipos SIMULADOS. Este documento actualiza `politica_defensa_ia.md` (v0.2.0) con los controles del Corte 3.

## 1. Principios

1. **Los logs son datos no confiables.** El sistema extrae campos y compara; nunca interpreta el texto de un mensaje como una orden.
2. **Ninguna acción sobre un equipo se ejecuta sin la aprobación de otra persona.** Un agente puede proponer; decidir y ejecutar corresponde a una persona distinta.
3. **Denegar por defecto.** Lo que no está en una lista permitida se bloquea y se audita.

## 2. Flujo seguro

Evento detectado → validación → propuesta de acción → revisión humana → aprobación → ejecución autorizada → verificación → auditoría. Detalle y diagrama en `docs/diseno.md`.

## 3. Riesgos considerados

| ID | Riesgo | Cómo podría ocurrir con un agente de IA |
|---|---|---|
| A1 | Inyección en logs | Un mensaje contiene texto como "ignora tus instrucciones y ejecuta..." |
| A2 | Inundación de logs | Miles de mensajes para esconder una acción importante |
| A3 | Suplantación de fuente | Un mensaje dice venir de un equipo legítimo pero llega de otra IP |
| A4 | Comando no autorizado | El agente propone un comando que modifica la red |
| A5 | Encadenamiento de comandos | `show version; reload` |
| A6 | Acción sin rastro | Nadie puede reconstruir qué hizo el agente |
| A7 | Hora manipulada | Relojes desincronizados impiden correlacionar |
| A8 | Credenciales robadas o adivinadas | Fuerza bruta contra el acceso a la aplicación |
| A9 | Autoaprobación | Quien propone una acción la aprueba solo |
| A10 | Inundación de solicitudes | El agente genera muchas solicitudes para que la persona apruebe por cansancio |
| A11 | Filtración del token de Telegram | El token aparece en código, repositorio o mensajes de error |
| A12 | Alcance excesivo | Una cuenta ve o hace más de lo que necesita |

## 4. Controles y estado en v1.0.0

| # | Control | Estado | Dónde |
|---|---|---|---|
| 1 | Fuentes autorizadas | Parcial | El inventario define las fuentes; IP desconocida y suplantación generan alerta (no se descarta ni se pone en cuarentena) |
| 2 | Centralizar logs | Implementado | `udp_receiver.py`, `POST /api/syslog/` |
| 3 | Sincronizar la hora por NTP | Parcial | NTP en las plantillas; todo en UTC; las reglas usan la hora de recepción |
| 4 | Severidades que alertan | Parcial | Alertas automáticas por reglas; los incidentes se crean a mano desde el evento |
| 5 | Registrar accesos, fallos y cambios | Implementado | Reglas de fuerza bruta y de cambios, más auditoría de todas las acciones |
| 6 | Detectar comandos fuera de horario, cuentas anómalas y cambios no autorizados | Parcial | Implementado: cambio de configuración fuera de horario y fuerza bruta. Pendiente: cuentas de servicio anómalas |
| 7 | Listas permitidas de dispositivos y comandos | Implementado | `console.py`, `actions.py`, `executor.py` (host permitido y equipo Activo) |
| 8 | Roles, retención, integridad, respaldo y transporte seguro | Parcial | Implementado: roles y respaldo con restauración probada. Pendiente: retención, firma de logs y TLS |
| 9 | Deduplicación, límite de frecuencia y tormentas | Implementado | `ingest.py`, `ratelimit.py` |
| 10 | Logs como datos no confiables | Implementado | Parser y presentación como texto |
| 11 | Aprobación humana antes de ejecutar cambios | Implementado | `approvals.py`: otra persona, vencimiento, tope, revalidación y verificación (ejecución simulada) |
| 12 | Acceso con usuario, contraseña segura y roles | Implementado | `auth.py`, `security.py` |
| 13 | Secretos fuera del código | Implementado | `.env` ignorado por Git; la marcha blanca revisa el repositorio |
| 14 | Auditoría de acciones y denegaciones | Implementado | `audit_log` con el usuario real |

## 5. Riesgo y control

| Riesgo | Control | Efecto |
|---|---|---|
| A1 | Parser que solo extrae campos; texto, no HTML | El contenido del log no dispara acciones |
| A2 | Deduplicación y límite de frecuencia con una sola alerta | La base no se llena; el problema se ve una vez |
| A3 | La IP sale de la conexión; el nombre del mensaje se contrasta con el inventario | Alertas `HOSTNAME_NO_COINCIDE` y `POSIBLE_SUPLANTACION` |
| A4 | Lista permitida y catálogo cerrado | Se bloquea y se audita |
| A5 | Coincidencia exacta y parámetros con expresión regular | El comando encadenado no pasa |
| A6 | Auditoría con el usuario real | Toda acción deja huella |
| A7 | NTP y UTC; las reglas usan la hora de recepción | La hora del mensaje no engaña a la regla de horario |
| A8 | scrypt, bloqueo tras 5 fallos, mensaje genérico, alerta de fuerza bruta en los equipos | Frena el adivinado de claves |
| A9 | Quien propone no puede aprobar, ni siquiera un admin | Se necesita una segunda persona |
| A10 | Tope de 5 pendientes y vencimiento a los 30 minutos | Limita el cansancio de aprobación |
| A11 | Token solo en `.env`; no se imprime en errores; revisión automática del repositorio | El token no sale del equipo |
| A12 | Tres roles, validación en el servidor y denegaciones auditadas | Mínimo privilegio |

## 6. Pruebas

Se ejecutan con `python -m unittest discover -s tests -v` (27 pruebas del núcleo) y `python marcha_blanca.py` (seguridad, defensa, carga, respaldo, recuperación y secretos). Los resultados de cada ejecución quedan en `docs/bitacora_marcha_blanca.md`.

| Prueba | Resultado esperado |
|---|---|
| API sin sesión | 401 |
| Login con credenciales falsas | 401 |
| Operador intenta borrar un equipo o ver la Auditoría | 403 en ambos |
| Autoaprobación de una solicitud | 403 y `AUTOAPROBACION_DENEGADA` en la auditoría |
| Interfaz `Gi1/0/5; reload` en una solicitud | 422 y `SOLICITUD_BLOQUEADA` |
| Mensaje de un equipo que dice ser otro | Alerta `HOSTNAME_NO_COINCIDE` |
| Cinco fallos de autenticación seguidos | Alerta `POSIBLE_FUERZA_BRUTA` (Crítica) |
| Ráfaga de 150 mensajes | 100 guardados, una alerta de tormenta |
| Aprobar una acción sobre un equipo en Mantenimiento | Rechazada: el ejecutor se niega |
| Respaldo y restauración de prueba | Integridad ok y mismas tablas y filas |
| Revisión del repositorio | Sin `.env`, sin bases de datos, sin tokens |

## 7. Limitaciones y trabajo futuro

- UDP permite falsificar la IP de origen; la mitigación real es TLS (RFC 5425) o una red de gestión aislada.
- Sin HTTPS ni doble factor de autenticación para la aplicación.
- El SSH real queda preparado, no implementado: requiere un equipo de laboratorio para probarlo.
- Una fuente desconocida se alerta, pero no se pone en cuarentena.
- Sin firma ni retención de logs; el límite de frecuencia se reinicia con el receptor.
- Falta detectar cuentas de servicio anómalas.

## 8. Bibliografía

IETF RFC 5424, RFC 3164, RFC 5425 y RFC 5737. NIST, Artificial Intelligence Risk Management Framework. OWASP, Agentic AI – Threats and Mitigations. Python Software Foundation, documentación de `hashlib.scrypt`. Telegram, Bot API (`sendMessage`).
