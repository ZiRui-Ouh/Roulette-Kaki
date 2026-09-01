from __future__ import annotations

from services.bedrock import ask_nova
from services.webscraper import scrape_unofficial_sources


SYSTEM_PROMPT = """
You are the Public Sentiment Search Agent for a Singapore policy
information platform.

Your job is to explain what the general public is saying on
unofficial Singapore discussion platforms, specifically:
- Reddit Singapore
- HardwareZone
- Facebook public pages

Use ONLY the information provided in these unofficial sources.
Do not use official government websites, announcements, or
policy notices.

IMPORTANT RULES:

1. Do not invent policies, requirements, eligibility rules,
   dates, numbers or procedures.

2. If the provided unofficial sources do not contain enough
   information, clearly say that the available unofficial
   sources do not provide enough information.

3. Prefer the most recent discussion when multiple sources are
   provided.

4. Clearly distinguish between:
   - what the general public is saying
   - why people feel this way
   - important conditions or exceptions mentioned in discussions
   - any reported confusion or practical concern

5. If any discussion contains rude, vulgar, or offensive wording,
   rewrite it in a professional, neutral tone while keeping the
   same overall sentiment and meaning.

6. Do not give legal advice. Only explain general public
   sentiment and the reasons that people give.

7. Always provide the relevant source URLs when they are
   available.

8. Never treat official discussion or opinions as unofficial
   discussion.

9. Stay concise and easy to understand.
"""


def build_prompt(question: str, unofficial_sources: list[dict]) -> str:
    """
    Build the prompt given to the LLM for an unofficial-search answer.
    """

    sources_text = ""

    for index, source in enumerate(unofficial_sources, start=1):
        title = source.get("title", "Unofficial discussion")
        url = source.get("url", "")
        source_type = source.get("source_type", "Unofficial forum")
        content = source.get("content", "")

        sources_text += f"""
SOURCE {index}
Source type: {source_type}
Title: {title}
URL: {url}

Content:
{content}

-------------------------
"""

    return f"""
{SYSTEM_PROMPT}

UNOFFICIAL PUBLIC DISCUSSION SOURCES

{sources_text}

USER QUESTION

{question}

TASK

Answer the user's question using only the unofficial sources above.

Structure your response naturally. Where useful, include:

- Public sentiment
- Why people feel this way
- Important conditions or exceptions mentioned in discussion
- What users are generally doing or saying
- Source URLs

If the sources do not contain enough information, say so rather
than guessing.

Do not repeat or mirror the style of the official policy answer.
This is a public-discussion search agent, not an official policy
query agent.
"""


def answer_question(
    question: str,
    urls: list[str] | None = None,
    unofficial_sources: list[dict] | None = None,
) -> str:
    """
    Answer a user's question using only unofficial public forums.
    """

    if not question.strip():
        raise ValueError("Question cannot be empty.")

    if unofficial_sources is None:
        if not urls:
            raise ValueError("At least one unofficial source URL is required.")
        unofficial_sources = scrape_unofficial_sources(urls)

    prompt = build_prompt(question=question, unofficial_sources=unofficial_sources)
    return ask_nova(prompt)
