# NOC Syslog Inteligente · v0.2.0 (MVP)

Proyecto académico individual de **Administración y Gestión de Redes** (Periodo 2026-2).
**Docente:** Ing. John Harold Pérez Calderón · **Estudiante:** Mauricio Ramirez

Aplicación de NOC que recibe mensajes Syslog, los clasifica (facility y severidad 0 a 7),
gestiona un inventario de equipos y un ciclo de incidentes, genera plantillas Syslog para
Cisco, Fortinet y Huawei, y aplica controles de seguridad frente a acciones no autorizadas
de agentes de IA.

> **Todos los datos incluidos son SIMULADOS.** No hay equipos ni IPs de producción.

## Funciones del MVP

| Función | Estado |
|---|---|
| Inventario editable (nombre, IP, marca, modelo, versión, ubicación, estado, fecha de actualización) | Listo |
| Recepción de Syslog por UDP (RFC 3164) y por API (simulado) | Listo |
| Clasificación por equipo, marca, fecha, facility y severidad | Listo |
| Dashboard con estado, eventos recientes, críticos e incidentes | Listo |
| Filtros por fecha, marca, equipo y severidad | Listo |
| Incidentes: crear, asignar, seguimiento y cierre | Listo |
| Plantillas Syslog comentadas (Cisco, Fortinet, Huawei) | Listo |
| Consola simulada de solo lectura con lista permitida | Listo |
| Auditoría de acciones | Listo |
| Telegram, SSH real, roles, TLS | Corte 3 |

## Requisitos

- Windows 10/11 con **Python 3.12** (Python 3.15 no es compatible con las dependencias)
- Git

## Instalación (PowerShell)

```powershell
git clone https://github.com/Mauricio1946/noc-syslog-inteligente.git
cd noc-syslog-inteligente
py -3.12 -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Si PowerShell bloquea la activación: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`

## Ejecución

1. **Servidor web y API** (terminal 1, con el venv activo):

```powershell
python -m uvicorn app.main:app --reload
```

   - Interfaz: http://127.0.0.1:8000/
   - Documentación de la API: http://127.0.0.1:8000/docs

2. **Datos de demostración simulados** (una sola vez, con el servidor detenido):

```powershell
python seed_demo.py
```

3. **Receptor Syslog UDP** (terminal 2, con el venv activo; puerto 5514):

```powershell
python udp_receiver.py
```

   Enviar un mensaje de prueba desde otra terminal:

```powershell
python -c "import socket; s=socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.sendto(b'<187>Oct 13 10:00:00 SW-CORE-SIMULADO-01 %LINK-3-UPDOWN: Interface Gi1/0/9, changed state to down', ('127.0.0.1', 5514))"
```

## Pruebas

Prueba manual del parser:

```powershell
python -m tests.probar_parser
```

Las pruebas funcionales del MVP (procedimiento, resultado esperado y evidencia) están en el
informe PDF del Corte 2.

## Estructura

```
app/
  main.py            API REST (FastAPI) y servidor de la interfaz
  models.py          Modelo de datos (SQLite)
  schemas.py         Validación de datos
  syslog_constants.py  Facility, severidad y decodificador de PRI
  syslog_parser.py   Parser RFC 3164
  ingest.py          Ingesta: deduplicación y fuente desconocida
  ratelimit.py       Límite de frecuencia por fuente
  configs.py         Plantillas Syslog Cisco / Fortinet / Huawei
  console.py         Consola simulada con lista permitida
static/index.html    Interfaz web
udp_receiver.py      Receptor Syslog UDP
seed_demo.py         Datos de demostración (SIMULADOS)
tests/               Pruebas
```

## Seguridad

- **Los logs son datos no confiables**: se extraen campos, nunca se interpretan como instrucciones.
  La interfaz los muestra como texto, no como HTML.
- Eventos de IP no registrada se guardan marcados como **fuente desconocida**.
- **Deduplicación**: mensajes idénticos en 60 s se agrupan con un contador.
- **Límite de frecuencia**: más de 100 mensajes en 60 s desde una IP genera una sola alerta y se
  descartan los siguientes (control de tormentas).
- **Consola**: lista permitida con coincidencia exacta; todo lo demás se bloquea. Es de solo lectura
  y no se conecta a ningún equipo.
- **Auditoría** de inventario, incidentes y comandos.
- No hay contraseñas, tokens ni IPs reales en el repositorio. Las plantillas usan IPs de
  documentación (RFC 5737).

Flujo previsto: evento detectado → validación → propuesta de acción → revisión humana →
aprobación → ejecución autorizada → verificación → auditoría. En el MVP la ejecución es solo
simulada.

## Limitaciones conocidas

- Sin autenticación ni roles (un actor fijo en la auditoría).
- Solo UDP; TLS (RFC 5425) y el formato RFC 5424 quedan para el Corte 3.
- El límite de frecuencia vive en memoria del receptor y se reinicia con él. UDP permite falsificar la IP de origen.
- La salida de la consola es texto fijo y no refleja el inventario.
- Las plantillas deben verificarse con la guía del fabricante y probarse en laboratorio.
- Sin migraciones de base de datos (se agregan columnas a mano).

## Licencia

Uso académico. Ver [LICENSE](LICENSE).
