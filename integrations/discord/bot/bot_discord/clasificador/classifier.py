
"""Clasificador local de Fabián y API de decisiones compatible con el transporte.

La integración recomendada vive en community_processor.integrated:procesar:
usa una hipótesis local sin contexto persistente y una confirmación async Gemini.
La API síncrona opcional requiere un GeneradorIA para dudas/bloqueos. Los logros
no publican. Los errores se propagan sin mensajes del proveedor. ReviewRequired
pide revisión explícita; no es una decisión discord-decision-v1.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import unicodedata
from collections import defaultdict, deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Deque, Dict, List, Mapping, Optional, Protocol, Sequence, Tuple, Union

import numpy as np
from bot_discord.contracts import ReviewRequired, validate_decision

log = logging.getLogger("clasificador")

RUTA_CONFIG_DEFECTO = Path(__file__).with_name("config_clasificador.json")

LOGRO = "LOGRO"
DUDA_TECNICA = "DUDA_TECNICA"
BLOQUEO_FRUSTRACION = "BLOQUEO_FRUSTRACION"
RUIDO = "RUIDO"
NO_CLASIFICADO = "NO_CLASIFICADO"
CLASES_OBJETIVO = (LOGRO, DUDA_TECNICA, BLOQUEO_FRUSTRACION)


# --------------------------------------------------------------------------- #
# Configuración default y carga desde JSON/YAML
# --------------------------------------------------------------------------- #
def cargar_config(ruta: Optional[Path | str] = None) -> Dict[str, Any]:
    """Carga la configuración desde JSON o YAML."""
    ruta = Path(ruta) if ruta else RUTA_CONFIG_DEFECTO
    texto = ruta.read_text(encoding="utf-8")
    if ruta.suffix.lower() in (".yaml", ".yml"):
        import yaml  # import perezoso: solo si se usa YAML

        return yaml.safe_load(texto)
    return json.loads(texto)


# --------------------------------------------------------------------------- #
# Esquema de datos (contrato)
# --------------------------------------------------------------------------- #
SCHEMA_ENTRADA = "discord-source-v1"
SCHEMA_SALIDA = "discord-decision-v1"

# Excepción de contrato inválido (no cumple discord-source-v1).
class ContratoInvalidoError(ValueError):
    """El mensaje de entrada no cumple discord-source-v1."""

# Normalizar de fecha de entrada
def _parsear_fecha(valor: Union[str, datetime]) -> datetime:
    """ISO 8601 (admite 'Z') o datetime -> datetime con zona UTC. Naive se asume UTC."""
    if isinstance(valor, datetime):
        d = valor
    elif isinstance(valor, str) and valor.strip():
        try:
            d = datetime.fromisoformat(valor.strip().replace("Z", "+00:00"))
        except ValueError as exc:
            raise ContratoInvalidoError(f"created_at no es ISO 8601: {valor!r}") from exc
    else:
        raise ContratoInvalidoError(f"created_at inválido: {valor!r}")
    return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d.astimezone(timezone.utc)##

# Validación del contrato de entrada y construcción desde JSON. Los ids numéricos se convierten a str.
@dataclass(frozen=True)
class DiscordSourceV1:
    """Contrato de entrada: discord-source-v1."""
    schema_version: str
    message_id: str
    guild_id: str
    channel_id: str
    author_id: str
    created_at: Union[str, datetime]
    content: str

    def validar(self) -> "DiscordSourceV1":
        if self.schema_version != SCHEMA_ENTRADA:
            raise ContratoInvalidoError(
                f"schema_version {self.schema_version!r}; se esperaba {SCHEMA_ENTRADA!r}")
        for nombre in ("message_id", "guild_id", "channel_id", "author_id"):
            v = getattr(self, nombre)
            if not isinstance(v, str) or not v:
                raise ContratoInvalidoError(
                    f"{nombre} debe ser un str no vacío (recibido {v!r}); convierte con str() si es un int")
        if not isinstance(self.content, str):
            raise ContratoInvalidoError("content debe ser str")
        _parsear_fecha(self.created_at)
        return self

    def fecha_utc(self) -> datetime:
        return _parsear_fecha(self.created_at)

    @classmethod
    def desde_dict(cls, d: Mapping[str, Any]) -> "DiscordSourceV1":
        """Construye y valida desde un payload JSON. Los ids numéricos se convierten a str."""
        faltan = [k for k in ("schema_version", "message_id", "guild_id", "channel_id",
                              "author_id", "created_at", "content") if k not in d]
        if faltan:
            raise ContratoInvalidoError(f"faltan campos: {faltan}")
        ids = {k: (str(d[k]) if isinstance(d[k], int) and not isinstance(d[k], bool) else d[k])
               for k in ("message_id", "guild_id", "channel_id", "author_id")}
        return cls(schema_version=d["schema_version"], created_at=d["created_at"],
                   content=d["content"], **ids).validar()

# Contrato de salida (solo campos públicos, no incluye similitudes ni motivos internos).
@dataclass(frozen=True)
class DiscordDecisionV1:
    """Contrato de salida: discord-decision-v1."""
    schema_version: str = SCHEMA_SALIDA
    message_id: str = ""
    es_duda: bool = False
    es_logro: bool = False
    es_bloqueo: bool = False
    tema: str = ""
    respuesta: str = ""
    alerta: str = ""

# Diagnóstico interno (no es parte del contrato público).
@dataclass(frozen=True)
class ClasificacionResultado:
    """Diagnóstico interno (no es parte del contrato público)."""
    message_id: str
    clase: str
    confianza: float
    motor: str
    tema: str = ""
    necesita_revision: bool = False
    motivos: Tuple[str, ...] = ()
    similitudes: Dict[str, float] = field(default_factory=dict)
    sentimiento: Dict[str, float] = field(default_factory=dict)
    rasgos: Dict[str, Any] = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Utilidades de texto
# --------------------------------------------------------------------------- #
def _quitar_acentos(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", t) if not unicodedata.combining(c))


def _normalizar(t: str) -> str:
    """Minúsculas, sin acentos, solo [a-z0-9] y espacios."""
    t = _quitar_acentos(t.lower())
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


# --------------------------------------------------------------------------- #
# 1. Sanitizador
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class TextoSanitizado:
    texto: str
    rasgos: Dict[str, Any]

# Sanitizador de texto: elimina código, trazas, URLs, menciones, canales y emotes; normaliza emojis y elongaciones; detecta mayúsculas sostenidas y señales léxicas.
class SanitizadorTexto:
    patron_bloque = re.compile(r"```.*?```", re.S)
    patron_inline = re.compile(r"`[^`\n]+`")
    patron_traza = re.compile(
        r"(Traceback \(most recent call last\)|\b\w+(Error|Exception)\s*:|\bat \S+:\d+|\bline \d+\b)",
        re.I,
    )
    patron_url = re.compile(r"https?://\S+|www\.\S+")
    patron_mencion = re.compile(r"<@[!&]?\d+>")
    patron_canal = re.compile(r"<#\d+>")
    patron_emote = re.compile(r"<a?:(\w+):\d+>")
    patron_elongacion_letra = re.compile(r"([A-Za-zÁÉÍÓÚÜÑáéíóúüñ])\1{2,}")
    patron_elongacion_signo = re.compile(r"([!?¡¿])\1{2,}")

    # Señales sobre texto normalizado (sin acentos)
    patron_idiom_frustracion = re.compile(
        r"\b(me quiero morir|me muero|me estoy volviendo loc[oa]|voy a explotar|"
        r"me va a dar algo|ya no aguanto|me rindo)\b"
    )
    patron_malestar = re.compile(
        r"\b(quiero morir(me)?|matarme|no quiero vivir|quitarme la vida|acabar con todo)\b"
    )
    patron_tecnico = re.compile(
        r"\b(bug|bugs|error|errores|codigo|compil\w*|script|terminal|servidor|programa|"
        r"test|tests|deploy|daemon|python|git|api|consola|ejercicio|proyecto|docker)\b"
    )
    palabras_ingles = {"the", "is", "and", "it", "my", "doesn", "not", "this", "with",
                       "to", "how", "can", "why", "i", "me", "work", "works", "stuck"}

    EMOTES = (
        (r"sad|cry|rip|pain|sob", "triste"),
        (r"pog|hype|happy|love|nice|gg", "feliz"),
        (r"angry|rage|mad", "enojado"),
    )
    EMOJIS = {
        "💀": " me muero ", "😭": " llorando ", "😡": " enojado ", "🤬": " enojado ",
        "😤": " frustrado ", "🤯": " increible ", "🎉": " celebracion ", "🔥": " genial ",
        "✅": " listo ", "😂": " jaja ", "🤣": " jaja ", "🙏": " por favor ",
        "🥲": " triste ", "😅": " nervioso ", "🫠": " agotado ", "😫": " agotado ",
    }

    def __init__(self) -> None:
        self._tabla_emoji = {ord(k): v for k, v in self.EMOJIS.items()}
        self._tabla_emoji[0xFE0F] = None  # variation selector

    def _emote(self, m: re.Match) -> str:
        nombre = m.group(1).lower()
        for patron, token in self.EMOTES:
            if re.search(patron, nombre):
                return f" {token} "
        return " " + nombre.replace("_", " ") + " "

    def limpiar(self, texto: str) -> TextoSanitizado:
        t = texto or ""
        rasgos: Dict[str, Any] = {
            "tiene_traza": bool(self.patron_traza.search(t)),
            "tiene_codigo": bool(self.patron_bloque.search(t) or self.patron_inline.search(t)),
            "exclamaciones": t.count("!"),
            "pregunta": ("?" in t) or ("¿" in t),
        }
        # Bloques de código/errores -> token (se conserva la señal, no el contenido)
        t = self.patron_bloque.sub(
            lambda m: " <ERROR> " if self.patron_traza.search(m.group(0)) else " <CODIGO> ", t
        )
        t = self.patron_inline.sub(" <CODIGO> ", t)
        t = self.patron_url.sub(" <URL> ", t)
        t = self.patron_mencion.sub(" <USUARIO> ", t)
        t = self.patron_canal.sub(" <CANAL> ", t)
        t = self.patron_emote.sub(self._emote, t)
        t = t.translate(self._tabla_emoji)

        # Elongaciones: 3+ letras iguales no existen en español -> 1 letra.
        t = self.patron_elongacion_letra.sub(r"\1", t)
        t = self.patron_elongacion_signo.sub(r"\1\1", t)
        t = re.sub(r"\s+", " ", t).strip()

        # Mayúsculas sostenidas (antes de cualquier paso a minúsculas)
        sin_marcas = re.sub(r"<[^>]+>", " ", t)
        palabras = re.findall(r"\b[^\W\d_]{3,}\b", sin_marcas)
        mayus = [w for w in palabras if w.isupper()]
        rasgos["mayusculas_sostenidas"] = bool(
            palabras
            and ((len(mayus) >= 2 and len(mayus) / len(palabras) >= 0.6)
                 or (len(mayus) == 1 and len(palabras) <= 2))
        )

        # Señales léxicas sobre texto normalizado
        norm = _normalizar(t)
        tecnico = bool(self.patron_tecnico.search(norm)) or rasgos["tiene_codigo"] or rasgos["tiene_traza"]
        rasgos["frustracion_idiomatica"] = bool(self.patron_idiom_frustracion.search(norm)) and tecnico
        rasgos["malestar_no_tecnico"] = bool(self.patron_malestar.search(norm)) and not tecnico

        toks = norm.split()
        en = sum(1 for w in toks if w in self.palabras_ingles)
        rasgos["idioma_probable"] = "en" if en >= 2 and toks and en / len(toks) >= 0.2 else "es"
        return TextoSanitizado(texto=t, rasgos=rasgos)


# --------------------------------------------------------------------------- #
# 2. Motor semántico
# --------------------------------------------------------------------------- #
class VectorizadorCaracteres:
    """TF-IDF de n-gramas de caracteres (char_wb 3-5), L2-normalizado, solo numpy."""

    def __init__(self, n_min: int = 3, n_max: int = 5) -> None:
        self.n_min, self.n_max = n_min, n_max
        self.vocab: Dict[str, int] = {}
        self.idf: np.ndarray = np.zeros(0)
        self.idf_desconocido = 1.0

    def _ngramas(self, texto: str) -> Dict[str, int]:
        cuenta: Dict[str, int] = defaultdict(int)
        for palabra in _normalizar(texto).split():
            p = f" {palabra} "
            for n in range(self.n_min, self.n_max + 1):
                for i in range(len(p) - n + 1):
                    cuenta[p[i:i + n]] += 1
        return cuenta

    def ajustar(self, corpus: Sequence[str]) -> "VectorizadorCaracteres":
        docs = [self._ngramas(t) for t in corpus]
        df: Dict[str, int] = defaultdict(int)
        for d in docs:
            for g in d:
                df[g] += 1
        self.vocab = {g: i for i, g in enumerate(sorted(df))}
        n = len(docs)
        self.idf = np.array([np.log((1 + n) / (1 + df[g])) + 1.0 for g in self.vocab])
        self.idf_desconocido = float(self.idf.max()) if len(self.idf) else 1.0
        return self

    def transformar(self, textos: Sequence[str]) -> np.ndarray:
        X = np.zeros((len(textos), len(self.vocab)), dtype=np.float64)
        for r, t in enumerate(textos):
            norma2 = 0.0
            for g, c in self._ngramas(t).items():
                tf = 1.0 + np.log(c)
                j = self.vocab.get(g)
                if j is None:
                    # n-grama fuera de vocabulario: no se guarda, pero cuenta en la norma
                    norma2 += (tf * self.idf_desconocido) ** 2
                else:
                    v = tf * self.idf[j]
                    X[r, j] = v
                    norma2 += v * v
            if norma2 > 0:
                X[r] /= np.sqrt(norma2)
        return X

# Comparación de similitud semántica contra prototipos con k-NN (promedio de los top-k cosenos por clase).
class MotorSemanticoLocal:
    """Similitud contra prototipos con k-NN (promedio de los top-k cosenos por clase)."""

    def __init__(self, config: Dict[str, Any], forzar_fallback: bool = False,
                 ruta_correcciones: Optional[Path] = None) -> None:
        self.k = int(config.get("k_vecinos", 3))
        self.clases: List[str] = list(config["prototipos"].keys())
        self.prototipos: Dict[str, List[str]] = {c: list(v) for c, v in config["prototipos"].items()}
        self.ruta_correcciones = ruta_correcciones
        self._cargar_correcciones()

        self._modelo = None
        self.motor = "fallback"
        if not forzar_fallback:
            try:
                from sentence_transformers import SentenceTransformer  # type: ignore

                self._modelo = SentenceTransformer(config["modelo_embeddings"])
                self.motor = "embeddings"
            except Exception as exc:  # librería ausente o modelo no descargable
                log.warning("sentence-transformers no disponible (%s).", exc)
        if self.motor == "fallback":
            log.warning("MOTOR FALLBACK (TF-IDF de caracteres): resultados de menor confianza.")
        self._vec: Optional[VectorizadorCaracteres] = None
        self._matrices: Dict[str, np.ndarray] = {}
        self._reconstruir()

    # -- prototipos y correcciones ------------------------------------------ #
    def _cargar_correcciones(self) -> None:
        ruta = self.ruta_correcciones
        if not ruta or not Path(ruta).exists():
            return
        for linea in Path(ruta).read_text(encoding="utf-8").splitlines():
            if not linea.strip():
                continue
            try:
                reg = json.loads(linea)
            except json.JSONDecodeError:
                continue
            if reg.get("clase") in self.prototipos and reg.get("texto"):
                self.prototipos[reg["clase"]].append(reg["texto"])

    def agregar_prototipo(self, clase: str, texto: str, persistir: bool = True) -> None:
        if clase not in self.prototipos:
            raise ValueError(f"Clase desconocida: {clase}")
        self.prototipos[clase].append(texto)
        if persistir and self.ruta_correcciones:
            with open(self.ruta_correcciones, "a", encoding="utf-8") as f:
                f.write(json.dumps({"clase": clase, "texto": texto}, ensure_ascii=False) + "\n")
        self._reconstruir()

    def _reconstruir(self) -> None:
        if self.motor == "fallback":
            todos = [t for c in self.clases for t in self.prototipos[c]]
            self._vec = VectorizadorCaracteres().ajustar(todos)
        self._matrices = {c: self.codificar(self.prototipos[c]) for c in self.clases}

    # -- vectorización ------------------------------------------------------ #
    def codificar(self, textos: Sequence[str]) -> np.ndarray:
        if self.motor == "embeddings":
            return np.asarray(
                self._modelo.encode(list(textos), normalize_embeddings=True, convert_to_numpy=True)
            )
        return self._vec.transformar(textos)

    def similitudes(self, textos: Sequence[str]) -> np.ndarray:
        """Matriz (n_textos, n_clases): promedio de los top-k cosenos por clase."""
        X = self.codificar(textos)
        columnas = []
        for c in self.clases:
            cos = X @ self._matrices[c].T
            k = min(self.k, cos.shape[1])
            columnas.append(np.sort(cos, axis=1)[:, -k:].mean(axis=1))
        return np.stack(columnas, axis=1)


# --------------------------------------------------------------------------- #
# 3. Sentimiento
# --------------------------------------------------------------------------- #
class AnalizadorSentimiento:
    """pysentimiento (probabilidades POS/NEG/NEU) con respaldo léxico."""
    #Añade frases y palabras negativas y positivas para el respaldo léxico
    NEG_FRASES = [
        r"no funciona", r"no compila", r"no corre", r"no arranca", r"no me deja",
        r"no puedo", r"no logro", r"no se que hacer", r"no sirve", r"no sale",
        r"no avanz\w+", r"sigue fallando", r"el mismo error", r"me rindo",
        r"me quiero morir", r"desgaste", r"doesn t work", r"not working",
    ]
    NEG_PALABRAS = {
        "error", "errores", "bug", "bugs", "frustrado", "frustrada", "frustrante", "harto",
        "harta", "odio", "imposible", "desesperado", "desesperada", "desesperando",
        "horrible", "fracaso", "atascado", "atascada", "bloqueado", "bloqueada", "cansado",
        "murio", "rompio", "crashea", "crasheo", "cuelga", "colgo", "pesadilla", "mal",
        "stuck", "broken", "fail", "failed", "loco",
    }
    POS_FRASES = [r"ya (funciona|corre|compila|salio|anda|quedo)", r"por fin", r"al fin", r"finalmente"]
    POS_PALABRAS = {
        "gracias", "genial", "excelente", "logre", "logrado", "listo", "perfecto", "increible",
        "feliz", "contento", "contenta", "joya", "resolvi", "solucione", "termine", "aprobe",
        "celebracion", "thanks", "works", "great",
    }

    def __init__(self, config: Dict[str, Any], forzar_fallback: bool = False) -> None:
        self._an = None
        self._emo = None
        if not forzar_fallback:
            try:
                from pysentimiento import create_analyzer  # type: ignore

                self._an = create_analyzer(task="sentiment", lang="es")
                if config.get("sentimiento", {}).get("usar_emocion"):
                    self._emo = create_analyzer(task="emotion", lang="es")
            except Exception as exc:
                log.warning("pysentimiento no disponible (%s); se usa respaldo léxico.", exc)
        self.motor = "pysentimiento" if self._an else "lexico"

    def _lexico(self, texto: str) -> Dict[str, float]:
        t = _normalizar(texto)
        neg = 0
        for p in self.NEG_FRASES:
            t, n = re.subn(p, " ", t)  # se retiran para no contarlas dos veces
            neg += n
        pos = 0
        for p in self.POS_FRASES:
            t, n = re.subn(p, " ", t)
            pos += n
        toks = t.split()
        neg += sum(1 for w in toks if w in self.NEG_PALABRAS)
        pos += sum(1 for w in toks if w in self.POS_PALABRAS)
        w_pos, w_neg = 0.3 + pos, 0.3 + neg
        w_neu = 1.0 if (pos + neg) == 0 else 0.3
        z = w_pos + w_neg + w_neu
        return {"POS": w_pos / z, "NEG": w_neg / z, "NEU": w_neu / z}

    def analizar_lote(self, textos: Sequence[str]) -> List[Dict[str, float]]:
        if not self._an:
            return [self._lexico(t) for t in textos]
        salida = [dict(r.probas) for r in self._an.predict(list(textos))]
        if self._emo:  # frustración aproximada = ira + asco + tristeza
            for d, r in zip(salida, self._emo.predict(list(textos))):
                p = r.probas
                d["FRUSTRACION"] = float(p.get("anger", 0) + p.get("disgust", 0) + p.get("sadness", 0))
        return salida


# --------------------------------------------------------------------------- #
# 4. Contexto conversacional
# --------------------------------------------------------------------------- #
class ContextoConversacional:
    """Ventana de mensajes y decisiones recientes por (guild, canal, autor)."""

    def __init__(self, max_mensajes: int = 3, ventana_segundos: int = 300, min_acumuladas: int = 2) -> None:
        self.max_mensajes = max_mensajes
        self.ventana = ventana_segundos
        self.min_acumuladas = min_acumuladas
        self._mensajes: Dict[Tuple, Deque] = defaultdict(lambda: deque(maxlen=10))
        self._decisiones: Dict[Tuple, Deque] = defaultdict(lambda: deque(maxlen=10))

    @staticmethod
    def _clave(f: DiscordSourceV1) -> Tuple:
        return (f.guild_id, f.channel_id, f.author_id)

    def _reciente(self, fecha_ref: datetime, fecha: datetime) -> bool:
        return 0 <= (fecha_ref - fecha).total_seconds() <= self.ventana

    def contexto_para(self, f: DiscordSourceV1) -> str:
        ref = f.fecha_utc()
        previos = [t for d, t in self._mensajes[self._clave(f)] if self._reciente(ref, d)]
        return " ".join(previos[-self.max_mensajes:])

    def registrar_mensaje(self, f: DiscordSourceV1, texto_sanitizado: str) -> None:
        self._mensajes[self._clave(f)].append((f.fecha_utc(), texto_sanitizado))

    def frustracion_acumulada(self, f: DiscordSourceV1) -> int:
        ref = f.fecha_utc()
        return sum(1 for d, senal in self._decisiones[self._clave(f)] if senal and self._reciente(ref, d))

    def registrar_decision(self, f: DiscordSourceV1, clase: str, p_neg: float) -> None:
        senal = clase == BLOQUEO_FRUSTRACION or p_neg > 0.5
        self._decisiones[self._clave(f)].append((f.fecha_utc(), senal))


# --------------------------------------------------------------------------- #
# 5. Generación (contrato intermedio + puerto)
# --------------------------------------------------------------------------- #
# El clasificador NO sabe qué proveedor de IA se usa: solo conoce este puerto.
# Las implementaciones (llamadas externas) viven en módulos aparte, p. ej. generador_ia.py,
# que importan de aquí. Así se evita el import circular y se mantiene la modularidad.
MAX_RESPUESTA = 1900  # unidades UTF-16; se rechaza el exceso, no se corta código


@dataclass(frozen=True)
class GeneracionSalida:
    """Contrato intermedio: lo que produce la capa generativa. Vacío = no aplica."""
    tema: str = "general"
    respuesta: str = ""
    alerta: str = ""


class GeneradorIA(Protocol):
    """Puerto de generación. Recibe el mensaje original y el diagnóstico; NO reclasifica."""

    def generar(self, fuente: DiscordSourceV1, resultado: ClasificacionResultado) -> GeneracionSalida:
        ...


# --------------------------------------------------------------------------- #
# 6. Clasificador (enrutamiento + contrato)
# --------------------------------------------------------------------------- #
# La clase _Analisis encapsula la información de un mensaje y su análisis previo a la decisión final.
# La decisión final se toma en la fase 3, que es barata y secuencial, usando la información de la fase 1+2 (preparación por lotes).
# Incluye el texto original, el texto sanitizado, el texto semántico (con contexto si aplica), la bandera de uso de contexto, la bandera de mensaje corto, las similitudes con los prototipos y el análisis de sentimiento.
@dataclass
class _Analisis:
    fuente: DiscordSourceV1
    san: TextoSanitizado
    texto_semantico: str
    usa_contexto: bool
    corto: bool
    sims: np.ndarray = None  # type: ignore
    sentimiento: Dict[str, float] = None  # type: ignore
    

class ClasificadorInteracciones:
    def __init__(self, ruta_config: Optional[Path | str] = None, config: Optional[Dict[str, Any]] = None,
                 forzar_fallback: bool = False, ruta_correcciones: Optional[Path | str] = None,
                 generador: Optional[GeneradorIA] = None,
                 responder_solo_sin_revision: Optional[bool] = None) -> None:
        self.config = config or cargar_config(ruta_config)
        if ruta_correcciones is None and self.config.get("ruta_correcciones"):
            base = Path(ruta_config).parent if ruta_config else RUTA_CONFIG_DEFECTO.parent
            ruta_correcciones = base / self.config["ruta_correcciones"]
        self.sanitizador = SanitizadorTexto()
        self.motor = MotorSemanticoLocal(
            self.config, forzar_fallback,
            Path(ruta_correcciones) if ruta_correcciones else None,
        )
        self.sentimiento = AnalizadorSentimiento(self.config, forzar_fallback)
        c = self.config["contexto"]
        self.contexto = ContextoConversacional(c["max_mensajes"], c["ventana_segundos"], c["min_acumuladas"])
        # Generación externa (puerto del bloque 5). Sin generador el clasificador sigue funcionando:
        # tema="general", respuesta="" y solo las alertas deterministas.
        self.generador: Optional[GeneradorIA] = generador
        # Parámetro del constructor > clave opcional del config > True (comportamiento previo).
        self.responder_solo_sin_revision: bool = (
            self.config.get("responder_solo_sin_revision", True)
            if responder_solo_sin_revision is None else responder_solo_sin_revision)

        m = self.motor.motor
        self.umbral: float = self.config["umbral"][m]
        self.margen: float = self.config["margen_minimo"][m]
        self.temperatura: float = self.config["temperatura"][m]
        self.pesos: Dict[str, float] = self.config["pesos"]
        self.sent_cfg: Dict[str, Any] = self.config["sentimiento"]
        self.longitud_minima: int = self.config["longitud_minima"]
        self.longitud_contexto: int = self.config["longitud_contexto"]

    # -- fase 1+2: preparación por lotes (lo costoso) ------------------------ #
    def preparar_lote(self, fuentes: Sequence[DiscordSourceV1],
                      respondidos: Optional[Sequence[Optional[str]]] = None,
                      usar_contexto: bool = True) -> List[_Analisis]:
        respondidos = list(respondidos) if respondidos is not None else [None] * len(fuentes)
        analisis: List[_Analisis] = []
        for fuente, resp in zip(fuentes, respondidos):
            fuente.validar()
            san = self.sanitizador.limpiar(fuente.content)
            ctx = ""
            if resp is not None:
                ctx = self.sanitizador.limpiar(resp).texto
            elif usar_contexto and len(san.texto) < self.longitud_contexto:
                ctx = self.contexto.contexto_para(fuente)
            usa_ctx = bool(ctx)
            texto_sem = f"{ctx} {san.texto}".strip() if usa_ctx else san.texto
            corto = len(san.texto) < self.longitud_minima and not usa_ctx
            if usar_contexto:
                self.contexto.registrar_mensaje(fuente, san.texto)
            analisis.append(_Analisis(fuente, san, texto_sem, usa_ctx, corto))
        if analisis:
            sims = self.motor.similitudes([a.texto_semantico for a in analisis])
            sents = self.sentimiento.analizar_lote([a.san.texto for a in analisis])
            for a, s_, p in zip(analisis, sims, sents):
                a.sims, a.sentimiento = s_, p
        return analisis

    # -- fase 3: decisión (barata, secuencial por el contexto) --------------- #
    def decidir(self, a: _Analisis, umbral: Optional[float] = None, margen: Optional[float] = None,
                registrar: bool = True) -> ClasificacionResultado:
        umbral = self.umbral if umbral is None else umbral
        margen = self.margen if margen is None else margen
        w, sc = self.pesos, self.sent_cfg
        rasgos = dict(a.san.rasgos, usa_contexto=a.usa_contexto)
        motivos: List[str] = []

        sims = {c: float(s_) for c, s_ in zip(self.motor.clases, a.sims)}
        p = a.sentimiento
        p_pos, p_neu = p["POS"], p["NEU"]
        p_neg = max(p["NEG"], p.get("FRUSTRACION", 0.0))
        acum = self.contexto.frustracion_acumulada(a.fuente) if registrar else 0
        rasgos["frustracion_acumulada"] = acum

        # Combinador de scores: semántica + sentimiento + rasgos
        # Funciona como un perceptrón de una capa (sin entrenamiento, solo pesos fijos).
        c = dict(sims)
        c[LOGRO] += w["logro_pos"] * p_pos - w["logro_neg"] * p_neg
        c[DUDA_TECNICA] += (w["duda_neu"] * p_neu - w["duda_neg"] * p_neg
                            + w["duda_pregunta"] * rasgos["pregunta"]
                            + w["duda_codigo"] * rasgos["tiene_codigo"])
        c[BLOQUEO_FRUSTRACION] += (
            w["bloqueo_neg"] * p_neg
            + w["bloqueo_mayusculas"] * rasgos["mayusculas_sostenidas"]
            + w["bloqueo_traza"] * rasgos["tiene_traza"]
            + w["bloqueo_idiomatica"] * rasgos["frustracion_idiomatica"]
            + (w["bloqueo_acumulada"] if acum >= self.contexto.min_acumuladas else 0.0)
        )

        orden = sorted(c, key=c.get, reverse=True)
        ganadora, segunda = orden[0], orden[1]
        valores = np.array([c[k] for k in self.motor.clases])
        z = np.exp((valores - valores.max()) / self.temperatura)
        probs = dict(zip(self.motor.clases, z / z.sum()))
        confianza = float(probs[ganadora])
        revision = False

        clase_final = ganadora
        if a.corto:
            clase_final, confianza = NO_CLASIFICADO, 0.0
            motivos.append("texto_corto")
        elif ganadora == RUIDO:
            clase_final, confianza = NO_CLASIFICADO, float(probs[RUIDO])
            motivos.append("ruido")
        elif sims[ganadora] < umbral:
            confianza = max(0.0, 1.0 - sims[ganadora] / umbral) if umbral > 0 else 0.0
            clase_final = NO_CLASIFICADO
            motivos.append("bajo_umbral")
        else:
            if (c[ganadora] - c[segunda]) < margen:
                revision = True
                motivos.append(f"margen_bajo({segunda})")
            if ganadora == DUDA_TECNICA and p_neg > sc["promocion_duda_a_bloqueo"]:
                clase_final = BLOQUEO_FRUSTRACION
                motivos.append("promocion_duda_a_bloqueo")
            if ganadora == LOGRO and p_neg > sc["conflicto_logro_neg"]:
                revision = True
                confianza *= 0.7
                motivos.append("logro_con_tono_negativo")
            if ganadora == BLOQUEO_FRUSTRACION and p_pos > sc["bloqueo_con_pos"]:
                revision = True
                motivos.append("bloqueo_con_tono_positivo")

        if rasgos["malestar_no_tecnico"]:
            revision = True
            motivos.append("posible_malestar_no_tecnico")
        if self.motor.motor == "fallback":
            confianza *= self.config.get("factor_confianza_fallback", 0.6)
        if rasgos["idioma_probable"] == "en":
            motivos.append("idioma_en")

        if registrar:
            self.contexto.registrar_decision(a.fuente, clase_final, p_neg)

        resultado = ClasificacionResultado(
            message_id=a.fuente.message_id, clase=clase_final, confianza=round(confianza, 4),
            motor=self.motor.motor,
            necesita_revision=revision, motivos=tuple(motivos),
            similitudes={k: round(v, 4) for k, v in sims.items()},
            sentimiento={k: round(float(v), 4) for k, v in p.items()}, rasgos=rasgos,
        )
        # Generar log detallado para depuración
        log.debug("clase=%s conf=%.3f rev=%s", clase_final, confianza, revision)
        return resultado

    # -- diagnóstico interno -> contrato de salida --------------------------- #
       # tema / respuesta / alerta los produce el GeneradorIA (puerto del bloque 5).
    def _generar(self, fuente: DiscordSourceV1, r: ClasificacionResultado) -> GeneracionSalida:
        """Dudas/bloqueos requieren generador; logros no publican.

        Los fallos se propagan con códigos públicos; revisión se señala mediante
        ReviewRequired. Nunca fabricar un resultado exitoso ni truncar código.
        """
        if self.responder_solo_sin_revision and r.necesita_revision:
            raise ReviewRequired("human_review_required")
        if r.clase == LOGRO or r.clase not in CLASES_OBJETIVO:
            return GeneracionSalida(tema="general")
        if self.generador is None:
            raise RuntimeError("generator_not_configured")
        try:
            g = self.generador.generar(fuente, r)
        except Exception:
            raise RuntimeError("generator_failed") from None
        if not isinstance(g, GeneracionSalida):
            raise ValueError("generator_output_invalid")
        tema = (g.tema or "").strip() or "general"
        if r.clase == BLOQUEO_FRUSTRACION:
            # Un bloqueo siempre debe quedar señalado, aunque el modelo no devuelva texto.
            alerta = (g.alerta or "").strip()
            return GeneracionSalida(tema=tema, respuesta="", alerta=alerta)
        respuesta = (g.respuesta or "").strip()
        return GeneracionSalida(tema=tema, respuesta=respuesta, alerta="")

    @staticmethod
    def _alertas_deterministas(r: ClasificacionResultado) -> List[str]:
        """Piso de seguridad: no depende del modelo generativo ni de la clase final."""
        if "posible_malestar_no_tecnico" in r.motivos or r.rasgos.get("malestar_no_tecnico"):
            return ["malestar_no_tecnico"]
        return []

    def construir_decision(self, fuente: DiscordSourceV1, r: ClasificacionResultado) -> DiscordDecisionV1:
        if self._alertas_deterministas(r):
            raise ReviewRequired("human_review_required")
        g = self._generar(fuente, r)
        decision = DiscordDecisionV1(
            message_id=r.message_id,
            es_duda=r.clase == DUDA_TECNICA,
            es_logro=r.clase == LOGRO,
            es_bloqueo=r.clase == BLOQUEO_FRUSTRACION,
            tema=g.tema,
            respuesta=g.respuesta,
            alerta=g.alerta,
        )
        validate_decision(asdict(decision), {"message_id": fuente.message_id})
        return decision
    

    # Funcionalidad de depuración: devuelve la decisión y el resultado completo (con motivos, similitudes, sentimiento, etc.)
    # -- API pública --------------------------------------------------------- #
    def clasificar_lote_detallado(self, fuentes: Sequence[DiscordSourceV1],
                                  respondidos: Optional[Sequence[Optional[str]]] = None
                                  ) -> List[Tuple[DiscordDecisionV1, ClasificacionResultado]]:
        """`respondidos[i]`: texto del mensaje al que responde la fuente i (reply de Discord;
        el contrato de entrada no lo trae, por eso es un parámetro aparte)."""
        out = []
        for a in self.preparar_lote(fuentes, respondidos):
            r = self.decidir(a)
            out.append((self.construir_decision(a.fuente, r), r))
        return out

    def clasificar_lote(self, fuentes: Sequence[DiscordSourceV1],
                        respondidos: Optional[Sequence[Optional[str]]] = None) -> List[DiscordDecisionV1]:
        return [d for d, _ in self.clasificar_lote_detallado(fuentes, respondidos)]

    def clasificar(self, fuente: DiscordSourceV1, texto_respondido: Optional[str] = None) -> DiscordDecisionV1:
        return self.clasificar_lote([fuente], [texto_respondido])[0]

    def clasificar_detallado(self, fuente: DiscordSourceV1, texto_respondido: Optional[str] = None
                             ) -> Tuple[DiscordDecisionV1, ClasificacionResultado]:
        return self.clasificar_lote_detallado([fuente], [texto_respondido])[0]

    def clasificar_payload(self, payload: Mapping[str, Any], texto_respondido: Optional[str] = None) -> Dict[str, Any]:
        """dict JSON (discord-source-v1) -> dict JSON (discord-decision-v1)."""
        return asdict(self.clasificar(DiscordSourceV1.desde_dict(payload), texto_respondido))

    async def clasificar_lote_async(self, fuentes: Sequence[DiscordSourceV1],
                                    respondidos: Optional[Sequence[Optional[str]]] = None
                                    ) -> List[DiscordDecisionV1]:
        """No bloquea el event loop del bot. Usar un solo worker a la vez por la memoria de contexto."""
        return await asyncio.to_thread(self.clasificar_lote, fuentes, respondidos)

    def registrar_correccion(self, texto: str, clase_correcta: str) -> None:
        """Bucle de mejora: un moderador corrige y el mensaje pasa a ser prototipo."""
        clase = RUIDO if clase_correcta == NO_CLASIFICADO else clase_correcta
        self.motor.agregar_prototipo(clase, self.sanitizador.limpiar(texto).texto)
