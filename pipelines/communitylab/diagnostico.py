"""Diagnóstico seguro de rechazos del proveedor de IA (logs, resultado del trabajo y API).

Política: nunca se copia texto del proveedor. El proveedor puede reflejar en su respuesta
fragmentos de la petición (textos del lote, valores de campos), con o sin comillas, así que
el mensaje libre (`error.message`) se descarta. Solo se conservan:

- el estado HTTP (entero) y una categoría interna derivada de él;
- `status` y `reason` si pertenecen a catálogos permitidos; si no, "OTRO" / "otra";
- rutas de campos normalizadas contra un vocabulario conocido de la petición generateContent
  (los segmentos desconocidos se reemplazan por "*"; nunca se copian);
- métricas numéricas de la forma de la petición (bytes, ítems, valores de enum);
- un detalle legible generado aquí desde la categoría y el estado.

`normalizar_diagnostico` vuelve a aplicar la misma política a cualquier diccionario, para que
cada capa (grafo, worker, API) solo propague valores del catálogo aunque reciba otra cosa.
"""
import re

CATEGORIAS = {400: "peticion_rechazada", 401: "credencial", 403: "permiso", 404: "modelo_o_ruta"}
CATEGORIA_GENERICA = "otro"

# google.rpc.Code (campo error.status de las APIs de Google).
ESTADOS_PROVEEDOR = frozenset({
    "INVALID_ARGUMENT", "FAILED_PRECONDITION", "OUT_OF_RANGE", "UNAUTHENTICATED", "PERMISSION_DENIED",
    "NOT_FOUND", "ABORTED", "ALREADY_EXISTS", "RESOURCE_EXHAUSTED", "CANCELLED", "DATA_LOSS",
    "UNKNOWN", "INTERNAL", "NOT_IMPLEMENTED", "UNIMPLEMENTED", "UNAVAILABLE", "DEADLINE_EXCEEDED",
})
ESTADO_GENERICO = "OTRO"

# google.rpc.ErrorInfo.reason habituales en generativelanguage.googleapis.com.
RAZONES = frozenset({
    "API_KEY_INVALID", "API_KEY_SERVICE_BLOCKED", "API_KEY_HTTP_REFERRER_BLOCKED",
    "API_KEY_IP_ADDRESS_BLOCKED", "API_KEY_ANDROID_APP_BLOCKED", "API_KEY_IOS_APP_BLOCKED",
    "SERVICE_DISABLED", "ACCESS_TOKEN_EXPIRED", "ACCESS_TOKEN_SCOPE_INSUFFICIENT",
    "CONSUMER_INVALID", "CONSUMER_SUSPENDED", "BILLING_DISABLED", "USER_PROJECT_DENIED",
    "RESOURCE_PROJECT_INVALID", "RATE_LIMIT_EXCEEDED", "RESOURCE_EXHAUSTED",
    "LOCATION_POLICY_VIOLATED", "MODEL_NOT_FOUND", "FAILED_PRECONDITION",
})
RAZON_GENERICA = "otra"

# Vocabulario de rutas de campos de la petición generateContent que construye este cliente.
SEGMENTOS = frozenset({
    "contents", "parts", "text", "role", "system_instruction", "generation_config",
    "response_mime_type", "response_json_schema", "response_schema", "max_output_tokens",
    "candidate_count", "temperature", "thinking_config", "thinking_level", "model",
    "safety_settings", "tools", "properties", "items", "enum", "required", "min_items",
    "max_items", "type", "additional_properties", "minimum", "maximum", "description",
    "generate_content_request",
})
MAX_CAMPOS = 5
MAX_SEGMENTOS = 8
METRICAS = ("bytes_peticion", "bytes_esquema", "valores_enum", "items_esperados")

