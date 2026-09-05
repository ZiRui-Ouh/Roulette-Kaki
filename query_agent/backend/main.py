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
from typing import Optional

<<<<<<< Updated upstream
=======
# Ensure default environment configurations before service initialization
os.environ.setdefault("USE_LOCAL_STUBS", "1")
os.environ.setdefault("SCRAPER_MODE", "fixture")
os.environ.setdefault("YOUTUBE_PLAYLIST", "PLetiU3qG4uSrSjL6UlfVsgR89lxBzP5D1")

>>>>>>> Stashed changes
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agents import digest as digest_agent
from agents import research as research_agent
from agents.query import answer_question
from services import sittings as sittings_service
from services import storage as storage_service

<<<<<<< Updated upstream
# Default environment for local demo. Clear these for real-AWS / real-scraper mode.
os.environ.setdefault("USE_LOCAL_STUBS", "1")
os.environ.setdefault("SCRAPER_MODE", "fixture")
os.environ.setdefault("YOUTUBE_PLAYLIST", "PLetiU3qG4uSrSjL6UlfVsgR89lxBzP5D1")

=======
>>>>>>> Stashed changes
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


class QueryResponse(BaseModel):
    answer: str
    session_id: str


class DebateSummary(BaseModel):
    date: str
    title: str
    youtube_url: str


class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str
    topic_id: Optional[str] = None


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
<<<<<<< Updated upstream
            "GET  /health",
=======
            "GET  /query/sessions/{session_id}",
>>>>>>> Stashed changes
            "GET  /sittings",
            "GET  /debates",
            "GET  /debates/{date}",
            "POST /debates/{date}/chat",
            "GET  /docs   (Swagger UI, interactive)",
        ],
    }


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "policy-and-parliament-api"}


# --- Policy Query Agent ------------------------------------------------------

<<<<<<< Updated upstream
@app.post("/query")
def query(q: QueryRequest) -> dict:
    if not q.question or not q.question.strip():
        raise HTTPException(
            status_code=400,
            detail={"error": "empty_question", "message": "question must be non-empty"},
        )
    answer = answer_question(question=q.question, urls=q.urls)
    return {"answer": answer}
=======
@app.post("/query", response_model=QueryResponse)
def query(q: QueryRequest):
    answer, session_id = answer_question(
        question=q.question,
        urls=q.urls,
        session_id=q.session_id,
        return_session=True,
    )
    return {"answer": answer, "session_id": session_id}


@app.get("/query/sessions/{session_id}")
def get_query_session(session_id: str):
    session = storage_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or expired")
    return session
>>>>>>> Stashed changes


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
def get_debate(date: str, refresh: bool = False) -> dict:
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
    return result


@app.post("/debates/{date}/chat", response_model=ChatResponse)
def chat_debate(date: str, req: ChatRequest) -> ChatResponse:
    session_id = req.session_id or str(uuid.uuid4())
    try:
        result = research_agent.run_chat(
            session_id=session_id,
            date=date,
            message=req.message,
            topic_id=req.topic_id,
        )
    except ValueError as e:
        # e.g. no digest for date — caller must GET /debates/{date} first.
        raise HTTPException(
            status_code=400,
            detail={"error": "no_digest_for_date", "message": str(e)},
        )
    except NotImplementedError as e:
        # Reached scraper.fetch_report in a mode without report bytes
        # (SCRAPER_MODE=fixture). Tell the caller how to fix it.
        raise HTTPException(
            status_code=503,
            detail={"error": "scraper_not_available", "message": str(e)},
        )
    return ChatResponse(
        session_id=session_id,
        reply=result.reply,
        topics_used=result.topics_used,
        grounded=result.grounded,
    )
