"""Puente permanente con backend falso en memoria (sin sockets) y bandeja SQLite real."""
from contextlib import closing
from datetime import datetime, timezone
from hashlib import sha256
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest import mock
import urllib.error

from pipelines.communitylab import prueba_integracion_discord as cli
from pipelines.communitylab.entregas_discord import Entregas
from pipelines.communitylab.puente_discord import Puente, fin_de, latido_sano, periodo_de

URL = "http://api.falsa/api/v1/trabajos"
LUNES_W42 = int(datetime(2026, 10, 12, tzinfo=timezone.utc).timestamp())


class Backend:
    """Imita POST idempotente por Idempotency-Key y GET de estado."""

    def __init__(self):
        self.trabajos, self.posts, self.caido, self.estado, self.rechazo = {}, 0, False, "terminado", None

    def urlopen(self, peticion, timeout=None):
        if self.caido:
            raise urllib.error.URLError("caida")
        if peticion.get_method() == "POST":
            self.posts += 1
            if self.rechazo:
                raise urllib.error.HTTPError(peticion.full_url, self.rechazo, "x", {}, io.BytesIO(b"{}"))
            clave = peticion.get_header("Idempotency-key")
            trabajo = self.trabajos.setdefault(clave, {"id": f"t{len(self.trabajos) + 1}",
                                                       "lote": json.loads(peticion.data)})
            cuerpo = {"procesamiento_id": trabajo["id"], "estado": "recibido"}
        else:
            trabajo_id = peticion.full_url.rsplit("/", 1)[-1]
            if trabajo_id not in {t["id"] for t in self.trabajos.values()}:
                raise urllib.error.HTTPError(peticion.full_url, 404, "x", {}, io.BytesIO(b"{}"))
            cuerpo = {"estado": self.estado}
        return _Resp(json.dumps(cuerpo).encode())


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


def evento(mid, fecha="2026-10-13T10:00:00Z", texto=None):
    return {"schema_version": "discord-source-v1", "message_id": str(mid), "guild_id": "1",
            "channel_id": "2", "author_id": f"a{mid}", "created_at": fecha,
            "content": texto or f"Mensaje ficticio {mid}"}


