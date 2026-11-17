# NOC Syslog Inteligente · v1.0.0

Aplicación web para un centro de operaciones de red (NOC): recibe mensajes Syslog de equipos Cisco, Fortinet y Huawei, los clasifica por severidad, detecta comportamientos sospechosos y exige aprobación humana para cualquier cambio sobre un equipo.

> **Datos SIMULADOS de laboratorio.** Ningún equipo ni red real fue probado. Proyecto académico de Administración y Gestión de Redes, periodo 2026-2.

## Funciones

| Área | Qué hace |
|---|---|
| Acceso | Login, roles (admin, operador, auditor), sesión por cookie, bloqueo tras 5 fallos en 15 minutos |
| Syslog | Receptor UDP (puerto 5514), parser RFC 3164, deduplicación de 60 s, límite de 100 mensajes por minuto por IP |
| Inventario y eventos | Dispositivos, eventos con filtros por severidad, marca, equipo y fecha, dashboard |
| Incidentes | Crear, asignar y cerrar incidentes desde un evento |
| Configuraciones | Plantillas Syslog para Cisco, Fortinet y Huawei |
| Consola | Comandos de solo lectura con lista permitida; lo demás se bloquea y se audita |
| Aprobaciones | Catálogo cerrado de acciones; otra persona debe aprobar; vence a los 30 minutos; ejecución SIMULADA |
| Defensa | Alertas por nombre falso, suplantación, fuente desconocida, cambio fuera de horario, fuerza bruta y tormenta de eventos |
| Notificaciones | Telegram si hay credenciales; si no, modo SIMULADA. El token nunca se muestra |
| Auditoría | Registro de accesos, denegaciones, solicitudes, comandos y alertas con el usuario real |
| Operación | Respaldo y restauración de la base de datos, pruebas automáticas y marcha blanca |

## Requisitos

- Python 3.12 (3.15 no es compatible con las dependencias)
- Git
- Windows, Linux o macOS

## Instalación

```powershell
git clone https://github.com/Mauricio1946/noc-syslog-inteligente.git
cd noc-syslog-inteligente
git checkout v1.0.0
python -m venv venv
.\venv\Scripts\Activate.ps1          # Linux/macOS: source venv/bin/activate
pip install -r requirements.txt
copy .env.example .env               # Linux/macOS: cp .env.example .env
python create_user.py                # crea un usuario; la contraseña se pide por teclado
```

El archivo `.env` guarda los secretos y **no se sube a GitHub**. `.env.example` lista las variables sin valores.

## Ejecución

Se necesitan dos procesos, cada uno en su terminal con el entorno virtual activado:

```powershell
python -m uvicorn app.main:app       # servidor web: http://127.0.0.1:8000
python udp_receiver.py               # receptor Syslog UDP: puerto 5514
```

- Interfaz: http://127.0.0.1:8000
- Documentación de la API: http://127.0.0.1:8000/docs
- Datos de prueba: `python seed_demo.py`
- Enviar mensajes de prueba (con el receptor encendido): `python simulador_syslog.py nombre|fuerza|cambio|normal|repetido|tormenta`

Si cambias el `.env`, reinicia el servidor y el receptor.

## Pruebas

```powershell
python -m unittest discover -s tests -v    # 27 pruebas automáticas del núcleo
python marcha_blanca.py                    # 9 verificaciones; requiere servidor y receptor encendidos
```

La marcha blanca prueba seguridad (401, 403), defensa, carga básica, respaldo, recuperación y revisa que no haya secretos en el repositorio. Los resultados quedan en `docs/bitacora_marcha_blanca.md`.

## Respaldo y restauración

```powershell
python backup_db.py                                   # crea backups\noc_syslog_AAAAMMDD_HHMMSS.db
python restore_db.py backups\ARCHIVO.db --probar      # verifica un respaldo sin tocar la base actual
python restore_db.py backups\ARCHIVO.db               # restaura (detener antes los dos procesos)
```

## Seguridad

- Contraseñas con scrypt y sal aleatoria; nunca se guardan en claro ni se escriben en el código.
- Sesión por cookie `HttpOnly` y `SameSite=Strict`; en la base solo se guarda el hash del token.
- Cada ruta declara los roles permitidos (denegar por defecto).
- Los registros Syslog se tratan como datos no confiables: nunca se interpretan como órdenes.
- Todo cambio sobre un equipo pasa por una solicitud, la aprobación de otra persona y auditoría.
- Los secretos viven solo en `.env`, que Git ignora.

La política frente a agentes de IA está en `docs/politica_defensa_ia_v1.md`.

## Documentación

| Documento | Contenido |
|---|---|
| `docs/manual_usuario.md` | Uso de la aplicación por rol |
| `docs/manual_tecnico.md` | Arquitectura, módulos, modelo de datos, API, configuración y solución de problemas |
| `docs/despliegue_rollback.md` | Despliegue y regreso a la versión anterior |
| `docs/bitacora_marcha_blanca.md` | Resultados de la marcha blanca |
| `docs/politica_defensa_ia_v1.md` | Riesgos, controles y pruebas frente a agentes de IA |
| `docs/diseno.md` | Requisitos, historias de usuario, arquitectura y modelo de datos |

## Versiones

| Etiqueta | Contenido |
|---|---|
| v0.1.0 | Base alfa: modelo de datos e inventario |
| v0.2.0 | Corte 2: MVP con Syslog, dashboard, incidentes, plantillas y consola |
| v1.0.0 | Corte 3: roles, aprobación humana, defensa, alertas, pruebas, respaldo y documentación |

## Limitaciones

- El ejecutor es **simulado**: el SSH real queda preparado (lista de hosts y catálogo cerrado), pero no implementado.
- Telegram se probó en modo SIMULADA; el envío real necesita `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID` en `.env`.
- Las plantillas de Cisco, Fortinet y Huawei no se aplicaron en equipos reales; deben contrastarse con la guía oficial de cada fabricante.
- UDP no está cifrado y permite falsificar la IP de origen; TLS (RFC 5425) y el formato RFC 5424 quedan como trabajo futuro.
- Sin HTTPS ni doble factor de autenticación.
- El límite de frecuencia vive en la memoria del receptor y se reinicia con él.

## Licencia

Uso académico. Ver `LICENSE`.
