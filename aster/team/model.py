"""The model call Forge uses to write and repair the booking application.

A caller returns the assistant text for one prompt. ``ModelCallError`` means the
call did not produce that text. The OpenAI-compatible caller reads
``ASTER_UPSTREAM_URL``, ``ASTER_UPSTREAM_API_KEY``, and ``ASTER_UPSTREAM_MODEL``
from the process environment. The key is sent only on that request.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from collections.abc import Mapping


class ModelCallError(RuntimeError):
    """The model did not return assistant text."""


class ModelCaller(ABC):
    """One completion: prompt text in, assistant text out."""

    @abstractmethod
    def complete(self, prompt: str) -> str:
        """Return the assistant text for ``prompt``.

        Raise ``ModelCallError`` when the provider does not answer or the body
        has no assistant text.
        """


class OpenAIChatModel(ModelCaller):
    """A chat completion against an OpenAI-compatible ``/v1/chat/completions`` URL."""

    def __init__(self, base_url: str, api_key: str, model: str, timeout_s: float = 60.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout_s = timeout_s

    def complete(self, prompt: str) -> str:
        payload = {"model": self.model, "messages": [{"role": "user", "content": prompt}]}
        request = urllib.request.Request(
            f"{self.base_url}/v1/chat/completions",
            data=json.dumps(payload).encode(),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
                body = json.loads(response.read().decode())
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")
            message = detail
            try:
                parsed = json.loads(detail)
                error = parsed.get("error", {})
                if isinstance(error, dict) and isinstance(error.get("message"), str):
                    message = error["message"]
            except json.JSONDecodeError:
                message = detail.strip() or str(exc)
            message = message.replace(self.api_key, "[key]")
            raise ModelCallError(message) from exc
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            raise ModelCallError(str(exc)) from exc
        try:
            text = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ModelCallError("the model response has no assistant text") from exc
        if not isinstance(text, str) or not text.strip():
            raise ModelCallError("the model response has no assistant text")
        return text


def model_from_environment(environ: Mapping[str, str] | None = None) -> ModelCaller | None:
    """The configured provider, or ``None`` when the URL or key is empty."""
    values = os.environ if environ is None else environ
    base_url = values.get("ASTER_UPSTREAM_URL", "").strip()
    api_key = values.get("ASTER_UPSTREAM_API_KEY", "").strip()
    model = values.get("ASTER_UPSTREAM_MODEL", "").strip() or "gpt-4o"
    if not base_url or not api_key:
        return None
    return OpenAIChatModel(base_url, api_key, model)
