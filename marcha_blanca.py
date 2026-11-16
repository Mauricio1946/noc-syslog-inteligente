"""Marcha blanca automática: ejecuta las pruebas y escribe la bitácora con resultados REALES.

Uso (con el servidor y el receptor UDP encendidos, desde la raíz del proyecto):
    python marcha_blanca.py              # limpia los eventos de prueba de la carga
    python marcha_blanca.py --conservar  # los deja en la base (para capturas)

Pide la contraseña de operador1 (no se guarda ni se muestra). Si pulsas Enter, omite esa prueba.
También acepta la variable de entorno MB_CLAVE_OPERADOR. No repitas antes de 1 minuto:
los mensajes idénticos se agrupan (deduplicación) y el límite de frecuencia sigue activo.

Escribe en docs/bitacora_marcha_blanca.md (agrega una ejecución nueva cada vez).
Todo el contenido es SIMULADO.
"""
import getpass
import http.cookiejar
import json
import os
import platform
import re
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime

BASE = "http://127.0.0.1:8000"
DB = "noc_syslog.db"
BITACORA = os.path.join("docs", "bitacora_marcha_blanca.md")
PY = sys.executable


def llamar(metodo, ruta, cuerpo=None, opener=None):
    datos = json.dumps(cuerpo).encode("utf-8") if cuerpo is not None else None
    req = urllib.request.Request(BASE + ruta, data=datos, method=metodo,
                                 headers={"Content-Type": "application/json"})
    try:
        return (opener or urllib.request.build_opener()).open(req, timeout=8).status
    except urllib.error.HTTPError as e:
        return e.code


def sql(consulta, parametros=()):
    con = sqlite3.connect(DB)
    try:
        return con.execute(consulta, parametros).fetchall()
    except sqlite3.Error:
        return []
    finally:
        con.close()


def alertas_por_tipo():
    return {k: (v or 0) for k, v in sql("SELECT kind, SUM(count) FROM security_alerts GROUP BY kind")}


def simular(escenario):
    r = subprocess.run([PY, "simulador_syslog.py", escenario], capture_output=True, text=True)
    return r.returncode == 0


# ---------------------------------------------------------------- pruebas
def p_unitarias():
    r = subprocess.run([PY, "-m", "unittest", "discover", "-s", "tests"], capture_output=True, text=True)
    m = re.search(r"Ran (\d+) tests?", r.stderr)
    n = m.group(1) if m else "?"
    if r.returncode == 0:
        return "OK", f"{n} pruebas automáticas, todas correctas"
    return "FALLA", f"{n} pruebas, con fallos (ver: python -m unittest discover -s tests -v)"


def p_sin_sesion():
    c = llamar("GET", "/api/devices/")
    return ("OK" if c == 401 else "FALLA"), f"GET /api/devices/ sin sesión -> {c} (esperado 401)"


def p_login_malo():
    c = llamar("POST", "/api/auth/login", {"username": "usuario-inexistente", "password": "clave-incorrecta"})
    return ("OK" if c == 401 else "FALLA"), f"login con credenciales falsas -> {c} (esperado 401)"


def p_roles(clave):
    if not clave:
        return "OMITIDA", "no se indicó la contraseña de operador1"
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    c0 = llamar("POST", "/api/auth/login", {"username": "operador1", "password": clave}, op)
    if c0 != 200:
        return "FALLA", f"login de operador1 -> {c0} (¿contraseña incorrecta?)"
    c1 = llamar("DELETE", "/api/devices/9999", None, op)      # id inexistente: no borra nada
    c2 = llamar("GET", "/api/audit/", None, op)
    ok = c1 == 403 and c2 == 403
    return ("OK" if ok else "FALLA"), f"operador1: DELETE /api/devices/9999 -> {c1} y GET /api/audit/ -> {c2} (esperado 403 y 403)"


def p_defensa():
    antes = alertas_por_tipo()
    simular("nombre")
    simular("fuerza")
    time.sleep(3)
    despues = alertas_por_tipo()
    a = despues.get("HOSTNAME_NO_COINCIDE", 0) - antes.get("HOSTNAME_NO_COINCIDE", 0)
    b = despues.get("POSIBLE_FUERZA_BRUTA", 0) - antes.get("POSIBLE_FUERZA_BRUTA", 0)
    det = f"HOSTNAME_NO_COINCIDE +{a}, POSIBLE_FUERZA_BRUTA +{b}"
    if a > 0 and b > 0:
        return "OK", det
    return "FALLA", det + " (¿receptor encendido? ¿repetido antes de 1 minuto?)"


def p_carga(conservar):
    antes = sql("SELECT COUNT(*) FROM syslog_events WHERE parsed_program='test'")[0][0]
    a_antes = alertas_por_tipo().get("TORMENTA_DE_EVENTOS", 0)
    t0 = time.time()
    simular("tormenta")
    envio = time.time() - t0
    time.sleep(4)
    nuevos = sql("SELECT COUNT(*) FROM syslog_events WHERE parsed_program='test'")[0][0] - antes
    a_desp = alertas_por_tipo().get("TORMENTA_DE_EVENTOS", 0) - a_antes
    limpieza = ""
    if not conservar and nuevos > 0:
        con = sqlite3.connect(DB)
        con.execute("DELETE FROM syslog_events WHERE parsed_program='test'")
        con.commit()
        con.close()
        limpieza = f"; {nuevos} eventos de prueba eliminados"
    det = (f"150 mensajes enviados en {envio:.2f} s; guardados {nuevos} (tope 100 por minuto); "
           f"alertas de tormenta +{a_desp}{limpieza}")
    return ("OK" if 50 <= nuevos <= 100 and a_desp > 0 else "FALLA"), det


