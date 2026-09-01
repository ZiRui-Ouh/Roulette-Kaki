"""
AWS Bedrock service for the Search Agent.

All calls to Amazon Bedrock should go through this module.
"""

from __future__ import annotations

import os

try:
    import boto3
    from botocore.config import Config
except ImportError:  # pragma: no cover - dependency is optional for tests
    boto3 = None
    Config = None


REGION = os.environ.get("AWS_REGION", "ap-southeast-1")
MODEL_ID = "amazon.nova-lite-v1:0"

_client = None


def get_client():
    """
    Create the Bedrock Runtime client.
    """

    if boto3 is None or Config is None:
        raise RuntimeError(
            "The AWS SDK dependencies are not installed. "
            "Install the backend requirements before calling the Bedrock API."
        )

    global _client

    if _client is None:
        profile = os.environ.get("AWS_PROFILE")

        if profile:
            session = boto3.Session(profile_name=profile)
        else:
            session = boto3.Session()

        _client = session.client(
            "bedrock-runtime",
            region_name=REGION,
            config=Config(retries={"max_attempts": 3, "mode": "standard"}),
        )

    return _client


def ask_nova(prompt: str, max_tokens: int = 2048) -> str:
    """
    Send a prompt to Amazon Nova Lite and return the answer.
    """

    response = get_client().converse(
        modelId=MODEL_ID,
        messages=[
            {
                "role": "user",
                "content": [{"text": prompt}],
            }
        ],
        inferenceConfig={
            "maxTokens": max_tokens,
            "temperature": 0.2,
            "topP": 0.9,
        },
    )

    return response["output"]["message"]["content"][0]["text"]
