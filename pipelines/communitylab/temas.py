"""Agrupación de temas casi iguales.

Gemini entrega el tema en minúsculas, pero de un lote a otro el mismo asunto puede llegar con o sin
tildes («documentacion curso» / «documentación del curso»), con o sin artículos y preposiciones
(«diapositivas sesion» / «diapositivas de sesión») o en singular y plural («ver factura» / «ver
facturas»). `clave_tema` reduce esas variantes a una misma clave; `etiqueta_tema` elige qué variante
mostrar. Temas distintos de verdad («certificación aws» / «certificación oci») conservan claves distintas.
"""
import unicodedata

# Palabras que no cambian el asunto del tema.
VACIAS = {"a", "al", "con", "de", "del", "el", "en", "la", "las", "lo", "los", "para", "por", "sobre", "un",
          "una", "y"}


def _sin_tildes(texto):
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def _singular(palabra):
    # Plurales regulares del español: tras consonante se agrega «es» («sesiones» → «sesion»,
    # «errores» → «error»); tras vocal, solo «s» («facturas» → «factura», «clientes» → «cliente»).
    if len(palabra) > 4 and palabra.endswith("es") and palabra[-3] in "nrldj":
        return palabra[:-2]
    if len(palabra) > 3 and palabra.endswith("s") and not palabra.endswith("ss"):
        return palabra[:-1]
    return palabra


def clave_tema(tema):
    """Clave para agrupar: minúsculas, sin tildes, sin palabras vacías y en singular."""
    palabras = _sin_tildes(" ".join(str(tema or "").lower().split())).split()
    utiles = [_singular(p) for p in palabras if p not in VACIAS]
    return " ".join(utiles or palabras)


def etiqueta_tema(variantes):
    """Variante a mostrar de un grupo {tema: cantidad}: la más usada; a igualdad, la que lleva
    tildes (la mejor escrita) y luego la más completa."""
    def puntaje(item):
        tema, cantidad = item
        tildes = sum(1 for c in tema if unicodedata.normalize("NFD", c) != c)
        return (cantidad, tildes, len(tema), tema)
    return max(variantes.items(), key=puntaje)[0]


def agrupar_temas(conteos, limite=None):
    """[(tema, cantidad)] → [(etiqueta, cantidad total)] agrupando variantes, del más frecuente al menos."""
    grupos = {}
    for tema, cantidad in conteos:
        tema = " ".join(str(tema or "").split())
        if not tema:
            continue
        variantes = grupos.setdefault(clave_tema(tema), {})
        variantes[tema] = variantes.get(tema, 0) + cantidad
    salida = sorted(((etiqueta_tema(v), sum(v.values())) for v in grupos.values()), key=lambda x: (-x[1], x[0]))
    return salida[:limite] if limite else salida
