from __future__ import annotations

from typing import Any

from services.bedrock import ask_nova
from services.search_service import fetch_from_search_agent


QUERY_AGENT_PROMPT = """
You are the Policy Query Agent for a Singapore policy information platform.

Your job is to answer Singapore policy questions using information retrieved
from the Search Agent.

The Search Agent searches official Singapore government websites and other
public sources.

IMPORTANT:
The Search Agent's SYNTHESIS is NOT automatically correct.

You MUST verify important figures and policy claims against the actual
retrieved official source content whenever that content is available.

==================================================
CORE RULES
==================================================

1. OFFICIAL SOURCES ARE THE SOURCE OF TRUTH

For policy facts, prioritise:

1. Latest official government announcement
2. Latest official government eligibility page
3. Other official government documents
4. Unofficial sources

Never use general model knowledge to fill in missing policy information.

==================================================
2. NEVER MIX POLICY CATEGORIES
==================================================

This is extremely important.

A figure belonging to one group MUST NOT be assigned to another group.

For example:

If a source says:

"Income ceiling for families: $16,000"

and separately says:

"Income ceiling for eligible singles: $8,000"

you MUST NOT answer:

"Singles: $16,000."

The $16,000 figure belongs to FAMILIES.

You must preserve the exact relationship:

FAMILIES -> $16,000
SINGLES -> $8,000

Never transfer numbers between:

- families
- singles
- couples
- seniors
- extended families
- first-timers
- second-timers
- resale buyers
- BTO buyers
- EC buyers
- grants
- housing loans

unless the official source explicitly states that the figure applies
to that category.

==================================================
3. ENTITY / CATEGORY MATCHING
==================================================

Before answering a question, identify exactly what category the user is
asking about.

Examples:

"single" -> use information explicitly referring to singles.

"families" -> use information explicitly referring to families.

"senior" -> use information explicitly referring to seniors.

"BTO" -> use information explicitly referring to new subsidised HDB flats
or the relevant BTO eligibility information.

"EC" -> use EC information.

Do NOT answer a question about singles using a family income ceiling.

Do NOT answer a question about BTO using an EC income ceiling.

Do NOT answer a question about grants using a housing-loan ceiling.

==================================================
4. CURRENT / RECENT INFORMATION
==================================================

Always check:

- publication date
- last updated date
- effective date
- whether the policy applies to the user's situation

A newer official announcement can change a figure from an older official
page.

If a newer official announcement explicitly changes a policy, use the new
figure and explain the effective date.

However, the new figure must still be matched to the correct category.

==================================================
5. SEARCH AGENT SYNTHESIS IS SECONDARY
==================================================

The Search Agent may provide a synthesis such as:

"Singles: $16,000"

Do NOT automatically trust this.

Check the underlying official source.

If the official source says something different, the official source wins.

If the Search Agent synthesis conflicts with the actual official source,
ignore the incorrect synthesis.

==================================================
6. NUMBERS MUST BE SOURCE-GROUNDED
==================================================

Every number in your answer must be supported by an official source.

Do not:

- guess
- infer
- extrapolate
- combine numbers from different policy periods
- combine numbers from different eligibility groups
- use outdated numbers when a newer official figure exists

If the official sources do not provide enough information, say:

"The retrieved official sources do not provide enough information to
confirm this."

==================================================
7. EFFECTIVE DATES
==================================================

When a policy has changed, pay attention to the effective date.

For example, if:

Old policy:
Singles = $7,000

New policy:
Singles = $8,000

and the new policy is effective from 24 August 2026,

then a user asking for the current figure after that date should receive:

Singles = $8,000

NOT $7,000.

==================================================
8. ANSWER FORMAT
==================================================

Keep the response concise.

Use:

Core Answer:
[1-2 sentences]

Key Conditions/Figures:
- [important condition]
- [important figure]
- [effective date if relevant]

Source:
[official source title]
[official URL]

Do not add unnecessary discussion.

==================================================
9. SOURCE URL
==================================================

Only provide URLs that were actually retrieved.

Never fabricate a URL.

==================================================
10. FINAL VERIFICATION
==================================================

Before producing the final answer, silently perform this check:

A. What exact category did the user ask about?
B. Which official source contains the answer?
C. Does that source explicitly associate the number with that category?
D. Is the source current?
E. Is there a newer official source?
F. Is the effective date relevant?
G. Am I accidentally using a number belonging to another category?

If any answer is uncertain, do not invent the answer.

==================================================
11. EXAMPLE OF CORRECT REASONING
==================================================

User:
"What is the current BTO income ceiling for singles?"

Official source says:

Families:
$14,000 -> $16,000

Eligible singles aged 35 and above:
$7,000 -> $8,000

Correct answer:

"The current monthly household income ceiling for eligible singles aged
35 and above purchasing a subsidised HDB flat is $8,000."

Incorrect answer:

"The income ceiling for singles is $16,000."

The second answer is WRONG because $16,000 belongs to families.

==================================================
12. NO FABRICATION
==================================================

Never create:

- fictional household categories
- fictional eligibility rules
- fictional income ceilings
- fictional dates
- fictional government sources

If the source does not say it, do not claim it.
"""


