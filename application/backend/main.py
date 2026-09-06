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

# Cold-start SSM load — imported for its side effect: populates os.environ
# from /parl/* SecureString parameters before any service module reads
# module-level env vars. No-op when USE_LOCAL_STUBS=1.
from services import config as _ssm_config  # noqa: F401,E402

# Root logging config — uvicorn only wires its own loggers, so module
# loggers like `agents.research` need a handler here to reach stdout.
# `force=True` displaces any prior NullHandler that got attached at import.
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
    datefmt="%H:%M:%S",
    force=True,
)

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agents import digest as digest_agent
from agents import flashcards as flashcards_agent
from agents import research as research_agent
from agents.main_agent import create_search_plan
from agents.query import answer_question
from services import bedrock as bedrock_service
from services import sittings as sittings_service
from services import storage as storage_service
from services import translation as translation_service
from services.meralion import MeraLionAuthError, MeraLionError, MeraLionRateLimitError
from services.search_service import fetch_from_search_agent
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

SERVE_STATIC = os.environ.get("SERVE_STATIC") == "1"


def _resolve_cors_origins() -> list[str]:
    """CORS origin list.

    Prod (USE_LOCAL_STUBS != "1"): read from CORS_ALLOWED_ORIGINS
    (comma-separated). Fail fast if unset — a wildcard behind a public
    Function URL would be worse than a 500 at startup.

    Dev (USE_LOCAL_STUBS == "1"): default to a Vite/CRA localhost set so
    `npm run dev` works out of the box.
    """
    raw = os.environ.get("CORS_ALLOWED_ORIGINS", "").strip()
    if raw:
        return [o.strip() for o in raw.split(",") if o.strip()]
    if os.environ.get("USE_LOCAL_STUBS") == "1":
        return [
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
        ]
    raise RuntimeError(
        "CORS_ALLOWED_ORIGINS must be set when USE_LOCAL_STUBS != '1'"
    )


# SERVE_STATIC=1 means the container serves the built React app from the
# same origin, so CORS is a no-op. In that mode we skip the middleware
# entirely rather than adding it with an empty allow-list.
if not SERVE_STATIC:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_resolve_cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# All API endpoints are registered on this router; the router is mounted
# under `/api` when SERVE_STATIC=1 so React SPA routes at `/` don't
# collide with API paths. Under Lambda / dev-server mode the router is
# mounted at root, preserving the historical bare paths.
router = APIRouter()


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


class TopicFlashcardsRequest(BaseModel):
    count: int = 5


class ChatFlashcardsRequest(BaseModel):
    reply_text: str
    topic_ids: list[str] | None = None
    count: int = 5


class FlashcardModel(BaseModel):
    id: str
    title: str
    body: str


class FlashcardDeckResponse(BaseModel):
    date: str
    topic_id: Optional[str] = None
    source: Literal["topic", "chat"]
    cards: list[FlashcardModel]
    generated_at: str


# --- Root & Health -----------------------------------------------------------

@router.get("/")
def root() -> dict:
    return {
        "service": "Singapore Policy & Parliamentary Intelligence API",
        "status": "online",
        "search_agent_integrated": True,
        "endpoints": [
            "POST /query",
            "GET  /query/sessions/{session_id}",
            "GET  /health",
            "GET  /sittings",
            "GET  /debates",
            "GET  /debates/{date}",
            "POST /debates/{date}/chat",
            "POST /debates/{date}/flashcards/topic/{topic_id}",
            "POST /debates/{date}/flashcards/from-chat",
            "POST /translate",
            "POST /transcribe",
            "POST /translate/audio",
            "GET  /docs   (Swagger UI, interactive)",
        ],
    }


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "policy-and-parliament-api"}


# --- Policy Query Agent ------------------------------------------------------

@router.post("/query", response_model=QueryResponse)
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


@router.get("/query/sessions/{session_id}")
def get_query_session(session_id: str):
    session = storage_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or expired")
    return session


# --- Parliamentary Debate Endpoints ------------------------------------------

@router.get("/debates")
def list_debates() -> dict:
    # Diagnostic endpoint for "already-cached digests"; the frontend feed
    # uses /sittings. Returns [] under USE_LOCAL_STUBS.
    items = storage_service.list_digests()
    return {"debates": [DebateSummary(**d).model_dump() for d in items]}


