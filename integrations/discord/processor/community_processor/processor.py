"""Adaptador async: no publica, no accede al backend y no ejecuta herramientas."""
import asyncio
from datetime import datetime
import json
import os
from pathlib import Path

from bot_discord.contracts import SOURCE_KEYS, snowflake, text, validate_decision

PROMPT = Path(__file__).with_name("prompt.txt").read_text(encoding="utf-8")
MODEL_FIELDS = {"es_duda", "es_logro", "es_bloqueo", "tema", "respuesta", "alerta"}


class ProcessingError(RuntimeError):
    """Código público de fallo; no incluye texto, credenciales ni respuesta cruda."""


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate")
            result[key] = value
        return result
    def constant(_):
        raise ValueError("non_finite")
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)


def validate_event(event):
    try:
        if not isinstance(event, dict) or set(event) != SOURCE_KEYS or event["schema_version"] != "discord-source-v1":
            raise ValueError()
        for field in ("message_id", "guild_id", "channel_id", "author_id"):
            snowflake(event[field])
        text(event["content"], 4000)
        date = datetime.fromisoformat(event["created_at"].replace("Z", "+00:00"))
        if date.tzinfo is None:
            raise ValueError()
        return dict(event)
    except (ValueError, TypeError, AttributeError, UnicodeError):
        raise ProcessingError("source_invalid") from None


class Processor:
    def __init__(self, provider, timeout=45):
        if type(timeout) not in (int, float) or not 0 < timeout <= 45:
            raise ValueError("timeout_invalid")
        self.provider, self.timeout = provider, timeout

    async def __call__(self, event):
        source = validate_event(event)
        # No enviar IDs ni nombres al proveedor. La identidad de salida se fija localmente.
        messages = [{"role": "system", "content": PROMPT},
                    {"role": "user", "content": json.dumps({"mensaje": source["content"]}, ensure_ascii=False)}]
        try:
            raw = await asyncio.wait_for(self.provider.complete(messages), timeout=self.timeout)
            if not isinstance(raw, str) or len(raw.encode("utf-8")) > 20000:
                raise ValueError()
            decision = strict_json(raw)
            if not isinstance(decision, dict) or set(decision) != MODEL_FIELDS:
                raise ValueError()
            result = {"schema_version": "discord-decision-v1", "message_id": source["message_id"], **decision}
            return validate_decision(result, source)
        except asyncio.CancelledError:
            raise
        except TimeoutError:
            raise ProcessingError("provider_timeout") from None
        except ProcessingError:
            raise
        except Exception:
            raise ProcessingError("provider_or_contract_invalid") from None


async def procesar(evento):
    """Punto de entrada --processor community_processor:procesar. Sin fallback ficticio."""
    # Validar antes de cargar configuración o contactar servicios externos.
    validate_event(evento)
    if os.environ.get("COMMUNITYLAB_BOT_ENABLE_LLM") != "1":
        raise ProcessingError("provider_not_enabled")
    from .provider import OpenRouter
    provider = OpenRouter.from_env()
    return await Processor(provider)(evento)
