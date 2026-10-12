"""
test_contrato_io.py — Pruebas de la capa de contratos adaptadas a classifier.py.

Ejecutar:
    python -m unittest test_contrato_io -v
Clasificador real (motor fallback léxico) + generador simulado (FakeGen). Sin red.
"""
from __future__ import annotations

import asyncio
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))

from classifier import (
    BLOQUEO_FRUSTRACION,
    CLASES_OBJETIVO,
    DUDA_TECNICA,
    LOGRO,
    MAX_RESPUESTA,
    NO_CLASIFICADO,
    RUIDO,
    SCHEMA_ENTRADA,
    SCHEMA_SALIDA,
    ClasificacionResultado,
    ClasificadorInteracciones,
    ContratoInvalidoError,
    DiscordDecisionV1,
    DiscordSourceV1,
    GeneracionSalida,
    GeneradorIA,
)

T0 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
BLOQUEO = "estoy harto, nada me compila"
LOGRO = "por fin me funcionó el código"
DUDA = "¿cómo instalo un paquete con pip?"
RUIDO = "jajaja buenos días a todos"


def fuente(texto: str, i: int = 0, autor: str = "42", guild: str = "g", canal: str = "c", minutos: int = 0) -> DiscordSourceV1:
    return DiscordSourceV1(
        schema_version=SCHEMA_ENTRADA,
        message_id=str(i),
        guild_id=guild,
        channel_id=canal,
        author_id=autor,
        created_at=(T0 + timedelta(minutes=minutos)).isoformat(),
        content=texto,
    )


class FakeGen:
    """Generador externo simulado conforme al protocolo GeneradorIA de classifiertwo."""

    def __init__(self, accion=None):
        self.llamadas: List[Tuple[DiscordSourceV1, ClasificacionResultado]] = []
        self.accion = accion

    def generar(self, fuente: DiscordSourceV1, resultado: ClasificacionResultado) -> GeneracionSalida:
        self.llamadas.append((fuente, resultado))
        if self.accion:
            r = self.accion(fuente, resultado)
            if isinstance(r, BaseException):
                raise r
            if isinstance(r, GeneracionSalida):
                return r
            if isinstance(r, str):
                return GeneracionSalida(tema="general", respuesta=r, alerta="texto-alerta")
            return r

        # Comportamiento predeterminado según la clase clasificada
        if resultado.clase == BLOQUEO_FRUSTRACION:
            return GeneracionSalida(tema="general", respuesta="", alerta="texto-alerta")
        return GeneracionSalida(tema="general", respuesta="texto-respuesta", alerta="")


def nuevo(gen: Optional[GeneradorIA] = None, **kw) -> ClasificadorInteracciones:
    kw.setdefault("ruta_correcciones", Path(tempfile.mkdtemp()) / "c.jsonl")
    return ClasificadorInteracciones(generador=gen, forzar_fallback=True, **kw)


# --------------------------------------------------------------------------- #
# Pruebas de entrada
# --------------------------------------------------------------------------- #
class TestEntrada(unittest.TestCase):
    def test_validaciones(self):
        c = nuevo()
        casos_invalidos = (
            DiscordSourceV1("otro", "1", "g", "c", "a", T0, "hola"),
            DiscordSourceV1(SCHEMA_ENTRADA, "", "g", "c", "a", T0, "hola"),
            DiscordSourceV1(SCHEMA_ENTRADA, "1", "g", "c", 5, T0, "hola"),  # autor int
            DiscordSourceV1(SCHEMA_ENTRADA, "1", "g", "c", "a", "no-es-fecha", "hola"),
            DiscordSourceV1(SCHEMA_ENTRADA, "1", "g", "c", "a", T0, None),  # type: ignore
        )
        for malo in casos_invalidos:
            with self.assertRaises(ContratoInvalidoError):
                c.clasificar(malo)

    def test_fechas_str_con_z_y_datetime_naive_conviven(self):
        a = DiscordSourceV1(SCHEMA_ENTRADA, "1", "g", "c", "a", "2026-01-01T12:00:00.123Z", "hola a todos")
        b = DiscordSourceV1(SCHEMA_ENTRADA, "2", "g", "c", "a", datetime(2026, 1, 1, 12, 1), "ok")
        res = nuevo().clasificar_lote([a, b])
        self.assertEqual(len(res), 2)

    def test_payload_dict_a_dict(self):
        c = nuevo(FakeGen())
        out = c.clasificar_payload({
            "schema_version": SCHEMA_ENTRADA,
            "message_id": 5,
            "guild_id": 1,
            "channel_id": 2,
            "author_id": 3,
            "created_at": "2026-01-01T12:00:00+00:00",
            "content": BLOQUEO,
        })
        self.assertEqual(
            set(out),
            {"schema_version", "message_id", "es_duda", "es_logro", "es_bloqueo", "tema", "respuesta", "alerta"},
        )
        self.assertEqual((out["schema_version"], out["message_id"]), (SCHEMA_SALIDA, "5"))
        with self.assertRaises(ContratoInvalidoError):
            c.clasificar_payload({"schema_version": SCHEMA_ENTRADA})


