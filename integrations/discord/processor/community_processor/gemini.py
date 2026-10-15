"""Proveedor Gemini async; no publica ni reintenta automáticamente."""
import re
import httpx
from .processor import ProcessingError, strict_json


class Gemini:
    def __init__(self, key, model="gemini-3.5-flash-lite", *, report=None, transport=None):
        if not key or not re.fullmatch(r"gemini-[a-zA-Z0-9._-]+", model):
            raise ProcessingError("gemini_configuration_missing")
        self.key, self.model = key, model
        self.report = report if report is not None else {}
        self.transport = transport

    async def complete(self, messages):
        payload = {
            "systemInstruction": {"parts": [{"text": messages[0]["content"]}]},
            "contents": [{"role": "user", "parts": [{"text": messages[1]["content"]}]}],
            "generationConfig": {"responseMimeType": "application/json", "maxOutputTokens": 2048},
        }
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(35, connect=5),
                                         follow_redirects=False, trust_env=False,
                                         transport=self.transport) as client:
                async with client.stream("POST",
                        "https://generativelanguage.googleapis.com/v1beta/models/"
                        + self.model + ":generateContent",
                        headers={"x-goog-api-key": self.key}, json=payload) as response:
                    self.report["estado_http"] = response.status_code
                    if response.status_code != 200:
                        raise ProcessingError("gemini_http_error")
                    parts, size = [], 0
                    async for part in response.aiter_bytes():
                        size += len(part)
                        if size > 65536:
                            raise ProcessingError("gemini_response_too_large")
                        parts.append(part)
                    body = strict_json(b"".join(parts).decode("utf-8"))
            candidates = body.get("candidates", [])
            if len(candidates) != 1 or candidates[0].get("finishReason") != "STOP":
                raise ProcessingError("gemini_response_incomplete_or_blocked")
            content = candidates[0]["content"]["parts"]
            texts = []
            for part in content:
                if part.get("thought") is True:
                    continue
                if not isinstance(part.get("text"), str) or "functionCall" in part:
                    raise ProcessingError("gemini_response_invalid")
                texts.append(part["text"])
            result = "".join(texts)
            if not result.strip():
                raise ProcessingError("gemini_response_empty")
            return result
        except ProcessingError:
            raise
        except httpx.TimeoutException:
            raise ProcessingError("gemini_timeout") from None
        except Exception:
            raise ProcessingError("gemini_response_invalid") from None
