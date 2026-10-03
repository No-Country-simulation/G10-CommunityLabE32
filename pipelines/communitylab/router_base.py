"""Router local determinista. Solo decide destinos; no genera ni publica contenido."""

from dataclasses import dataclass
import math
import unicodedata


class EntradaInvalida(ValueError):
    """El lote o su análisis no cumplen el contrato provisional."""


def _texto(valor, campo):
    if not isinstance(valor, str) or not valor.strip():
        raise EntradaInvalida(f"{campo}: se requiere texto no vacío")
    return valor.strip()


def _booleano(valor, campo):
    if type(valor) is not bool:
        raise EntradaInvalida(f"{campo}: se requiere true o false, no texto ni número")
    return valor


def _puntaje(valor, campo):
    if type(valor) not in (int, float) or not 0 <= valor <= 1 or not math.isfinite(valor):
        raise EntradaInvalida(f"{campo}: se requiere un número finito entre 0 y 1")
    return float(valor)


def _canonico(texto):
    return " ".join(unicodedata.normalize("NFKC", texto).casefold().split())


@dataclass(frozen=True)
class Configuracion:
    relevancia_minima: float = 0.6
    autores_minimos_duda: int = 2

    def __post_init__(self):
        _puntaje(self.relevancia_minima, "relevancia_minima")
        if type(self.autores_minimos_duda) is not int or self.autores_minimos_duda < 2:
            raise EntradaInvalida("autores_minimos_duda: se requiere un entero >= 2")


def _validar(lote):
    if not isinstance(lote, dict):
        raise EntradaInvalida("lote: se requiere un objeto")
    origen = _texto(lote.get("origen_comunidad"), "origen_comunidad")
    periodo = _texto(lote.get("periodo_referencia"), "periodo_referencia")
    cierre = _booleano(lote.get("cierre_periodo"), "cierre_periodo")
    if not isinstance(lote.get("interacciones"), list):
        raise EntradaInvalida("interacciones: se requiere una lista")
    mensajes, ids = [], set()
    for indice, raw in enumerate(lote["interacciones"]):
        prefijo = f"interacciones[{indice}]"
        if not isinstance(raw, dict):
            raise EntradaInvalida(f"{prefijo}: se requiere un objeto")
        # Se conservan los cinco campos de Interaccion del backend como entrada.
        campos = {k: _texto(raw.get(k), f"{prefijo}.{k}")
                  for k in ("id", "autor", "canal", "fecha", "texto")}
        if campos["id"] in ids:
            raise EntradaInvalida(f"{prefijo}.id: ID duplicado; deduplicar en ingesta")
        ids.add(campos["id"])
        analisis = raw.get("analisis")
        if not isinstance(analisis, dict):
            raise EntradaInvalida(f"{prefijo}.analisis: se requiere análisis estructurado")
        esperado = {"es_logro", "es_duda", "es_bloqueo", "tema", "relevancia"}
        if set(analisis) != esperado:
            raise EntradaInvalida(f"{prefijo}.analisis: campos esperados {sorted(esperado)}")
        a = {k: _booleano(analisis[k], f"{prefijo}.analisis.{k}")
             for k in ("es_logro", "es_duda", "es_bloqueo")}
        a["relevancia"] = _puntaje(analisis["relevancia"], f"{prefijo}.analisis.relevancia")
        if not isinstance(analisis["tema"], str):
            raise EntradaInvalida(f"{prefijo}.analisis.tema: se requiere texto")
        a["tema"] = _canonico(analisis["tema"])
        if a["es_duda"] and not a["tema"]:
            raise EntradaInvalida(f"{prefijo}.analisis.tema: obligatorio para agrupar dudas")
        mensajes.append({**campos, "analisis": a})
    return origen, periodo, cierre, sorted(mensajes, key=lambda m: m["id"])


def enrutar_lote(lote, configuracion=None):
    """Devuelve decisiones trazables sin llamadas externas ni mutación de la entrada.

    Precedencia por mensaje: bloqueo > duda recurrente > logro.
    Período es una agregación independiente, habilitada por cierre_periodo.
    """
    cfg = configuracion if configuracion is not None else Configuracion()
    if not isinstance(cfg, Configuracion):
        raise EntradaInvalida("configuracion: se requiere Configuracion")
    origen, periodo, cierre, mensajes = _validar(lote)
    decisiones = []
    asignadas = {m["id"]: [] for m in mensajes}
    motivos = {}

    def agregar(ruta, destino, fuentes, motivo, visibilidad="borrador"):
        fuentes = sorted(fuentes)
        decisiones.append({"ruta": ruta, "destino": destino, "fuentes": fuentes,
                           "motivo": motivo, "visibilidad": visibilidad})
        for fuente in fuentes:
            asignadas[fuente].append(ruta)

    elegibles = []
    for m in mensajes:
        a = m["analisis"]
        if a["es_bloqueo"]:
            agregar("bloqueo", "alerta_interna", [m["id"]],
                    "Bloqueo detectado; excluido de todas las rutas de contenido.", "interna")
        elif a["relevancia"] >= cfg.relevancia_minima:
            elegibles.append(m)
        else:
            motivos[m["id"]] = "Relevancia inferior al umbral configurado."

    grupos = {}
    for m in elegibles:
        if m["analisis"]["es_duda"]:
            grupos.setdefault(m["analisis"]["tema"], []).append(m)
    for tema, grupo in sorted(grupos.items()):
        autores = {_canonico(m["autor"]) for m in grupo}
        if len(autores) >= cfg.autores_minimos_duda:
            agregar("dudas", "generador_faq_tip", [m["id"] for m in grupo],
                    f"Duda recurrente sobre '{tema}' entre {len(autores)} autores distintos.")

    for m in elegibles:
        if not asignadas[m["id"]] and m["analisis"]["es_logro"]:
            agregar("logro", "generador_post_linkedin_x", [m["id"]],
                    "Logro relevante sin bloqueo ni prioridad de duda recurrente.")

    if cierre and elegibles:
        agregar("periodo", "generador_highlights", [m["id"] for m in elegibles],
                "Cierre explícito del período; agrega fuentes relevantes sin bloqueos.")

    omitidos = []
    for m in mensajes:
        if not asignadas[m["id"]]:
            motivo = motivos.get(m["id"])
            if motivo is None:
                motivo = ("Duda sin recurrencia suficiente y sin otra ruta aplicable."
                          if m["analisis"]["es_duda"] else "Sin regla de enrutamiento aplicable.")
            omitidos.append({"fuente": m["id"], "motivo": motivo})

    return {
        "version_contrato": "router-local-v1-provisional",
        "origen_comunidad": origen,
        "periodo_referencia": periodo,
        "configuracion": {"relevancia_minima": cfg.relevancia_minima,
                          "autores_minimos_duda": cfg.autores_minimos_duda},
        "decisiones": decisiones,
        "sin_ruta": omitidos,
        "rutas_por_fuente": asignadas,
    }
