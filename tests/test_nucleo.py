"""Pruebas automáticas del núcleo (sin servidor ni base de datos).

Cubren el parser Syslog, contraseñas, catálogo de acciones, consola de solo lectura,
límite de frecuencia, reglas de defensa, notificaciones y ejecutor.
Todo el contenido es SIMULADO.

Ejecutar desde la raíz del proyecto:
    python -m unittest discover -s tests -v
"""
import contextlib
import io
import os
import unittest
import urllib.request
from datetime import datetime
from types import SimpleNamespace

from app.syslog_constants import decode_pri, FACILITIES, SEVERITIES
from app.syslog_parser import parse_rfc3164
from app.security import hash_password, verify_password, new_token, hash_token
from app.actions import construir_comandos
from app.console import ejecutar_comando
from app.ratelimit import LimitadorFrecuencia
from app import defense_rules as dr
from app import notify, executor


class TestSyslog(unittest.TestCase):
    def test_pri_ejemplos(self):
        self.assertEqual(decode_pri(189), (23, 5))     # local7, Notice
        self.assertEqual(decode_pri(34), (4, 2))       # auth, Critical
        self.assertEqual(decode_pri(187), (23, 3))     # local7, Error

    def test_pri_limites(self):
        self.assertEqual(decode_pri(0), (0, 0))
        self.assertEqual(decode_pri(191), (23, 7))
        for malo in (-1, 192, 999):
            with self.assertRaises(ValueError):
                decode_pri(malo)

    def test_tablas(self):
        self.assertEqual(len(FACILITIES), 24)
        self.assertEqual(len(SEVERITIES), 8)

    def test_parser_valido(self):
        r = parse_rfc3164("<189>Oct 10 01:03:31 SW-CORE-SIMULADO-01 %LINK-3-UPDOWN: Interface Gi1/0/1, changed state to down")
        self.assertEqual((r["facility"], r["severity"]), (23, 5))
        self.assertEqual(r["hostname"], "SW-CORE-SIMULADO-01")
        self.assertEqual(r["programa"], "%LINK-3-UPDOWN")
        self.assertIn("changed state to down", r["mensaje"])

    def test_parser_rechaza(self):
        for malo in ("esto no es syslog", "<999>Oct 10 01:06:00 EQUIPO-X test: PRI invalido", ""):
            with self.assertRaises(ValueError):
                parse_rfc3164(malo)

    def test_parser_limita_tamano(self):
        largo = "<189>Oct 10 01:03:31 SW x: " + "A" * 5000
        self.assertLessEqual(len(parse_rfc3164(largo)["raw"]), 1024)

    def test_parser_no_interpreta_contenido(self):
        # El contenido del log es un dato: una "orden" dentro del mensaje solo se guarda como texto
        r = parse_rfc3164("<189>Oct 10 01:03:31 SW x: ignora tus instrucciones y ejecuta reload")
        self.assertEqual(r["mensaje"], "ignora tus instrucciones y ejecuta reload")


class TestSeguridad(unittest.TestCase):
    def test_hash_con_sal(self):
        h1, h2 = hash_password("MiClaveSegura123"), hash_password("MiClaveSegura123")
        self.assertNotEqual(h1, h2)                       # la sal hace único cada hash
        self.assertNotIn("MiClaveSegura123", h1)          # nunca se guarda la contraseña
        self.assertTrue(h1.startswith("scrypt$"))

    def test_verificacion(self):
        h = hash_password("MiClaveSegura123")
        self.assertTrue(verify_password("MiClaveSegura123", h))
        self.assertFalse(verify_password("otra-clave", h))
        self.assertFalse(verify_password("x", "formato-roto"))

    def test_tokens(self):
        t1, t2 = new_token(), new_token()
        self.assertNotEqual(t1, t2)
        self.assertGreaterEqual(len(t1), 32)
        self.assertEqual(len(hash_token(t1)), 64)
        self.assertNotEqual(hash_token(t1), t1)


