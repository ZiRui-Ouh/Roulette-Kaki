"""DynamoDB + S3 access.

Tables:
- DebateDigests  (PK: date)  — no TTL, sittings don't change.
- ChatSessions   (PK: session_id) — TTL enabled; refreshed on each message.

Bucket:
- parl-debate-cache — raw report bytes at `{date}/{topic_id}.{ext}`.

Clients are lazily initialized on first use; nothing hits AWS at import
time.

`USE_LOCAL_STUBS=1` short-circuits every operation so local dev works
without AWS credentials — reads return None/empty, writes log and no-op.
Leave unset in production / against real infra.
"""

from __future__ import annotations

import logging
import os
import time

import boto3
from botocore.exceptions import ClientError

REGION = os.environ.get("AWS_REGION", "us-east-1")
DIGESTS_TABLE = os.environ.get("DIGESTS_TABLE", "DebateDigests")
SESSIONS_TABLE = os.environ.get("SESSIONS_TABLE", "ChatSessions")
CACHE_BUCKET = os.environ.get("CACHE_BUCKET", "parl-debate-cache-v2")

SESSION_TTL_SECONDS = 3600  # 1 hour, refreshed on every message.

STUB_MODE = os.environ.get("USE_LOCAL_STUBS") == "1"

log = logging.getLogger(__name__)

# Agents use this module instead of calling AWS directly. DynamoDB stores
# digests and sessions; S3 stores reusable raw Hansard reports.
_ddb_singleton = None
_s3_singleton = None


def _ddb():
    global _ddb_singleton
    if _ddb_singleton is None:
        _ddb_singleton = boto3.resource("dynamodb", region_name=REGION)
    return _ddb_singleton


def _s3():
    global _s3_singleton
    if _s3_singleton is None:
        _s3_singleton = boto3.client("s3", region_name=REGION)
    return _s3_singleton


# In-memory stores for STUB_MODE
_stub_digests: dict[str, dict] = {}
_stub_sessions: dict[str, dict] = {}
_stub_reports: dict[str, bytes] = {}


# --- Digest cache ------------------------------------------------------------

def get_digest(date: str) -> dict | None:
    if STUB_MODE:
        return _stub_digests.get(date)
    resp = _ddb().Table(DIGESTS_TABLE).get_item(Key={"date": date})
    return resp.get("Item")


def put_digest(digest: dict) -> None:
    if STUB_MODE:
        date = digest.get("date")
        if date:
            _stub_digests[date] = digest
        return
    _ddb().Table(DIGESTS_TABLE).put_item(Item=digest)


def list_digests(limit: int = 50) -> list[dict]:
    """List cached digests, most recent first. Compact projection —
    only returns `date`, `title`, `youtube_url` — for the blog feed page.

    `date` is a DDB reserved word so we alias it via ExpressionAttributeNames.
    """
    if STUB_MODE:
        items = [
            {"date": d.get("date"), "title": d.get("title"), "youtube_url": d.get("youtube_url")}
            for d in _stub_digests.values()
        ]
        items.sort(key=lambda x: x.get("date", ""), reverse=True)
        return items[:limit]
    resp = _ddb().Table(DIGESTS_TABLE).scan(
        ProjectionExpression="#d, title, youtube_url",
        ExpressionAttributeNames={"#d": "date"},
        Limit=limit,
    )
    items = resp.get("Items", [])
    items.sort(key=lambda x: x.get("date", ""), reverse=True)
    return items


# --- Session state -----------------------------------------------------------

def is_stub_mode() -> bool:
    return os.environ.get("USE_LOCAL_STUBS") == "1"


def get_session(session_id: str) -> dict | None:
    if is_stub_mode() or STUB_MODE:
        return _stub_sessions.get(session_id)
    resp = _ddb().Table(SESSIONS_TABLE).get_item(Key={"session_id": session_id})
    return resp.get("Item")


def put_session(session: dict) -> None:
    """Write a session row, always refreshing TTL. Callers must not skip
    this — TTL is set here so it cannot be forgotten upstream.
    """
    session = {**session, "ttl": int(time.time()) + SESSION_TTL_SECONDS}
    session_id = session.get("session_id")

    if is_stub_mode() or STUB_MODE:
        if session_id:
            _stub_sessions[session_id] = session
        return

    _ddb().Table(SESSIONS_TABLE).put_item(Item=session)


def append_chat_turn(
    *,
    session_id: str,
    date: str | None,
    new_items: list[dict],
    topics_loaded: list[str],
    created_at: str | None = None,
) -> None:
    """Atomically append `new_items` to `chat_history` and refresh session
    metadata + TTL.

    Uses DynamoDB `UpdateItem` with `list_append` so overlapping requests
    on the same `session_id` don't drop each other's turns — the failure
    mode we can no longer tolerate now that persistence happens outside
    the tool loop. `topics_loaded` and `date` are still last-writer-wins
    because they're small and mostly monotonic; a lost topic add is
    self-healing (the next fetch re-adds it), a lost chat turn is not.
    """
    ttl = int(time.time()) + SESSION_TTL_SECONDS

    if is_stub_mode() or STUB_MODE:
        session = _stub_sessions.get(session_id) or {
            "session_id": session_id,
            "date": date,
            "chat_history": [],
            "topics_loaded": [],
            "created_at": created_at,
        }
        session["chat_history"] = [*session.get("chat_history", []), *new_items]
        if topics_loaded is not None:
            session["topics_loaded"] = topics_loaded
        if date:
            session["date"] = date
        session["ttl"] = ttl
        if created_at and not session.get("created_at"):
            session["created_at"] = created_at
        _stub_sessions[session_id] = session
        return

    expr_names = {"#d": "date", "#ttl": "ttl"}
    expr_values: dict = {
        ":empty": [],
        ":new_items": new_items,
        ":tl": topics_loaded or [],
        ":ttl": ttl,
    }
    set_clauses = [
        "chat_history = list_append(if_not_exists(chat_history, :empty), :new_items)",
        "topics_loaded = :tl",
        "#ttl = :ttl",
    ]
    if date:
        expr_values[":date"] = date
        set_clauses.append("#d = :date")
    if created_at:
        expr_values[":created_at"] = created_at
        set_clauses.append("created_at = if_not_exists(created_at, :created_at)")

    _ddb().Table(SESSIONS_TABLE).update_item(
        Key={"session_id": session_id},
        UpdateExpression="SET " + ", ".join(set_clauses),
        ExpressionAttributeNames=expr_names,
        ExpressionAttributeValues=expr_values,
    )


# --- Raw report cache --------------------------------------------------------

def report_key(date: str, topic_id: str, ext: str) -> str:
    return f"{date}/{topic_id}.{ext}"


def get_report(date: str, topic_id: str, ext: str) -> bytes | None:
    if STUB_MODE:
        return _stub_reports.get(report_key(date, topic_id, ext))
    try:
        resp = _s3().get_object(Bucket=CACHE_BUCKET, Key=report_key(date, topic_id, ext))
        return resp["Body"].read()
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") in ("NoSuchKey", "404"):
            return None
        raise


def put_report(date: str, topic_id: str, ext: str, data: bytes) -> None:
    if STUB_MODE:
        _stub_reports[report_key(date, topic_id, ext)] = data
        return
    _s3().put_object(
        Bucket=CACHE_BUCKET,
        Key=report_key(date, topic_id, ext),
        Body=data,
    )
