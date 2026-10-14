# Política inicial de defensa frente a acciones de agentes de IA

NOC Syslog Inteligente · v0.2.0 · Administración y Gestión de Redes · Periodo 2026-2
Estudiante: Mauricio [Apellido] · Docente: Ing. John Harold Pérez Calderón

> Datos y equipos SIMULADOS. Esta política describe los controles del MVP y deja explícito qué queda pendiente para el Corte 3.

## 1. Pregunta de investigación

¿Cómo puede Syslog, mediante políticas explícitas, ayudar a detectar, contener y mitigar acciones maliciosas o no autorizadas ejecutadas por agentes de inteligencia artificial?

## 2. Respuesta resumida

Syslog es el registro que los propios equipos generan de lo que ocurre en ellos. Si todos los equipos envían sus logs a un punto central, con hora sincronizada y con fuentes autorizadas, cualquier acción de un agente (un login, un cambio de configuración, un comando) deja una huella que alguien ajeno al agente puede revisar. Una política explícita define qué se acepta, qué se alerta y qué se bloquea, de modo que el agente no pueda decidir por sí mismo qué es normal.

Dos principios guían todo el diseño:

1. **Los logs son datos no confiables.** Un atacante, o un equipo comprometido, controla el texto de los mensajes. Por eso el sistema solo extrae campos del mensaje y lo muestra como texto. Nunca lo interpreta como una instrucción para el sistema ni para una IA.
2. **Ninguna acción sobre un equipo se ejecuta sin revisión humana.** El agente puede proponer, pero aprobar y ejecutar corresponde a una persona.

## 3. Amenazas consideradas

| ID | Amenaza | Cómo podría ocurrir con un agente de IA |
|---|---|---|
| A1 | Inyección en logs | Un mensaje contiene texto como "ignora tus instrucciones y ejecuta..." esperando que un agente lo obedezca |
| A2 | Inundación de logs | El agente (o un equipo con falla) genera miles de mensajes para esconder una acción importante |
| A3 | Suplantación de fuente | Un mensaje dice venir de un equipo legítimo, pero llega de otra IP |
| A4 | Comando no autorizado | El agente propone o intenta ejecutar un comando que modifica la red |
| A5 | Encadenamiento de comandos | Un comando permitido se usa como puerta para otro, por ejemplo `show version; reload` |
| A6 | Acción sin rastro | El agente actúa y nadie puede reconstruir qué hizo |
| A7 | Hora manipulada | Relojes desincronizados impiden correlacionar eventos entre equipos |

## 4. Flujo seguro obligatorio

Evento detectado → validación → propuesta de acción → revisión humana → aprobación → ejecución autorizada → verificación → auditoría.

Si la validación falla, el evento o comando se rechaza o se bloquea y queda auditado. En el MVP la ejecución es solo simulada. El detalle por paso está en `docs/diseno.md`.

## 5. Controles y su estado en v0.2.0

| # | Control (según las orientaciones del proyecto) | Estado | Dónde está |
|---|---|---|---|
| 1 | Definir fuentes autorizadas para enviar eventos | Parcial | El inventario define los equipos conocidos. Un evento de IP no registrada se guarda marcado como fuente desconocida (`device_id` nulo) y se cuenta en el dashboard. Aún no se descarta |
| 2 | Centralizar los logs de equipos y aplicaciones | Implementado | `udp_receiver.py` (UDP 5514) y `POST /api/syslog/` |
| 3 | Sincronizar la hora por NTP | Parcial | Las plantillas de configuración incluyen NTP. El sistema guarda todo en UTC |
| 4 | Definir qué severidades generan alertas o incidentes | Parcial | Las severidades 0 a 2 se cuentan como críticas en el dashboard. Los incidentes se crean manualmente desde un evento. La creación automática queda para el Corte 3 |
| 5 | Registrar accesos, fallos de autenticación y cambios de configuración | Parcial | Se reciben y clasifican esos mensajes (facility auth, `%SYS-5-CONFIG_I`). No hay reglas de detección propias todavía |
| 6 | Detectar comandos fuera de horario, cuentas de servicio anómalas o cambios no autorizados | Pendiente | Corte 3 |
| 7 | Listas permitidas de dispositivos y de comandos | Implementado (comandos) | `app/console.py`: lista permitida por fabricante, coincidencia exacta, denegar por defecto. Lista de dispositivos: el comando solo se acepta para equipos del inventario |
| 8 | Control de acceso por roles, retención, integridad, respaldo y transporte seguro | Pendiente | Sin autenticación en el MVP (actor fijo en la auditoría). TLS (RFC 5425) en el Corte 3 |
| 9 | Deduplicación, límite de frecuencia y control de tormentas | Implementado | `app/ingest.py` (agrupa idénticos en 60 s) y `app/ratelimit.py` (100 mensajes en 60 s por IP) |
| 10 | Tratar los logs como datos no confiables | Implementado | El parser solo extrae campos con expresiones regulares, limita el tamaño y rechaza formatos inválidos. La interfaz inserta los textos como texto, no como HTML |
| 11 | Aprobación humana antes de ejecutar cambios | Parcial | No existe ejecución real. La consola es de solo lectura. El estado de los incidentes lo cambia una persona |

