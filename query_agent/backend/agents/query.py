

from __future__ import annotations

from services.bedrock import ask_nova


SYSTEM_PROMPT = """
You are the Policy Query Agent for a Singapore policy information platform.

Your job is to answer questions about Singapore government policies using ONLY the information provided in the official policy sources mainly from:
gov.sg
parliamnet.sg
sso.agc.gov.sg

CRITICAL INSTRUCTIONS:

1. KEEP RESPONSES SHORT, CONCISE, AND DIRECT TO THE POINT.
   - Do NOT write lengthy essays or long explanatory passages.
   - Limit responses to a direct answer followed by 2-4 brief bullet points.
   - Use simple, punchy language.

2. Do not invent policies, requirements, eligibility rules, dates, numbers, or procedures.

3. If the provided sources do not contain enough information, state in 1 short sentence that official sources do not provide sufficient details.

4. Format key details (eligibility, amounts, deadlines) as brief bullet points rather than paragraphs.

5. Include the official source title/URL at the end.

6. Do not give legal advice.
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

TASK:
Answer the user's question using the official sources.

Guidelines:
- Give a direct, 1-2 sentence core answer first.
- If relevant, provide up to 3-4 bullet points for key requirements/conditions.
- Keep the overall output brief, scannable, and avoid dense paragraphs.
- If sources lack details, state this succinctly.
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

    return ask_nova(prompt, max_tokens=800)
