"""Restauración de la base de datos desde un respaldo.

Uso:
  python restore_db.py backups\\archivo.db --probar   # verifica el respaldo SIN tocar la base actual
  python restore_db.py backups\\archivo.db            # restaura (DETENER servidor y receptor antes)

Antes de restaurar de verdad se guarda una copia de seguridad de la base actual
(backups/antes_de_restaurar_*.db), para poder deshacer.
"""
import os
import sqlite3
import sys
import tempfile
from datetime import datetime

from backup_db import DB, CARPETA, contar_tablas, integridad, respaldar


def probar(respaldo: str, actual: str = DB):
    """Restaura el respaldo en un archivo temporal y lo comprueba.

    Devuelve (integridad, filas_del_respaldo, filas_de_la_base_actual).
    No modifica la base actual.
    """
    if not os.path.exists(respaldo):
        raise FileNotFoundError(f"No existe el respaldo: {respaldo}")
    temporal = os.path.join(tempfile.mkdtemp(), "restaurada.db")
    src, dst = sqlite3.connect(respaldo), sqlite3.connect(temporal)
    try:
        with dst:
            src.backup(dst)
    finally:
        src.close()
        dst.close()
    estado = integridad(temporal)
    filas = contar_tablas(temporal)
    actuales = contar_tablas(actual) if os.path.exists(actual) else {}
    os.remove(temporal)
    return estado, filas, actuales


def restaurar(respaldo: str, destino: str = DB) -> str:
    """Restaura de verdad. Devuelve la ruta de la copia de seguridad de la base anterior."""
    if not os.path.exists(respaldo):
        raise FileNotFoundError(f"No existe el respaldo: {respaldo}")
    if integridad(respaldo) != "ok" or not contar_tablas(respaldo):
        raise RuntimeError("El respaldo está dañado o vacío: no se restaura")
    previa = ""
    if os.path.exists(destino):
        previa = respaldar(destino, CARPETA)
        nombre = os.path.join(CARPETA, f"antes_de_restaurar_{datetime.now():%Y%m%d_%H%M%S}.db")
        os.replace(previa, nombre)
        previa = nombre
    src, dst = sqlite3.connect(respaldo), sqlite3.connect(destino)
    try:
        with dst:
            src.backup(dst)
    finally:
        src.close()
        dst.close()
    if integridad(destino) != "ok":
        raise RuntimeError("La base restaurada no pasó la comprobación de integridad")
    return previa


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    solo_probar = "--probar" in sys.argv
    if len(args) != 1:
        print(__doc__)
        return 1
    try:
        if solo_probar:
            estado, filas, actuales = probar(args[0])
            print(f"Integridad del respaldo: {estado}")
            print("Tabla".ljust(24) + "Respaldo".rjust(10) + "Actual".rjust(10))
            for t in sorted(set(filas) | set(actuales)):
                print(t.ljust(24) + str(filas.get(t, "-")).rjust(10) + str(actuales.get(t, "-")).rjust(10))
            return 0 if estado == "ok" and filas else 1
        print("ATENCIÓN: detén el servidor y el receptor antes de restaurar.")
        if input("Escribe SI para restaurar: ").strip() != "SI":
            print("Cancelado.")
            return 1
        previa = restaurar(args[0])
        print(f"Restaurado desde {args[0]}")
        if previa:
            print(f"Copia de la base anterior: {previa}")
        print("Filas por tabla: " + ", ".join(f"{k}={v}" for k, v in contar_tablas(DB).items()))
        return 0
    except Exception as e:
        print(f"ERROR: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