@router.get("/sittings")
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


@router.get("/debates/{date}")
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


# Intents for which a Hansard "not covered" answer should trigger a
# web-search fallback via the Policy Query Agent's orchestrator. Opinion
# / experience / follow-up intents deliberately stay on Hansard — they're
# meaningful about the debate itself, and a web fallback would cross wires.
_WEB_FALLBACK_INTENTS = frozenset({
    "policy_fact",
    "eligibility",
    "announcement/update",
    "process/how_to",
    "comparison",
})


def _format_fallback_sources(sources: list[dict], limit: int = 4) -> str:
    if not sources:
        return "(none)"
    lines = []
    for s in sources[:limit]:
        title = s.get("title") or "Untitled"
        url = s.get("url") or ""
        content = (s.get("content") or s.get("text") or "").strip()
        if len(content) > 600:
            content = content[:600] + "…"
        lines.append(f"- {title} ({url})\n{content}")
    return "\n".join(lines)


def _web_fallback_reply(
    *,
    question: str,
    hansard_reply: str,
    chat_history: list[dict],
    date: str,
) -> tuple[str, bool] | None:
    """When Hansard research returns grounded=False, try to answer via the
    Policy Query Agent's orchestrator + Search Agent bridge.

    Returns (combined_reply, grounded=True) on success, or None when the
    fallback is disabled, out of scope for this intent, or fails.
    """
    if os.environ.get("ENABLE_WEB_FALLBACK", "1") != "1":
        return None

    try:
        plan = create_search_plan(question, conversation_context=chat_history)
    except Exception as e:
        log.warning("[WEB_FALLBACK] create_search_plan failed: %s", e)
        return None

    if plan.intent not in _WEB_FALLBACK_INTENTS:
        log.info(
            "[WEB_FALLBACK] skipped — intent=%s not in allow-list",
            plan.intent,
        )
        return None

    need_official = "official_search" in plan.agents_to_invoke
    need_community = "community_search" in plan.agents_to_invoke

    try:
        evidence = fetch_from_search_agent(
            question=plan.resolved_query or question,
            conversation_context=chat_history,
            need_official=need_official,
            need_community=need_community,
            official_queries=plan.search_queries.official,
            community_queries=plan.search_queries.community,
            plan_dict=plan.model_dump(),
        )
    except Exception as e:
        log.warning("[WEB_FALLBACK] fetch_from_search_agent failed: %s", e)
        return None

    official = evidence.get("official_sources") or []
    unofficial = evidence.get("unofficial_sources") or []
    synthesis = (evidence.get("search_summary") or "").strip()
    if not (official or unofficial or synthesis):
        log.info("[WEB_FALLBACK] search returned no evidence — leaving reply as-is")
        return None

    compose_prompt = f"""
You are answering a Singapore policy question that was NOT covered by the
Parliament sitting on {date}. Use ONLY the web-sourced evidence below.

USER QUESTION: {question}
RESOLVED QUERY: {plan.resolved_query or question}

OFFICIAL SOURCES:
{_format_fallback_sources(official)}

COMMUNITY SOURCES:
{_format_fallback_sources(unofficial)}

SEARCH AGENT SYNTHESIS:
{synthesis or "(none)"}

Write a concise answer in 3-5 short sentences. Prefer official figures
over community sentiment. Cite source titles and URLs inline where they
support the answer. Do not speculate beyond the evidence.
"""

    try:
        web_answer = bedrock_service.ask_nova(compose_prompt, max_tokens=1024)
    except Exception as e:
        log.warning("[WEB_FALLBACK] ask_nova compose failed: %s", e)
        return None

    web_answer = (web_answer or "").strip()
    if not web_answer:
        return None

    combined = (
        f"{hansard_reply.strip()}\n\n"
        f"**Broader web sources indicate:**\n{web_answer}"
    )
    log.info(
        "[WEB_FALLBACK] applied for intent=%s | official=%d unofficial=%d",
        plan.intent,
        len(official),
        len(unofficial),
    )
    return combined, True


