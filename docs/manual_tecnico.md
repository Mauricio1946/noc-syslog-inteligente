# Manual técnico · NOC Syslog Inteligente v1.0.0

Estudiante: Mauricio Ramirez · Periodo 2026-2 · Datos y equipos SIMULADOS.

## 1. Arquitectura

```
Equipos (SIMULADOS) --UDP 5514--> udp_receiver.py --> ingest.py --> SQLite (noc_syslog.db)
                                   (límite de            |  parser RFC 3164, deduplicación,
                                    frecuencia)          |  fuente desconocida, defense.py (alertas)
Navegador --HTTP/JSON--> FastAPI (app/main.py) ----------+--> auth.py (sesión y roles)
                            |-- approvals.py (aprobación humana) --> executor.py --> actions.py
                            |-- defense.py --> notify.py (Telegram o SIMULADA)
                            |-- console.py, configs.py
```

Dos procesos: el **servidor web** (`uvicorn app.main:app`) y el **receptor UDP** (`python udp_receiver.py`). Comparten la base SQLite.

## 2. Módulos

| Archivo | Función |
|---|---|
| `app/main.py` | API REST, login, middleware de cabeceras seguras y servidor de la interfaz |
| `app/auth.py` | Sesión por cookie, `current_user`, `require_roles`, auditoría |
| `app/security.py` | Hash de contraseñas (scrypt con sal) y tokens de sesión |
| `app/config.py` | Lector de `.env` y parámetros |
| `app/models.py`, `schemas.py`, `database.py` | Modelo de datos, validación y conexión |
| `app/syslog_constants.py`, `syslog_parser.py` | Facility, severidad, PRI y parser RFC 3164 |
| `app/ingest.py` | Ingesta: deduplicación, fuente desconocida y llamada a defensa |
| `app/ratelimit.py` | Límite de frecuencia por IP |
| `app/defense_rules.py` | Reglas puras de defensa (probadas de forma automática) |
| `app/defense.py` | Alertas de seguridad: registro, deduplicación y API |
| `app/notify.py` | Telegram o modo SIMULADA; el token nunca se muestra |
| `app/actions.py` | Catálogo cerrado de acciones y validación de parámetros |
| `app/approvals.py` | Solicitudes, aprobación por otra persona, ejecución y verificación |
| `app/executor.py` | Ejecutor SIMULADO con lista de hosts y estado Activo |
| `app/console.py`, `app/configs.py` | Consola de solo lectura y plantillas Syslog |
| `static/index.html`, `static/extras.js` | Interfaz web |
| `udp_receiver.py`, `simulador_syslog.py` | Receptor UDP y simulador de equipos |
| `create_user.py` | Alta de usuarios (contraseña por teclado) |
| `backup_db.py`, `restore_db.py` | Respaldo y restauración |
| `marcha_blanca.py` | Pruebas automáticas y bitácora |
| `tests/test_nucleo.py` | Pruebas unitarias del núcleo |

## 3. Modelo de datos

| Tabla | Campos principales |
|---|---|
| `devices` | id, hostname, ip_address (única), vendor, model, os_version, location, status, updated_at |
| `syslog_events` | id, device_id (nulo = fuente desconocida), source_ip, hostname_reported, facility, severity, timestamp, repeat_count, last_seen, parsed_program, message, raw_message, origin |
| `incidents` | id, title, description, severity, status, assigned_to, created_at, device_id |
| `audit_log` | id, timestamp, actor, action, detail, result |
| `users` | id, username (único), password_hash, role, active, failed_attempts, locked_until, created_at |
| `sessions` | id, token_hash (único), user_id, created_at, expires_at |
| `command_requests` | id, device_id, action, params, commands, requested_by, status, created_at, expires_at, decided_by, decided_at, decision_note, executed_at, output, verified_by, verified_at, verify_note |
| `security_alerts` | id, created_at, last_seen, kind, severity, source_ip, device_id, detail, count, status, notified, acknowledged_by |

Las tablas nuevas se crean solas al arrancar. No se hacen migraciones: esta versión solo agrega tablas.

## 4. Configuración (`.env`)

El archivo `.env` no se sube a GitHub. `.env.example` lista las variables sin valores secretos.

| Variable | Por defecto | Para qué sirve |
|---|---|---|
| `SESSION_HOURS` | 8 | Duración de la sesión |
| `MAX_FAILED_LOGINS` | 5 | Intentos fallidos antes de bloquear |
| `LOCK_MINUTES` | 15 | Minutos de bloqueo |
| `COOKIE_SECURE` | 0 | Poner 1 cuando haya HTTPS |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | vacío | Alertas reales; si faltan, modo SIMULADA |
| `WORK_HOURS_START`, `WORK_HOURS_END` | 7 y 19 | Horario laboral (Bogotá) de la regla de cambios |
| `AUTH_FAIL_THRESHOLD` | 5 | Fallos de autenticación para alertar |
| `APPROVAL_MINUTES` | 30 | Vigencia de una solicitud |
| `MAX_PENDING_PER_USER` | 5 | Solicitudes pendientes por persona |
| `EXEC_MODE` | simulado | Solo se admite `simulado` |
| `SSH_ALLOWED_HOSTS` | vacío | IPs permitidas para el ejecutor (vacío = todo el inventario Activo) |

