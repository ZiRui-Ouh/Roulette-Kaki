"""FastAPI app for the Parliament Debate Digest.

Phase 2 scaffolding: all three endpoints return stub data. No AWS calls
are made from these handlers yet — the digest/research agents raise
NotImplementedError, which the handlers catch and turn into stub
responses so the frontend can start integrating.

Later phases will wire the agents in.
"""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agents import digest as digest_agent
from agents import research as research_agent

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
        "phase": 2,
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
    return {"status": "ok", "phase": 2}


@app.get("/debates")
def list_debates() -> dict:
    # Phase 3+ will read from DynamoDB DebateDigests. Stub for now.
    stub = [
        DebateSummary(
            date="2026-08-05",
            title="Sitting of 05 August 2026 (stub)",
            youtube_url="https://www.youtube.com/watch?v=example",
        ),
    ]
    return {"debates": [d.model_dump() for d in stub], "phase": 2}


@app.get("/debates/{date}")
def get_debate(date: str) -> dict:
    try:
        return digest_agent.run_digest(date)
    except NotImplementedError:
        return {
            "date": date,
            "title": f"Sitting of {date} (stub)",
            "youtube_url": "https://www.youtube.com/watch?v=example",
            "summary": "Stub digest — Phase 3 will populate.",
            "topic_count": 0,
            "category_breakdown": {},
            "interesting_topics": [],
            "topics": [],
            "phase": 2,
        }


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
        return ChatResponse(
            session_id=session_id,
            reply=result.reply,
            topics_used=result.topics_used,
            grounded=result.grounded,
        )
    except NotImplementedError:
        return ChatResponse(
            session_id=session_id,
            reply=(
                f"[stub, phase 2] echoing message for {date}: {req.message!r} "
                "— Phase 4 wires the research agent."
            ),
            topics_used=[req.topic_id] if req.topic_id else [],
            grounded=False,
        )