# --------------------------------------------------------------------------- #
# Pruebas de salida y generación
# --------------------------------------------------------------------------- #
class TestSalida(unittest.TestCase):
    def test_duda_y_logro_llenan_respuesta_y_no_alerta(self):
        for texto, flag in ((DUDA, "es_duda"), (LOGRO, "es_logro")):
            gen = FakeGen()
            c = nuevo(gen, responder_solo_sin_revision=False)
            d = c.clasificar(fuente(texto, i=7))
            self.assertIsInstance(d, DiscordDecisionV1)
            self.assertTrue(getattr(d, flag))
            self.assertEqual((d.respuesta, d.alerta), ("texto-respuesta", ""))
            self.assertEqual(len(gen.llamadas), 1)
            self.assertEqual((d.schema_version, d.message_id), (SCHEMA_SALIDA, "7"))

    def test_bloqueo_llena_alerta_y_no_respuesta(self):
        gen = FakeGen()
        c = nuevo(gen)
        d = c.clasificar(fuente(BLOQUEO))
        self.assertTrue(d.es_bloqueo)
        self.assertEqual((d.respuesta, d.alerta), ("", "texto-alerta"))
        self.assertEqual(len(gen.llamadas), 1)

    def test_nunca_ambos_campos_ni_mas_de_una_bandera(self):
        c = nuevo(FakeGen(), responder_solo_sin_revision=False)
        textos = [BLOQUEO, LOGRO, DUDA, RUIDO, "gg", "NO FUNCIONA, ya probé todo", "ya quedó, compiló sin errores"]
        res = c.clasificar_lote([fuente(t, i=i, autor=f"u{i}") for i, t in enumerate(textos)])
        for d in res:
            self.assertFalse(d.respuesta and d.alerta)
            self.assertLessEqual(sum([d.es_duda, d.es_logro, d.es_bloqueo]), 1)

    def test_ruido_no_invoca_al_generador(self):
        gen = FakeGen()
        d = nuevo(gen).clasificar(fuente(RUIDO))
        self.assertEqual(gen.llamadas, [])
        self.assertEqual((d.es_duda, d.es_logro, d.es_bloqueo, d.respuesta, d.alerta), (False, False, False, "", ""))

    def test_sin_generador_campos_vacios_pero_clasificacion_intacta(self):
        d = nuevo(None).clasificar(fuente(BLOQUEO))
        self.assertEqual((d.es_bloqueo, d.respuesta, d.alerta), (True, "", ""))

    def test_fallo_del_generador_produce_alerta_ia_no_disponible(self):
        gen = FakeGen(accion=lambda f, r: RuntimeError("error de red"))
        d = nuevo(gen).clasificar(fuente(DUDA))
        self.assertTrue(d.es_duda)
        self.assertEqual((d.respuesta, d.alerta), ("", "ia_no_disponible"))

    def test_generador_vacio_o_invalido_deja_respuesta_vacia(self):
        for resp in ("", "   ", None):
            gen = FakeGen(accion=lambda f, r: GeneracionSalida(respuesta=resp))
            d = nuevo(gen, responder_solo_sin_revision=False).clasificar(fuente(DUDA))
            self.assertTrue(d.es_duda)
            self.assertEqual(d.respuesta, "")

    def test_el_generador_recibe_datos_de_entrada_e_internos(self):
        gen = FakeGen()
        crudo = BLOQUEO + " <@123456> https://x.com/secreto"
        c = nuevo(gen)
        c.clasificar(fuente(crudo, i=3, autor="99"))
        self.assertEqual(len(gen.llamadas), 1)
        f_recibida, r_recibido = gen.llamadas[0]

        # Entrada intacta
        self.assertEqual((f_recibida.author_id, f_recibida.content), ("99", crudo))
        # Diagnóstico interno
        self.assertIsInstance(r_recibido, ClasificacionResultado)
        self.assertEqual(r_recibido.message_id, "3")
        self.assertTrue(hasattr(r_recibido, "necesita_revision"))
        self.assertIn("frustracion_acumulada", r_recibido.rasgos)

    def test_generador_trunca_a_max_respuesta(self):
        largo = "x" * (MAX_RESPUESTA + 150)
        gen = FakeGen(accion=lambda f, r: GeneracionSalida(respuesta=f"  {largo}  "))
        d = nuevo(gen, responder_solo_sin_revision=False).clasificar(fuente(DUDA))
        self.assertEqual(len(d.respuesta), MAX_RESPUESTA)
        self.assertEqual(d.respuesta, "x" * MAX_RESPUESTA)

    def test_responder_solo_sin_revision_suprime_respuesta(self):
        gen = FakeGen(accion=lambda f, r: GeneracionSalida(respuesta="solución"))
        # Con responder_solo_sin_revision=True, si el caso requiere revisión, respuesta debe ser ""
        c = nuevo(gen, responder_solo_sin_revision=True)
        # Una duda muy corta o ambigua genera necesita_revision=True
        d, r = c.clasificar_detallado(fuente("¿pip?"))
        if r.necesita_revision and d.es_duda:
            self.assertEqual(d.respuesta, "")


