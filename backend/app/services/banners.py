"""Banner 1200x630 (LinkedIn/X) de un activo APROBADO, renderizado como SVG determinista.

Porta la plantilla de Fabián (generar_tarjeta.py, Tarea 1 del 15-10-26): mismo fondo, rejilla,
marca, etiqueta y acento por formato. Diferencias deliberadas:
- SVG en el servidor en lugar de captura con Edge en Windows: no depende de un navegador.
- Sin emojis (dependen de fuentes del sistema y harían el resultado no determinista).
- Solo usa texto del copy aprobado (titular, extracto, pregunta, viñetas y hashtags). No
  añade nombres, cifras ni hechos que no estén en el copy. Las etiquetas fijas ("Logro de la
  comunidad", "FAQ técnico"...) son las de la plantilla.

No es generación con IA: proveedor = "plantilla-svg-v1". Un proveedor de imágenes con IA queda
como decisión pendiente (ver docs/flujo-hibrido-banners.md).
"""
from hashlib import sha256
import re
from xml.sax.saxutils import escape

PROVEEDOR = "plantilla-svg-v1"
PLANTILLA = "fabian-tarjeta-1200x630"
ACENTOS = {"logro": "#ff5a1f", "faq": "#4d8dff", "highlights": "#8b6cff"}
TIPO_POR_FORMATO = {"linkedin": "logro", "faq": "faq", "newsletter": "highlights"}
ETIQUETAS = {"logro": "LOGRO DE LA COMUNIDAD", "faq": "FAQ TÉCNICO", "highlights": "COMMUNITY HIGHLIGHTS"}
EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿️‍⬀-⯿]+")
CONTROL = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f]")
MARCAS = re.compile(r"\*\*|__|`|^#+\s|^[-*•]\s+|^\d+[.)]\s+")


class BannerNoGenerable(ValueError):
    """El copy no tiene texto suficiente para una tarjeta."""


def huella_texto(copy: str) -> str:
    return sha256(copy.encode("utf-8")).hexdigest()


def _limpiar(linea):
    linea = CONTROL.sub("", EMOJI.sub("", linea))
    return " ".join(MARCAS.sub("", linea.strip()).split())


ESTRECHAS = set("iljtfr.,:;'!|()[] ")


def _ancho_px(texto, tam, negrita=False):
    """Ancho aproximado en píxeles (sin métricas de fuente: el SVG debe ser determinista)."""
    unidades = sum(0.30 if c in ESTRECHAS else 0.70 if (c.isupper() or c.isdigit() or c in "mwMW@#%&—")
                   else 0.55 for c in texto)
    return unidades * tam * (1.08 if negrita else 1.0)


def _envolver(texto, maximo_px, tam, lineas_max, negrita=False):
    """Corte por palabras según el ancho estimado; añade «…» si se trunca."""
    cabe = lambda s: _ancho_px(s, tam, negrita) <= maximo_px
    lineas, actual = [], ""
    for palabra in texto.split():
        candidata = f"{actual} {palabra}".strip()
        if cabe(candidata):
            actual = candidata
            continue
        if actual:
            lineas.append(actual)
        while not cabe(palabra):  # palabra sin espacios más ancha que la línea
            corte = max(i for i in range(1, len(palabra) + 1) if cabe(palabra[:i]))
            lineas.append(palabra[:corte])
            palabra = palabra[corte:]
        actual = palabra
    if actual:
        lineas.append(actual)
    if len(lineas) > lineas_max:
        lineas = lineas[:lineas_max]
        ultima = lineas[-1]
        while ultima and not cabe(ultima.rstrip() + "…"):
            ultima = ultima[:-1]
        lineas[-1] = ultima.rstrip() + "…"
    return lineas


def contenido(formato: str, copy: str) -> dict:
    """Extrae del copy (y solo del copy) los textos de la tarjeta."""
    tipo = TIPO_POR_FORMATO.get(formato, "logro")
    crudas = [l for l in copy.splitlines() if l.strip()]
    tags = " ".join(w for l in crudas[-2:] for w in l.split() if re.fullmatch(r"#\w[\w-]*", w))[:80]
    lineas = [t for t in (_limpiar(l) for l in crudas if not l.strip().startswith("#")) if t]
    if not lineas:
        raise BannerNoGenerable("El texto aprobado no tiene contenido para la tarjeta")
    datos = {"tipo": tipo, "etiqueta": ETIQUETAS[tipo], "hashtags": tags}
    if tipo == "faq":
        pregunta = next((l.removeprefix("Pregunta:").strip() for l in lineas if "?" in l), lineas[0])
        datos.update(titulo="FAQ de la comunidad", destacado="comunidad", texto=pregunta,
                     pie="Respuesta completa en la publicación")
    elif tipo == "highlights":
        # Viñetas o encabezados breves que empiezan con emoji (formato de los highlights generados).
        viñetas = [_limpiar(l) for l in crudas if re.match(r"^\s*([-*•]|\d+[.)])\s+", l)
                   or (EMOJI.match(l.strip()) and len(l) <= 90)]
        datos.update(titulo="Lo mejor de la semana", destacado="semana", texto=lineas[0],
                     items=[v for v in viñetas if v][:4], pie="CommunityLab")
    else:
        datos.update(titulo=lineas[0].rstrip("."), destacado=None,
                     texto=lineas[1] if len(lineas) > 1 else "", pie="¡Felicitaciones!")
    return datos


