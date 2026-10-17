"""Procesamiento parcial bajo demanda en el puente: backend falso en memoria, sin sockets."""
from contextlib import closing
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest import mock
import urllib.error

from pipelines.communitylab import prueba_integracion_discord as cli
from pipelines.communitylab.puente_discord import Puente

URL = "http://api.falsa/api/v1/trabajos"
CONTROL = "http://api.falsa/api/v1/puente"
LUNES_W42 = int(datetime(2026, 10, 12, tzinfo=timezone.utc).timestamp())


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


class Backend:
    """Trabajos idempotentes por Idempotency-Key + control de solicitudes con token."""

    def __init__(self):
        self.trabajos, self.estado, self.caido = {}, "recibido", False
        self.solicitudes = []        # ids pendientes de entregar al puente
        self.informes, self.tomas = [], []
        self.posts_trabajo = 0

    def urlopen(self, peticion, timeout=None):
        if self.caido:
            raise urllib.error.URLError("caida")
        url = peticion.full_url
        if url.startswith(CONTROL):
            if peticion.get_header("Authorization") != "Bearer token-local-prueba":
                raise urllib.error.HTTPError(url, 401, "x", {}, io.BytesIO(b"{}"))
            datos = json.loads(peticion.data)
            if url.endswith("/solicitudes/tomar"):
                self.tomas.append(datos)
                return _Resp(json.dumps({"id": self.solicitudes.pop(0) if self.solicitudes else None}).encode())
            self.informes.append((url.split("/")[-2], datos))
            return _Resp(b'{"ok": true}')
        if peticion.get_method() == "POST":
            self.posts_trabajo += 1
            clave = peticion.get_header("Idempotency-key")
            t = self.trabajos.setdefault(clave, {"id": f"t{len(self.trabajos) + 1}",
                                                 "lote": json.loads(peticion.data), "estado": None})
            return _Resp(json.dumps({"procesamiento_id": t["id"], "estado": "recibido"}).encode())
        trabajo_id = url.rsplit("/", 1)[-1]
        t = next(t for t in self.trabajos.values() if t["id"] == trabajo_id)
        return _Resp(json.dumps({"estado": t["estado"] or self.estado}).encode())

    def lotes(self):
        return [t["lote"] for t in self.trabajos.values()]


def evento(mid, fecha="2026-10-13T10:00:00Z"):
    return {"schema_version": "discord-source-v1", "message_id": str(mid), "guild_id": "1",
            "channel_id": "2", "author_id": f"a{mid}", "created_at": fecha,
            "content": f"Mensaje ficticio {mid}"}


