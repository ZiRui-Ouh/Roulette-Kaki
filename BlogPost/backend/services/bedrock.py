"""Bedrock Nova wrapper.

All Bedrock calls in this codebase MUST go through this module. It:

- Instantiates the sole `bedrock-runtime` client.
- Enforces the session-scope caps (5 topics OR 50K accumulated document
  tokens per session, whichever hits first — drop-oldest above that).
- Attaches a `cachePoint` block after documents so Bedrock prompt caching
  applies to the (usually stable) document body across turns.
- Returns Bedrock's own token-usage numbers so callers can log cost.

Do NOT create a `boto3.client('bedrock-runtime', ...)` anywhere else.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Literal

import boto3
from botocore.config import Config

# REGION = os.environ.get("AWS_REGION", "ap-southeast-1")
REGION = "us-east-1"

MODEL_NOVA_LITE = "amazon.nova-lite-v1:0"
MODEL_NOVA_PRO = "amazon.nova-pro-v1:0"

MAX_TOPICS_PER_SESSION = 5
MAX_DOC_TOKENS_PER_SESSION = 50_000

# Pre-call sizing heuristic. Nova returns exact token counts in its
# response; this is only used to decide what to drop before we call.
APPROX_TOKENS_PER_BYTE = 0.25

DocFormat = Literal["pdf", "html", "txt", "md", "docx"]

log = logging.getLogger(__name__)

_client_singleton = None


def _client():
    global _client_singleton
    if _client_singleton is None:
        _client_singleton = boto3.client(
            "bedrock-runtime",
            region_name=REGION,
            config=Config(retries={"max_attempts": 3, "mode": "standard"}),
        )
    return _client_singleton


@dataclass
class Document:
    topic_id: str
    name: str
    format: DocFormat
    bytes_: bytes


def _cap_documents(docs: list[Document]) -> list[Document]:
    kept = list(docs)
    while len(kept) > MAX_TOPICS_PER_SESSION:
        dropped = kept.pop(0)
        log.warning("dropping topic %s (over 5-topic cap)", dropped.topic_id)
    total = sum(int(len(d.bytes_) * APPROX_TOKENS_PER_BYTE) for d in kept)
    while total > MAX_DOC_TOKENS_PER_SESSION and kept:
        dropped = kept.pop(0)
        total -= int(len(dropped.bytes_) * APPROX_TOKENS_PER_BYTE)
        log.warning("dropping topic %s (over 50K-token cap)", dropped.topic_id)
    return kept


def _document_blocks(docs: list[Document]) -> list[dict]:
    return [
        {
            "document": {
                "name": d.name,
                "format": d.format,
                "source": {"bytes": d.bytes_},
            }
        }
        for d in docs
    ]


def summarize(prompt: str, *, max_tokens: int = 2048) -> tuple[str, dict]:
    """Single-shot Nova Lite call. Returns (text, usage_dict)."""
    resp = _client().converse(
        modelId=MODEL_NOVA_LITE,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"maxTokens": max_tokens, "temperature": 0.2, "topP": 0.9},
    )
    text = resp["output"]["message"]["content"][0]["text"]
    return text, resp.get("usage", {})


def chat_with_documents(
    system: str,
    history: list[dict],
    user_message: str,
    docs: list[Document],
    *,
    model_id: str = MODEL_NOVA_PRO,
    max_tokens: int = 1024,
) -> tuple[str, list[str], dict]:
    """Chat turn with attached documents.

    The 5-topic / 50K-token caps are enforced here — callers cannot bypass
    them. Documents are followed by a `cachePoint` block so Bedrock caches
    them across turns in the same session.

    Returns (reply_text, kept_topic_ids, usage_dict).
    """
    capped = _cap_documents(docs)

    current_user_content: list[dict] = _document_blocks(capped)
    if capped:
        # Cache the (large, stable) document tail; the user message text
        # sits after the cachePoint and is billed fresh on every turn.
        current_user_content.append({"cachePoint": {"type": "default"}})
    current_user_content.append({"text": user_message})

    messages = [*history, {"role": "user", "content": current_user_content}]

    resp = _client().converse(
        modelId=model_id,
        system=[{"text": system}],
        messages=messages,
        inferenceConfig={
            "maxTokens": max_tokens,
            "temperature": 0.3,
            "topP": 0.9,
        },
    )
    text = resp["output"]["message"]["content"][0]["text"]
    return text, [d.topic_id for d in capped], resp.get("usage", {})
