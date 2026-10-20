"""Cliente Gemini compartido por los nodos del grafo (REST generateContent, síncrono).

Política única para todo un trabajo:
- Modelos escalonados (GEMINI_MODELOS, de rápido a escalado). Solo se escala cuando la
  respuesta incumple el contrato (JSON inválido, truncada, vacía o rechazada por el validador).
- Nunca se escala por credenciales, configuración o cuota agotada.
- 429 por ritmo y fallos transitorios: reintentos acotados en el mismo modelo, respetando
  Retry-After/RetryInfo si llegan, siempre dentro del presupuesto.
- Presupuesto por trabajo: tiempo total, número de llamadas y tokens de salida.

No usa el SDK google-genai a propósito: el SDK reintenta por su cuenta y multiplicaría
los reintentos de esta política y del worker. Los errores y los logs nunca incluyen
textos del lote, respuestas del modelo ni mensajes del proveedor. De un rechazo 4xx solo se
conserva un diagnóstico estructurado (diagnostico.py): estado HTTP, categoría interna, estado y
razón del proveedor de catálogos permitidos, rutas de campos normalizadas y métricas de tamaño.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import email.utils
import json
import logging
import os
import re
import time

import httpx

# diagnostico_seguro se reexporta: cliente, grafo y pruebas lo importan desde aquí.
from .diagnostico import diagnostico_seguro  # noqa: F401

URL_BASE = "https://generativelanguage.googleapis.com/v1beta/models/"
LOG = logging.getLogger("communitylab.gemini")
MODELO_VALIDO = re.compile(r"gemini-[a-z0-9][a-z0-9.\-]*")
NIVELES_RAZONAMIENTO = {"MINIMAL", "LOW", "MEDIUM", "HIGH"}
TAMANO_MAXIMO_RESPUESTA = 1_000_000
BLOQUEOS = {"SAFETY", "RECITATION", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII", "LANGUAGE"}


class ErrorIA(Exception):
    """Base: el mensaje es siempre un código controlado, sin texto externo."""
    codigo = "ia_error"

    def __init__(self, detalle=None, diagnostico=None):
        super().__init__(detalle or self.codigo)
        # Diagnóstico de catálogo (ver diagnostico.py); nunca texto del proveedor.
        self.diagnostico = diagnostico


class ErrorConfiguracionIA(ErrorIA):
    codigo = "ia_configuracion"  # clave ausente/inválida, permisos, modelo inexistente, petición rechazada


class ErrorCuotaIA(ErrorIA):
    codigo = "ia_cuota"  # 429 sin margen para esperar o cuota diaria agotada


class ErrorTransitorioIA(ErrorIA):
    codigo = "ia_transitorio"  # timeout, conexión, 5xx tras agotar reintentos


class RespuestaInvalidaIA(ErrorIA):
    codigo = "ia_respuesta_invalida"  # todos los modelos incumplieron el contrato


class RespuestaTruncadaIA(RespuestaInvalidaIA):
    """La respuesta llegó cortada por maxOutputTokens (finishReason=MAX_TOKENS).

    Solo la reciben los llamadores que lo piden (generar_json(..., escalar_si_trunca=False)): escalar al
    modelo siguiente con el mismo límite de salida no arregla un truncamiento. analisis_gemini la usa
    para dividir el bloque; nunca sale del nodo (se traduce a RespuestaInvalidaIA si no hay solución)."""


class ContenidoBloqueadoIA(ErrorIA):
    codigo = "ia_bloqueado"  # filtro de seguridad del proveedor


class PresupuestoAgotadoIA(ErrorIA):
    codigo = "ia_presupuesto"  # tiempo, llamadas o tokens del trabajo


class _FalloContrato(Exception):
    """Interno: la respuesta llegó pero no sirve; habilita el escalamiento."""

    def __init__(self, motivo):
        super().__init__(motivo)
        self.motivo = motivo


def _entero(env, nombre, defecto, minimo, maximo):
    try:
        valor = int(env.get(nombre, defecto))
    except (TypeError, ValueError):
        raise ErrorConfiguracionIA(f"{nombre} inválido") from None
    if not minimo <= valor <= maximo:
        raise ErrorConfiguracionIA(f"{nombre} fuera de rango")
    return valor


def _real(env, nombre, defecto, minimo, maximo):
    try:
        valor = float(env.get(nombre, defecto))
    except (TypeError, ValueError):
        raise ErrorConfiguracionIA(f"{nombre} inválido") from None
    if not minimo <= valor <= maximo:
        raise ErrorConfiguracionIA(f"{nombre} fuera de rango")
    return valor


@dataclass(frozen=True)
class ConfiguracionGemini:
    clave: str = field(repr=False)
    modelos: tuple
    timeout_peticion: float = 30.0
    presupuesto_segundos: float = 100.0
    max_llamadas: int = 16
    max_tokens_salida: int = 2048
    max_tokens_trabajo: int = 40000
    reintentos: int = 1
    espera_maxima: float = 10.0
    tamano_bloque: int = 40
    nivel_razonamiento: str | None = None
    temperatura: float | None = None

    def __post_init__(self):
        if not isinstance(self.clave, str) or not self.clave.strip():
            raise ErrorConfiguracionIA("Falta GEMINI_API_KEY")
        if (not self.modelos or len(set(self.modelos)) != len(self.modelos)
                or any(not isinstance(m, str) or not MODELO_VALIDO.fullmatch(m) for m in self.modelos)):
            raise ErrorConfiguracionIA("GEMINI_MODELOS inválido")
        if self.timeout_peticion > self.presupuesto_segundos:
            raise ErrorConfiguracionIA("El timeout por petición supera el presupuesto del trabajo")
        if self.nivel_razonamiento is not None and self.nivel_razonamiento not in NIVELES_RAZONAMIENTO:
            raise ErrorConfiguracionIA("GEMINI_NIVEL_RAZONAMIENTO inválido")

    @classmethod
    def desde_entorno(cls, env=None):
        env = os.environ if env is None else env
        modelos = tuple(m.strip() for m in env.get("GEMINI_MODELOS", "").split(",") if m.strip())
        nivel = env.get("GEMINI_NIVEL_RAZONAMIENTO", "").strip().upper() or None
        temperatura = env.get("GEMINI_TEMPERATURA", "").strip()
        return cls(
            clave=env.get("GEMINI_API_KEY", "").strip(),
            modelos=modelos,
            timeout_peticion=_real(env, "GEMINI_TIMEOUT_PETICION", 30, 1, 120),
            presupuesto_segundos=_real(env, "GEMINI_PRESUPUESTO_SEGUNDOS", 100, 5, 1800),
            max_llamadas=_entero(env, "GEMINI_MAX_LLAMADAS", 16, 1, 200),
            max_tokens_salida=_entero(env, "GEMINI_MAX_TOKENS_SALIDA", 2048, 64, 65536),
            max_tokens_trabajo=_entero(env, "GEMINI_MAX_TOKENS_TRABAJO", 40000, 256, 2_000_000),
            reintentos=_entero(env, "GEMINI_REINTENTOS", 1, 0, 3),
            espera_maxima=_real(env, "GEMINI_ESPERA_MAXIMA", 10, 0, 60),
            tamano_bloque=_entero(env, "GEMINI_TAMANO_BLOQUE", 40, 1, 500),
            nivel_razonamiento=nivel,
            temperatura=_real(env, "GEMINI_TEMPERATURA", 0, 0, 2) if temperatura else None,
        )


class Presupuesto:
    """Límites de un trabajo completo (las 5 etapas comparten la misma instancia)."""

    def __init__(self, cfg, reloj):
        self.cfg, self.reloj = cfg, reloj
        self.fin = reloj() + cfg.presupuesto_segundos
        self.llamadas = 0
        self.tokens = 0

    def restante(self):
        return self.fin - self.reloj()

    def reservar_llamada(self):
        if self.llamadas >= self.cfg.max_llamadas:
            raise PresupuestoAgotadoIA("llamadas")
        if self.tokens >= self.cfg.max_tokens_trabajo:
            raise PresupuestoAgotadoIA("tokens")
        if self.restante() < 1:
            raise PresupuestoAgotadoIA("tiempo")
        self.llamadas += 1

    def registrar_tokens(self, cantidad):
        self.tokens += max(0, int(cantidad or 0))


def _retry_after(respuesta, cuerpo, ahora=time.time):
    """Segundos sugeridos por el proveedor (cabecera Retry-After o RetryInfo), o None."""
    valor = respuesta.headers.get("retry-after")
    if valor:
        try:
            return max(0.0, float(valor))
        except ValueError:
            try:
                fecha = email.utils.parsedate_to_datetime(valor)
            except (TypeError, ValueError):
                fecha = None
            if fecha is not None and fecha.tzinfo is not None:
                return max(0.0, fecha.timestamp() - ahora())
    for detalle in (cuerpo.get("error", {}) or {}).get("details", []) or []:
        if isinstance(detalle, dict) and str(detalle.get("@type", "")).endswith("RetryInfo"):
            m = re.fullmatch(r"(\d+(?:\.\d+)?)s", str(detalle.get("retryDelay", "")))
            if m:
                return float(m.group(1))
    return None


def _cuota_diaria(cuerpo):
    """Heurística documentada: los detalles QuotaFailure con un quotaId 'PerDay'."""
    for detalle in (cuerpo.get("error", {}) or {}).get("details", []) or []:
        if isinstance(detalle, dict):
            for violacion in detalle.get("violations", []) or []:
                if "perday" in str(violacion.get("quotaId", "")).lower():
                    return True
    return False


def _json(respuesta):
    try:
        datos = respuesta.json()
    except ValueError:
        return {}
    return datos if isinstance(datos, dict) else {}


def _forma_peticion(cuerpo, esquema):
    """Métricas de tamaño de la petición, sin contenido."""
    def contar_enum(nodo):
        if isinstance(nodo, dict):
            propio = len(nodo["enum"]) if isinstance(nodo.get("enum"), list) else 0
            return propio + sum(contar_enum(v) for v in nodo.values())
        if isinstance(nodo, list):
            return sum(contar_enum(v) for v in nodo)
        return 0
    items = ((esquema.get("properties") or {}).get("resultados") or {}) if isinstance(esquema, dict) else {}
    # Sin maxItems (analisis_gemini ya no fija la longitud), los ítems esperados son los IDs del enum.
    enum_ids = (((items.get("items") or {}).get("properties") or {}).get("id") or {}).get("enum")
    return {"bytes_peticion": len(json.dumps(cuerpo, ensure_ascii=False).encode()),
            "bytes_esquema": len(json.dumps(esquema, ensure_ascii=False).encode()),
            "valores_enum": contar_enum(esquema),
            "items_esperados": items.get("maxItems") or (len(enum_ids) if isinstance(enum_ids, list) else 0)}


class ClienteGemini:
    def __init__(self, cfg, *, transporte=None, reloj=time.monotonic, dormir=time.sleep):
        self.cfg = cfg
        self.presupuesto = Presupuesto(cfg, reloj)
        self.reloj, self.dormir = reloj, dormir
        self.http = httpx.Client(transport=transporte, follow_redirects=False, trust_env=False)

    def generar_json(self, tarea, sistema, usuario, esquema, validar, escalar_si_trunca=True):
        """Devuelve validar(objeto_json). Escala de modelo solo si el contrato falla.

        Con escalar_si_trunca=False, una respuesta truncada (MAX_TOKENS) lanza RespuestaTruncadaIA en vez
        de repetir la misma petición, con el mismo límite de salida, en el modelo siguiente."""
        for indice, modelo in enumerate(self.cfg.modelos):
            try:
                texto = self._llamar(tarea, modelo, sistema, usuario, esquema)
                try:
                    objeto = json.loads(texto)
                except ValueError:
                    raise _FalloContrato("json_invalido") from None
                try:
                    return validar(objeto)
                except (ValueError, TypeError, KeyError):
                    raise _FalloContrato("contrato") from None
            except _FalloContrato as fallo:
                if fallo.motivo == "truncado" and not escalar_si_trunca:
                    LOG.warning("gemini truncado tarea=%s modelo=%s sin_escalamiento", tarea, modelo)
                    raise RespuestaTruncadaIA("truncado") from None
                siguiente = self.cfg.modelos[indice + 1] if indice + 1 < len(self.cfg.modelos) else None
                LOG.warning("gemini escalamiento tarea=%s modelo=%s motivo=%s siguiente=%s",
                            tarea, modelo, fallo.motivo, siguiente or "ninguno")
        raise RespuestaInvalidaIA()

    def _cuerpo(self, sistema, usuario, esquema):
        config = {"responseMimeType": "application/json", "responseJsonSchema": esquema,
                  "candidateCount": 1, "maxOutputTokens": self.cfg.max_tokens_salida}
        if self.cfg.temperatura is not None:
            config["temperature"] = self.cfg.temperatura
        if self.cfg.nivel_razonamiento:
            config["thinkingConfig"] = {"thinkingLevel": self.cfg.nivel_razonamiento}
        return {"systemInstruction": {"parts": [{"text": sistema}]},
                "contents": [{"role": "user", "parts": [{"text": usuario}]}],
                "generationConfig": config}

    def _llamar(self, tarea, modelo, sistema, usuario, esquema):
        cuerpo = self._cuerpo(sistema, usuario, esquema)
        ultimo_cuota = False
        for intento in range(self.cfg.reintentos + 1):
            self.presupuesto.reservar_llamada()
            plazo = min(self.cfg.timeout_peticion, self.presupuesto.restante())
            inicio = self.reloj()
            espera = None
            try:
                respuesta = self.http.post(
                    URL_BASE + modelo + ":generateContent", json=cuerpo,
                    headers={"x-goog-api-key": self.cfg.clave},
                    timeout=httpx.Timeout(plazo, connect=min(5.0, plazo)))
            except httpx.TimeoutException:
                self._metrica(tarea, modelo, intento, "timeout", None, inicio)
                ultimo_cuota = False
            except httpx.TransportError:
                self._metrica(tarea, modelo, intento, "conexion", None, inicio)
                ultimo_cuota = False
            else:
                estado = respuesta.status_code
                if estado == 200:
                    return self._extraer(tarea, modelo, intento, respuesta, inicio)
                datos = _json(respuesta)
                if estado in (400, 401, 403, 404):
                    self._metrica(tarea, modelo, intento, "configuracion", estado, inicio)
                    diagnostico = diagnostico_seguro(estado, datos, _forma_peticion(cuerpo, esquema))
                    self._diagnostico(tarea, modelo, diagnostico)
                    raise ErrorConfiguracionIA(f"http_{estado}", diagnostico)
                if estado == 402:
                    self._metrica(tarea, modelo, intento, "cuota", estado, inicio)
                    raise ErrorCuotaIA("http_402")
                if estado == 429:
                    self._metrica(tarea, modelo, intento, "cuota", estado, inicio)
                    if _cuota_diaria(datos):
                        raise ErrorCuotaIA("cuota_diaria")
                    ultimo_cuota, espera = True, _retry_after(respuesta, datos)
                elif estado in (408, 500, 502, 503, 504):
                    self._metrica(tarea, modelo, intento, "transitorio", estado, inicio)
                    ultimo_cuota, espera = False, _retry_after(respuesta, datos)
                else:
                    self._metrica(tarea, modelo, intento, "configuracion", estado, inicio)
                    diagnostico = diagnostico_seguro(estado, datos, _forma_peticion(cuerpo, esquema))
                    self._diagnostico(tarea, modelo, diagnostico)
                    raise ErrorConfiguracionIA(f"http_{estado}", diagnostico)
            if intento == self.cfg.reintentos:
                break
            espera = min(2.0 ** intento, self.cfg.espera_maxima) if espera is None else espera
            # Sin margen para esperar y volver a llamar: se corta en vez de exceder el trabajo.
            if espera > self.cfg.espera_maxima or espera + 1 >= self.presupuesto.restante():
                break
            self.dormir(espera)
        raise ErrorCuotaIA("rate_limit") if ultimo_cuota else ErrorTransitorioIA()

    def _extraer(self, tarea, modelo, intento, respuesta, inicio):
        if len(respuesta.content) > TAMANO_MAXIMO_RESPUESTA:
            self._metrica(tarea, modelo, intento, "demasiado_grande", 200, inicio)
            raise _FalloContrato("demasiado_grande")
        datos = _json(respuesta)
        uso = datos.get("usageMetadata") or {}
        tokens = (uso.get("candidatesTokenCount") or 0) + (uso.get("thoughtsTokenCount") or 0)
        self.presupuesto.registrar_tokens(tokens)
        if (datos.get("promptFeedback") or {}).get("blockReason"):
            self._metrica(tarea, modelo, intento, "bloqueado", 200, inicio, tokens)
            raise ContenidoBloqueadoIA()
        candidatos = datos.get("candidates")
        if not isinstance(candidatos, list) or len(candidatos) != 1 or not isinstance(candidatos[0], dict):
            self._metrica(tarea, modelo, intento, "sin_candidato", 200, inicio, tokens)
            raise _FalloContrato("sin_candidato")
        final = candidatos[0].get("finishReason")
        if final in BLOQUEOS:
            self._metrica(tarea, modelo, intento, "bloqueado", 200, inicio, tokens)
            raise ContenidoBloqueadoIA()
        if final != "STOP":
            motivo = "truncado" if final == "MAX_TOKENS" else "terminacion"
            self._metrica(tarea, modelo, intento, motivo, 200, inicio, tokens)
            raise _FalloContrato(motivo)
        partes = (candidatos[0].get("content") or {}).get("parts")
        textos = []
        for parte in partes if isinstance(partes, list) else []:
            if not isinstance(parte, dict) or parte.get("thought") is True:
                continue
            if not isinstance(parte.get("text"), str):
                self._metrica(tarea, modelo, intento, "formato", 200, inicio, tokens)
                raise _FalloContrato("formato")
            textos.append(parte["text"])
        texto = "".join(textos)
        if not texto.strip():
            self._metrica(tarea, modelo, intento, "vacio", 200, inicio, tokens)
            raise _FalloContrato("vacio")
        self._metrica(tarea, modelo, intento, "ok", 200, inicio, tokens)
        return texto

    def _diagnostico(self, tarea, modelo, d):
        LOG.warning("gemini diagnostico tarea=%s modelo=%s http=%s categoria=%s estado_proveedor=%s "
                    "razon=%s campos=%s peticion=%s", tarea, modelo, d["http"], d["categoria"],
                    d["estado_proveedor"], d["razon"], ",".join(d["campos"]) or "-",
                    json.dumps(d.get("peticion", {})))

    def _metrica(self, tarea, modelo, intento, resultado, http, inicio, tokens=None):
        LOG.info("gemini tarea=%s modelo=%s intento=%d resultado=%s http=%s latencia_ms=%d "
                 "tokens_salida=%s llamadas=%d", tarea, modelo, intento, resultado, http,
                 int((self.reloj() - inicio) * 1000), tokens, self.presupuesto.llamadas)
