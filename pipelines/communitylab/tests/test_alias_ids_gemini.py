"""Alias cortos por bloque y presupuesto de salida en analizar/puntuar (regresión del trabajo 7e2f5d03).

Experimento real con datos ficticios (19-10-2026, gemini-3.5-flash-lite):
- 19 IDs de Discord en el enum con min/maxItems=19 → 400 INVALID_ARGUMENT; mismos datos con alias → 200.
- 40 alias con min/maxItems=40 → 400; sin longitud fija → 200 pero truncado (MAX_TOKENS con 2048).
Por eso: alias cortos, sin longitud fija del array, bloques dimensionados por el límite de salida y una
sola división si aun así se trunca. Estas pruebas usan Gemini simulado (sin red).
"""
import json
import unittest

from pipelines.communitylab import ejecutar_lote
from pipelines.communitylab import analisis_gemini as ag
from pipelines.communitylab.componentes_gemini import crear_componentes_gemini
from pipelines.communitylab.gemini import (
    ClienteGemini, PresupuestoAgotadoIA, RespuestaInvalidaIA, RespuestaTruncadaIA,
)
from pipelines.communitylab.gemini_falso import (
    CLAVE_FICTICIA, GeminiFalso, configuracion, cuerpo_ok, error, ok, responder_con_senales, tarea_de,
)


def ids_discord(n, base=1559400000000000000):
    # Formato del lector en vivo y del importador histórico: «discord-<message_id>», 27 caracteres.
    return [f"discord-{base + 7_100_000_000_000 * i}" for i in range(n)]


def ids_uuid(n):
    return [f"{i:08x}-0000-4000-8000-{i:012x}" for i in range(n)]


FORMATOS = {"discord": ids_discord, "uuid": ids_uuid, "corto": lambda n: [f"d-{i:02d}" for i in range(n)]}


def lote(ids, prefijo="Mensaje de prueba", canales=None):
    return {"origen_comunidad": "prueba", "periodo_referencia": "2026-W43", "cierre_periodo": False,
            "interacciones": [{"id": i, "autor": f"persona {n}", "canal": (canales or {}).get(i, "general"),
                               "fecha": "2026-10-19T10:00:00Z", "texto": f"{prefijo} {n} sobre Python"}
                              for n, i in enumerate(ids)]}


def senales_distintas(ids):
    """Señales diferentes por mensaje, para detectar cualquier cruce entre IDs."""
    return {i: {"es_logro": n % 3 == 0, "es_duda": n % 3 == 1, "es_bloqueo": False, "tema": f"tema {n}",
                "relevancia": round(0.05 + n / (len(ids) * 2), 4),
                "sentimiento": ag.SENTIMIENTOS[n % len(ag.SENTIMIENTOS)]} for n, i in enumerate(ids)}


def contexto_de(peticion):
    return json.loads(peticion["cuerpo"]["contents"][0]["parts"][0]["text"])


def esquema_de(peticion):
    return peticion["cuerpo"]["generationConfig"]["responseJsonSchema"]


def cliente(falso, **cfg):
    return ClienteGemini(configuracion(**cfg), transporte=falso.transporte, dormir=lambda s: None)


def truncada(texto='{"resultados": ['):
    return 200, cuerpo_ok(None, finish="MAX_TOKENS", texto=texto), {}


def analizar_y_puntuar(datos, c):
    analisis = ag.analizar(datos, c)
    return analisis, ag.puntuar({"lote": datos, "analisis": analisis}, c)


