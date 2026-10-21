"""Banner 1200x630 (LinkedIn/X) de un activo APROBADO, renderizado como SVG determinista.

Geometría y reglas de texto de la plantilla de Fabián (generar_tarjeta.py, 15-10-26); estética con la
identidad vigente del panel (21-10-26): fondo negro, acento por formato con la paleta de CommunityLab
(rosado #ff90e8 logros, azul #90a8ed FAQ, amarillo #f1f333 highlights, verde #b9e9c5 de detalle), el
símbolo de tres figuras (frontend/public/brand/communitylab-logo-current.svg) y ABC Favorit con fuentes
de respaldo. Diferencias deliberadas:
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
PLANTILLA = "communitylab-2026-10-1200x630"
ACENTOS = {"logro": "#ff90e8", "faq": "#90a8ed", "highlights": "#f1f333"}
VERDE, NEGRO, BLANCO, GRIS, GRIS_CLARO, PANEL = "#b9e9c5", "#0b0b0b", "#ffffff", "#a3a3a3", "#d4d4d4", "#1a1a1a"
FUENTES = "ABC Favorit, Inter, Segoe UI, system-ui, sans-serif"
# Símbolo de CommunityLab (tres figuras), mismo trazado que frontend/public/brand/communitylab-logo-current.svg.
SIMBOLO = (
    '<defs><linearGradient id="cl-v" x1="585" y1="450" x2="628" y2="506" gradientUnits="userSpaceOnUse">'
    '<stop offset="0" stop-color="#467756"/><stop offset=".45" stop-color="#639d73"/><stop offset="1" stop-color="#7eb78d"/>'
    '</linearGradient><linearGradient id="cl-r" x1="358" y1="457" x2="395" y2="515" gradientUnits="userSpaceOnUse">'
    '<stop offset="0" stop-color="#a74e91"/><stop offset=".45" stop-color="#c165ae"/><stop offset="1" stop-color="#d478c1"/>'
    '</linearGradient><linearGradient id="cl-a" x1="459" y1="300" x2="459" y2="375" gradientUnits="userSpaceOnUse">'
    '<stop offset="0" stop-color="#898b1e"/><stop offset=".45" stop-color="#a7aa25"/><stop offset="1" stop-color="#c0c32b"/>'
    '</linearGradient></defs>'
    '<circle cx="512" cy="208" r="36.5" fill="#f1f333"/><polygon points="428,280 491,321 491,383 428,342" fill="url(#cl-a)"/>'
    '<polygon points="428,280 491,246 598,311 598,378 535,415 535,348 491,321" fill="#f1f333"/>'
    '<circle cx="368.5" cy="319" r="36.5" fill="#ff90e8"/><polygon points="317,484 400,435 400,530" fill="url(#cl-r)"/>'
    '<polygon points="317,402 428,342 491,383 400,435 317,484" fill="#ff90e8"/>'
    '<polygon points="400,435 460,470 460,586 400,551" fill="#ff90e8"/>'
    '<circle cx="655.5" cy="319" r="36.5" fill="#b9e9c5"/><polygon points="568,472 628,438.8 628,506" fill="url(#cl-v)"/>'
    '<polygon points="535,415 638,355 707,395 638,433.2 568,472" fill="#b9e9c5"/>'
    '<polygon points="638,433.2 707,395 707,490 638,530" fill="#7eb78d"/>'
    '<polygon points="520,542 568,515 568,472 628,506 628,558 520,620" fill="#b9e9c5"/>'
    '<polygon points="460,508 520,542 520,620 460,586" fill="#6fa57e"/>')
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
    # El contenido termina antes de la franja inferior (y=566).
    y = 220 if d["tipo"] != "logro" else 230 - 30 * (len(titulo) - 2)
    cuerpo = _texto(64, y, titulo, 54, 60, BLANCO, 800, d.get("destacado"), acento)
    y += 60 * len(titulo) + 20
    if d["tipo"] == "faq":
        cuerpo += _texto(64, y, _envolver(d["texto"], 1072, 34, 3, negrita=True), 34, 43, GRIS_CLARO, 700)
    else:
        sub = _envolver(d["texto"], 1072, 26, 2 if d.get("items") else 3)
        cuerpo += _texto(64, y, sub, 26, 35, GRIS_CLARO)
        y += 35 * len(sub) + 26
        items = d.get("items") or []
        if items:
            ancho = (1072 - 18 * (len(items) - 1)) // len(items)
            for i, item in enumerate(items):
                x = 64 + i * (ancho + 18)
                cuerpo += (f'<rect x="{x}" y="{y}" width="{ancho}" height="96" rx="16" fill="{PANEL}" '
                           f'stroke="{acento}" stroke-opacity=".7" stroke-width="2"/>')
                cuerpo += _texto(x + 20, y + 40, _envolver(item, ancho - 40, 20, 2, negrita=True), 20, 26, BLANCO, 600)
    etiqueta = escape(d["etiqueta"])
    ancho_etiqueta = 36 + int(len(d["etiqueta"]) * 11.2)
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630" '
        f'font-family="{FUENTES}" role="img" '
        f'aria-label="{escape(d["titulo"], {chr(34): "&quot;"})}">'
        '<defs><pattern id="puntos" width="32" height="32" patternUnits="userSpaceOnUse">'
        '<circle cx="2" cy="2" r="1.6" fill="#fff" fill-opacity=".07"/></pattern></defs>'
        f'<rect width="1200" height="630" fill="{NEGRO}"/><rect width="1200" height="566" fill="url(#puntos)"/>'
        # Formas de la marca: acento grande arriba a la derecha y un detalle verde fuera del área de texto (x>1136).
        f'<circle cx="1150" cy="-30" r="210" fill="{acento}" fill-opacity=".16"/>'
        f'<circle cx="1170" cy="132" r="18" fill="{VERDE}" fill-opacity=".9"/>'
        f'<svg x="58" y="36" width="54" height="62" viewBox="305 160 414 472">{SIMBOLO}</svg>'
        f'<text x="124" y="70" font-size="24" font-weight="700" fill="{BLANCO}">CommunityLab</text>'
        f'<text x="124" y="92" font-size="14" font-weight="600" fill="{GRIS}" letter-spacing="1.1">'
        'G10 · EQUIPO 32</text>'
        f'<rect x="{1136 - ancho_etiqueta}" y="50" width="{ancho_etiqueta}" height="38" rx="19" fill="{acento}" '
        f'stroke="{NEGRO}" stroke-width="2"/>'
        f'<text x="{1136 - ancho_etiqueta / 2}" y="75" text-anchor="middle" font-size="17" font-weight="700" '
        f'fill="{NEGRO}" letter-spacing="1">{etiqueta}</text>'
        f'{cuerpo}'
        f'<rect y="566" width="1200" height="64" fill="{acento}"/>'
        f'<text x="64" y="606" font-size="19" font-weight="700" fill="{NEGRO}">{escape(d["pie"])}</text>'
        f'<text x="1136" y="606" text-anchor="end" font-size="19" font-weight="700" fill="{NEGRO}">'
        f'{escape(d["hashtags"])}</text>'
        '</svg>')