class PruebasPuenteParcial(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.bandeja = self.dir / "bandeja.sqlite3"
        with closing(sqlite3.connect(self.bandeja)) as c, c:
            c.execute("CREATE TABLE messages (sequence INTEGER PRIMARY KEY AUTOINCREMENT, guild_id TEXT, "
                      "message_id TEXT, payload TEXT, UNIQUE(guild_id, message_id))")
        self.backend = Backend()
        parche = mock.patch.object(cli.urllib.request, "urlopen", self.backend.urlopen)
        parche.start()
        self.addCleanup(parche.stop)
        self.ahora = LUNES_W42 + 2 * 86400  # miércoles: W42 abierta

    def agregar(self, *ids, fecha="2026-10-13T10:00:00Z"):
        with closing(sqlite3.connect(self.bandeja)) as c, c:
            for i in ids:
                e = evento(i, fecha)
                c.execute("INSERT INTO messages(guild_id,message_id,payload) VALUES (?,?,?)",
                          (e["guild_id"], e["message_id"], json.dumps(e)))

    def puente(self, token="token-local-prueba", **kw):
        return Puente(self.dir / "estado.sqlite3", self.bandeja, URL, gracia=3600,
                      reloj=lambda: self.ahora, token=token, **kw)

    def ids(self, lote, previo=None):
        return sorted(m["id"] for m in lote["interacciones"]
                      if previo is None or bool(m.get("previo")) == previo)

    def test_sin_solicitud_no_envia_parciales_y_reporta_pendientes(self):
        self.agregar(1, 2)
        self.puente().ciclo()
        self.assertEqual(self.backend.posts_trabajo, 0)
        self.assertEqual(self.backend.tomas[-1]["pendientes"], {"2026-W42": 2})

    def test_solicitud_envia_solo_nuevos_sin_cerrar_el_periodo(self):
        self.agregar(1, 2)
        self.backend.solicitudes = ["s1"]
        resumen = self.puente().ciclo()
        self.assertEqual(resumen["parciales"], 1)
        (lote,) = self.backend.lotes()
        self.assertIs(lote["cierre_periodo"], False)
        self.assertEqual(self.ids(lote), ["discord-1", "discord-2"])
        self.assertEqual(self.backend.informes[-1][1]["estado"], "en_curso")

    def test_sin_pendientes_cero_trabajos(self):
        self.backend.solicitudes = ["s1"]
        self.puente().ciclo()
        self.assertEqual(self.backend.posts_trabajo, 0)
        self.assertEqual(self.backend.informes[-1], ("s1", {"origen": "discord", "estado": "sin_pendientes",
                                                          "lotes": [], "pendientes": {}}))

    def test_mensajes_que_llegan_durante_el_proceso_esperan_la_siguiente(self):
        self.agregar(1)
        self.backend.solicitudes = ["s1"]
        p = self.puente()
        p.ciclo()
        self.agregar(2)
        self.backend.solicitudes = ["s2"]
        p.ciclo()  # s1 sigue en curso: no se toma otra ni se mezcla el mensaje 2
        self.assertEqual(len(self.backend.lotes()), 1)
        self.assertEqual(self.backend.tomas, [{"origen": "discord", "pendientes": {"2026-W42": 1}}])
        self.backend.estado = "terminado"
        p.ciclo()   # s1 termina e informa
        self.assertEqual(self.backend.informes[-1][1]["estado"], "finalizada")
        p.ciclo()   # ahora toma s2 con contexto previo
        segundo = self.backend.lotes()[1]
        self.assertEqual((self.ids(segundo, False), self.ids(segundo, True)), (["discord-2"], ["discord-1"]))

    def test_doble_toma_y_reinicio_no_duplican(self):
        self.agregar(1, 2)
        p = self.puente()
        primera = p.planificar_parcial("s1", {"2026-W42": self._mensajes(1, 2)})
        repetida = self.puente().planificar_parcial("s1", {"2026-W42": self._mensajes(1, 2)})
        self.assertEqual([l["clave"] for l in primera], [l["clave"] for l in repetida])
        self.assertEqual(self.puente().planificar_parcial("s2", {"2026-W42": self._mensajes(1, 2)}), [])

    def test_caida_de_api_conserva_el_plan_y_reenvia_misma_clave(self):
        self.agregar(1)
        self.backend.solicitudes = ["s1"]
        p = self.puente()
        with mock.patch.object(Puente, "_entregar", side_effect=cli.SinConexion("x")):
            self.assertTrue(p.ciclo()["sin_conexion"])
        self.assertEqual(self.backend.posts_trabajo, 0)
        self.puente().ciclo()  # tras "reinicio"
        self.puente().ciclo()
        self.assertEqual(len(self.backend.trabajos), 1)  # misma clave: un solo trabajo

    def test_error_libera_mensajes_para_la_proxima_solicitud(self):
        self.agregar(1)
        self.backend.solicitudes = ["s1"]
        p = self.puente()
        p.ciclo()
        self.backend.estado = "error"
        p.ciclo()
        self.assertEqual(self.backend.informes[-1][1]["lotes"][0]["estado"], "error")
        self.backend.solicitudes = ["s2"]
        p.ciclo()
        segundo = self.backend.lotes()[-1]
        self.assertEqual(self.ids(segundo, False), ["discord-1"])
        self.assertEqual(len(self.backend.trabajos), 2)  # clave nueva por solicitud

    def test_cierre_se_aplaza_con_parciales_en_curso_y_marca_previos(self):
        self.agregar(1, 2)
        self.backend.solicitudes = ["s1"]
        p = self.puente()
        p.ciclo()
        self.ahora = LUNES_W42 + 8 * 86400  # W42 vencida
        self.assertEqual(p.ciclo().get("cierres_aplazados"), 1)
        self.backend.estado = "terminado"
        p.ciclo()   # el parcial termina; el cierre se planifica en el ciclo siguiente
        p.ciclo()
        cierre = [l for l in self.backend.lotes() if l["cierre_periodo"]]
        self.assertEqual(len(cierre), 1)
        self.assertEqual(self.ids(cierre[0], True), ["discord-1", "discord-2"])

    def test_limite_de_contexto(self):
        self.agregar(*range(1, 6))
        p = self.puente(max_previos=2)
        p.planificar_parcial("s1", {"2026-W42": self._mensajes(1, 2, 3, 4)})
        with closing(sqlite3.connect(self.dir / "estado.sqlite3")) as c, c:
            c.execute("UPDATE entregas SET estado='terminado'")
        (plan,) = p.planificar_parcial("s2", {"2026-W42": self._mensajes(1, 2, 3, 4, 5)})
        self.assertEqual((plan["nuevos"], plan["contexto"]), (1, 2))

    def test_sin_token_la_funcion_queda_desactivada(self):
        self.agregar(1)
        self.backend.solicitudes = ["s1"]
        self.puente(token=None).ciclo()
        self.assertEqual((self.backend.tomas, self.backend.posts_trabajo), ([], 0))

    def test_token_invalido_no_rompe_el_ciclo(self):
        self.agregar(1)
        resumen = self.puente(token="otro").ciclo()
        self.assertEqual((resumen["sin_conexion"], self.backend.posts_trabajo), (False, 0))

    def _mensajes(self, *ids):
        from pipelines.communitylab.normalizador_discord import normalizar_eventos
        return normalizar_eventos([evento(i) for i in ids])["interacciones"]


if __name__ == "__main__":
    unittest.main()