DETALLES = {
    ("peticion_rechazada", "INVALID_ARGUMENT"): "El proveedor rechazó la petición por un argumento inválido (por ejemplo, el esquema de respuesta o su tamaño).",
    ("peticion_rechazada", "FAILED_PRECONDITION"): "El proveedor rechazó la petición: falta una condición previa (por ejemplo, región o facturación).",
    ("credencial", None): "Credencial del proveedor ausente, inválida o vencida.",
    ("permiso", None): "La credencial no tiene permiso para este modelo o servicio.",
    ("modelo_o_ruta", None): "Modelo o ruta inexistente en el proveedor.",
    ("peticion_rechazada", None): "El proveedor rechazó la petición.",
}
DETALLE_GENERICO = "El proveedor rechazó la petición; revisar estado HTTP y categoría."

_CAMELO = re.compile(r"(?<!^)(?=[A-Z])")
_INDICE = re.compile(r"\[\d*\]")  # [3] del proveedor y [] ya normalizado


def _estado_permitido(valor):
    if valor is None:
        return None
    return valor if isinstance(valor, str) and valor in ESTADOS_PROVEEDOR else ESTADO_GENERICO


def _razon_permitida(valor):
    if valor is None:
        return None
    return valor if isinstance(valor, str) and valor in RAZONES else RAZON_GENERICA


def normalizar_campo(campo):
    """Ruta de campo con segmentos del vocabulario; los desconocidos se reemplazan por '*'."""
    if not isinstance(campo, str) or not campo:
        return None
    segmentos = []
    for crudo in campo.split(".")[:MAX_SEGMENTOS]:
        base = _INDICE.sub("", crudo)
        indexado = base != crudo
        nombre = _CAMELO.sub("_", base).lower()
        segmento = nombre if nombre in SEGMENTOS else "*"
        segmentos.append(segmento + ("[]" if indexado and segmento != "*" else ""))
    if not segmentos or segmentos[0] == "*":
        return "*"
    return ".".join(segmentos)


def _detalle(categoria, estado):
    return DETALLES.get((categoria, estado)) or DETALLES.get((categoria, None)) or DETALLE_GENERICO


def _http(valor):
    return valor if type(valor) is int and 100 <= valor <= 599 else None


def diagnostico_seguro(estado_http, cuerpo, peticion=None):
    """Diagnóstico de un rechazo HTTP del proveedor; ignora error.message y todo texto libre."""
    error = cuerpo.get("error") if isinstance(cuerpo, dict) else None
    error = error if isinstance(error, dict) else {}
    razon, campos = None, []
    detalles = error.get("details")
    for detalle in detalles if isinstance(detalles, list) else []:
        if not isinstance(detalle, dict):
            continue
        if razon is None and "reason" in detalle:
            razon = _razon_permitida(detalle.get("reason"))
        violaciones = detalle.get("fieldViolations")
        for violacion in violaciones if isinstance(violaciones, list) else []:
            campo = normalizar_campo(violacion.get("field") if isinstance(violacion, dict) else None)
            if campo and campo not in campos and len(campos) < MAX_CAMPOS:
                campos.append(campo)
    return normalizar_diagnostico({
        "http": estado_http, "estado_proveedor": _estado_permitido(error.get("status")),
        "razon": razon, "campos": campos, "peticion": peticion,
    })


def normalizar_diagnostico(diagnostico):
    """Reaplica la política a un diagnóstico de cualquier origen; None si no es un dict."""
    if not isinstance(diagnostico, dict):
        return None
    http = _http(diagnostico.get("http"))
    categoria = CATEGORIAS.get(http, CATEGORIA_GENERICA)
    estado = _estado_permitido(diagnostico.get("estado_proveedor"))
    campos = diagnostico.get("campos")
    campos = [c for c in (normalizar_campo(c) for c in (campos if isinstance(campos, list) else []))
              if c][:MAX_CAMPOS]
    peticion = diagnostico.get("peticion")
    peticion = {k: peticion[k] for k in METRICAS
                if isinstance(peticion, dict) and type(peticion.get(k)) in (int, float)}
    salida = {"http": http, "categoria": categoria, "estado_proveedor": estado,
              "razon": _razon_permitida(diagnostico.get("razon")), "campos": campos,
              "detalle": _detalle(categoria, estado)}
    if peticion:
        salida["peticion"] = peticion
    return salida
