"""Respaldo de la base de datos SQLite con la API de respaldo en línea de SQLite.

Uso:  python backup_db.py

Crea backups/noc_syslog_AAAAMMDD_HHMMSS.db y comprueba su integridad.
Se puede ejecutar con el servidor encendido. La carpeta backups/ no se sube a GitHub.
"""
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

DB = "noc_syslog.db"
CARPETA = "backups"


def abrir_lectura(ruta: str):
    """Abre una base SQLite SOLO de lectura (si no existe, falla en vez de crear un archivo vacío)."""
    return sqlite3.connect(Path(ruta).resolve().as_uri() + "?mode=ro", uri=True)


def contar_tablas(ruta: str) -> dict:
    """Devuelve {tabla: número de filas} de una base SQLite."""
    con = abrir_lectura(ruta)
    try:
        nombres = [r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        return {n: con.execute(f'SELECT COUNT(*) FROM "{n}"').fetchone()[0] for n in nombres}
    finally:
        con.close()


def integridad(ruta: str) -> str:
    """'ok' si la base pasa PRAGMA integrity_check."""
    con = abrir_lectura(ruta)
    try:
        return con.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        con.close()


def respaldar(origen: str = DB, carpeta: str = CARPETA) -> str:
    """Copia consistente de la base. Devuelve la ruta del respaldo."""
    if not os.path.exists(origen):
        raise FileNotFoundError(f"No existe la base de datos: {origen}")
    os.makedirs(carpeta, exist_ok=True)
    base = f"noc_syslog_{datetime.now():%Y%m%d_%H%M%S}"
    destino, n = os.path.join(carpeta, base + ".db"), 1
    while os.path.exists(destino):              # nunca sobrescribir un respaldo existente
        n += 1
        destino = os.path.join(carpeta, f"{base}_{n}.db")
    src, dst = sqlite3.connect(origen), sqlite3.connect(destino)
    try:
        with dst:
            src.backup(dst)
    finally:
        src.close()
        dst.close()
    if integridad(destino) != "ok":
        raise RuntimeError(f"El respaldo {destino} no pasó la comprobación de integridad")
    return destino


def main() -> int:
    try:
        ruta = respaldar()
    except Exception as e:
        print(f"ERROR: {e}")
        return 1
    tablas = contar_tablas(ruta)
    print(f"Respaldo creado: {ruta}")
    print("Integridad: ok")
    print("Filas por tabla: " + ", ".join(f"{k}={v}" for k, v in tablas.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
