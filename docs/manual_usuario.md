# Manual de usuario · NOC Syslog Inteligente v1.0.0

Proyecto académico · Administración y Gestión de Redes · Periodo 2026-2
Estudiante: Mauricio Ramirez · Docente: Ing. John Harold Pérez Calderón

> Todos los equipos, direcciones y mensajes son **SIMULADOS**. La aplicación no se conecta a equipos reales.

## 1. Para qué sirve

Reúne los mensajes Syslog de los equipos de red (Cisco, Fortinet y Huawei), los clasifica por severidad, avisa de comportamientos sospechosos y permite gestionar incidentes y acciones sobre los equipos con **aprobación de otra persona**.

## 2. Entrar y salir

1. Abre `http://127.0.0.1:8000/` en el navegador.
2. Escribe tu **usuario** y **contraseña** y pulsa **Entrar**.
3. Arriba a la derecha verás tu usuario y rol. Pulsa **Salir** al terminar.

- Tras **5 intentos fallidos** la cuenta se bloquea **15 minutos**.
- La sesión dura 8 horas. Si vence, la aplicación te devuelve a la pantalla de acceso.
- No compartas tu contraseña. Cada acción queda registrada con tu nombre.

## 3. Qué puede hacer cada rol

| Función | admin | operador | auditor |
|---|:---:|:---:|:---:|
| Ver dashboard, eventos, inventario, incidentes, plantillas y alertas | Sí | Sí | Sí |
| Crear, editar y eliminar equipos del inventario | Sí | No | No |
| Crear, asignar y cerrar incidentes | Sí | Sí | No |
| Usar la consola simulada de solo lectura | Sí | Sí | No |
| Proponer, aprobar o rechazar acciones (nunca las propias) | Sí | Sí | No |
| Reconocer alertas de seguridad | Sí | Sí | No |
| Ver la Auditoría | Sí | No | Sí |

Los botones que tu rol no puede usar no aparecen. Aunque alguien intentara saltarse la pantalla, el servidor también valida el rol y lo registra como `ACCESO_DENEGADO`.

## 4. Pestañas

### Dashboard
Tarjetas con equipos, eventos, críticos (severidad 0 a 2), fuentes desconocidas e incidentes. Más abajo, la tabla de eventos con fecha (hora de Bogotá), equipo, IP, facility, severidad, programa, mensaje, repeticiones y origen.

**Filtros:** fecha desde/hasta, marca, equipo y severidad. Marca "esta severidad o más grave" para incluir las de menor número. Pulsa **Filtrar**.

**Origen:** `SIMULADO` (ingresado por la API o por datos de demostración), `REAL` (llegó por UDP, aunque se haya enviado desde el propio equipo) y `SISTEMA` (generado por la aplicación). Un evento con `xN` se repitió N veces y se muestra una sola vez.

### Incidentes
Crea un incidente desde el formulario o desde un evento ("Crear incidente"). Cambia su estado (Abierto, En Progreso, Cerrado) y asígnalo con **Asignar**.

### Inventario
Lista los equipos con su fecha de actualización. El administrador agrega, edita (**Editar**) y elimina (**Eliminar**). La IP de cada equipo debe ser única.

### Configuraciones Syslog
Elige el fabricante y la severidad mínima: aparece la plantilla comentada. Usa IPs de documentación (192.0.2.x). **Verifícala con la guía del fabricante antes de aplicarla en un equipo real.**

### Consola
Elige un equipo y escribe un comando. Solo responden los comandos de la lista permitida (por ejemplo `show version`). Cualquier otro se bloquea y queda auditado. La salida es simulada.

### Aprobaciones
Flujo para cambios sobre un equipo, en cuatro pasos:

1. **Proponer** (operador o admin): elige equipo, acción (apagar o encender interfaz) y el nombre de la interfaz. No se escriben comandos libres.
2. **Revisar y aprobar o rechazar** (otra persona): quien propuso no puede aprobar, ni siquiera un admin. La solicitud vence a los 30 minutos.
3. **Ejecución** (simulada) al aprobar. Pulsa **Ver** para leer la salida.
4. **Verificar** (quien propuso, o un admin): confirma que el resultado es el esperado.

Estados: `PENDIENTE`, `EJECUTADA`, `VERIFICADA`, `RECHAZADA`, `EXPIRADA`. Puedes retirar una solicitud propia con **Retirar**. Hay un máximo de 5 solicitudes pendientes por persona.

### Alertas
Alertas automáticas del módulo de defensa:

| Alerta | Cuándo aparece | Severidad |
|---|---|---|
| `HOSTNAME_NO_COINCIDE` | La IP es de un equipo, pero el mensaje dice ser otro | Media |
| `POSIBLE_SUPLANTACION` | Una IP no registrada usa el nombre de un equipo del inventario | Alta |
| `FUENTE_DESCONOCIDA` | Llega un mensaje de una IP no registrada | Media |
| `CAMBIO_FUERA_DE_HORARIO` | Cambio de configuración fuera de 7:00 a 19:00 (Bogotá) | Alta |
| `POSIBLE_FUERZA_BRUTA` | 5 o más fallos de autenticación en 10 minutos desde una IP | Crítica |
| `TORMENTA_DE_EVENTOS` | Una IP supera 100 mensajes por minuto | Alta |

Una alerta igual en menos de una hora solo suma al contador ("Veces"). **Aviso** indica si se envió por Telegram (`TELEGRAM`), si no hay Telegram configurado (`SIMULADA`) o si falló (`ERROR`). Pulsa **Reconocer** cuando una persona la haya revisado.

### Auditoría
Registro de quién hizo qué, cuándo y con qué resultado: accesos, cambios, solicitudes, comandos, alertas y denegaciones.

## 5. Mensajes frecuentes

| Mensaje | Qué significa |
|---|---|
| Usuario o contraseña incorrectos | Datos erróneos; se registra el intento |
| Demasiados intentos fallidos | Cuenta bloqueada temporalmente; espera 15 minutos |
| Tu sesión terminó | Entra de nuevo |
| Tu rol no tiene permiso para esta acción | La acción no corresponde a tu rol |
| No puedes aprobar tu propia solicitud | Debe aprobarla otra persona |
| La solicitud venció sin ser revisada | Proponla de nuevo |
| El equipo está en estado Mantenimiento | El ejecutor solo actúa sobre equipos Activos |
| Nombre de interfaz inválido | El nombre no cumple el formato del fabricante |
