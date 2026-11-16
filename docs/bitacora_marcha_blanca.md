# Bitácora de marcha blanca · NOC Syslog Inteligente v1.0.0

Estudiante: Mauricio Ramirez · Periodo 2026-2 · Todos los datos son **SIMULADOS**.

## Objetivo y método

Operar la aplicación de forma controlada, en el equipo del estudiante, antes de la entrega, registrando lo que se prueba, lo que falla y lo que se corrige. No se hicieron pruebas sobre equipos ni redes reales.

- **Automática:** `python marcha_blanca.py` ejecuta las pruebas automáticas del núcleo, de seguridad (acceso sin sesión, credenciales falsas, roles), de defensa (alertas), de carga básica (ráfaga de 150 mensajes), de respaldo, de recuperación y de secretos. Cada ejecución se agrega al final de este documento.
- **Manual:** flujo de aprobación con dos usuarios y recorrido de la interfaz por cada rol (capturas en el informe).

## Hallazgos y correcciones

| # | Hallazgo | Cómo se detectó | Corrección |
|---|---|---|---|
| 1 | Las dependencias no se instalaban con Python 3.15 | Error al instalar `pydantic-core` y `pyyaml` | Usar Python 3.12 y fijar versiones en `requirements.txt` |
| 2 | El receptor UDP no cerraba con Ctrl+C en Windows | Prueba manual | Tiempo de espera de 1 s en el socket |
| 3 | Archivos creados pero vacíos o sin guardar | `ImportError` y tamaño 0 al arrancar | Verificar el tamaño y compilar (`py_compile`) antes de ejecutar |
| 4 | Un script de parche no se aplicó por falta de salto de línea al final de `ingest.py` | El propio script avisó y no modificó nada | Agregar la línea final y repetirlo; el script comprueba todos los anclajes antes de escribir |
| 5 | Una pestaña de la interfaz no aparecía | Error de JavaScript en la consola del navegador (paréntesis faltante) | Corregir el archivo y recargar |
| 6 | Los mensajes de prueba llegaban a la nada: el receptor no estaba encendido | UDP no confirma la entrega; la alerta no aparecía | Documentar los tres procesos y usar `simulador_syslog.py` con un escenario por palabra |
| 7 | **La restauración podía dejar la base vacía** si se hacía en el mismo segundo que el respaldo | Prueba de recuperación: el respaldo de seguridad sobrescribía el respaldo original | Nombres de respaldo únicos, comprobar que el respaldo existe y tiene datos antes de tocar nada, abrirlo en solo lectura |
| 8 | El detector de secretos marcaba `config.py` como si guardara un token | Prueba con datos de control | Patrón más estricto: solo valores con forma de token |
| 9 | El script de marcha blanca tapaba un módulo de Python con el nombre de una función | Primera ejecución de prueba | Renombrar la función |

## Ejecuciones

Las ejecuciones de `marcha_blanca.py` se agregan a continuación.

## Ejecución #1 · 2026-11-16 13:41

Ambiente: Windows 11, Python 3.12.10, servidor http://127.0.0.1:8000, datos simulados.

| # | Prueba | Resultado | Detalle |
|---|---|---|---|
| 1 | Pruebas automáticas del núcleo | FALLA | 27 pruebas, con fallos (ver: python -m unittest discover -s tests -v) |
| 2 | Seguridad: API sin sesión rechazada | FALLA | el servidor no responde (¿está encendido en 127.0.0.1:8000?) |
| 3 | Seguridad: login con credenciales falsas rechazado | FALLA | el servidor no responde (¿está encendido en 127.0.0.1:8000?) |
| 4 | Seguridad: roles (operador sin permiso de borrar ni de auditoría) | FALLA | el servidor no responde (¿está encendido en 127.0.0.1:8000?) |
| 5 | Defensa: nombre falso y fuerza bruta generan alertas | FALLA | HOSTNAME_NO_COINCIDE +0, POSIBLE_FUERZA_BRUTA +0 (¿receptor encendido? ¿repetido antes de 1 minuto?) |
| 6 | Carga básica: 150 mensajes en ráfaga | FALLA | 150 mensajes enviados en 0.07 s; guardados 0 (tope 100 por minuto); alertas de tormenta +0 |
| 7 | Respaldo de la base de datos | OK | backups\noc_syslog_20261116_134145.db; integridad ok; 8 tablas, 66 filas |
| 8 | Recuperación: restauración de prueba | OK | restauración de prueba en archivo temporal: integridad ok; 8 tablas y 66 filas recuperadas (la base actual no se tocó) |
| 9 | Secretos: nada sensible en el repositorio | OK | 35 archivos versionados revisados: sin .env, sin bases de datos, sin tokens; .env ignorado por Git |

Resumen: 3 OK, 6 FALLA, 0 OMITIDA.
