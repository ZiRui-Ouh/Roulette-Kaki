"""MERaLiON API client.

Thin wrapper around https://api.meralion.ai/v1 for the audio-input paths
where MERaLiON's Singlish/accent-aware models outperform generic ASR:

- POST /audio/transcriptions   — speech → same-language text
- POST /audio/translations     — speech → target-language text

Text-to-text translation stays on Nova (services/bedrock.py); this module
is deliberately narrow so we don't grow a second LLM surface.

Auth: X-API-Key header. Reads MERALION_API_KEY and MERALION_BASE_URL at
import time; a shared httpx.Client is reused across calls, mirroring the
"one client, one module" pattern of services/bedrock.py.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import httpx

log = logging.getLogger(__name__)

MERALION_BASE_URL = os.environ.get("MERALION_BASE_URL", "https://api.meralion.ai/v1")
MERALION_API_KEY = os.environ.get("MERALION_API_KEY", "")
MERALION_MODEL = os.environ.get("MERALION_MODEL", "MERaLiON/MERaLiON-3-10B")
DEFAULT_TIMEOUT = float(os.environ.get("MERALION_TIMEOUT", "60"))

_client_singleton: Optional[httpx.Client] = None


class MeraLionError(RuntimeError):
    """Base class for MERaLiON HTTP failures surfaced to the caller."""


class MeraLionRateLimitError(MeraLionError):
    """MERaLiON returned 429. Includes the Retry-After hint if provided."""

    def __init__(self, message: str, retry_after: Optional[str] = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class MeraLionAuthError(MeraLionError):
    """API key missing or invalid."""


def _client() -> httpx.Client:
    global _client_singleton
    if _client_singleton is None:
        if not MERALION_API_KEY:
            raise MeraLionAuthError(
                "MERALION_API_KEY is not set. Add it to the backend environment "
                "before calling MERaLiON audio endpoints."
            )
        _client_singleton = httpx.Client(
            base_url=MERALION_BASE_URL,
            timeout=DEFAULT_TIMEOUT,
            headers={"X-API-Key": MERALION_API_KEY},
        )
    return _client_singleton


def _audio_data_uri(audio_b64: str, mime: str) -> str:
    """MERaLiON accepts either a raw base64 string or a data URI. Normalize
    to a data URI so the server always sees the mime hint (avoids WAV vs
    MP3 sniffing failures on truncated headers).
    """
    if audio_b64.startswith("data:"):
        return audio_b64
    return f"data:{mime};base64,{audio_b64}"


def _extract_reply(response_json: dict) -> str:
    """MERaLiON's audio endpoints return the OpenAI ChatCompletionResponse
    envelope: `{choices: [{message: {content: str | [...] }}]}`. Content
    can be a string OR a list of content blocks; support both.
    """
    try:
        message = response_json["choices"][0]["message"]
    except (KeyError, IndexError) as exc:
        raise MeraLionError(f"malformed MERaLiON response: {response_json}") from exc
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and "text" in block:
                parts.append(str(block["text"]))
        return "".join(parts).strip()
    raise MeraLionError(f"unexpected MERaLiON content shape: {content!r}")


def _post(path: str, payload: dict) -> dict:
    try:
        resp = _client().post(path, json=payload)
    except httpx.HTTPError as exc:
        raise MeraLionError(f"MERaLiON network error on {path}: {exc}") from exc

    if resp.status_code == 429:
        raise MeraLionRateLimitError(
            "MERaLiON rate limit exceeded",
            retry_after=resp.headers.get("Retry-After"),
        )
    if resp.status_code == 401 or resp.status_code == 403:
        raise MeraLionAuthError(f"MERaLiON auth failed ({resp.status_code}): {resp.text}")
    if resp.status_code >= 400:
        raise MeraLionError(
            f"MERaLiON {resp.status_code} on {path}: {resp.text[:400]}"
        )
    return resp.json()


def transcribe(audio_b64: str, mime: str = "audio/wav") -> str:
    """POST /audio/transcriptions — same-language speech-to-text."""
    payload = {
        "audio_url": _audio_data_uri(audio_b64, mime),
        "model": MERALION_MODEL,
    }
    return _extract_reply(_post("/audio/transcriptions", payload))


def translate(audio_b64: str, target_language: str, mime: str = "audio/wav") -> str:
    """POST /audio/translations — speech-to-translated-text."""
    payload = {
        "audio_url": _audio_data_uri(audio_b64, mime),
        "model": MERALION_MODEL,
        "translation_params": {"target_language": target_language},
    }
    return _extract_reply(_post("/audio/translations", payload))