def p_respaldo(estado):
    import backup_db
    try:
        ruta = backup_db.respaldar()
    except Exception as e:
        return "FALLA", str(e)
    estado["respaldo"] = ruta
    filas = backup_db.contar_tablas(ruta)
    return "OK", f"{ruta}; integridad ok; {len(filas)} tablas, {sum(filas.values())} filas"


def p_recuperacion(estado):
    import restore_db
    if "respaldo" not in estado:
        return "OMITIDA", "no hay respaldo de la prueba anterior"
    try:
        integ, filas, actuales = restore_db.probar(estado["respaldo"])
    except Exception as e:
        return "FALLA", str(e)
    ok = integ == "ok" and len(filas) > 0 and set(filas) == set(actuales)
    return ("OK" if ok else "FALLA"), (f"restauración de prueba en archivo temporal: integridad {integ}; "
                                      f"{len(filas)} tablas y {sum(filas.values())} filas recuperadas (la base actual no se tocó)")


def p_secretos():
    try:
        lista = subprocess.run(["git", "ls-files"], capture_output=True, text=True, check=True).stdout.splitlines()
    except Exception:
        return "OMITIDA", "git no está disponible"
    problemas = []
    for f in lista:
        if f == ".env" or f.endswith((".db", ".sqlite3")):
            problemas.append(f"archivo sensible versionado: {f}")
            continue
        if not f.endswith((".py", ".md", ".js", ".html", ".txt", ".example")):
            continue
        try:
            texto = open(f, encoding="utf-8", errors="ignore").read()
        except OSError:
            continue
        if re.search(r"\b\d{8,10}:[A-Za-z0-9_-]{35}\b", texto):
            problemas.append(f"posible token de Telegram en {f}")
        if re.search(r"TELEGRAM_BOT_TOKEN[ \t]*=[ \t]*['\"]?[A-Za-z0-9:_-]{20,}", texto):
            problemas.append(f"TELEGRAM_BOT_TOKEN con valor en {f}")
    ignorado = subprocess.run(["git", "check-ignore", "-q", ".env"]).returncode == 0
    if not ignorado:
        problemas.append(".env no está en .gitignore")
    if problemas:
        return "FALLA", "; ".join(problemas)
    return "OK", f"{len(lista)} archivos versionados revisados: sin .env, sin bases de datos, sin tokens; .env ignorado por Git"


# ---------------------------------------------------------------- bitácora
def escribir(resultados):
    os.makedirs("docs", exist_ok=True)
    previo = open(BITACORA, encoding="utf-8").read() if os.path.exists(BITACORA) else \
        "# Bitácora de marcha blanca · NOC Syslog Inteligente v1.0.0\n\nDatos SIMULADOS.\n"
    n = previo.count("## Ejecución #") + 1
    ok = sum(1 for _, e, _ in resultados if e == "OK")
    mal = sum(1 for _, e, _ in resultados if e == "FALLA")
    om = sum(1 for _, e, _ in resultados if e == "OMITIDA")
    lineas = [f"\n## Ejecución #{n} · {datetime.now():%Y-%m-%d %H:%M}\n",
              f"Ambiente: {platform.system()} {platform.release()}, Python {platform.python_version()}, "
              f"servidor {BASE}, datos simulados.\n",
              "| # | Prueba | Resultado | Detalle |", "|---|---|---|---|"]
    for i, (nombre, estado, detalle) in enumerate(resultados, 1):
        lineas.append(f"| {i} | {nombre} | {estado} | {detalle.replace('|', '/')} |")
    lineas.append(f"\nResumen: {ok} OK, {mal} FALLA, {om} OMITIDA.\n")
    with open(BITACORA, "w", encoding="utf-8") as f:
        f.write(previo.rstrip("\n") + "\n" + "\n".join(lineas))
    return ok, mal, om


def main():
    conservar = "--conservar" in sys.argv
    clave = os.getenv("MB_CLAVE_OPERADOR") or getpass.getpass("Contraseña de operador1 (Enter para omitir): ")
    estado = {}
    plan = [
        ("Pruebas automáticas del núcleo", p_unitarias),
        ("Seguridad: API sin sesión rechazada", p_sin_sesion),
        ("Seguridad: login con credenciales falsas rechazado", p_login_malo),
        ("Seguridad: roles (operador sin permiso de borrar ni de auditoría)", lambda: p_roles(clave)),
        ("Defensa: nombre falso y fuerza bruta generan alertas", p_defensa),
        ("Carga básica: 150 mensajes en ráfaga", lambda: p_carga(conservar)),
        ("Respaldo de la base de datos", lambda: p_respaldo(estado)),
        ("Recuperación: restauración de prueba", lambda: p_recuperacion(estado)),
        ("Secretos: nada sensible en el repositorio", p_secretos),
    ]
    resultados = []
    for nombre, fn in plan:
        print(f"... {nombre}")
        try:
            e, d = fn()
        except urllib.error.URLError:
            e, d = "FALLA", "el servidor no responde (¿está encendido en 127.0.0.1:8000?)"
        except Exception as ex:
            e, d = "FALLA", f"{type(ex).__name__}: {ex}"
        print(f"    {e}: {d}")
        resultados.append((nombre, e, d))
    ok, mal, om = escribir(resultados)
    print(f"\nResumen: {ok} OK, {mal} FALLA, {om} OMITIDA. Bitácora: {BITACORA}")
    return 0 if mal == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
