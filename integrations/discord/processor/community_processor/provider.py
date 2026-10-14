"""Una petición async acotada; sin reintentos automáticos ni logs del contenido."""
import os
import httpx

from .processor import ProcessingError, strict_json


class OpenRouter:
    URL = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(self, api_key, model, *, transport=None):
        if (not isinstance(api_key, str) or not api_key.strip()
                or not isinstance(model, str) or not model.strip() or len(model) > 200):
            raise ProcessingError("provider_configuration_missing")
        self._api_key, self.model, self._transport = api_key, model, transport

    @classmethod
    def from_env(cls):
        return cls(os.environ.get("OPENROUTER_API_KEY"), os.environ.get("COMMUNITYLAB_BOT_MODEL"))

    async def complete(self, messages):
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(35, connect=5), follow_redirects=False,
                                         trust_env=False, transport=self._transport) as client:
                async with client.stream("POST", self.URL,
                        headers={"Authorization": "Bearer " + self._api_key},
                        json={"model": self.model, "messages": messages, "stream": False,
                              "temperature": 0, "max_tokens": 1000,
                              "response_format": {"type": "json_object"}}) as response:
                    if response.status_code != 200:
                        raise ProcessingError("provider_http_error")
                    parts, size = [], 0
                    async for part in response.aiter_bytes():
                        size += len(part)
                        if size > 65536:
                            raise ProcessingError("provider_response_too_large")
                        parts.append(part)
                    body = strict_json(b"".join(parts).decode("utf-8"))
            choices = body["choices"]
            if not isinstance(choices, list) or len(choices) != 1:
                raise ValueError()
            choice = choices[0]
            if choice.get("finish_reason") != "stop" or choice["message"].get("tool_calls"):
                raise ValueError()
            content = choice["message"]["content"]
            if not isinstance(content, str) or not content.strip():
                raise ValueError()
            return content
        except ProcessingError:
            raise
        except httpx.TimeoutException:
            raise ProcessingError("provider_timeout") from None
        except Exception:
            raise ProcessingError("provider_response_invalid") from None
