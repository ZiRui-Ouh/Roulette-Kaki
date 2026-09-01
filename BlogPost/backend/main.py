"""FastAPI app for the Parliament Debate Digest.

Phase 3: `/debates/{date}` is wired to the real digest agent — cache
check, fixture-backed topic scrape, Nova Lite summarization, DDB write.
`/debates/{date}/chat` still returns a stub reply; Phase 4 wires the
research agent.

The `NotImplementedError` catches are kept as defensive fallbacks so a
partial regression during later phases doesn't 500 the demo.
"""

from __future__ import annotations

import logging
import uuid
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agents import digest as digest_agent
from agents import research as research_agent
from services import sittings, storage

log = logging.getLogger(__name__)

app = FastAPI(title="Parliament Debate Digest", version="0.2.0")

# CORS wide-open for local dev; tighten before deploy.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Models ------------------------------------------------------------------

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


# --- Endpoints ---------------------------------------------------------------

@app.get("/")
def root() -> dict:
    return {
        "name": "Parliament Debate Digest API",
        "phase": 3,
        "endpoints": [
            "GET  /health",
            "GET  /debates",
            "GET  /debates/{date}",
            "POST /debates/{date}/chat",
            "GET  /docs   (Swagger UI, interactive)",
        ],
    }


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "phase": 3}


@app.get("/debates")
def list_debates() -> dict:
    # Real DDB scan (Phase 5). Returns [] under USE_LOCAL_STUBS.
    # Kept as a diagnostic endpoint for "already-cached digests"; the
    # frontend feed uses /sittings (Phase 5.1) instead.
    items = storage.list_digests()
    return {"debates": [DebateSummary(**d).model_dump() for d in items]}


@app.get("/sittings")
def get_sittings(limit: int = 5, offset: int = 0) -> dict:
    if limit < 1 or limit > 25 or offset < 0 or offset > 100:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "bad_pagination",
                "message": "limit must be 1..25, offset must be 0..100",
            },
        )
    try:
        return sittings.list_sittings(limit=limit, offset=offset)
    except sittings.SittingsUnavailableError as e:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "sittings_unavailable",
                "message": str(e),
            },
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
            "phase": 3,
        }
    if result.get("error") == "no_sitting":
        raise HTTPException(status_code=404, detail=result)
    return result


@app.post("/debates/{date}/chat", response_model=ChatResponse)
def chat(date: str, req: ChatRequest) -> ChatResponse:
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
        # Reached scraper.fetch_report in a mode that doesn't have report
        # bytes (SCRAPER_MODE=fixture). Tell the caller how to fix it.
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
