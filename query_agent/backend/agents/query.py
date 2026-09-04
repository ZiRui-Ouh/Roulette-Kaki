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

A figure belonging to one group (e.g. Families, Couples) MUST NOT be assigned to another group (e.g. Singles, Seniors).

You must preserve the exact official relationship:
- Family / Couple figures apply ONLY to Families / Couples.
- Single figures apply ONLY to Singles.
- 2-room flat figures apply ONLY to 2-room flats.
- Executive Condominium (EC) figures apply ONLY to ECs.

Never transfer numbers between:
- families
- singles
- couples
- seniors
- first-timers
- resale buyers
- BTO buyers
- EC buyers
- grants
- housing loans

unless the official source explicitly states that the figure applies to that category.

==================================================
3. ENTITY / CATEGORY MATCHING
==================================================

Before answering a question, identify exactly what category the user is asking about.

Examples:
- "single" -> use information explicitly referring to singles.
- "families" -> use information explicitly referring to families.
- "senior" -> use information explicitly referring to seniors.
- "BTO" -> use information explicitly referring to new subsidised HDB flats.
- "EC" -> use EC information.

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

If an official announcement explicitly modifies a policy, use the current active figure and note the effective date.

==================================================
5. SEARCH AGENT SYNTHESIS IS SECONDARY
==================================================

The Search Agent summary is secondary evidence.
Verify figures against the actual retrieved official source content.
If the Search Agent synthesis conflicts with the actual official source, the official source ALWAYS takes precedence.

==================================================
6. NUMBERS MUST BE SOURCE-GROUNDED & ACCURATE
==================================================

Every number, dollar value, percentage, and age threshold in your answer must be supported by an official Singapore government source.

OFFICIAL SINGAPORE BENCHMARKS REFERENCE:
- HDB BTO (4-room & larger for Families/Couples): Gross monthly household income ceiling is $16,000 (raised from $14,000).
- HDB BTO (2-room Flexi for Singles aged 35+): Gross monthly household income ceiling is $8,000 (raised from $7,000).
- Executive Condominiums (EC): Gross monthly household income ceiling is $18,000 (raised from $16,000).
- 3-room BTO Flats: $8,000 or $16,000 depending on project.
- CPF: OA interest is 2.5% p.a., SA/MA/RA is 4.0% p.a. SA closes at age 55. ERS ceiling is 4x BRS ($426,000 in 2025).
- MediShield Life: Annual claim limit is $200,000.

You must preserve the exact relationship:
- FAMILIES / COUPLES -> $16,000
- SINGLES -> $8,000
- EXECUTIVE CONDOMINIUMS (EC) -> $18,000

Do not:
- guess or extrapolate
- invent hypothetical future revisions
- combine numbers from different eligibility groups

If the retrieved sources do not contain the specific number requested, state:
"The retrieved official sources do not provide enough information to confirm this figure."

==================================================
7. ANSWER FORMAT
==================================================

Keep the response concise and clearly formatted in Markdown:

Core Answer:
[1-2 clear, direct sentences answering the question]

Key Conditions/Figures:
- [Condition or eligibility criterion]
- [Exact official figure]
- [Effective date if applicable]

Official Source:
[Official source title and URL]

==================================================
8. SOURCE URL
==================================================

Only provide URLs that were actually retrieved in the sources list. Never fabricate URLs.

==================================================
9. NO FABRICATION
==================================================

Never create:
- fictional household categories
- fictional eligibility rules
- fictional income ceilings or payout figures
- fictional dates or government gazettes

If the source does not explicitly state it, do not claim it.
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