"""FastAPI app for the Singapore Policy & Legislative Intelligence API.

Merges the Policy Query Agent (`POST /query`) with the Parliament Debate
Digest (`/debates`, `/sittings`, `/debates/{date}`, `/debates/{date}/chat`)
under a single FastAPI app. Both feature sets share `services/bedrock.py`,
`services/storage.py`, and the SPRS scraper stack.

Error-handling philosophy: agents raise typed exceptions (`ValueError`,
`NotImplementedError`, `SittingsUnavailableError`); this module maps each
to a narrow HTTP response. No broad `except Exception` fallbacks — the
API never silently synthesizes fake data on failure.
"""

from __future__ import annotations

import logging
import os
import uuid
from typing import Literal, Optional

# Set the default environment BEFORE importing services so `storage.py` and
# friends read the intended values at import time. Clear these for real-AWS /
# real-scraper mode.
os.environ.setdefault("USE_LOCAL_STUBS", "1")
os.environ.setdefault("SCRAPER_MODE", "fixture")
os.environ.setdefault("YOUTUBE_PLAYLIST", "PLetiU3qG4uSrSjL6UlfVsgR89lxBzP5D1")

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agents import digest as digest_agent
from agents import research as research_agent
from agents.query import answer_question
from services import sittings as sittings_service
from services import storage as storage_service
from services import translation as translation_service
from services.meralion import MeraLionAuthError, MeraLionError, MeraLionRateLimitError
from services.translation import TranslationError
from services.translation_wrapper import is_fast_path, with_translation

Lang = Literal["English", "Chinese", "Malay", "Tamil", "Singlish"]

log = logging.getLogger(__name__)

app = FastAPI(
    title="Singapore Policy & Legislative Intelligence API",
    description=(
        "Unified API for the Policy Query Agent (with Search Agent "
        "intelligence) and the Parliamentary Debate Hansard Digest."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://localhost:4173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5175",
        "http://127.0.0.1:4173",
        "http://127.0.0.1:3000",
        "*",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Models ------------------------------------------------------------------

class QueryRequest(BaseModel):
    question: str
    urls: list[str] | None = None
    session_id: Optional[str] = None
    language: Lang = "English"


class QueryResponse(BaseModel):
    answer: str
    session_id: str
    language: Lang = "English"


class DebateSummary(BaseModel):
    date: str
    title: str
    youtube_url: str


class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str
    topic_id: Optional[str] = None
    language: Lang = "English"


class TranslateRequest(BaseModel):
    text: str
    target_language: Lang
    source_language: Lang = "English"


class TranscribeRequest(BaseModel):
    audio_b64: str
    mime: str = "audio/wav"


class TranslateAudioRequest(BaseModel):
    audio_b64: str
    target_language: Lang
    mime: str = "audio/wav"


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    topics_used: list[str]
    grounded: bool


# --- Root & Health -----------------------------------------------------------

@app.get("/")
def root() -> dict:
    return {
        "service": "Singapore Policy & Parliamentary Intelligence API",
        "status": "online",
        "endpoints": [
            "POST /query",
            "GET  /query/sessions/{session_id}",
            "GET  /health",
            "GET  /sittings",
            "GET  /debates",
            "GET  /debates/{date}",
            "POST /debates/{date}/chat",
            "POST /translate",
            "POST /transcribe",
            "POST /translate/audio",
            "GET  /docs   (Swagger UI, interactive)",
        ],
    }


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "policy-and-parliament-api"}


# --- Policy Query Agent ------------------------------------------------------

@app.post("/query", response_model=QueryResponse)
def query(q: QueryRequest) -> dict:
    if not q.question or not q.question.strip():
        raise HTTPException(
            status_code=400,
            detail={"error": "empty_question", "message": "question must be non-empty"},
        )

    # Capture session_id from inside the translation sandwich so it makes
    # it back to the client even on the non-English (wrapped) path.
    captured = {"session_id": q.session_id or ""}

    def _run(english_question: str) -> str:
        answer, sid = answer_question(
            question=english_question,
            urls=q.urls,
            session_id=q.session_id,
            return_session=True,
        )
        captured["session_id"] = sid
        return answer

    try:
        answer = with_translation(q.language, q.question, _run)
    except TranslationError as e:
        raise HTTPException(
            status_code=502,
            detail={"error": "translation_failed", "message": str(e)},
        )
    return {
        "answer": answer,
        "session_id": captured["session_id"],
        "language": q.language,
    }


@app.get("/query/sessions/{session_id}")
def get_query_session(session_id: str):
    session = storage_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or expired")
    return session


# --- Parliamentary Debate Endpoints ------------------------------------------

@app.get("/debates")
def list_debates() -> dict:
    # Diagnostic endpoint for "already-cached digests"; the frontend feed
    # uses /sittings. Returns [] under USE_LOCAL_STUBS.
    items = storage_service.list_digests()
    return {"debates": [DebateSummary(**d).model_dump() for d in items]}


@app.get("/sittings")
def get_sittings(limit: int = 6, offset: int = 0) -> dict:
    if limit < 1 or limit > 25 or offset < 0 or offset > 100:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "bad_pagination",
                "message": "limit must be 1..25, offset must be 0..100",
            },
        )
    try:
        return sittings_service.list_sittings(limit=limit, offset=offset)
    except sittings_service.SittingsUnavailableError as e:
        raise HTTPException(
            status_code=503,
            detail={"error": "sittings_unavailable", "message": str(e)},
        )