Los cambios en `.env` requieren reiniciar el servidor **y** el receptor.

## 5. API

Rutas bajo `/api`. Documentación interactiva en `/docs` (la cookie de sesión se comparte con la interfaz).

| Método y ruta | Quién |
|---|---|
| `POST /auth/login`, `POST /auth/logout` | Público |
| `GET /auth/me` | Autenticado |
| `GET /devices/`, `GET /devices/{id}` | Autenticado |
| `POST`, `PUT`, `DELETE /devices/...` | admin |
| `GET /syslog/` (filtros: severity, max_severity, device_id, vendor, date_from, date_to, limit) | Autenticado |
| `POST /syslog/` (ingesta simulada) | admin, operador |
| `GET /incidents/` | Autenticado |
| `POST /incidents/`, `PUT /incidents/{id}` | admin, operador |
| `GET /dashboard/`, `GET /configs/{fabricante}` | Autenticado |
| `POST /console/` | admin, operador |
| `GET /audit/` | admin, auditor |
| `GET /actions/`, `GET /requests/` | Autenticado |
| `POST /requests/`, `POST /requests/{id}/approve`, `.../reject` | admin, operador (nadie aprueba su propia solicitud) |
| `POST /requests/{id}/verify` | Quien propuso, o admin |
| `GET /alerts/` | Autenticado |
| `POST /alerts/{id}/ack` | admin, operador |

Códigos: `401` sin sesión, `403` rol sin permiso o autoaprobación, `409` estado inválido o solicitud vencida, `422` datos inválidos, `429` demasiados intentos o solicitudes.

## 6. Seguridad del diseño

- **Contraseñas:** hash scrypt con sal aleatoria; nunca se guardan en claro. Se piden por teclado (`getpass`), sin dejar rastro en el código ni en el historial.
- **Sesión:** cookie `HttpOnly` y `SameSite=Strict`; en la base solo se guarda el hash del token. Bloqueo temporal tras varios fallos y mensaje igual para usuario inexistente o clave errónea (se verifica un hash falso para igualar tiempos).
- **Denegar por defecto:** cada ruta declara los roles permitidos; la interfaz solo oculta botones.
- **Logs no confiables:** el parser extrae campos; la interfaz inserta texto, no HTML; el contenido de un mensaje nunca se interpreta como orden.
- **Acciones:** catálogo cerrado, parámetros con expresión regular estricta, aprobación por otra persona, vencimiento, tope de pendientes, revalidación antes de ejecutar y ejecutor con lista de hosts.
- **Defensa:** las reglas leen campos y comparan; si fallan, la ingesta continúa.
- **Secretos:** solo en `.env`; el envío a Telegram no imprime la URL (contiene el token) en caso de error.
- **Auditoría:** accesos, denegaciones, solicitudes, comandos y alertas, con el usuario real.

## 7. Operación

| Tarea | Comando |
|---|---|
| Pruebas automáticas | `python -m unittest discover -s tests -v` |
| Marcha blanca completa | `python marcha_blanca.py` (con servidor y receptor encendidos) |
| Enviar mensajes de prueba | `python simulador_syslog.py nombre|fuerza|cambio|normal|repetido|tormenta` |
| Respaldo | `python backup_db.py` |
| Verificar un respaldo | `python restore_db.py backups\ARCHIVO.db --probar` |
| Restaurar | detener procesos y `python restore_db.py backups\ARCHIVO.db` |
| Alta de usuario | `python create_user.py` |

## 8. Solución de problemas

| Síntoma | Causa probable | Qué hacer |
|---|---|---|
| `No module named uvicorn` | Entorno virtual sin activar | `.\venv\Scripts\Activate.ps1` |
| El simulador dice "Enviados" pero no hay eventos | El receptor no está encendido (UDP no avisa) | `python udp_receiver.py` |
| No aparecen alertas nuevas | Mensaje repetido en menos de 1 minuto (se agrupa) o receptor con código viejo | Reiniciar el receptor y variar el mensaje |
| La pestaña Alertas no aparece | Caché del navegador | `Ctrl + F5` |
| Cuenta bloqueada | 5 intentos fallidos | Esperar 15 minutos |
| Cambios en `.env` sin efecto | Los procesos leen `.env` al arrancar | Reiniciar servidor y receptor |

## 9. Limitaciones conocidas

UDP sin cifrado y con IP falsificable; sin HTTPS ni autenticación de doble factor; el límite de frecuencia del receptor está en memoria; el ejecutor es simulado (el SSH real queda preparado, no implementado); sin migraciones de base de datos; sin retención ni firma de logs; plantillas de configuración no verificadas en equipos reales.
