"""Cold-start SSM parameter loader.

Fetches SecureString parameters under `/parl/` from SSM Parameter Store and
populates `os.environ` for keys not already set. Idempotent — safe to
import multiple times.

Skipped when `USE_LOCAL_STUBS=1` (local dev doesn't hit AWS).

Import this **before** any service module that reads env vars at module
init (e.g., `services.bedrock`, `services.meralion`, `services.storage`) so
their module-level `os.environ.get(...)` reads see the values.
"""

from __future__ import annotations

import logging
import os

log = logging.getLogger(__name__)

# SSM path prefix (with trailing slash) → env var mapping. Add new keys here
# as more secrets move to SSM; TF `ssm.tf` provisions the parameters and the
# Lambda IAM role's `ssm:GetParametersByPath` grants read.
_PARL_PARAM_MAP: dict[str, str] = {
    "/parl/youtube_api_key": "YOUTUBE_API_KEY",
    "/parl/meralion_api_key": "MERALION_API_KEY",
    "/parl/google_api_key": "GOOGLE_API_KEY",
    "/parl/google_cse_id": "GOOGLE_CSE_ID",
}


def load_ssm_config() -> None:
    if os.environ.get("USE_LOCAL_STUBS") == "1":
        return

    # Deferred imports so local dev / tests never require boto3 at import time.
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError

    region = os.environ.get("AWS_REGION", "us-east-1")
    try:
        client = boto3.client("ssm", region_name=region)
        resp = client.get_parameters_by_path(
            Path="/parl/",
            WithDecryption=True,
            Recursive=False,
        )
    except (ClientError, BotoCoreError) as e:
        # A missing IAM permission or empty parameter store shouldn't crash
        # cold start — surface via logs and let downstream env reads decide
        # whether missing keys are fatal.
        log.warning("SSM parameter load failed (%s) — using env vars only", e)
        return

    loaded = 0
    for param in resp.get("Parameters", []):
        env_key = _PARL_PARAM_MAP.get(param.get("Name", ""))
        value = param.get("Value")
        if env_key and value and not os.environ.get(env_key):
            os.environ[env_key] = value
            loaded += 1

    if loaded:
        log.info("SSM: loaded %d parameter(s) into env", loaded)


# Run at import time so `from services import config` is sufficient.
load_ssm_config()