class PruebasAlias(unittest.TestCase):
    def test_tamanos_y_formatos_usan_alias_y_restauran_ids_exactos(self):
        for formato, generar in FORMATOS.items():
            for n in (1, 3, 19, 40):
                with self.subTest(formato=formato, n=n):
                    ids = generar(n)
                    datos = lote(ids)
                    senales = senales_distintas(ids)
                    falso = GeminiFalso(responder=responder_con_senales(senales, interacciones=datos["interacciones"]))
                    analisis, puntos = analizar_y_puntuar(datos, cliente(falso, tamano_bloque=40))
                    for p in falso.peticiones:
                        resultados = esquema_de(p)["properties"]["resultados"]
                        esperados = [f"m{k:02d}" for k in range(1, len(contexto_de(p)) + 1)]
                        self.assertEqual(resultados["items"]["properties"]["id"]["enum"], esperados)
                        self.assertEqual([m["id"] for m in contexto_de(p)], esperados)
                        self.assertNotIn("minItems", resultados)  # sin longitud fija (400 con 40 alias)
                        self.assertNotIn("maxItems", resultados)
                        serializado = json.dumps(p["cuerpo"], ensure_ascii=False)
                        for i in ids:  # el ID original nunca viaja a Gemini
                            self.assertNotIn(i, serializado)
                    self.assertEqual(set(analisis), set(ids))
                    self.assertEqual(set(puntos), set(ids))
                    for i in ids:
                        esperado = {k: senales[i][k] for k in ("es_logro", "es_duda", "es_bloqueo", "tema", "sentimiento")}
                        self.assertEqual(analisis[i], esperado)
                        self.assertEqual(puntos[i], senales[i]["relevancia"])

    def test_esquema_no_depende_del_formato_ni_largo_de_los_ids(self):
        tamanos = {}
        for formato, generar in FORMATOS.items():
            ids = generar(19)
            datos = lote(ids)
            falso = GeminiFalso(responder=responder_con_senales(senales_distintas(ids), interacciones=datos["interacciones"]))
            ag.analizar(datos, cliente(falso))
            tamanos[formato] = len(json.dumps(esquema_de(falso.peticiones[0]), ensure_ascii=False).encode())
        self.assertEqual(len(set(tamanos.values())), 1, tamanos)
        self.assertLess(tamanos["discord"], 1164)  # el esquema rechazado en producción medía 1164 bytes

    def test_resultados_en_otro_orden_se_asocian_por_alias_no_por_posicion(self):
        ids = ids_discord(19)
        datos = lote(ids)
        senales = senales_distintas(ids)
        base = responder_con_senales(senales, interacciones=datos["interacciones"])

        def invertido(p):
            estado, cuerpo, cab = base(p)
            objeto = json.loads(cuerpo["candidates"][0]["content"]["parts"][0]["text"])
            objeto["resultados"].reverse()
            return ok(objeto)
        analisis, puntos = analizar_y_puntuar(datos, cliente(GeminiFalso(responder=invertido)))
        for i in ids:
            self.assertEqual(analisis[i]["tema"], senales[i]["tema"])
            self.assertEqual(puntos[i], senales[i]["relevancia"])

    def test_textos_repetidos_con_ids_distintos_conservan_su_correspondencia(self):
        ids = ids_discord(12)
        canales = {i: f"canal-{n}" for n, i in enumerate(ids)}
        datos = lote(ids, canales=canales)
        for m in datos["interacciones"]:  # el mismo texto para todos: solo el alias los distingue
            m["texto"] = "¿Alguien sabe por qué falla mi contenedor?"
        senales = senales_distintas(ids)
        base = responder_con_senales(senales, interacciones=datos["interacciones"])

        def mezclado(p):
            estado, cuerpo, cab = base(p)
            objeto = json.loads(cuerpo["candidates"][0]["content"]["parts"][0]["text"])
            objeto["resultados"] = objeto["resultados"][1::2] + objeto["resultados"][0::2]
            return ok(objeto)
        analisis, puntos = analizar_y_puntuar(datos, cliente(GeminiFalso(responder=mezclado)))
        for i in ids:
            self.assertEqual((analisis[i]["tema"], puntos[i]), (senales[i]["tema"], senales[i]["relevancia"]))

    def test_alias_desconocidos_duplicados_faltantes_o_mal_formados_se_rechazan(self):
        ids = ids_discord(19)
        datos = lote(ids)
        base = responder_con_senales(senales_distintas(ids), interacciones=datos["interacciones"])
        casos = {
            "desconocido": lambda r: r[0].update(id="m20"),
            "id_original": lambda r: r[0].update(id=ids[0]),
            "mayuscula": lambda r: r[0].update(id="M01"),
            "sin_cero": lambda r: r[0].update(id="m1"),
            "entero": lambda r: r[0].update(id=1),
            "nulo": lambda r: r[0].update(id=None),
            "duplicado": lambda r: r[1].update(id=r[0]["id"]),
            "faltante": lambda r: r.pop(),
            "sobrante": lambda r: r.append(dict(r[0], id="m99")),
            "campo_extra": lambda r: r[0].update(otro=1),
            "tipo_incorrecto": lambda r: r[0].update(es_logro="sí"),
        }
        for nombre, mutar in casos.items():
            with self.subTest(caso=nombre):
                def responder(p, mutar=mutar):
                    estado, cuerpo, cab = base(p)
                    objeto = json.loads(cuerpo["candidates"][0]["content"]["parts"][0]["text"])
                    mutar(objeto["resultados"])
                    return ok(objeto)
                falso = GeminiFalso(responder=responder)
                with self.assertRaises(RespuestaInvalidaIA):
                    ag.analizar(datos, cliente(falso))
                self.assertEqual(falso.modelos, ["gemini-rapido", "gemini-escalado"])  # contrato: escala una vez

    def test_respuestas_no_json_o_sin_resultados_se_rechazan(self):
        datos = lote(ids_discord(3))
        respuestas = {
            "no_json": (200, cuerpo_ok(None, texto="no es json"), {}),
            "sin_resultados": ok({"otra": []}),
            "resultados_no_lista": ok({"resultados": {"m01": {}}}),
        }
        for nombre, respuesta in respuestas.items():
            with self.subTest(caso=nombre):
                with self.assertRaises(RespuestaInvalidaIA):
                    ag.analizar(datos, cliente(GeminiFalso(guion=[respuesta, respuesta])))


