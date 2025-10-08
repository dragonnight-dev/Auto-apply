"""Client for the local small language model, served by Ollama.

``call_tool`` is the tool fallback chain, because small models do not always emit a
well-formed tool call:
  1. native tool calling;
  2. a JSON object found in the model's plain-text reply;
  3. a retry constrained to the tool's JSON schema.
If all three fail it raises SLMError, and callers use their deterministic fallback.
"""
import json
import logging

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)


class SLMError(Exception):
    pass


def _first_json_object(text: str):
    decoder = json.JSONDecoder()
    index = text.find("{")
    while index != -1:
        try:
            value, _ = decoder.raw_decode(text[index:])
            if isinstance(value, dict):
                return value
        except json.JSONDecodeError:
            pass
        index = text.find("{", index + 1)
    return None


class SLMClient:
    def __init__(self, base_url=None, model=None, timeout=None, transport=None):
        self.model = model or settings.SLM_MODEL
        self._http = httpx.Client(
            base_url=base_url or settings.SLM_BASE_URL,
            timeout=timeout or settings.SLM_TIMEOUT_SECONDS,
            transport=transport,
        )

    def _chat(self, system: str, user: str, **extra) -> dict:
        body = {
            "model": self.model,
            "stream": False,
            "options": {"temperature": 0.1, "num_ctx": settings.SLM_NUM_CTX},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            **extra,
        }
        try:
            response = self._http.post("/api/chat", json=body)
            response.raise_for_status()
            return response.json()["message"]
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            raise SLMError(f"SLM request failed: {exc}") from exc

    def complete(self, system: str, user: str) -> str:
        text = (self._chat(system, user).get("content") or "").strip()
        if not text:
            raise SLMError("SLM returned an empty reply")
        return text

    def call_tool(self, system: str, user: str, name: str, description: str, parameters: dict) -> dict:
        tool = {"type": "function", "function": {"name": name, "description": description, "parameters": parameters}}
        message = self._chat(system, user, tools=[tool])
        for call in message.get("tool_calls") or []:
            function = call.get("function", {})
            arguments = function.get("arguments")
            if isinstance(arguments, str):
                arguments = _first_json_object(arguments)
            if function.get("name") == name and isinstance(arguments, dict):
                return arguments

        parsed = _first_json_object(message.get("content") or "")
        if parsed is not None:
            return parsed

        logger.info("SLM skipped tool %s; retrying with schema-constrained output", name)
        retry = self._chat(system, user, format=parameters)
        parsed = _first_json_object(retry.get("content") or "")
        if parsed is None:
            raise SLMError(f"SLM produced no usable output for tool {name}")
        return parsed
