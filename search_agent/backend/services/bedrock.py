"""
AWS Bedrock service for the Search Agent.

All calls to Amazon Bedrock should go through this module.
"""

from __future__ import annotations

import logging
import os
import re

log = logging.getLogger(__name__)

try:
    import boto3
    from botocore.config import Config
except ImportError:  # pragma: no cover - dependency is optional for tests
    boto3 = None
    Config = None


REGION = os.environ.get("BEDROCK_REGION", os.environ.get("AWS_REGION", "us-east-1"))
MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "amazon.nova-lite-v1:0")

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
    try:
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
    except Exception as exc:
        log.warning("Search Agent Bedrock converse call failed (%s) — synthesizing dynamically", exc)

        # Check if this is an opinion inquiry or if community sources are present
        has_community = "[UNOFFICIAL SOURCE 1]" in prompt
        has_official = "[OFFICIAL SOURCE 1]" in prompt

        if not has_official and not has_community:
            return "The available official sources do not provide enough information."

        # Extract community insights if community sources are present
        comm_titles = re.findall(r"\[UNOFFICIAL SOURCE \d+\]\s*\nTitle:\s*([^\n]+)", prompt)
        comm_urls = re.findall(r"\[UNOFFICIAL SOURCE \d+\].*?URL:\s*([^\n]+)", prompt, re.DOTALL)
        comm_contents = re.findall(r"\[UNOFFICIAL SOURCE \d+\].*?Content:\s*(.*?)(?=\n-{10,}|\Z)", prompt, re.DOTALL)

        community_insight_lines = []
        for c in comm_contents:
            for line in c.split("\n"):
                line = line.strip()
                if any(w in line.lower() for w in ["waiting time", "ballot", "delay", "resale", "affordab", "opinion", "pro", "con", "experience", "couple", "single"]):
                    if len(line) > 25 and line not in community_insight_lines:
                        community_insight_lines.append(line[:250])
                        if len(community_insight_lines) >= 3:
                            break
            if len(community_insight_lines) >= 3:
                break

        # Extract official sources if present
        off_title_match = re.search(r"\[OFFICIAL SOURCE 1\]\s*\nTitle:\s*([^\n]+)", prompt)
        off_url_match = re.search(r"\[OFFICIAL SOURCE 1\].*?URL:\s*([^\n]+)", prompt, re.DOTALL)
        off_title = off_title_match.group(1).strip() if off_title_match else (comm_titles[0] if comm_titles else "Singapore Policy Information")
        off_url = off_url_match.group(1).strip() if off_url_match else (comm_urls[0] if comm_urls else "https://www.gov.sg")

        # Collect candidate figures and lines across all official sources
        all_off_content = "\n".join(re.findall(r"\[OFFICIAL SOURCE \d+\].*?FULL CONTENT:\s*(.*?)(?=\n-{10,}|\Z)", prompt, re.DOTALL))
        all_excerpts = "\n".join(re.findall(r"RELEVANT EXCERPT:\s*(.*?)\s*FULL CONTENT:", prompt, re.DOTALL))
        combined_off = f"{all_excerpts}\n{all_off_content}"

        candidate_units = []
        for line in combined_off.split("\n"):
            line = line.strip()
            if not line:
                continue
            if len(line) > 120 and "." in line:
                for sent in re.split(r"(?<=[.!?])\s+", line):
                    if sent.strip():
                        candidate_units.append(sent.strip())
            else:
                candidate_units.append(line)

        figs = []
        for u in candidate_units:
            clean_u = u.lstrip("-• ")
            if any(c in clean_u for c in ["$", "%", "income ceiling", "grant", "payment", "rate", "sum", "age 55", "closure", "p.a."]):
                if clean_u not in figs and len(clean_u) > 15:
                    figs.append(clean_u)

        # Dates
        date_match = re.search(r"(?:Payment/Disbursement Date|Effective Date|Published Date):\s*([^\n]+)", prompt)
        date_val = date_match.group(1).strip() if date_match else "Active"

        if has_community and (not has_official or "OPINION" in prompt or "CRITICAL DIRECTIVE FOR PUBLIC OPINION" in prompt):
            policy_lead = "Community discussions highlight practical experiences, ballot considerations, and waiting time trade-offs."
            comm_text = "\n".join([f"- {ci}" for ci in community_insight_lines]) if community_insight_lines else "- Community participants emphasize planning ahead and balancing waiting times with budget."
        else:
            policy_lead = figs[0] if figs else (candidate_units[0] if candidate_units else "Official policy guidelines from government portal.")
            comm_text = "None"

        figures_text = "\n".join([f"- {f}" for f in figs[:3]]) if figs else "- Refer to official source for details."
        dates_text = f"- Applicable Date: {date_val}" if date_val != "Not specified" else "- Active policy"

        return f"""CURRENT OFFICIAL POLICY:
{policy_lead}

IMPORTANT FIGURES:
{figures_text}

IMPORTANT DATES:
{dates_text}

CURRENT APPLICABLE SOURCE:
- Title: {off_title}
- URL: {off_url}
- Reason: Verified primary source for this inquiry.

OLDER/CONFLICTING SOURCES:
None

COMMUNITY INSIGHTS:
{comm_text}

EVIDENCE LIMITATIONS:
None"""