def _texto(x, y, lineas, tam, alto, color, peso=400, destacado=None, acento=None):
    partes = []
    for i, linea in enumerate(lineas):
        contenido_linea = escape(linea)
        if destacado and acento and destacado in linea:
            antes, _, despues = linea.partition(destacado)
            contenido_linea = (f'{escape(antes)}<tspan fill="{acento}">{escape(destacado)}</tspan>'
                               f'{escape(despues)}')
        partes.append(f'<text x="{x}" y="{y + i * alto}" font-size="{tam}" font-weight="{peso}" '
                      f'fill="{color}">{contenido_linea}</text>')
    return "".join(partes)


def renderizar(formato: str, copy: str) -> str:
    d = contenido(formato, copy)
    acento = ACENTOS[d["tipo"]]
    titulo = _envolver(d["titulo"], 1072, 54, 3 if d["tipo"] == "logro" else 2, negrita=True)
    y = 250 if d["tipo"] != "logro" else 230 - 30 * (len(titulo) - 2)
    cuerpo = _texto(64, y, titulo, 54, 60, "#f3f5f8", 800, d.get("destacado"), acento)
    y += 60 * len(titulo) + 20
    if d["tipo"] == "faq":
        cuerpo += _texto(64, y, _envolver(d["texto"], 1072, 34, 3, negrita=True), 34, 43, "#f3f5f8", 700)
    else:
        sub = _envolver(d["texto"], 1072, 26, 2 if d.get("items") else 3)
        cuerpo += _texto(64, y, sub, 26, 35, "#c3cde0")
        y += 35 * len(sub) + 26
        items = d.get("items") or []
        if items:
            ancho = (1072 - 18 * (len(items) - 1)) // len(items)
            for i, item in enumerate(items):
                x = 64 + i * (ancho + 18)
                cuerpo += (f'<rect x="{x}" y="{y}" width="{ancho}" height="96" rx="18" fill="#ffffff" '
                           f'fill-opacity=".07" stroke="#ffffff" stroke-opacity=".13"/>')
                cuerpo += _texto(x + 20, y + 40, _envolver(item, ancho - 40, 20, 2, negrita=True), 20, 26, "#f3f5f8", 600)
    etiqueta = escape(d["etiqueta"])
    ancho_etiqueta = 36 + int(len(d["etiqueta"]) * 11.2)
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630" '
        'font-family="Segoe UI, Inter, system-ui, sans-serif" role="img" '
        f'aria-label="{escape(d["titulo"], {chr(34): "&quot;"})}">'
        '<defs>'
        f'<radialGradient id="g1" cx="105%" cy="-10%" r="75%"><stop offset="0" stop-color="{acento}" '
        f'stop-opacity=".38"/><stop offset=".62" stop-color="{acento}" stop-opacity="0"/></radialGradient>'
        '<radialGradient id="g2" cx="-10%" cy="115%" r="63%"><stop offset="0" stop-color="#d43008" '
        'stop-opacity=".30"/><stop offset=".62" stop-color="#d43008" stop-opacity="0"/></radialGradient>'
        '<linearGradient id="g0" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#0f1a2e"/>'
        '<stop offset="1" stop-color="#132240"/></linearGradient>'
        '<pattern id="rej" width="48" height="48" patternUnits="userSpaceOnUse">'
        '<path d="M48 0H0V48" fill="none" stroke="#fff" stroke-opacity=".07"/></pattern>'
        '</defs>'
        '<rect width="1200" height="630" fill="url(#g0)"/><rect width="1200" height="630" fill="url(#g1)"/>'
        '<rect width="1200" height="630" fill="url(#g2)"/><rect width="1200" height="630" fill="url(#rej)"/>'
        '<g transform="translate(64 44)"><rect width="46" height="46" rx="10" fill="#d43008"/>'
        '<g transform="translate(10 10) scale(1.08)" stroke="#fff" stroke-width="2" fill="none" '
        'stroke-linecap="round" stroke-linejoin="round"><ellipse cx="12" cy="5" rx="9" ry="3"/>'
        '<path d="M3 5V19A9 3 0 0 0 21 19V5"/><path d="M3 12A9 3 0 0 0 21 12"/></g></g>'
        '<text x="124" y="70" font-size="24" font-weight="700" fill="#f3f5f8">CommunityLab</text>'
        '<text x="124" y="92" font-size="14" font-weight="600" fill="#c3cde0" letter-spacing="1.1">'
        'G10 · EQUIPO 32</text>'
        f'<rect x="{1136 - ancho_etiqueta}" y="50" width="{ancho_etiqueta}" height="38" rx="19" fill="{acento}"/>'
        f'<text x="{1136 - ancho_etiqueta / 2}" y="75" text-anchor="middle" font-size="17" font-weight="700" '
        f'fill="#0f1a2e" letter-spacing="1">{etiqueta}</text>'
        f'{cuerpo}'
        f'<text x="64" y="586" font-size="19" fill="#c3cde0">{escape(d["pie"])}</text>'
        f'<text x="1136" y="586" text-anchor="end" font-size="19" font-weight="600" fill="{acento}">'
        f'{escape(d["hashtags"])}</text>'
        '</svg>')