class PruebasBloquesYPresupuesto(unittest.TestCase):
    def test_bloque_efectivo_cabe_en_el_limite_de_salida_configurado(self):
        c = cliente(GeminiFalso(guion=[]), tamano_bloque=40)
        self.assertEqual(c.cfg.max_tokens_salida, 2048)  # límite por llamada sin cambios
        for tarea in ("analizar", "puntuar"):
            tam = ag._bloque_efectivo(c, tarea)
            self.assertLessEqual(ag.TOKENS_RESERVA[tarea] + tam * ag.TOKENS_POR_RESULTADO[tarea], 2048)
            self.assertLessEqual(tam, 40)
        self.assertEqual(ag._bloque_efectivo(cliente(GeminiFalso(guion=[]), tamano_bloque=5), "analizar"), 5)
        self.assertEqual(ag._bloque_efectivo(cliente(GeminiFalso(guion=[]), max_tokens_salida=64), "analizar"), 1)

    def test_lote_de_40_usa_varios_bloques_dentro_de_los_limites(self):
        ids = ids_discord(40)
        datos = lote(ids)
        senales = senales_distintas(ids)
        falso = GeminiFalso(responder=responder_con_senales(senales, interacciones=datos["interacciones"]))
        c = cliente(falso, tamano_bloque=40)
        analisis, puntos = analizar_y_puntuar(datos, c)
        bloque_a, bloque_p = ag._bloque_efectivo(c, "analizar"), ag._bloque_efectivo(c, "puntuar")
        tam = [len(contexto_de(p)) for p in falso.peticiones]
        self.assertTrue(all(t <= bloque_a for t in tam[:-2]) and max(tam) <= max(bloque_a, bloque_p))
        self.assertEqual(sum(len(contexto_de(p)) for p in falso.peticiones if tarea_de(p) == "analizar"), 40)
        self.assertEqual(sum(len(contexto_de(p)) for p in falso.peticiones if tarea_de(p) == "puntuar"), 40)
        self.assertLessEqual(c.presupuesto.llamadas, c.cfg.max_llamadas)
        self.assertEqual((set(analisis), set(puntos)), (set(ids), set(ids)))
        for p in falso.peticiones:
            self.assertEqual(p["cuerpo"]["generationConfig"]["maxOutputTokens"], 2048)

    def test_varios_bloques_no_mezclan_sus_mapas(self):
        ids = ids_discord(85)
        datos = lote(ids)
        senales = senales_distintas(ids)
        falso = GeminiFalso(responder=responder_con_senales(senales, interacciones=datos["interacciones"]))
        c = cliente(falso, tamano_bloque=40, max_llamadas=16)
        analisis, puntos = analizar_y_puntuar(datos, c)
        a, p = ag._bloque_efectivo(c, "analizar"), ag._bloque_efectivo(c, "puntuar")
        esperado = [len(b) for b in ag._bloques(ids, a)] + [len(b) for b in ag._bloques(ids, p)]
        self.assertEqual([len(contexto_de(x)) for x in falso.peticiones], esperado)
        self.assertTrue(all(contexto_de(x)[0]["id"] == "m01" for x in falso.peticiones))  # mapas por bloque
        for i in ids:
            self.assertEqual(analisis[i]["tema"], senales[i]["tema"])
            self.assertEqual(puntos[i], senales[i]["relevancia"])

    def test_alias_de_otro_bloque_no_se_acepta(self):
        c0 = cliente(GeminiFalso(guion=[]))
        primero = ag._bloque_efectivo(c0, "analizar")
        ids = ids_discord(primero + 6)  # analizar: un bloque completo y otro de 6
        datos = lote(ids)
        base = responder_con_senales(senales_distintas(ids), interacciones=datos["interacciones"])

        def segundo_bloque_con_alias_del_primero(p):
            estado, cuerpo, cab = base(p)
            objeto = json.loads(cuerpo["candidates"][0]["content"]["parts"][0]["text"])
            if len(objeto["resultados"]) == 6:
                objeto["resultados"][0]["id"] = f"m{primero:02d}"  # existe en el primer bloque, no en este
            return ok(objeto)
        with self.assertRaises(RespuestaInvalidaIA):
            ag.analizar(datos, cliente(GeminiFalso(responder=segundo_bloque_con_alias_del_primero)))

    def test_truncamiento_divide_el_bloque_una_vez_sin_escalar_ni_repetir_bloques(self):
        ids = ids_discord(19)
        datos = lote(ids)
        senales = senales_distintas(ids)
        base = responder_con_senales(senales, interacciones=datos["interacciones"])

        def trunca_si_mas_de_10(p):
            return truncada() if len(contexto_de(p)) > 10 else base(p)
        falso = GeminiFalso(responder=trunca_si_mas_de_10)
        analisis = ag.analizar(datos, cliente(falso))
        self.assertEqual([len(contexto_de(p)) for p in falso.peticiones], [19, 9, 10])
        self.assertEqual(falso.modelos, ["gemini-rapido"] * 3)  # nunca escaló con el mismo límite
        self.assertEqual({i: r["tema"] for i, r in analisis.items()}, {i: senales[i]["tema"] for i in ids})

    def test_truncamiento_de_una_mitad_falla_controlado_sin_resultados_parciales(self):
        datos = lote(ids_discord(19))
        falso = GeminiFalso(responder=lambda p: truncada())
        with self.assertRaises(RespuestaInvalidaIA) as ctx:
            ag.analizar(datos, cliente(falso))
        self.assertNotIsInstance(ctx.exception, RespuestaTruncadaIA)  # se traduce al código conocido
        self.assertEqual(len(falso.peticiones), 2)  # bloque + primera mitad; no sigue intentando
        with self.assertRaises(RespuestaInvalidaIA):
            ag.analizar(lote(ids_discord(1)), cliente(GeminiFalso(responder=lambda p: truncada())))

    def test_json_incompleto_truncado_nunca_se_acepta(self):
        ids = ids_discord(3)
        parcial = json.dumps({"resultados": [{"id": "m01", "es_logro": False, "es_duda": False,
                                              "es_bloqueo": False, "tema": "x", "sentimiento": "neutral"}]})
        for texto in (parcial, parcial[:-3]):
            with self.subTest(texto=texto[-12:]):
                falso = GeminiFalso(responder=lambda p, t=texto: truncada(t))
                with self.assertRaises(RespuestaInvalidaIA):
                    ag.analizar(lote(ids), cliente(falso))

    def test_presupuestos_insuficientes_cortan_con_error_controlado(self):
        ids = ids_discord(40)
        datos = lote(ids)
        senales = senales_distintas(ids)
        base = responder_con_senales(senales, interacciones=datos["interacciones"])
        with self.assertRaises(PresupuestoAgotadoIA):  # 40 mensajes necesitan 2 bloques de análisis
            ag.analizar(datos, cliente(GeminiFalso(responder=base), max_llamadas=1))
        with self.assertRaises(PresupuestoAgotadoIA):
            ag.analizar(datos, cliente(GeminiFalso(responder=lambda p: ok(json.loads(
                base(p)[1]["candidates"][0]["content"]["parts"][0]["text"]), tokens=500)), max_tokens_trabajo=256))

    def test_generadores_mantienen_el_escalamiento_por_truncamiento(self):
        falso = GeminiFalso(guion=[truncada('{"copy": "texto'), ok({"copy": "Texto completo."})])
        c = cliente(falso)
        self.assertEqual(c.generar_json("post_linkedin_x", "s", "u", {"type": "object"}, lambda o: o["copy"]),
                         "Texto completo.")
        self.assertEqual(falso.modelos, ["gemini-rapido", "gemini-escalado"])