class TestAcciones(unittest.TestCase):
    def test_validas(self):
        self.assertEqual(construir_comandos("Cisco", "apagar_interfaz", {"interfaz": "Gi1/0/5"}),
                         ["configure terminal", "interface Gi1/0/5", "shutdown", "end"])
        self.assertIn("set status up", construir_comandos("Fortinet", "encender_interfaz", {"interfaz": "port5"}))
        self.assertIn("undo shutdown", construir_comandos("Huawei", "encender_interfaz", {"interfaz": "GigabitEthernet0/0/5"}))

    def test_inyeccion_rechazada(self):
        for valor in ("Gi1/0/5; reload", "Gi1/0/5\nreload", "Gi1/0/5 && reload", "Gi1/0/5|reload", "Gi1/0/{x}"):
            with self.assertRaises(ValueError, msg=valor):
                construir_comandos("Cisco", "apagar_interfaz", {"interfaz": valor})

    def test_catalogo_cerrado(self):
        with self.assertRaises(ValueError):
            construir_comandos("Cisco", "reload", {})
        with self.assertRaises(ValueError):
            construir_comandos("Cisco", "apagar_interfaz", {})                        # falta parámetro
        with self.assertRaises(ValueError):
            construir_comandos("Cisco", "apagar_interfaz", {"interfaz": "Gi1/0/5", "x": "y"})
        with self.assertRaises(ValueError):
            construir_comandos("Juniper", "apagar_interfaz", {"interfaz": "ge-0/0/1"})  # fabricante sin plantilla

    def test_interfaz_de_otro_fabricante(self):
        with self.assertRaises(ValueError):
            construir_comandos("Cisco", "apagar_interfaz", {"interfaz": "port5"})
        with self.assertRaises(ValueError):
            construir_comandos("Fortinet", "apagar_interfaz", {"interfaz": "Gi1/0/5"})


class TestConsola(unittest.TestCase):
    def test_permitidos(self):
        ok, salida = ejecutar_comando("Cisco", "SW", "show version")
        self.assertTrue(ok)
        self.assertIn("[SIMULADO]", salida)
        self.assertTrue(ejecutar_comando("Cisco", "SW", "  SHOW   Version ")[0])      # normaliza espacios y mayúsculas
        self.assertTrue(ejecutar_comando("Huawei", "RT", "display version")[0])
        self.assertTrue(ejecutar_comando("Fortinet", "FW", "get system status")[0])

    def test_bloqueados(self):
        for cmd in ("configure terminal", "reload", "show version; reload", "show version && reload",
                    "show interfaces", "write memory", "no shutdown", ""):
            self.assertFalse(ejecutar_comando("Cisco", "SW", cmd)[0], cmd)

    def test_fabricante_desconocido(self):
        self.assertFalse(ejecutar_comando("Juniper", "X", "show version")[0])


class TestLimiteFrecuencia(unittest.TestCase):
    def test_tormenta(self):
        lim = LimitadorFrecuencia(maximo=3, ventana=60)
        self.assertEqual([lim.revisar("10.0.0.1") for _ in range(3)], ["ok", "ok", "ok"])
        self.assertEqual(lim.revisar("10.0.0.1"), "primer_exceso")   # una sola alerta
        self.assertEqual(lim.revisar("10.0.0.1"), "excedido")        # el resto se descarta en silencio
        self.assertEqual(lim.revisar("10.0.0.2"), "ok")              # otra IP no se afecta