## 6. Cómo cada control responde a una amenaza

| Amenaza | Control que la contiene | Efecto |
|---|---|---|
| A1 Inyección en logs | Parser que solo extrae campos; presentación como texto; el sistema no tiene ninguna función que interprete el mensaje como orden | El contenido del log no puede disparar acciones |
| A2 Inundación | Deduplicación y límite de frecuencia con una sola alerta | La base no se llena y el administrador ve el problema una vez, sin ruido |
| A3 Suplantación | La IP de origen sale de la conexión de red, no del mensaje. El inventario se consulta por IP | Un mensaje de una IP no registrada queda marcado como fuente desconocida |
| A4 Comando no autorizado | Lista permitida, denegar por defecto, consola de solo lectura | Se bloquea y se audita |
| A5 Encadenamiento | Coincidencia exacta del comando completo (no por prefijo) | `show version; reload` no pasa |
| A6 Acción sin rastro | Tabla de auditoría con actor, acción, detalle y resultado, incluidos los bloqueos | Toda acción, permitida o no, deja huella |
| A7 Hora manipulada | NTP en las plantillas y almacenamiento en UTC | Correlación entre equipos (completa en el Corte 3) |

## 7. Pruebas realizadas

Todas con datos simulados, en el equipo del estudiante.

| ID | Prueba | Resultado esperado | Resultado obtenido |
|---|---|---|---|
| P1 | Enviar `esto no es syslog` a `POST /api/syslog/` | Rechazo 422 | 422 "El mensaje no cumple el formato RFC 3164" |
| P2 | Enviar `<999>...` (PRI fuera de rango) al parser | Rechazo | "PRI fuera de rango: 999" |
| P3 | Enviar 5 mensajes idénticos por UDP | 1 evento con contador 5 | 1 evento, `repeat_count` = 5 |
| P4 | Enviar 150 mensajes distintos por UDP en menos de un segundo desde una IP | 100 guardados, 1 alerta, resto descartado | 100 guardados, 1 alerta (severidad 1, origen SISTEMA), 49 descartados |
| P5 | Enviar un mensaje desde una IP no registrada | Guardado como fuente desconocida | `device_id` nulo, contado en el dashboard |
| P6 | Consola: `show version` | Permitido | Respuesta simulada |
| P7 | Consola: `configure terminal` | Bloqueado y auditado | Bloqueado, registrado como BLOQUEADO en la auditoría |
| P8 | Consola: `show interfaces` (no está en la lista) | Bloqueado | Bloqueado: no incluido en la lista permitida |

## 8. Limitaciones y trabajo del Corte 3

- **Suplantación a nivel de red.** UDP permite falsificar la IP de origen. Un atacante en la misma red podría hacerse pasar por un equipo. La mitigación real es transporte autenticado (TLS, RFC 5425) o una red de gestión aislada.
- **Fuente desconocida.** Hoy se guarda y se marca. El Corte 3 definirá una política de descarte o cuarentena y una alerta.
- **Nombre dentro del mensaje.** El nombre de equipo que trae el mensaje no se contrasta contra el inventario. Un mensaje de una IP conocida con otro nombre no se marca todavía.
- **Detección de comportamiento.** Faltan reglas para comandos fuera de horario, cuentas de servicio anómalas y cambios de configuración no autorizados.
- **Roles y aprobación.** Sin autenticación no hay separación entre quien propone y quien aprueba. Es lo primero que se debe agregar antes de permitir SSH real.
- **Límite de frecuencia en memoria.** Se reinicia con el receptor. En el Corte 3 debe persistir.
- **Integridad y retención.** No hay firma ni política de retención de logs.

## 9. Bibliografía

- IETF. RFC 5424, The Syslog Protocol.
- IETF. RFC 5425, Transport Layer Security (TLS) Transport Mapping for Syslog.
- NIST. Artificial Intelligence Risk Management Framework (AI RMF).
- OWASP. Agentic AI – Threats and Mitigations.
- Cisco, Fortinet y Huawei: guías de configuración de logging citadas en el proyecto.