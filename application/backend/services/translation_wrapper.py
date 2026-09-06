"""Translation sandwich for feature routes.

Any route whose shape is "user text in → English string out" can wrap
itself with `with_translation(language, source_text, run)` to gain
multilingual support without knowing anything about the translation
backend.

Fast path: language == "English" (or empty) — `run(source_text)` is
called directly, no extra model calls. This means every existing feature
keeps its current behaviour byte-for-byte when the user hasn't switched
languages.

Slow path (non-English):
  1. Translate source_text → English + a key-points summary (Nova).
  2. Prepend the key-points as bracketed context so the downstream agent
     sees the user's real intent even when the English rendering loses
     nuance.
  3. Call the feature `run` with the augmented English input.
  4. Translate the English answer back to the user's language (Nova).
"""

from __future__ import annotations

import logging
from typing import Callable

from services import translation

log = logging.getLogger(__name__)


def is_fast_path(language: str | None) -> bool:
    return not language or language == "English"


def with_translation(
    language: str | None,
    source_text: str,
    run: Callable[[str], str],
) -> str:
    # English takes the fast path. Other languages go to English for the agent
    # and the completed answer is translated back before it reaches the UI.
    """Wrap a feature call with input+output translation when the user's
    language is non-English. Returns the (translated) final string.

    `run` must accept English text and return English text. All Nova
    plumbing is hidden inside `services.translation`.
    """
    if is_fast_path(language):
        return run(source_text)

    assert language is not None  # for type checkers; is_fast_path ruled out None
    translated_in = translation.translate_to_english(source_text, language)

    if translated_in.key_points:
        prompt_input = (
            f"{translated_in.english}\n\n"
            f"[Context inferred from the original {language} question: "
            f"{translated_in.key_points}]"
        )
    else:
        prompt_input = translated_in.english

    english_answer = run(prompt_input)

    if not english_answer or not english_answer.strip():
        return english_answer

    return translation.translate_from_english(english_answer, language)