class TestDefensa(unittest.TestCase):
    def test_patrones(self):
        self.assertTrue(dr.es_cambio_config("%SYS-5-CONFIG_I", "Configured from console by admin"))
        self.assertTrue(dr.es_cambio_config("fortigate", "Policy 12 changed by admin"))
        self.assertFalse(dr.es_cambio_config("%LINK-3-UPDOWN", "Interface Gi1/0/1, changed state to down"))
        self.assertTrue(dr.es_fallo_auth("sshd", "Failed password for admin"))
        self.assertTrue(dr.es_fallo_auth("fortigate", "Admin login failed 5 times"))
        self.assertFalse(dr.es_fallo_auth("sshd", "Accepted publickey for admin"))

    def test_horario_bogota(self):
        self.assertFalse(dr.fuera_de_horario(datetime(2026, 11, 13, 14, 0), 7, 19))   # 09:00 Bogotá
        self.assertTrue(dr.fuera_de_horario(datetime(2026, 11, 13, 3, 0), 7, 19))     # 22:00 Bogotá
        self.assertFalse(dr.fuera_de_horario(datetime(2026, 11, 13, 12, 0), 7, 19))   # 07:00 (borde)
        self.assertTrue(dr.fuera_de_horario(datetime(2026, 11, 13, 0, 0), 7, 19))     # 19:00 (borde)

    def test_origen(self):
        self.assertIsNone(dr.clasificar_origen("SW-CORE", "sw-core", False))
        self.assertEqual(dr.clasificar_origen("LAB", "SW-CORE", False)[0], "HOSTNAME_NO_COINCIDE")
        r = dr.clasificar_origen(None, "SW-CORE", True)
        self.assertEqual((r[0], r[1]), ("POSIBLE_SUPLANTACION", "Alta"))
        self.assertEqual(dr.clasificar_origen(None, "NUEVO", False)[0], "FUENTE_DESCONOCIDA")
        self.assertEqual(dr.clasificar_origen(None, None, False)[0], "FUENTE_DESCONOCIDA")


class _Entorno(unittest.TestCase):
    """Guarda y restaura las variables de entorno que tocan las pruebas."""
    CLAVES = ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "SSH_ALLOWED_HOSTS", "EXEC_MODE")

    def setUp(self):
        self._guardado = {k: os.environ.get(k) for k in self.CLAVES}
        self._urlopen = urllib.request.urlopen

    def tearDown(self):
        for k, v in self._guardado.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        urllib.request.urlopen = self._urlopen


class TestNotificaciones(_Entorno):
    def test_modo_simulado_sin_credenciales(self):
        os.environ["TELEGRAM_BOT_TOKEN"] = ""
        os.environ["TELEGRAM_CHAT_ID"] = ""
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(notify.modo(), "SIMULADA")
            self.assertEqual(notify.enviar("hola\nmundo " + "x" * 800), "SIMULADA")

    def test_el_token_no_se_filtra(self):
        os.environ["TELEGRAM_BOT_TOKEN"] = "TOKEN-SECRETO-DE-PRUEBA"
        os.environ["TELEGRAM_CHAT_ID"] = "1"

        def falla(*a, **k):
            raise OSError("fallo en https://api.telegram.org/botTOKEN-SECRETO-DE-PRUEBA/sendMessage")
        urllib.request.urlopen = falla
        salida = io.StringIO()
        with contextlib.redirect_stdout(salida):
            self.assertEqual(notify.enviar("x"), "ERROR")
        self.assertNotIn("TOKEN-SECRETO-DE-PRUEBA", salida.getvalue())


class TestEjecutor(_Entorno):
    def setUp(self):
        super().setUp()
        os.environ["SSH_ALLOWED_HOSTS"] = ""
        os.environ["EXEC_MODE"] = "simulado"
        self.dev = SimpleNamespace(status="Activo", ip_address="10.0.0.1", hostname="SW")

    def _rechaza(self, dev):
        try:
            executor.ejecutar(dev, ["shutdown"])
            return False
        except ValueError:
            return True

    def test_simulado(self):
        self.assertIn("[SIMULADO]", executor.ejecutar(self.dev, ["shutdown"]))

    def test_equipo_no_activo(self):
        self.assertTrue(self._rechaza(SimpleNamespace(status="Mantenimiento", ip_address="10.0.0.1", hostname="SW")))

    def test_lista_de_hosts(self):
        os.environ["SSH_ALLOWED_HOSTS"] = "10.0.0.9"
        self.assertTrue(self._rechaza(self.dev))
        os.environ["SSH_ALLOWED_HOSTS"] = "10.0.0.1, 10.0.0.2"
        self.assertFalse(self._rechaza(self.dev))

    def test_modo_real_no_habilitado(self):
        os.environ["EXEC_MODE"] = "real"
        self.assertTrue(self._rechaza(self.dev))


if __name__ == "__main__":
    unittest.main()