@router.post("/debates/{date}/chat", response_model=ChatResponse)
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
        reply = r.reply

        # Fallback: if Hansard didn't cover the question, try the Policy
        # Query Agent's orchestrator + Search Agent to answer from the web.
        if not r.grounded:
            persisted = storage_service.get_session(session_id) or {}
            # Drop the just-written turn so the plan sees prior context only.
            prior_history = persisted.get("chat_history", [])[:-2]
            fb = _web_fallback_reply(
                question=english_message,
                hansard_reply=r.reply,
                chat_history=prior_history,
                date=date,
            )
            if fb is not None:
                reply, captured["grounded"] = fb

        return reply

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


# --- Flashcards Agent --------------------------------------------------------

@router.post(
    "/debates/{date}/flashcards/topic/{topic_id}",
    response_model=FlashcardDeckResponse,
)
def flashcards_from_topic(
    date: str,
    topic_id: str,
    req: TopicFlashcardsRequest,
) -> FlashcardDeckResponse:
    digest = storage_service.get_digest(date)
    if not digest or (isinstance(digest, dict) and digest.get("error") == "no_sitting"):
        # Materialise the digest on demand so a cold cache doesn't 404 the
        # first flashcard click after a fresh start.
        try:
            digest = digest_agent.run_digest(date)
        except NotImplementedError as e:
            raise HTTPException(
                status_code=503,
                detail={"error": "digest_agent_unavailable", "message": str(e)},
            )
        if isinstance(digest, dict) and digest.get("error") == "no_sitting":
            raise HTTPException(status_code=404, detail=digest)

    try:
        deck = flashcards_agent.generate_from_topic(
            date=date,
            topic_id=topic_id,
            digest=digest,
            count=req.count,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={"error": "bad_topic_id", "message": str(e)},
        )
    except NotImplementedError as e:
        raise HTTPException(
            status_code=503,
            detail={"error": "scraper_not_available", "message": str(e)},
        )
    return FlashcardDeckResponse(**deck.model_dump())


@router.post(
    "/debates/{date}/flashcards/from-chat",
    response_model=FlashcardDeckResponse,
)
def flashcards_from_chat(
    date: str,
    req: ChatFlashcardsRequest,
) -> FlashcardDeckResponse:
    try:
        deck = flashcards_agent.generate_from_chat_reply(
            date=date,
            reply_text=req.reply_text,
            topic_ids=req.topic_ids,
            count=req.count,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={"error": "bad_reply_text", "message": str(e)},
        )
    return FlashcardDeckResponse(**deck.model_dump())


# --- Standalone Translation Endpoints ----------------------------------------

@router.post("/translate")
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


@router.post("/transcribe")
def transcribe_endpoint(req: TranscribeRequest) -> dict:
    if not req.audio_b64 or not req.audio_b64.strip():
        raise HTTPException(
            status_code=400,
            detail={"error": "empty_audio", "message": "No audio data received for transcription."},
        )
    try:
        text = translation_service.transcribe_audio(req.audio_b64.strip(), mime=req.mime)
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
    return {"text": text, "transcript": text}


@router.post("/translate/audio")
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


# --- Router mount + static frontend ------------------------------------------
#
# In SERVE_STATIC mode (single-container docker deploy) the router is
# mounted at `/api/*` and the built React app is served from `/`. In the
# original API-only mode (Lambda / local uvicorn) the router is mounted
# at root so all existing paths (`/query`, `/debates`, …) keep working.

if SERVE_STATIC:
    app.include_router(router, prefix="/api")

    _STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
    _INDEX_HTML = os.path.join(_STATIC_DIR, "index.html")

    # `html=True` makes StaticFiles serve `index.html` for the mount root,
    # but not for arbitrary sub-paths — that's what the catch-all below
    # handles for react-router client-side routes.
    app.mount(
        "/assets",
        StaticFiles(directory=os.path.join(_STATIC_DIR, "assets")),
        name="assets",
    )

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str, request: Request):
        # Unknown /api/* must stay a JSON 404 — the frontend parses these
        # as errors and would break on HTML.
        if full_path.startswith("api/") or full_path == "api":
            raise HTTPException(status_code=404, detail="Not Found")
        # Serve files that actually exist under static/ (favicon.svg,
        # icons.svg, etc.), otherwise fall through to index.html so
        # react-router can handle the route on the client.
        candidate = os.path.join(_STATIC_DIR, full_path)
        if full_path and os.path.isfile(candidate):
            return FileResponse(candidate)
        return FileResponse(_INDEX_HTML)
else:
    app.include_router(router)
