

from __future__ import annotations

from services.bedrock import ask_nova


SYSTEM_PROMPT = """
You are the Policy Query Agent for a Singapore policy
information platform.

Your job is to answer questions about Singapore government
policies using ONLY the information provided in the official
policy sources.

IMPORTANT RULES:

1. Do not invent policies, requirements, eligibility rules,
   dates, numbers or procedures.

2. If the provided sources do not contain enough information,
   clearly say that the available official sources do not
   provide enough information.

3. Prefer the most recent official information when multiple
   sources are provided.

4. Clearly distinguish between:
   - what the policy says
   - who is eligible
   - what the user needs to do
   - important conditions or exceptions

5. Keep answers concise and easy to understand.

6. Do not give legal advice. Explain the policy information
   and direct users to the official source when appropriate.

7. Always provide the relevant source URLs when they are
   available.

8. Never treat unofficial discussion or opinions as official
   policy.
"""


def build_prompt(
    question: str,
    official_sources: list[dict],
    search_agent_data: str | None = None,
) -> str:
    """
    Build the prompt given to the LLM.

    official_sources:
        Information retrieved from official government sources.

    search_agent_data:
        Optional information from the Search Agent.
        This will be connected later.
    """

    sources_text = ""

    for index, source in enumerate(official_sources, start=1):

        title = source.get("title", "Official source")
        url = source.get("url", "")
        content = source.get("content", "")

        sources_text += f"""
SOURCE {index}
Title: {title}
URL: {url}

Content:
{content}

-------------------------
"""

    search_text = ""

    if search_agent_data:
        search_text = f"""
ADDITIONAL SEARCH AGENT INFORMATION

The following information comes from the Search Agent.
It is NOT official policy and must NOT override official
government sources.

{search_agent_data}

-------------------------
"""

    return f"""
{SYSTEM_PROMPT}

OFFICIAL POLICY SOURCES

{sources_text}

{search_text}

USER QUESTION

{question}

TASK

Answer the user's question using the official sources.

Structure your response naturally. Where useful, include:

- Direct answer
- Eligibility
- Requirements
- What the user should do
- Important conditions
- Official source

If the sources do not contain enough information,
say so rather than guessing.
"""


def answer_question(
    question: str,
    official_sources: list[dict],
    search_agent_data: str | None = None,
) -> str:
    """
    Answer a user's policy question.
    """

    if not question.strip():
        raise ValueError("Question cannot be empty.")

    prompt = build_prompt(
        question=question,
        official_sources=official_sources,
        search_agent_data=search_agent_data,
    )

    return ask_nova(prompt)
