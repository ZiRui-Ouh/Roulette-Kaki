"""DynamoDB + S3 access.

Tables:
- DebateDigests  (PK: date)  — no TTL, sittings don't change.
- ChatSessions   (PK: session_id) — TTL enabled; refreshed on each message.

Bucket:
- parl-debate-cache — raw report bytes at `{date}/{topic_id}.{ext}`.

Clients are lazily initialized on first use; nothing hits AWS at import
time.
"""

from __future__ import annotations

import os
import time

import boto3
from botocore.exceptions import ClientError

REGION = os.environ.get("AWS_REGION", "ap-southeast-1")
DIGESTS_TABLE = os.environ.get("DIGESTS_TABLE", "DebateDigests")
SESSIONS_TABLE = os.environ.get("SESSIONS_TABLE", "ChatSessions")
CACHE_BUCKET = os.environ.get("CACHE_BUCKET", "parl-debate-cache")

SESSION_TTL_SECONDS = 3600  # 1 hour, refreshed on every message.

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


# --- Digest cache ------------------------------------------------------------

def get_digest(date: str) -> dict | None:
    resp = _ddb().Table(DIGESTS_TABLE).get_item(Key={"date": date})
    return resp.get("Item")


def put_digest(digest: dict) -> None:
    _ddb().Table(DIGESTS_TABLE).put_item(Item=digest)


# --- Session state -----------------------------------------------------------

def get_session(session_id: str) -> dict | None:
    resp = _ddb().Table(SESSIONS_TABLE).get_item(Key={"session_id": session_id})
    return resp.get("Item")


def put_session(session: dict) -> None:
    """Write a session row, always refreshing TTL. Callers must not skip
    this — TTL is set here so it cannot be forgotten upstream.
    """
    session = {**session, "ttl": int(time.time()) + SESSION_TTL_SECONDS}
    _ddb().Table(SESSIONS_TABLE).put_item(Item=session)


# --- Raw report cache --------------------------------------------------------

def report_key(date: str, topic_id: str, ext: str) -> str:
    return f"{date}/{topic_id}.{ext}"


def get_report(date: str, topic_id: str, ext: str) -> bytes | None:
    try:
        resp = _s3().get_object(Bucket=CACHE_BUCKET, Key=report_key(date, topic_id, ext))
        return resp["Body"].read()
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") in ("NoSuchKey", "404"):
            return None
        raise


def put_report(date: str, topic_id: str, ext: str, data: bytes) -> None:
    _s3().put_object(
        Bucket=CACHE_BUCKET,
        Key=report_key(date, topic_id, ext),
        Body=data,
    )
