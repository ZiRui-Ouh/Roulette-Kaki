"""Translation abstraction.

The single entry point any feature in this backend uses to translate
text or audio. Text translation runs on Amazon Nova via services.bedrock
(Nova is the default inference model for this project). Audio input
paths delegate to services.meralion.

Supported language names (used verbatim in prompts and passed to
MERaLiON's `translation_params.target_language`):

    "English", "Chinese", "Malay", "Tamil", "Singlish"

"English" is the fast path — callers should special-case it and skip
the round-trip entirely (see services.translation_wrapper).
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

from services import bedrock, meralion

log = logging.getLogger(__name__)

SUPPORTED_LANGUAGES = ("English", "Chinese", "Malay", "Tamil", "Singlish")


class TranslationError(RuntimeError):
    """Raised when the translation model returns unusable output."""


@dataclass
class TranslatedInput:
    """Result of a to-English translation, with a key-points summary
    that downstream agents can use as extra context so nuance from the
    original language isn't lost.
    """

    english: str
    key_points: str


_TO_ENGLISH_SYSTEM = (
    "You are an expert translator for Singapore government policy questions. "
    "Translate the user's text into natural, faithful English. Also produce a "
    "concise key-points summary that captures what the user is really asking "
    "about — including any implied intent, entities, or eligibility category "
    "that would help a policy assistant answer correctly.\n\n"
    "Output ONLY a single JSON object with two string fields: `english` and "
    "`key_points`. No prose, no code fences, no explanations."
)

_FROM_ENGLISH_SYSTEM = (
    "You are an expert translator. Translate the user's text from English "
    "into {target}. Preserve the meaning, register, and any Markdown "
    "structure (headings, bullets, links, bold, code spans) exactly. "
    "CRITICAL: Output ONLY the final translated string. Do not include "
    "quotes, introductory text, conversational filler, or explanations."
)


_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json_object(text: str) -> dict:
    """Nova occasionally wraps JSON in prose or a code fence. Pull out
    the first `{...}` block and json.loads it. Raise TranslationError on
    anything unparseable so the route layer can map to a typed HTTP error.
    """
    match = _JSON_BLOCK_RE.search(text)
    if not match:
        raise TranslationError(f"no JSON object in model output: {text[:200]}")
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise TranslationError(f"invalid JSON from translator: {exc}") from exc


def translate_to_english(text: str, source_language: str) -> TranslatedInput:
    """Language-A text → English text + key-points summary. One Nova call."""
    if not text or not text.strip():
        raise TranslationError("cannot translate empty text")
    if source_language == "English":
        # Callers should short-circuit before hitting this; still safe.
        return TranslatedInput(english=text.strip(), key_points="")

    prompt = (
        f"{_TO_ENGLISH_SYSTEM}\n\n"
        f"Source language: {source_language}\n"
        f"Source text:\n{text}"
    )
    try:
        raw = bedrock.ask_nova(prompt, max_tokens=1024).strip()
        obj = _extract_json_object(raw)
        english = str(obj.get("english", "")).strip()
        key_points = str(obj.get("key_points", "")).strip()
        if not english:
            return TranslatedInput(english=text.strip(), key_points="")
        return TranslatedInput(english=english, key_points=key_points)
    except Exception as exc:
        log.warning("translate_to_english fallback due to error: %s", exc)
        return TranslatedInput(english=text.strip(), key_points="")


def translate_from_english(text: str, target_language: str) -> str:
    """English text → language-A text. One Nova call. Preserves markdown."""
    if not text or not text.strip():
        return ""
    if target_language == "English":
        return text
    if target_language not in SUPPORTED_LANGUAGES:
        return text

    system = _FROM_ENGLISH_SYSTEM.format(target=target_language)
    prompt = f"{system}\n\nEnglish text to translate:\n{text}"
    try:
        translated = bedrock.ask_nova(prompt, max_tokens=2048).strip()
        return translated if translated else text
    except Exception as exc:
        log.warning("translate_from_english fallback due to error: %s", exc)
        return text


# --- Audio (MERaLiON) --------------------------------------------------------

def transcribe_audio(audio_b64: str, mime: str = "audio/wav") -> str:
    """Same-language ASR via MERaLiON (Singlish/accent-aware)."""
    return meralion.transcribe(audio_b64, mime=mime)


def translate_audio(
    audio_b64: str,
    target_language: str,
    mime: str = "audio/wav",
) -> str:
    """Speech → target-language text via MERaLiON."""
    if target_language not in SUPPORTED_LANGUAGES:
        raise TranslationError(f"unsupported target_language: {target_language!r}")
    return meralion.translate(audio_b64, target_language=target_language, mime=mime)
