"""Research agent — stub.

One call per chat message. Loads the session's `topics_loaded` documents
from S3 and passes them to Nova Pro via Converse `document` content
blocks. No embeddings, no retrieval — see ARCHITECTURE.md.

Real implementation lands in Phase 4.
"""

from __future__ import annotations

from dataclasses import dataclass

from services import bedrock, storage


SYSTEM_PROMPT = """You are a research assistant for Singapore Parliament debates.
You will answer questions using ONLY the attached debate report documents.

Rules:
- If the answer is present in the documents, cite the topic title and
  speaker where relevant.
- If the answer is NOT in the documents, output exactly the marker
  <grounded>false</grounded> at the end of your reply, then say the report
  does not cover it.
- Do not answer from general knowledge. Do not speculate.
"""


@dataclass
class ChatResult:
    reply: str
    topics_used: list[str]
    grounded: bool
    usage: dict


def _parse_grounded(reply: str) -> bool:
    return "<grounded>false</grounded>" not in reply


def run_chat(
    session_id: str,  # noqa: ARG001
    date: str,  # noqa: ARG001
    message: str,  # noqa: ARG001
    topic_id: str | None = None,  # noqa: ARG001
) -> ChatResult:
    """Handle one chat turn. Phase 4 will implement.

    Flow (from AGENTS.md):
    1. Load session from `storage.get_session`, create if missing.
    2. If `topic_id` provided and not in `topics_loaded`, append it.
    3. For each topic_id in topics_loaded, fetch bytes from S3
       (`storage.get_report`); miss → scrape via `services.scraper` and
       cache before retrying.
    4. Call `bedrock.chat_with_documents(SYSTEM_PROMPT, history, message, docs)`.
    5. Parse `<grounded>false</grounded>` marker.
    6. Append to `chat_history`, write back via `storage.put_session`
       (refreshes TTL).
    """
    raise NotImplementedError("Phase 4 — see AGENTS.md research agent")
