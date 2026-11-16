# Despliegue y rollback · NOC Syslog Inteligente v1.0.0

Estudiante: Mauricio Ramirez · Periodo 2026-2 · Datos y equipos SIMULADOS.

## 1. Requisitos

- Windows 10/11, **Python 3.12** (Python 3.15 no es compatible con las dependencias), Git.
- Dos procesos permanentes: el servidor web y el receptor Syslog UDP (puerto 5514).
- Esta versión no agrega dependencias: `requirements.txt` es el mismo de la v0.2.0.

## 2. Despliegue desde cero

```powershell
git clone https://github.com/Mauricio1946/noc-syslog-inteligente.git
cd noc-syslog-inteligente
git checkout v1.0.0
py -3.12 -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

1. **Configura `.env`** (nunca se sube a GitHub). Variables: ver `docs/manual_tecnico.md`, sección 4. Para alertas reales por Telegram, agrega `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID`; si quedan vacías, las alertas se muestran en modo SIMULADO.
2. **Crea los usuarios** (la contraseña se pide por teclado y solo se guarda su hash):

```powershell
python create_user.py      # admin
python create_user.py      # operador (repetir para un segundo operador)
python create_user.py      # auditor
```

3. **Datos de demostración (opcional, una sola vez):** `python seed_demo.py`
4. **Arrancar** (una terminal por proceso, con el entorno virtual activo):

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
python udp_receiver.py
```

5. **Verificar el despliegue:** con ambos procesos encendidos, `python marcha_blanca.py`. Debe terminar con `0 FALLA` y dejar el resultado en `docs/bitacora_marcha_blanca.md`.

Para exponer el servicio fuera del equipo hay que ponerlo detrás de HTTPS y definir `COOKIE_SECURE=1`. Esta versión no incluye TLS.

## 3. Antes de cada cambio de versión

```powershell
python backup_db.py
git tag
```

Anota el nombre del respaldo creado (`backups\noc_syslog_AAAAMMDD_HHMMSS.db`) y la versión actual. Con eso se puede volver atrás.

## 4. Rollback

**Cuándo:** el servicio falla o se comporta mal después de actualizar.

1. Detén el servidor y el receptor (`Ctrl + C` en cada terminal).
2. Guarda el estado actual por si hace falta analizarlo: `python backup_db.py`
3. Vuelve a la versión anterior del código:

```powershell
git fetch --tags
git checkout v0.2.0
python -m pip install -r requirements.txt
```

4. Solo si la base de datos quedó dañada o con datos incorrectos, restaura el respaldo hecho antes del cambio. Primero comprueba que el respaldo sirve, sin tocar la base actual:

```powershell
python restore_db.py backups\noc_syslog_AAAAMMDD_HHMMSS.db --probar
python restore_db.py backups\noc_syslog_AAAAMMDD_HHMMSS.db
```

   La restauración pide escribir `SI` y guarda antes una copia de la base actual en `backups\antes_de_restaurar_*.db`, para poder deshacerla.
5. Arranca de nuevo servidor y receptor, y verifica (sección 5).

**Compatibilidad de la base:** la v1.0.0 solo **agrega** tablas (`users`, `sessions`, `command_requests`, `security_alerts`); no cambia las existentes. La v0.2.0 ignora las tablas nuevas y funciona con la misma base.

**Volver a la versión final:** `git checkout main` (o `git checkout v1.0.0`).

## 5. Verificación después de desplegar o de volver atrás

| Comprobación | Resultado esperado |
|---|---|
| `http://127.0.0.1:8000/` | Aparece la pantalla de acceso (v1.0.0) o el dashboard (v0.2.0) |
| `python simulador_syslog.py normal` | El receptor imprime `[OK]` |
| Dashboard | El nuevo evento aparece |
| `python marcha_blanca.py` (solo v1.0.0) | `0 FALLA` |

## 6. Limitaciones

- No hay servicio de Windows ni reinicio automático: los dos procesos se arrancan a mano.
- La restauración de la base requiere detener los procesos.
- El límite de frecuencia del receptor vive en memoria y se reinicia con él.