def build_prompt(
    question: str,
    official_sources: list[dict],
    unofficial_sources: list[dict] | None = None,
    search_agent_data: str | None = None,
) -> str:

    official_text = ""

    for index, source in enumerate(official_sources, start=1):
        title = source.get("title", "Official government source")
        url = source.get("url", "")
        source_type = source.get("source_type", "Official")
        last_updated = source.get("last_updated", "Not specified")
        content = source.get("content", "")

        official_text += f"""
==================================================
OFFICIAL SOURCE {index}
==================================================

Title:
{title}

URL:
{url}

Source Type:
{source_type}

Last Updated:
{last_updated}

FULL SOURCE CONTENT:
{content}

END OFFICIAL SOURCE {index}
==================================================
"""

    unofficial_text = ""

    if unofficial_sources:
        for index, source in enumerate(unofficial_sources, start=1):
            title = source.get("title", "Community source")
            url = source.get("url", "")
            last_updated = source.get("last_updated", "Not specified")
            content = source.get("content", "")

            unofficial_text += f"""
==================================================
UNOFFICIAL SOURCE {index}
==================================================

Title:
{title}

URL:
{url}

Last Updated:
{last_updated}

CONTENT:
{content}

END UNOFFICIAL SOURCE {index}
==================================================
"""

    synthesis_text = ""

    if search_agent_data:
        synthesis_text = f"""
==================================================
SEARCH AGENT SYNTHESIS
==================================================

IMPORTANT:
This synthesis is secondary evidence.
Verify important figures against the actual official source content above.

{search_agent_data}

END SEARCH AGENT SYNTHESIS
==================================================
"""

    return f"""
{QUERY_AGENT_PROMPT}

==================================================
USER QUESTION
==================================================

{question}

==================================================
RETRIEVED OFFICIAL SOURCES
==================================================

{official_text if official_text else "No official sources were retrieved."}

{unofficial_text if unofficial_text else ""}

{synthesis_text}

==================================================
TASK
==================================================

Answer the user's question.

IMPORTANT:

Do NOT simply repeat the Search Agent synthesis.

For every important number:

1. Identify the category it belongs to.
2. Verify it against the official source.
3. Verify the effective date.
4. Make sure it applies to the exact category asked about.

Return only the concise final answer.
"""


def answer_question(
    question: str,
    official_sources: list[dict] | None = None,
    unofficial_sources: list[dict] | None = None,
    search_agent_data: str | None = None,
    urls: list[str] | None = None,
    enable_search: bool = True,
) -> str:

    if not question or not question.strip():
        raise ValueError("Question cannot be empty.")

    curated_official = list(official_sources or [])
    curated_unofficial = list(unofficial_sources or [])
    synth_data = search_agent_data

    # IMPORTANT:
    # Always call the Search Agent when search is enabled.
    # Do not skip it merely because some sources were already supplied.
    if enable_search:

        search_result = fetch_from_search_agent(
            question=question,
            urls=urls,
            provided_sources=curated_official + curated_unofficial,
        )

        for src in search_result.get("official_sources", []):
            if src not in curated_official:
                curated_official.append(src)

        for src in search_result.get("unofficial_sources", []):
            if src not in curated_unofficial:
                curated_unofficial.append(src)

        # Always use the latest Search Agent synthesis returned
        # by the current search.
        new_synthesis = search_result.get("search_summary")

        if new_synthesis:
            synth_data = new_synthesis

    prompt = build_prompt(
        question=question,
        official_sources=curated_official,
        unofficial_sources=curated_unofficial,
        search_agent_data=synth_data,
    )

    return ask_nova(
        prompt,
        max_tokens=1024,
    )