# --------------------------------------------------------------------------- #
# Pruebas de tema y contexto
# --------------------------------------------------------------------------- #
class TestTemaYContexto(unittest.TestCase):
    def test_tema_asignado_por_generador(self):
        gen = FakeGen(accion=lambda f, r: GeneracionSalida(tema="docker", respuesta="ok"))
        c = nuevo(gen, responder_solo_sin_revision=False)
        self.assertEqual(c.clasificar(fuente(DUDA)).tema, "docker")

        # RUIDO no invoca generador y su tema final queda vacío
        self.assertEqual(c.clasificar(fuente(RUIDO)).tema, "")

    def test_contexto_no_cruza_servidores(self):
        c = nuevo()
        c.clasificar(fuente(BLOQUEO, autor="x", guild="g1", minutos=0))
        _, mismo = c.clasificar_detallado(fuente("ok", i=1, autor="x", guild="g1", minutos=1))
        _, otro = c.clasificar_detallado(fuente("ok", i=2, autor="x", guild="g2", minutos=1))
        self.assertTrue(mismo.rasgos["usa_contexto"])
        self.assertFalse(otro.rasgos["usa_contexto"])

    def test_respuesta_a_otro_mensaje(self):
        _, r = nuevo().clasificar_detallado(
            fuente("no"), texto_respondido="¿ya probaste reiniciar el servicio? sigue el mismo error"
        )
        self.assertTrue(r.rasgos["usa_contexto"])
        self.assertNotIn("texto_corto", r.motivos)


# --------------------------------------------------------------------------- #
# Pruebas de lote y concurrencia asíncrona
# --------------------------------------------------------------------------- #
class TestLote(unittest.IsolatedAsyncioTestCase):
    async def test_lote_sync_y_async_consistentes(self):
        gen = FakeGen()
        c = nuevo(gen)
        fuentes = [fuente(BLOQUEO, i=i, autor=f"u{i}") for i in range(5)]

        res_sync = c.clasificar_lote(fuentes)
        res_async = await c.clasificar_lote_async(fuentes)

        self.assertEqual([d.message_id for d in res_sync], [str(i) for i in range(5)])
        self.assertEqual([d.message_id for d in res_sync], [d.message_id for d in res_async])
        self.assertEqual([d.es_bloqueo for d in res_sync], [d.es_bloqueo for d in res_async])
        self.assertEqual([d.alerta for d in res_sync], [d.alerta for d in res_async])


if __name__ == "__main__":
    unittest.main()