class PruebasPuente(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.bandeja = self.dir / "bandeja.sqlite3"
        with closing(sqlite3.connect(self.bandeja)) as c, c:  # mismo esquema que discord_reader.store.Inbox
            c.execute("CREATE TABLE messages (sequence INTEGER PRIMARY KEY AUTOINCREMENT, guild_id TEXT, "
                      "message_id TEXT, payload TEXT, UNIQUE(guild_id, message_id))")
        self.backend = Backend()
        parche = mock.patch.object(cli.urllib.request, "urlopen", self.backend.urlopen)
        parche.start()
        self.addCleanup(parche.stop)
        self.ahora = LUNES_W42 + 8 * 86400  # martes de la semana siguiente: W42 vencida

    def tearDown(self):
        self.tmp.cleanup()

    def agregar(self, *eventos):
        with closing(sqlite3.connect(self.bandeja)) as c, c:
            for e in eventos:
                c.execute("INSERT INTO messages(guild_id,message_id,payload) VALUES (?,?,?)",
                          (e["guild_id"], e["message_id"], json.dumps(e)))

    def puente(self, **kw):
        return Puente(self.dir / "estado.sqlite3", self.bandeja, URL, gracia=3600,
                      reloj=lambda: self.ahora, latido=self.dir / "latido.json", **kw)

    def entregas(self):
        with Entregas(self.dir / "estado.sqlite3").conexion() as c:
            return [dict(r) for r in c.execute("SELECT * FROM entregas")]

    def test_periodo_vencido_se_envia_una_vez_con_cierre_y_termina(self):
        self.agregar(evento(1), evento(2))
        p = self.puente()
        r = p.ciclo()
        self.assertEqual((r["planificados"], r["enviados"], r["finalizados"]), (1, 1, 1))
        lote = next(iter(self.backend.trabajos.values()))["lote"]
        self.assertIs(lote["cierre_periodo"], True)
        self.assertEqual(lote["periodo_referencia"], "2026-W42")
        self.assertEqual(self.entregas()[0]["estado"], "terminado")
        r = p.ciclo()
        self.assertEqual((r["planificados"], r["enviados"], self.backend.posts), (0, 0, 1))

    def test_periodo_abierto_espera_hasta_cierre_explicito(self):
        self.ahora = LUNES_W42 + 2 * 86400
        self.agregar(evento(1))
        p = self.puente()
        self.assertEqual(p.ciclo()["planificados"], 0)
        p.solicitar_cierre("2026-W42")
        self.assertEqual(p.ciclo()["planificados"], 1)
        self.assertEqual(self.backend.posts, 1)

    def test_api_caida_no_pierde_nada_y_reintenta(self):
        self.agregar(evento(1))
        self.backend.caido = True
        r = self.puente().ciclo()
        self.assertTrue(r["sin_conexion"])
        self.assertEqual(self.entregas()[0]["estado"], "pendiente")
        self.backend.caido = False
        r = self.puente().ciclo()  # nuevo proceso, mismo estado
        self.assertEqual((r["enviados"], r["finalizados"], len(self.backend.trabajos)), (1, 1, 1))

    def test_caida_entre_post_y_checkpoint_no_duplica_trabajo(self):
        self.agregar(evento(1), evento(2))
        p = self.puente()
        with mock.patch.object(Entregas, "confirmar", side_effect=RuntimeError("caida del proceso")):
            with self.assertRaises(RuntimeError):
                p.ciclo()
        self.assertEqual((self.backend.posts, self.entregas()[0]["trabajo"]), (1, None))
        self.puente().ciclo()  # reinicio: reenvía el mismo payload con la misma clave
        self.assertEqual((self.backend.posts, len(self.backend.trabajos)), (2, 1))
        self.assertEqual(self.entregas()[0]["estado"], "terminado")

    def test_caida_antes_del_post_conserva_payload_y_clave(self):
        self.agregar(evento(1))
        with mock.patch("pipelines.communitylab.puente_discord.enviar_lote", side_effect=RuntimeError("caida")):
            with self.assertRaises(RuntimeError):
                self.puente().ciclo()
        guardada = self.entregas()[0]
        self.assertEqual((guardada["estado"], self.backend.posts), ("pendiente", 0))
        self.puente().ciclo()
        self.assertEqual(next(iter(self.backend.trabajos)), guardada["clave"])

    def test_trabajo_aceptado_sin_terminar_no_se_da_por_completado(self):
        self.agregar(evento(1))
        self.backend.estado = "procesando"
        self.puente().ciclo()
        self.assertEqual(self.entregas()[0]["estado"], "aceptado")
        self.backend.estado = "terminado"
        self.puente().ciclo()
        self.assertEqual((self.entregas()[0]["estado"], self.backend.posts), ("terminado", 1))

    def test_trabajo_con_error_y_rechazo_quedan_para_revision(self):
        self.agregar(evento(1))
        self.backend.estado = "error"
        self.puente().ciclo()
        self.assertEqual(self.entregas()[0]["estado"], "error")
        self.puente().ciclo()
        self.assertEqual(self.backend.posts, 1)
        otro = Backend()
        otro.rechazo = 422
        with mock.patch.object(cli.urllib.request, "urlopen", otro.urlopen):
            self.agregar(evento(9, fecha="2026-10-20T10:00:00Z"))
            self.ahora += 7 * 86400
            self.puente().ciclo()
            self.puente().ciclo()
        self.assertEqual(otro.posts, 1)
        self.assertIn("rechazado", {e["estado"] for e in self.entregas()})

    def test_mensajes_tardios_se_registran_y_no_se_envian(self):
        self.agregar(evento(1))
        p = self.puente()
        p.ciclo()
        self.agregar(evento(2, fecha="2026-10-14T09:00:00Z"))
        self.assertEqual(p.ciclo()["tardios_nuevos"], 1)
        self.assertEqual(p.ciclo()["tardios_nuevos"], 0)
        self.assertEqual((self.backend.posts, p.resumen_estado()["tardios"]), (1, 1))

    def test_exportacion_creciente_abre_un_periodo_nuevo_sin_tocar_el_anterior(self):
        self.agregar(evento(1))
        p = self.puente()
        p.ciclo()
        self.agregar(evento(5, fecha="2026-10-20T10:00:00Z"))
        self.ahora += 7 * 86400
        r = p.ciclo()
        self.assertEqual((r["planificados"], len(self.backend.trabajos)), (1, 2))
        periodos = sorted(t["lote"]["periodo_referencia"] for t in self.backend.trabajos.values())
        self.assertEqual(periodos, ["2026-W42", "2026-W43"])

    def test_no_modifica_la_bandeja(self):
        self.agregar(evento(1), evento(2))
        antes = sha256(self.bandeja.read_bytes()).hexdigest()
        self.puente().ciclo()
        self.assertEqual(sha256(self.bandeja.read_bytes()).hexdigest(), antes)

    def test_registros_invalidos_no_detienen_el_resto(self):
        self.agregar(evento(1), evento(2, fecha="sin-zona"))
        r = self.puente().ciclo()
        self.assertEqual((r["rechazados_bandeja"], len(self.backend.trabajos)), (1, 1))

    def test_reconciliar_tras_restaurar_la_base(self):
        self.agregar(evento(1))
        p = self.puente()
        p.ciclo()
        self.assertEqual(self.entregas()[0]["estado"], "terminado")
        clave = self.entregas()[0]["clave"]
        self.backend.trabajos.clear()  # la base restaurada ya no tiene ese trabajo
        self.assertEqual(p.reconciliar(), {"verificadas": 0, "reabiertas": 1})
        p.ciclo()
        self.assertEqual(list(self.backend.trabajos), [clave])  # misma clave, mismo payload
        self.assertEqual(self.entregas()[0]["estado"], "terminado")
        self.assertEqual(p.reconciliar(), {"verificadas": 1, "reabiertas": 0})

    def test_latido(self):
        p = self.puente()
        p.escribir_latido(p.ciclo())
        self.assertTrue(latido_sano(self.dir / "latido.json", 60, reloj=lambda: self.ahora + 10))
        self.assertFalse(latido_sano(self.dir / "latido.json", 60, reloj=lambda: self.ahora + 120))
        self.assertFalse(latido_sano(self.dir / "no_existe.json", 60))

    def test_periodos(self):
        self.assertEqual(periodo_de("2026-10-12T00:00:00+00:00", "semana"), "2026-W42")
        self.assertEqual(periodo_de("2026-10-11T23:59:59+00:00", "semana"), "2026-W41")
        self.assertEqual(periodo_de("2026-10-12T05:00:00+00:00", "dia"), "2026-10-12")
        self.assertEqual(fin_de("2026-W42", "semana").timestamp(), LUNES_W42 + 7 * 86400)
        self.assertEqual(fin_de("2026-10-12", "dia").timestamp(), LUNES_W42 + 86400)


if __name__ == "__main__":
    unittest.main()
