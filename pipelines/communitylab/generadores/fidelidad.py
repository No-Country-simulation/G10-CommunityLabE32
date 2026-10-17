"""Controles de fidelidad comprobables de un texto generado frente a sus fuentes.

No detectan toda afirmación inventada (eso exige revisión humana): marcan para el curador
afirmaciones verificables que no constan en los mensajes fuente.

- cifra_no_sustentada: números del texto que no aparecen en las fuentes ni en el período.
- detalle_no_sustentado: posts y resúmenes que describen documentación, configuraciones,
  despliegues, diapositivas, funciones o responsabilidades que la fuente no menciona.
- archivo_no_sustentado: nombres de archivo (p. ej. config.yml) ausentes de las fuentes.
- diagnostico_no_sustentado: afirmaciones de causa ("la causa es", "carecía de", "se debe a")
  cuando las fuentes solo plantean una pregunta.
- posible_atribucion_individual: la fuente describe un logro colectivo ("organizamos",
  "terminamos", "nuestro equipo") y el texto no lo presenta como trabajo de un equipo.

Las advertencias contienen el término detectado, nunca fragmentos del lote.
"""
import re
import unicodedata


def normalizar(texto):
    sin_tildes = unicodedata.normalize("NFKD", str(texto or ""))
    sin_tildes = "".join(c for c in sin_tildes if not unicodedata.combining(c))
    return " ".join(sin_tildes.casefold().split())


# Concepto -> raíces; el concepto está sustentado si alguna raíz aparece en las fuentes.
DETALLES = {
    "documentación": ("documentac", "documentad"),
    "guía o tutorial": ("guia", "tutorial", "manual"),
    "configuración": ("configur",),
    "despliegue": ("despleg", "desplieg", "deploy"),
    "instalación": ("instalac", "instalar"),
    "diapositivas o material": ("diapositiva", "slides", "material"),
    "responsabilidades o funciones": ("a cargo de", "a su cargo", "responsable de", "se encargar",
                                      "sus funciones", "sus tareas", "coordin", "lidera", "liderar",
                                      "supervis", "gestionara"),
    # Párrafo de "alcance" que el modelo completa con conocimiento general (observado el 17/10).
    "alcance o contenido descrito": ("abarca", "abarco", "abarcaron", "cubrio", "cubre ", "comprende",
                                     "la posicion incluye", "el rol incluye"),
    "resultados o métricas": ("descargas", "usuarios activos", "clientes", "ventas", "reduccion",
                              "aumento", "mejora del"),
}
ARCHIVO = re.compile(r"\b[\w\-]+\.(?:py|md|ya?ml|json|sh|ts|tsx|js|env|toml|ini|cfg|txt)\b", re.I)
# Sin dígitos pegados a letras, guiones o barras: IDs (demo-02), períodos (2026-W43) o rutas.
NUMERO = re.compile(r"(?<![\w#\-/])\d+(?:[.,]\d+)?(?![\w\-/])")
DIAGNOSTICOS = (
    r"\b(?:se|fue) (?:encontro|detecto|identifico|determino|diagnostico)\b",
    r"\bla causa (?:es|era|fue|principal)\b",
    r"\bcarec(?:ia|e|ian|en) de\b",
    r"\bel (?:problema|error|fallo) (?:es|era|fue|radica|radicaba|estaba)\b",
    r"\bse debe a\b", r"\bse debia a\b", r"\bfaltaba\b",
    r"\bel origen del (?:problema|error|fallo)\b",
)
COLECTIVO_FUENTE = re.compile(
    r"\b(?:organizamos|terminamos|logramos|lanzamos|publicamos|creamos|desarrollamos|ganamos|"
    r"construimos|nuestro equipo|el equipo|en equipo|juntos)\b")
COLECTIVO_TEXTO = re.compile(
    r"\b(?:equipo|equipos|junto|juntos|colectiv\w*|organizador\w*|integrantes|participantes|"
    r"companer\w*|colaborador\w*|mentores)\b")


def _numeros(texto):
    return {re.sub(r"[.,]", "", n) for n in NUMERO.findall(texto)}


def _todos_los_digitos(texto):
    # Para fuentes y contexto: cualquier secuencia de dígitos (incluye 43 de "2026-W43").
    return set(re.findall(r"\d+", texto))


def revisar_fidelidad(copy, interacciones, formato, contexto=()):
    """Lista de advertencias {'tipo', 'detalle'} para revisión humana; vacía si no detecta nada."""
    fuentes = normalizar(" ".join(str(m.get("texto", "")) for m in interacciones))
    # IDs, autores, canales y fechas de las fuentes también son datos sustentados.
    metadatos = [str(m.get(k, "")) for m in interacciones for k in ("id", "autor", "canal", "fecha")]
    permitido = normalizar(" ".join([*map(str, contexto), *metadatos]))
    texto = normalizar(copy)
    # Las listas numeradas ("1.") y los hashtags no son afirmaciones.
    sin_marcas = normalizar(re.sub(r"(?m)^\s*\d+[.)]\s", " ", re.sub(r"#\w+", " ", str(copy))))
    advertencias = []

    cifras = sorted(_numeros(sin_marcas) - _todos_los_digitos(fuentes) - _todos_los_digitos(permitido))
    for cifra in cifras[:5]:
        advertencias.append({"tipo": "cifra_no_sustentada", "detalle": cifra})

    for archivo in sorted({a.lower() for a in ARCHIVO.findall(copy)}):
        if archivo not in fuentes:
            advertencias.append({"tipo": "archivo_no_sustentado", "detalle": archivo})

    if formato in ("post_linkedin_x", "community_highlights"):
        for concepto, raices in DETALLES.items():
            if any(r in texto for r in raices) and not any(r in fuentes for r in raices):
                advertencias.append({"tipo": "detalle_no_sustentado", "detalle": concepto})
        # Palabras como "equipos" o "participantes" copiadas de la fuente son datos, no encuadre colectivo.
        encuadre = {m.group(0) for m in COLECTIVO_TEXTO.finditer(texto)} - set(re.findall(r"\w+", fuentes))
        if COLECTIVO_FUENTE.search(fuentes) and not encuadre:
            advertencias.append({"tipo": "posible_atribucion_individual",
                                 "detalle": "la fuente describe un logro colectivo"})

    for patron in DIAGNOSTICOS:
        hallado = re.search(patron, texto)
        if hallado and not re.search(patron, fuentes):
            advertencias.append({"tipo": "diagnostico_no_sustentado", "detalle": hallado.group(0)})
    return advertencias