class PruebasGrafoCompleto(unittest.TestCase):
    def test_grafo_completo_con_19_ids_de_discord_conserva_ids_y_fuentes(self):
        ids = ids_discord(19)
        datos = lote(ids)
        senales = {i: {**s, "relevancia": 0.9 if s["es_logro"] else 0.1, "es_duda": False}
                   for i, s in senales_distintas(ids).items()}
        senales[ids[2]]["es_bloqueo"] = True
        falso = GeminiFalso(responder=responder_con_senales(senales, interacciones=datos["interacciones"]))
        salida = ejecutar_lote(datos, crear_componentes_gemini(configuracion(tamano_bloque=40), transporte=falso.transporte))
        self.assertEqual(salida["estado"], "completado_local", salida["errores"])
        self.assertEqual(salida["sentimientos"], {i: senales[i]["sentimiento"] for i in ids})
        fuentes = [f for a in salida["activos_distribucion_generados"] for f in a["fuentes"]]
        self.assertTrue(fuentes and set(fuentes) <= set(ids))
        self.assertNotIn(ids[2], fuentes)  # un bloqueo nunca es fuente de contenido público
        self.assertIn(ids[2], [a["fuente"] for a in salida["alertas_internas"]])
        self.assertNotIn("m01", json.dumps({k: v for k, v in salida.items() if k != "traza"}, ensure_ascii=False))

    def test_fallo_tras_completar_un_bloque_no_deja_nada_parcial(self):
        ids = ids_discord(40)  # analizar en 2 bloques: el primero responde bien, el segundo 400
        datos = lote(ids)
        base = responder_con_senales(senales_distintas(ids), interacciones=datos["interacciones"])
        llamadas = []

        def responder(p):
            llamadas.append(p)
            return base(p) if len(llamadas) == 1 else error(400, mensaje="secreto del proveedor")
        salida = ejecutar_lote(datos, crear_componentes_gemini(configuracion(), transporte=GeminiFalso(responder=responder).transporte))
        self.assertEqual(salida["estado"], "error")
        self.assertEqual((salida["activos_distribucion_generados"], salida["alertas_internas"], salida["sentimientos"]), ([], [], {}))
        self.assertEqual(len(llamadas), 2)

    def test_rechazo_400_no_deja_contenidos_parciales_ni_texto_del_proveedor(self):
        ids = ids_discord(19)
        datos = lote(ids)
        secreto = "texto-libre-del-proveedor CLAVE=AIzaFICTICIA mensaje filtrado"
        falso = GeminiFalso(responder=lambda p: error(400, mensaje=secreto, detalles=[{"reason": "OTRA_COSA"}]))
        salida = ejecutar_lote(datos, crear_componentes_gemini(configuracion(), transporte=falso.transporte))
        self.assertEqual(salida["estado"], "error")
        self.assertEqual((salida["activos_distribucion_generados"], salida["alertas_internas"]), ([], []))
        self.assertEqual(len(falso.peticiones), 1)  # un 400 no se reintenta ni escala
        diag = salida["errores"][0]["diagnostico"]
        self.assertEqual((diag["http"], diag["categoria"], diag["razon"]), (400, "peticion_rechazada", "otra"))
        self.assertEqual(diag["peticion"]["items_esperados"], 19)
        serializado = json.dumps(salida, ensure_ascii=False)
        self.assertNotIn(secreto, serializado)
        self.assertNotIn(CLAVE_FICTICIA, serializado)
        for m in datos["interacciones"]:
            self.assertNotIn(m["texto"], json.dumps(salida["errores"], ensure_ascii=False))

    def test_truncamiento_irrecuperable_en_el_grafo_es_respuesta_invalida(self):
        salida = ejecutar_lote(lote(ids_discord(5)), crear_componentes_gemini(
            configuracion(), transporte=GeminiFalso(responder=lambda p: truncada()).transporte))
        self.assertEqual((salida["estado"], salida["errores"][0]["tipo"]), ("error", "RespuestaInvalidaIA"))
        self.assertEqual(salida["activos_distribucion_generados"], [])


if __name__ == "__main__":
    unittest.main()
