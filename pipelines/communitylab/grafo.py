"""Orquestación local de Paulo. Los componentes de IA se inyectan explícitamente."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
import json
import math
from typing import Callable, TypedDict

from langgraph.graph import END, START, StateGraph
from langsmith import tracing_context
from .router_base import Configuracion, enrutar_lote


VERSION = "grafo-local-v1-provisional"
FORMATOS = {
    "generador_post_linkedin_x": "post_linkedin_x",
    "generador_faq_tip": "faq_tip_tecnico",
    "generador_highlights": "community_highlights",
}


class ContratoInvalido(ValueError):
    """Un límite entre componentes no cumple el contrato local."""


class Estado(TypedDict, total=False):
    entrada: dict
    lote: dict
    fuentes: dict
    analisis: dict
    puntuaciones: dict
    enrutamiento: dict
    pendientes: list
    actual: dict
    borradores: list
    alertas: list
    errores: list
    traza: list
    salida: dict


@dataclass(frozen=True)
class Componentes:
    # Cada función recibe una copia: no puede cambiar el estado del grafo.
    analizar: Callable[[dict], dict]
    puntuar: Callable[[dict], dict]
    generar_post: Callable[[dict], dict]
    generar_faq: Callable[[dict], dict]
    generar_highlights: Callable[[dict], dict]
    simulado: bool  # Obligatorio: no presentar un doble de prueba como IA real.

    def __post_init__(self):
        if type(self.simulado) is not bool:
            raise ContratoInvalido("simulado debe ser booleano")
        for nombre in ("analizar", "puntuar", "generar_post", "generar_faq", "generar_highlights"):
            if not callable(getattr(self, nombre)):
                raise ContratoInvalido(f"{nombre} debe ser una función")


def texto(valor, nombre):
    if not isinstance(valor, str) or not valor.strip():
        raise ContratoInvalido(f"{nombre}: texto no vacío requerido")
    return valor.strip()


def preparar_entrada(interacciones, *, origen_comunidad, periodo_referencia, cierre_periodo):
    """Adaptador de salida de José: list[Interaccion] o list[dict] normalizados.

    No parsea archivos ni deduplica: esas responsabilidades siguen en ingesta.
    La validación se realiza en el nodo de ingesta del grafo.
    """
    if not isinstance(interacciones, list):
        raise ContratoInvalido("La salida de ingesta debe ser una lista")
    return {
        "origen_comunidad": origen_comunidad,
        "periodo_referencia": periodo_referencia,
        "cierre_periodo": cierre_periodo,
        "interacciones": [deepcopy(m.model_dump() if hasattr(m, "model_dump") else m)
                          for m in interacciones],
    }


def validar_lote(entrada):
    if not isinstance(entrada, dict):
        raise ContratoInvalido("entrada debe ser un objeto")
    origen = texto(entrada.get("origen_comunidad"), "origen_comunidad")
    periodo = texto(entrada.get("periodo_referencia"), "periodo_referencia")
    cierre = entrada.get("cierre_periodo")
    if type(cierre) is not bool:
        raise ContratoInvalido("cierre_periodo debe ser booleano explícito")
    items = entrada.get("interacciones")
    if not isinstance(items, list):
        raise ContratoInvalido("interacciones debe ser una lista")
    mensajes, ids = [], set()
    for item in items:
        if not isinstance(item, dict):
            raise ContratoInvalido("interacción debe ser un objeto")
        m = {k: texto(item.get(k), k) for k in ("id", "autor", "canal", "fecha", "texto")}
        if m["id"] in ids:
            raise ContratoInvalido("IDs duplicados: deben resolverse en ingesta")
        ids.add(m["id"])
        # 'tipo' es una pista para Santiago, no sustituye las señales del router.
        if "tipo" in item:
            m["tipo"] = texto(item["tipo"], "tipo")
        mensajes.append(m)
    return {"origen_comunidad": origen, "periodo_referencia": periodo,
            "cierre_periodo": cierre, "interacciones": sorted(mensajes, key=lambda m: m["id"])}


def validar_ids(mapa, ids):
    if not isinstance(mapa, dict) or set(mapa) != set(ids):
        raise ContratoInvalido("Se requiere exactamente un resultado por ID de entrada")


def validar_analisis(mapa, ids):
    validar_ids(mapa, ids)
    for a in mapa.values():
        if not isinstance(a, dict) or set(a) != {"es_logro", "es_duda", "es_bloqueo", "tema"}:
            raise ContratoInvalido("Campos de análisis inválidos")
        if any(type(a[k]) is not bool for k in ("es_logro", "es_duda", "es_bloqueo")):
            raise ContratoInvalido("Las señales deben ser booleanos reales")
        if not isinstance(a["tema"], str) or (a["es_duda"] and not a["tema"].strip()):
            raise ContratoInvalido("Una duda requiere tema no vacío")


def validar_puntuaciones(mapa, ids):
    validar_ids(mapa, ids)
    for score in mapa.values():
        if type(score) not in (float, int) or not math.isfinite(score) or not 0 <= score <= 1:
            raise ContratoInvalido("La relevancia debe estar entre 0 y 1 y ser finita")


def identificador(prefijo, lote, decision):
    clave = json.dumps({"origen": lote["origen_comunidad"], "periodo": lote["periodo_referencia"],
                        "ruta": decision["ruta"], "fuentes": decision["fuentes"]}, sort_keys=True)
    return prefijo + sha256(clave.encode()).hexdigest()[:20]


def construir_grafo(componentes: Componentes, configuracion: Configuracion | None = None):
    """Compila un StateGraph real, sin persistencia ni servicios externos propios.

    Error en un nodo: corta el flujo y consolida estado error sin borradores
    parciales. No registra mensajes de excepciones externas (pueden contener
    credenciales o texto privado). No reintenta Gemini: corresponde a Santiago.
    """
    if not isinstance(componentes, Componentes):
        raise ContratoInvalido("Se requieren componentes explícitos")
    cfg = Configuracion() if configuracion is None else configuracion
    if not isinstance(cfg, Configuracion):
        raise ContratoInvalido("configuracion debe ser Configuracion")

    def protegido(nombre, funcion):
        def nodo(estado):
            try:
                cambios = funcion(estado)
            except Exception as exc:
                cambios = {"errores": [{"nodo": nombre, "codigo": "fallo_de_nodo",
                                         "tipo": type(exc).__name__,
                                         "mensaje": "Falló el componente o su contrato; revisar con su responsable."}]}
            return {**cambios, "traza": estado.get("traza", []) + [nombre]}
        return nodo

    def ingesta(estado):
        lote = validar_lote(estado.get("entrada"))
        return {"lote": lote, "fuentes": {m["id"]: m for m in lote["interacciones"]}}

    def analizar(estado):
        resultado = componentes.analizar(deepcopy(estado["lote"]))
        validar_analisis(resultado, estado["fuentes"])
        return {"analisis": deepcopy(resultado)}

    def puntuar(estado):
        resultado = componentes.puntuar(deepcopy({"lote": estado["lote"], "analisis": estado["analisis"]}))
        validar_puntuaciones(resultado, estado["fuentes"])
        return {"puntuaciones": deepcopy(resultado)}

    def enrutar(estado):
        lote = deepcopy(estado["lote"])
        for m in lote["interacciones"]:
            m["analisis"] = {**estado["analisis"][m["id"]], "relevancia": estado["puntuaciones"][m["id"]]}
        resultado = enrutar_lote(lote, cfg)
        return {"enrutamiento": resultado, "pendientes": resultado["decisiones"]}

    def despachar(estado):
        pendientes = estado["pendientes"]
        return {"actual": pendientes[0] if pendientes else {}, "pendientes": pendientes[1:]}

    def generador(destino, funcion):
        def ejecutar(estado):
            d = estado["actual"]
            # Se comparte únicamente el subconjunto seleccionado; nunca el lote completo.
            peticion = {"ruta": d["ruta"], "formato": FORMATOS[destino],
                        "origen_comunidad": estado["lote"]["origen_comunidad"],
                        "periodo_referencia": estado["lote"]["periodo_referencia"],
                        "fuentes": deepcopy(d["fuentes"]),
                        "interacciones": [deepcopy(estado["fuentes"][i]) for i in d["fuentes"]]}
            respuesta = funcion(peticion)
            if not isinstance(respuesta, dict) or set(respuesta) != {"copy", "fuentes"}:
                raise ContratoInvalido("El generador debe devolver copy y fuentes")
            contenido = texto(respuesta["copy"], "copy")
            fuentes = respuesta["fuentes"]
            if (not isinstance(fuentes, list) or any(not isinstance(i, str) for i in fuentes)
                    or len(fuentes) != len(set(fuentes)) or set(fuentes) != set(d["fuentes"])):
                raise ContratoInvalido("El generador cambió u omitió las fuentes seleccionadas")
            activo = {"id_activo": identificador("activo-", estado["lote"], d),
                      "formato": FORMATOS[destino], "copy": contenido,
                      "fuentes": sorted(fuentes), "estado": "borrador",
                      "simulado": componentes.simulado}
            return {"borradores": estado["borradores"] + [activo]}
        return ejecutar

    def alertar(estado):
        d = estado["actual"]
        alerta = {"id_alerta": identificador("alerta-", estado["lote"], d),
                  "nivel": "revision", "mensaje": "Bloqueo detectado; requiere revisión interna.",
                  "fuente": d["fuentes"][0], "visibilidad": "interna"}
        return {"alertas": estado["alertas"] + [alerta]}

    def consolidar(estado):
        fallo = bool(estado["errores"])
        activos = [] if fallo else estado["borradores"]
        alertas = [] if fallo else estado["alertas"]
        referencias = sorted({f for a in activos for f in a["fuentes"]} | {a["fuente"] for a in alertas})
        salida = {
            "version_contrato": VERSION, "estado": "error" if fallo else "completado_local",
            "simulado": componentes.simulado,
            "origen_comunidad": estado.get("lote", {}).get("origen_comunidad"),
            "periodo_referencia": estado.get("lote", {}).get("periodo_referencia"),
            "activos_distribucion_generados": activos, "alertas_internas": alertas,
            "fuentes": [{k: estado["fuentes"][i][k] for k in ("id", "autor", "canal", "fecha")}
                        for i in referencias],
            "enrutamiento": deepcopy(estado.get("enrutamiento", {})),
            "errores": deepcopy(estado["errores"]),
            "almacenamiento": {"proveedor": "pendiente", "estado": "no_persistido"},
            "traza": estado["traza"] + ["consolidacion"],
        }
        return {"salida": salida, "traza": salida["traza"],
                "borradores": activos, "alertas": alertas}

    def inicializar(estado):
        # Permite reutilizar la misma instancia sin arrastrar resultados previos.
        return {"lote": {}, "fuentes": {}, "analisis": {}, "puntuaciones": {},
                "enrutamiento": {}, "pendientes": [], "actual": {},
                "borradores": [], "alertas": [], "errores": [], "traza": []}

    g = StateGraph(Estado)
    g.add_node("inicializar", inicializar)
    for nombre, funcion in (("ingesta", ingesta), ("analizar", analizar), ("puntuar", puntuar),
                            ("router", enrutar), ("despachar", despachar), ("alerta_interna", alertar)):
        g.add_node(nombre, protegido(nombre, funcion))
    for destino, funcion in (("generador_post_linkedin_x", componentes.generar_post),
                              ("generador_faq_tip", componentes.generar_faq),
                              ("generador_highlights", componentes.generar_highlights)):
        g.add_node(destino, protegido(destino, generador(destino, funcion)))
    g.add_node("consolidacion", consolidar)
    g.add_edge(START, "inicializar")
    g.add_edge("inicializar", "ingesta")
    g.add_conditional_edges("ingesta", lambda s: "consolidacion" if s["errores"] or not s["fuentes"] else "analizar",
                            ["consolidacion", "analizar"])
    for origen, destino in (("analizar", "puntuar"), ("puntuar", "router"), ("router", "despachar")):
        g.add_conditional_edges(origen, lambda s, siguiente=destino: "consolidacion" if s["errores"] else siguiente,
                               ["consolidacion", destino])
    g.add_conditional_edges("despachar", lambda s: "consolidacion" if s["errores"] or not s["actual"] else s["actual"]["destino"],
                           ["consolidacion", "alerta_interna", *FORMATOS])
    for nombre in ("alerta_interna", *FORMATOS):
        g.add_conditional_edges(nombre, lambda s: "consolidacion" if s["errores"] else "despachar",
                               ["consolidacion", "despachar"])
    g.add_edge("consolidacion", END)
    return g.compile()


def ejecutar_lote(entrada, componentes, configuracion=None):
    """Entrada pública para el futuro worker. No guarda ni publica el resultado."""
    cantidad = len(entrada.get("interacciones", [])) if isinstance(entrada, dict) and isinstance(entrada.get("interacciones"), list) else 0
    # Cada mensaje puede producir una decisión + el resumen de período.
    limite = 20 + 4 * cantidad
    with tracing_context(enabled=False):
        return construir_grafo(componentes, configuracion).invoke(
            {"entrada": deepcopy(entrada)}, config={"recursion_limit": limite})["salida"]
