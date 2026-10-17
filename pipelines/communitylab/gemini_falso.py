"""Doble de transporte HTTP de Gemini para pruebas deterministas, sin red ni claves.

Solo se usa en pruebas: se inyecta en ClienteGemini/crear_componentes_gemini como
`transporte`. No abre sockets (compatible con los validadores que bloquean la red).
"""
import json

import httpx

from .gemini import ConfiguracionGemini

CLAVE_FICTICIA = "clave-ficticia-de-prueba"


def configuracion(**cambios):
    datos = {"clave": CLAVE_FICTICIA, "modelos": ("gemini-rapido", "gemini-escalado"),
             "timeout_peticion": 10, "presupuesto_segundos": 60}
    datos.update(cambios)
    return ConfiguracionGemini(**datos)


def cuerpo_ok(objeto, finish="STOP", tokens=10, texto=None):
    return {"candidates": [{"content": {"role": "model", "parts": [
                {"text": texto if texto is not None else json.dumps(objeto, ensure_ascii=False)}]},
             "finishReason": finish}],
            "usageMetadata": {"candidatesTokenCount": tokens, "totalTokenCount": tokens + 5}}


def ok(objeto, **kw):
    return 200, cuerpo_ok(objeto, **kw), {}


def error(estado, mensaje="detalle del proveedor", detalles=None, cabeceras=None):
    cuerpo = {"error": {"code": estado, "message": mensaje, "details": detalles or []}}
    return estado, cuerpo, cabeceras or {}


class Reloj:
    def __init__(self):
        self.ahora = 0.0
        self.esperas = []

    def __call__(self):
        return self.ahora

    def dormir(self, segundos):
        self.esperas.append(segundos)
        self.ahora += segundos


class GeminiFalso:
    """Responde en orden con `guion`, o con `responder(peticion)` si se indica."""

    def __init__(self, guion=None, responder=None, reloj=None, latencia=0.0):
        self.guion = list(guion or [])
        self.responder = responder
        self.reloj, self.latencia = reloj, latencia
        self.peticiones = []
        self.transporte = httpx.MockTransport(self)

    def __call__(self, request):
        cuerpo = json.loads(request.content)
        modelo = request.url.path.rsplit("/", 1)[-1].split(":")[0]
        self.peticiones.append({"modelo": modelo, "cuerpo": cuerpo, "cabeceras": dict(request.headers),
                                "timeout": request.extensions.get("timeout", {})})
        if self.reloj is not None:
            self.reloj.ahora += self.latencia
        paso = self.responder(self.peticiones[-1]) if self.responder else self.guion.pop(0)
        if isinstance(paso, Exception):
            raise paso
        estado, datos, cabeceras = paso
        return httpx.Response(estado, json=datos, headers=cabeceras)

    @property
    def modelos(self):
        return [p["modelo"] for p in self.peticiones]


def tarea_de(peticion):
    """Distingue la etapa por el esquema solicitado (analizar, puntuar o generador)."""
    esquema = peticion["cuerpo"]["generationConfig"]["responseJsonSchema"]
    if "copy" in esquema["properties"]:
        return "generar"
    item = esquema["properties"]["resultados"]["items"]["properties"]
    return "analizar" if "es_logro" in item else "puntuar"


def responder_con_senales(senales, copy="Borrador generado para revisión editorial."):
    """Respuestas válidas para el grafo completo a partir de señales por ID."""
    def responder(peticion):
        tarea = tarea_de(peticion)
        if tarea == "generar":
            return ok({"copy": copy})
        ids = [m["id"] for m in json.loads(peticion["cuerpo"]["contents"][0]["parts"][0]["text"])]
        if tarea == "analizar":
            return ok({"resultados": [{"id": i, **{k: senales[i][k] for k in
                       ("es_logro", "es_duda", "es_bloqueo", "tema")},
                       "sentimiento": senales[i].get("sentimiento", "neutral")} for i in ids]})
        return ok({"resultados": [{"id": i, "relevancia": senales[i]["relevancia"]} for i in ids]})
    return responder