@app.get("/debates/{date}")
def get_debate(date: str, refresh: bool = False, language: Lang = "English") -> dict:
    try:
        result = digest_agent.run_digest(date, refresh=refresh)
    except NotImplementedError:
        # Defensive fallback so a partial regression can't 500 the demo.
        log.warning("digest agent NotImplementedError for %s — returning stub", date)
        return {
            "date": date,
            "title": f"Sitting of {date} (stub)",
            "youtube_url": "",
            "summary": "Stub digest — digest agent is not yet implemented.",
            "topic_count": 0,
            "category_breakdown": {},
            "interesting_topics": [],
            "topics": [],
        }
    if isinstance(result, dict) and result.get("error") == "no_sitting":
        raise HTTPException(status_code=404, detail=result)
    if not is_fast_path(language) and isinstance(result, dict):
        try:
            result = _translate_digest(result, language)
        except TranslationError as e:
            raise HTTPException(
                status_code=502,
                detail={"error": "translation_failed", "message": str(e)},
            )
    return result


def _translate_digest(digest: dict, language: Lang) -> dict:
    """Translate user-facing prose fields of a digest to `language`.

    Only `summary` and each `interesting_topics[].reason` are translated.
    Topic titles and `topics[]` metadata stay English — they're used
    as citation anchors by the Hansard chat agent downstream and
    translating them would break that flow.
    """
    translated = dict(digest)
    if digest.get("summary"):
        translated["summary"] = translation_service.translate_from_english(
            digest["summary"], language
        )
    interesting = digest.get("interesting_topics") or []
    if interesting:
        translated_interesting = []
        for entry in interesting:
            if not isinstance(entry, dict):
                translated_interesting.append(entry)
                continue
            reason = entry.get("reason")
            if reason:
                translated_interesting.append(
                    {
                        **entry,
                        "reason": translation_service.translate_from_english(
                            reason, language
                        ),
                    }
                )
            else:
                translated_interesting.append(entry)
        translated["interesting_topics"] = translated_interesting
    translated["language"] = language
    return translated


@app.post("/debates/{date}/chat", response_model=ChatResponse)
def chat_debate(date: str, req: ChatRequest) -> ChatResponse:
    session_id = req.session_id or str(uuid.uuid4())
    # Result is populated inside the translation sandwich so that
    # topics_used / grounded are captured from the ONE agent call whose
    # answer becomes the (possibly translated) reply.
    captured: dict = {"topics_used": [], "grounded": False}

    def _run(english_message: str) -> str:
        try:
            r = research_agent.run_chat(
                session_id=session_id,
                date=date,
                message=english_message,
                topic_id=req.topic_id,
            )
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail={"error": "no_digest_for_date", "message": str(e)},
            )
        except NotImplementedError as e:
            raise HTTPException(
                status_code=503,
                detail={"error": "scraper_not_available", "message": str(e)},
            )
        captured["topics_used"] = r.topics_used
        captured["grounded"] = r.grounded
        return r.reply

    try:
        reply = with_translation(req.language, req.message, _run)
    except TranslationError as e:
        raise HTTPException(
            status_code=502,
            detail={"error": "translation_failed", "message": str(e)},
        )
    return ChatResponse(
        session_id=session_id,
        reply=reply,
        topics_used=captured["topics_used"],
        grounded=captured["grounded"],
    )


# --- Standalone Translation Endpoints ----------------------------------------

@app.post("/translate")
def translate_text(req: TranslateRequest) -> dict:
    if not req.text or not req.text.strip():
        raise HTTPException(
            status_code=400,
            detail={"error": "empty_text", "message": "text must be non-empty"},
        )
    try:
        if req.source_language == "English":
            out = translation_service.translate_from_english(
                req.text, req.target_language
            )
        elif req.target_language == "English":
            out = translation_service.translate_to_english(
                req.text, req.source_language
            ).english
        else:
            # Two-hop A → English → B keeps the abstraction on Nova and
            # avoids maintaining N² prompt variants.
            english = translation_service.translate_to_english(
                req.text, req.source_language
            ).english
            out = translation_service.translate_from_english(
                english, req.target_language
            )
    except TranslationError as e:
        raise HTTPException(
            status_code=502,
            detail={"error": "translation_failed", "message": str(e)},
        )
    return {"translated_text": out, "target_language": req.target_language}


@app.post("/transcribe")
def transcribe_endpoint(req: TranscribeRequest) -> dict:
    try:
        text = translation_service.transcribe_audio(req.audio_b64, mime=req.mime)
    except MeraLionRateLimitError as e:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "meralion_rate_limit",
                "message": str(e),
                "retry_after": e.retry_after,
            },
        )
    except MeraLionAuthError as e:
        raise HTTPException(
            status_code=502,
            detail={"error": "meralion_auth_error", "message": str(e)},
        )
    except MeraLionError as e:
        raise HTTPException(
            status_code=502,
            detail={"error": "meralion_error", "message": str(e)},
        )
    return {"transcript": text}


@app.post("/translate/audio")
def translate_audio_endpoint(req: TranslateAudioRequest) -> dict:
    try:
        text = translation_service.translate_audio(
            req.audio_b64,
            target_language=req.target_language,
            mime=req.mime,
        )
    except TranslationError as e:
        raise HTTPException(
            status_code=400,
            detail={"error": "translation_error", "message": str(e)},
        )
    except MeraLionRateLimitError as e:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "meralion_rate_limit",
                "message": str(e),
                "retry_after": e.retry_after,
            },
        )
    except MeraLionAuthError as e:
        raise HTTPException(
            status_code=502,
            detail={"error": "meralion_auth_error", "message": str(e)},
        )
    except MeraLionError as e:
        raise HTTPException(
            status_code=502,
            detail={"error": "meralion_error", "message": str(e)},
        )
    return {"translated_text": text, "target_language": req.target_language}
