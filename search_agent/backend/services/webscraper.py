"""
Singapore Policy Search Agent / Web Scraper

Purpose:
    Retrieve and verify CURRENT Singapore government policy information.

Design:
    User query
        ↓
    Detect policy category
        ↓
    Add known high-priority official sources
        ↓
    Search for NEW official announcements
        ↓
    Scrape official sources
        ↓
    Extract publication/update/effective dates
        ↓
    Rank sources by authority + recency
        ↓
    Detect conflicting figures
        ↓
    Return structured evidence to Query Agent

IMPORTANT:
    This file DOES NOT hard-code policy answers.
    Numbers such as income ceilings must come from scraped sources.
"""

from __future__ import annotations

import re
import time
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup


# ============================================================
# CONFIGURATION
# ============================================================

REQUEST_TIMEOUT = 20
MAX_CONTENT_LENGTH = 30000
SEARCH_RESULTS_LIMIT = 8

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/151.0 Safari/537.36"
    )
}


# ============================================================
# OFFICIAL POLICY SOURCES
# ============================================================

POLICY_SOURCES = {

    # --------------------------------------------------------
    # HDB
    # --------------------------------------------------------

    "hdb": {

        "domains": [
            "hdb.gov.sg"
        ],

        "priority_urls": [

            # IMPORTANT:
            # Newest HDB income ceiling announcement
            {
                "url": (
                    "https://www.hdb.gov.sg/hdb-pulse/news/2026/"
                    "increase-in-income-ceilings-and-greater-support-for-families-with-children"
                ),
                "title": (
                    "Increase in Income Ceilings and Greater Support "
                    "for Families with Children"
                ),
                "priority": 100
            },

            # Couples / Families
            {
                "url": (
                    "https://www.hdb.gov.sg/buying-a-flat/"
                    "flat-grant-and-loan-eligibility/couples-and-families"
                ),
                "title": "Couples and Families",
                "priority": 90
            },

            # Singles
            {
                "url": (
                    "https://www.hdb.gov.sg/buying-a-flat/"
                    "flat-grant-and-loan-eligibility/singles"
                ),
                "title": "Singles",
                "priority": 90
            },

            # Seniors
            {
                "url": (
                    "https://www.hdb.gov.sg/buying-a-flat/"
                    "flat-grant-and-loan-eligibility/seniors"
                ),
                "title": "Seniors",
                "priority": 90
            },
        ],
    },


    # --------------------------------------------------------
    # CPF
    # --------------------------------------------------------

    "cpf": {

        "domains": [
            "cpf.gov.sg"
        ],

        "priority_urls": [

            # Current CPF contribution rates
            {
                "url": (
                    "https://www.cpf.gov.sg/employer/"
                    "employer-obligations/how-much-cpf-contributions-to-pay"
                ),
                "title": "How much CPF contributions to pay",
                "priority": 100
            },

            # Current CPF interest rates
            {
                "url": (
                    "https://www.cpf.gov.sg/service/"
                    "article/what-are-the-cpf-interest-rates"
                ),
                "title": "What are the CPF interest rates?",
                "priority": 100
            },

            # CPF interest-rate announcement
            {
                "url": (
                    "https://www.cpf.gov.sg/member/infohub/news/"
                    "news-releases/cpf-interest-rates-from-1-july-to-30-september-2026"
                ),
                "title": (
                    "CPF Interest Rates from 1 July to "
                    "30 September 2026"
                ),
                "priority": 100
            },

            # 2026 senior worker contribution changes
            {
                "url": (
                    "https://www.cpf.gov.sg/service/article/"
                    "what-are-the-changes-to-the-cpf-contribution-rates-"
                    "for-senior-workers-from-1-january-2026"
                ),
                "title": (
                    "Changes to CPF contribution rates for senior workers "
                    "from 1 January 2026"
                ),
                "priority": 95
            },

            # 2027 announcement - useful for questions about future rates
            {
                "url": (
                    "https://www.cpf.gov.sg/employer/infohub/news/"
                    "cpf-related-announcements/new-contribution-rates"
                ),
                "title": (
                    "Increase in CPF Contribution Rates "
                    "from 1 January 2027"
                ),
                "priority": 95
            },

            # CPF allocation rates
            {
                "url": (
                    "https://www.cpf.gov.sg/service/article/"
                    "what-are-the-cpf-allocation-rates"
                ),
                "title": "What are the CPF allocation rates for 2026?",
                "priority": 90
            },
        ],
    },
}


# ============================================================
# CATEGORY DETECTION
# ============================================================

CATEGORY_KEYWORDS = {

    "hdb": [
        "bto",
        "hdb",
        "build to order",
        "build-to-order",
        "sbf",
        "sale of balance flats",
        "housing grant",
        "hdb loan",
        "hfe",
        "flat eligibility",
        "income ceiling",
        "income ceiling for flats",
        "resale flat",
        "new flat",
        "singles hdb",
        "couples hdb",
        "families hdb",
        "seniors hdb",
    ],

    "cpf": [
        "cpf",
        "cpf contribution",
        "cpf contribution rate",
        "cpf interest",
        "cpf interest rate",
        "ordinary account",
        "oa",
        "special account",
        "sa",
        "retirement account",
        "ra",
        "medisave",
        "cpf allocation",
        "cpf salary ceiling",
        "cpf monthly salary ceiling",
        "platform worker cpf",
    ],
}


def detect_policy_categories(query: str) -> list[str]:
    """
    Detect which policy categories are relevant.
    """

    query_lower = query.lower()

    categories = []

    for category, keywords in CATEGORY_KEYWORDS.items():

        for keyword in keywords:

            if keyword in query_lower:
                categories.append(category)
                break

    # If nothing matched, search broadly.
    if not categories:
        return ["general"]

    return categories


# ============================================================
# DATE EXTRACTION
# ============================================================

DATE_PATTERNS = [

    # 22 August 2026
    r"\b(\d{1,2}\s+"
    r"(?:January|February|March|April|May|June|July|August|September|"
    r"October|November|December)\s+\d{4})\b",

    # August 22, 2026
    r"\b((?:January|February|March|April|May|June|July|August|September|"
    r"October|November|December)\s+\d{1,2},\s+\d{4})\b",

    # 22/08/2026
    r"\b(\d{1,2}/\d{1,2}/\d{4})\b",

    # 2026-08-22
    r"\b(\d{4}-\d{2}-\d{2})\b",
]


def parse_date_string(value: str) -> Optional[datetime]:

    if not value:
        return None

    formats = [
        "%d %B %Y",
        "%B %d, %Y",
        "%d/%m/%Y",
        "%Y-%m-%d",
    ]

    for fmt in formats:

        try:
            return datetime.strptime(value.strip(), fmt)

        except ValueError:
            continue

    return None


def extract_dates(text: str) -> list[datetime]:

    dates = []

    for pattern in DATE_PATTERNS:

        matches = re.findall(pattern, text, flags=re.IGNORECASE)

        for match in matches:

            parsed = parse_date_string(match)

            if parsed:
                dates.append(parsed)

    # Remove duplicates
    unique_dates = sorted(
        set(dates),
        reverse=True
    )

    return unique_dates


# ============================================================
# EFFECTIVE DATE EXTRACTION
# ============================================================

EFFECTIVE_DATE_PATTERNS = [

    r"(?:with effect from|effective from|effective|"
    r"with effect|from)\s+"
    r"(\d{1,2}\s+"
    r"(?:January|February|March|April|May|June|July|August|September|"
    r"October|November|December)\s+\d{4})",

    r"(?:with effect from|effective from|effective|"
    r"with effect|from)\s+"
    r"((?:January|February|March|April|May|June|July|August|September|"
    r"October|November|December)\s+\d{1,2},\s+\d{4})",

    r"(?:from)\s+(\d{1,2}/\d{1,2}/\d{4})",

    r"(?:from)\s+(\d{4}-\d{2}-\d{2})",
]


def extract_effective_dates(text: str) -> list[datetime]:

    dates = []

    text_lower = text.lower()

    for pattern in EFFECTIVE_DATE_PATTERNS:

        matches = re.findall(
            pattern,
            text_lower,
            flags=re.IGNORECASE
        )

        for match in matches:

            parsed = parse_date_string(match)

            if parsed:
                dates.append(parsed)

    return sorted(
        set(dates),
        reverse=True
    )


# ============================================================
# WEB PAGE SCRAPER
# ============================================================

def scrape_page(url: str) -> Optional[dict]:

    try:

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT
        )

        response.raise_for_status()

    except requests.RequestException as exc:

        print(f"[SCRAPER] Failed: {url}")
        print(f"[SCRAPER] Error: {exc}")

        return None


    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )


    # --------------------------------------------------------
    # Remove irrelevant HTML
    # --------------------------------------------------------

    for tag in soup([
        "script",
        "style",
        "noscript",
        "nav",
        "footer",
        "header",
        "svg"
    ]):

        tag.decompose()


    # --------------------------------------------------------
    # Extract metadata
    # --------------------------------------------------------

    metadata = {}

    for meta in soup.find_all("meta"):

        name = (
            meta.get("name")
            or meta.get("property")
            or ""
        ).lower()

        content = meta.get("content")

        if content:

            if any(
                keyword in name
                for keyword in [
                    "date",
                    "published",
                    "modified",
                    "updated"
                ]
            ):

                metadata[name] = content


    # --------------------------------------------------------
    # Extract title
    # --------------------------------------------------------

    title = ""

    if soup.title:

        title = soup.title.get_text(
            " ",
            strip=True
        )


    # --------------------------------------------------------
    # Preserve tables
    # --------------------------------------------------------

    tables = []

    for table in soup.find_all("table"):

        rows = []

        for row in table.find_all("tr"):

            cells = []

            for cell in row.find_all(
                ["th", "td"]
            ):

                text = cell.get_text(
                    " ",
                    strip=True
                )

                if text:
                    cells.append(text)

            if cells:
                rows.append(" | ".join(cells))

        if rows:

            tables.append(
                "\n".join(rows)
            )


    # --------------------------------------------------------
    # Main text
    # --------------------------------------------------------

    text = soup.get_text(
        "\n",
        strip=True
    )

    # Clean excessive whitespace
    text = re.sub(
        r"\n{3,}",
        "\n\n",
        text
    )

    text = re.sub(
        r"[ \t]{2,}",
        " ",
        text
    )


    # --------------------------------------------------------
    # Dates
    # --------------------------------------------------------

    dates = extract_dates(text)

    effective_dates = extract_effective_dates(
        text
    )


    # --------------------------------------------------------
    # Metadata dates
    # --------------------------------------------------------

    metadata_dates = []

    for value in metadata.values():

        parsed = parse_date_string(
            value
        )

        if parsed:
            metadata_dates.append(parsed)


    all_dates = sorted(
        set(
            dates
            + metadata_dates
        ),
        reverse=True
    )


    publication_date = (
        all_dates[0]
        if all_dates
        else None
    )


    # --------------------------------------------------------
    # Determine official domain
    # --------------------------------------------------------

    domain = urlparse(
        url
    ).netloc.lower()

    is_official = (
        domain.endswith("hdb.gov.sg")
        or domain.endswith("cpf.gov.sg")
        or domain.endswith("gov.sg")
    )


    # --------------------------------------------------------
    # Combine text + tables
    # --------------------------------------------------------

    if tables:

        text += (
            "\n\n"
            "===== TABLE DATA =====\n"
            + "\n\n".join(tables)
        )


    text = text[:MAX_CONTENT_LENGTH]


    return {

        "url": url,

        "title": title,

        "text": text,
        "content": text,

        "domain": domain,

        "is_official": is_official,

        "publication_date": (
            publication_date.strftime("%Y-%m-%d")
            if publication_date
            else "Not specified"
        ),

        "last_updated": (
            publication_date.strftime("%Y-%m-%d")
            if publication_date
            else "Not specified"
        ),

        "effective_date": (
            effective_dates[0].strftime("%Y-%m-%d")
            if effective_dates
            else "Not specified"
        ),

        "metadata": metadata,

        "source_type": (
            "Official Government Source"
            if is_official
            else "Unofficial Public Source"
        ),
    }


# ============================================================
# SEARCH WEB
# ============================================================

def search_web(
    user_query: str,
    domains: Optional[list[str]] = None,
    max_results: int = SEARCH_RESULTS_LIMIT
) -> list[dict]:

    """
    Search the web for additional sources.

    Uses DuckDuckGo if available.

    Returns:
        [
            {
                "title": ...,
                "url": ...,
                "snippet": ...
            }
        ]
    """

    try:

        from duckduckgo_search import DDGS

    except ImportError:

        print(
            "[SEARCH] duckduckgo_search not installed."
        )

        return []


    results = []


    try:

        with DDGS() as ddgs:

            search_query = user_query

            if domains:

                domain_filter = " OR ".join(
                    f"site:{domain}"
                    for domain in domains
                )

                search_query = (
                    f"{user_query} "
                    f"({domain_filter})"
                )


            search_results = ddgs.text(
                search_query,
                max_results=max_results
            )


            for result in search_results:

                results.append({

                    "title": result.get(
                        "title",
                        ""
                    ),

                    "url": result.get(
                        "href",
                        ""
                    ),

                    "snippet": result.get(
                        "body",
                        ""
                    ),
                })


    except Exception as exc:

        print(
            f"[SEARCH] Search failed: {exc}"
        )


    return results


# ============================================================
# OFFICIAL URL SELECTION
# ============================================================

def get_priority_policy_urls(
    user_query: str
) -> list[dict]:

    categories = detect_policy_categories(
        user_query
    )

    urls = []


    # --------------------------------------------------------
    # Known official sources
    # --------------------------------------------------------

    for category in categories:

        if category not in POLICY_SOURCES:
            continue

        for source in POLICY_SOURCES[
            category
        ]["priority_urls"]:

            source_copy = dict(source)

            source_copy[
                "category"
            ] = category

            urls.append(
                source_copy
            )


    # --------------------------------------------------------
    # Search for NEW official information
    # --------------------------------------------------------

    for category in categories:

        if category not in POLICY_SOURCES:
            continue

        domains = POLICY_SOURCES[
            category
        ]["domains"]


        search_queries = [

            f"{user_query} latest 2026",

            f"{user_query} current 2026",

            f"{user_query} revised 2026",

            f"{user_query} announcement 2026",

        ]


        for query in search_queries:

            results = search_web(
                query,
                domains=domains,
                max_results=5
            )


            for result in results:

                url = result.get(
                    "url",
                    ""
                )

                if not url:
                    continue


                # Only accept official domain
                domain = urlparse(
                    url
                ).netloc.lower()


                if not any(
                    domain.endswith(
                        official_domain
                    )
                    for official_domain in domains
                ):
                    continue


                urls.append({

                    "url": url,

                    "title": result.get(
                        "title",
                        ""
                    ),

                    "priority": 80,

                    "category": category,

                    "search_snippet": result.get(
                        "snippet",
                        ""
                    ),
                })


    # --------------------------------------------------------
    # Remove duplicate URLs
    # --------------------------------------------------------

    unique = {}

    for source in urls:

        url = source["url"]

        if url not in unique:

            unique[url] = source

        else:

            # Keep higher priority
            if (
                source.get("priority", 0)
                >
                unique[url].get(
                    "priority",
                    0
                )
            ):

                unique[url] = source


    return list(
        unique.values()
    )


# ============================================================
# SCRAPE OFFICIAL SOURCES
# ============================================================

def scrape_official_sources(
    user_query: str
) -> list[dict]:

    source_urls = get_priority_policy_urls(
        user_query
    )

    sources = []


    for source_info in source_urls:

        url = source_info["url"]

        print(
            f"[SCRAPER] Checking: {url}"
        )

        source = scrape_page(
            url
        )

        if not source:
            continue


        # Add category
        source[
            "category"
        ] = source_info.get(
            "category",
            "general"
        )


        # Preserve configured priority
        source[
            "priority"
        ] = source_info.get(
            "priority",
            50
        )


        # Search snippet can be useful
        source[
            "search_snippet"
        ] = source_info.get(
            "search_snippet",
            ""
        )


        sources.append(
            source
        )

        # Avoid hammering websites
        time.sleep(0.3)


    return rank_sources(
        sources
    )


# ============================================================
# UNOFFICIAL SOURCES
# ============================================================

def scrape_unofficial_sources(
    user_query: str
) -> list[dict]:

    """
    Community sources are supplementary only.

    They NEVER determine official policy figures.
    """

    results = search_web(
        user_query,
        domains=[
            "reddit.com",
            "hardwarezone.com.sg"
        ],
        max_results=5
    )


    sources = []


    for result in results:

        url = result.get(
            "url",
            ""
        )

        if not url:
            continue


        source = scrape_page(
            url
        )

        if not source:
            continue


        source[
            "source_type"
        ] = "Unofficial Public Source"

        source[
            "is_official"
        ] = False

        source[
            "priority"
        ] = 10


        sources.append(
            source
        )

    return sources


def scrape_sources(urls: list[str]) -> list[dict]:
    sources = []
    for url in urls:
        src = scrape_page(url)
        if src:
            sources.append(src)
    return sources


def match_policy_urls(question: str) -> tuple[list[str], list[str]]:
    official_objs = get_priority_policy_urls(question)
    official_urls = [o["url"] for o in official_objs if "url" in o]
    unofficial_objs = scrape_unofficial_sources(question) if isinstance(question, str) else []
    community_urls = [u["url"] for u in unofficial_objs if isinstance(u, dict) and "url" in u]
    return official_urls, community_urls


# ============================================================
# SOURCE RANKING
# ============================================================

def source_date(
    source: dict
) -> datetime:

    date_string = source.get(
        "publication_date",
        ""
    )

    parsed = parse_date_string(
        date_string
    )

    if parsed:
        return parsed


    return datetime.min


def effective_date(
    source: dict
) -> datetime:

    date_string = source.get(
        "effective_date",
        ""
    )

    parsed = parse_date_string(
        date_string
    )

    if parsed:
        return parsed


    return datetime.min


def rank_sources(
    sources: list[dict]
) -> list[dict]:

    """
    Rank sources.

    Priority order:

    1. Official source
    2. Explicit source priority
    3. Effective date
    4. Publication date

    This prevents an old Reddit post from beating
    a new government announcement.
    """

    return sorted(
        sources,

        key=lambda source: (

            1
            if source.get(
                "is_official",
                False
            )
            else 0,

            source.get(
                "priority",
                0
            ),

            effective_date(
                source
            ),

            source_date(
                source
            ),
        ),

        reverse=True
    )


# ============================================================
# CONFLICT DETECTION
# ============================================================

def find_conflicting_sources(
    sources: list[dict]
) -> list[dict]:

    """
    Find official sources that may contain different
    policy figures.

    We don't decide which number is correct here.
    We expose the conflict to the Query Agent.
    """

    official_sources = [
        source
        for source in sources
        if source.get(
            "is_official",
            False
        )
    ]


    conflicts = []


    # Look for common policy numbers
    number_pattern = re.compile(
        r"\$[\d,]+"
    )


    for source in official_sources:

        numbers = number_pattern.findall(
            source.get(
                "text",
                ""
            )
        )


        if numbers:

            source_copy = dict(
                source
            )

            source_copy[
                "policy_numbers_found"
            ] = list(
                dict.fromkeys(
                    numbers
                )
            )

            conflicts.append(
                source_copy
            )


    return conflicts


# ============================================================
# BUILD SEARCH INTELLIGENCE
# ============================================================

def build_search_intelligence(
    user_query: str,
    include_unofficial: bool = True
) -> dict:

    """
    Main function for the Query Agent.

    Call this function with the user's question.

    Example:

        result = build_search_intelligence(
            "What is the current BTO income ceiling?"
        )
    """

    print(
        "\n========================================"
    )

    print(
        f"SEARCH QUERY: {user_query}"
    )

    print(
        "========================================\n"
    )


    categories = detect_policy_categories(
        user_query
    )


    print(
        f"[SEARCH] Categories: {categories}"
    )


    # --------------------------------------------------------
    # Official sources
    # --------------------------------------------------------

    official_sources = scrape_official_sources(
        user_query
    )


    # --------------------------------------------------------
    # Unofficial sources
    # --------------------------------------------------------

    unofficial_sources = []

    if include_unofficial:

        unofficial_sources = (
            scrape_unofficial_sources(
                user_query
            )
        )


    # --------------------------------------------------------
    # Combine
    # --------------------------------------------------------

    all_sources = (
        official_sources
        + unofficial_sources
    )


    all_sources = rank_sources(
        all_sources
    )


    # --------------------------------------------------------
    # Conflicts
    # --------------------------------------------------------

    conflicts = find_conflicting_sources(
        all_sources
    )


    # --------------------------------------------------------
    # Separate official / unofficial
    # --------------------------------------------------------

    official_ranked = [
        source
        for source in all_sources
        if source.get(
            "is_official",
            False
        )
    ]


    unofficial_ranked = [
        source
        for source in all_sources
        if not source.get(
            "is_official",
            False
        )
    ]


    # --------------------------------------------------------
    # Current strongest source
    # --------------------------------------------------------

    current_source = (
        official_ranked[0]
        if official_ranked
        else None
    )


    return {

        "user_query": user_query,

        "categories": categories,

        "current_source": current_source,

        "official_sources": official_ranked,

        "unofficial_sources": unofficial_ranked,

        "conflicting_sources": conflicts,

        "source_count": len(
            all_sources
        ),

        "official_source_count": len(
            official_ranked
        ),

        "unofficial_source_count": len(
            unofficial_ranked
        ),
    }


# ============================================================
# QUERY AGENT SYNTHESIS PROMPT
# ============================================================

SEARCH_SYNTHESIS_PROMPT = """

You are the Search Agent for a Singapore policy
information platform.

Your job is to retrieve CURRENT and VERIFIED policy
information for the Policy Query Agent.

IMPORTANT:

The retrieved sources may contain different numbers
because government policies change over time.

DO NOT simply choose the number that appears most often.

CURRENT POLICY RULES:

1. Official Singapore government sources have priority.

2. A newer official announcement can supersede an older
   official eligibility page.

3. Always check:
   - publication date
   - last updated date
   - effective date
   - phrases such as "from", "with effect from",
     "effective from", "will be raised", "revised"

4. If an official announcement says a new policy takes
   effect on a specific date, use the new figure when
   answering questions about the period after that date.

5. If the user asks "current", determine the policy
   applicable TODAY.

6. Never use Reddit, HardwareZone, or other community
   discussions to determine an official policy figure.

7. Community sources may only be used for:
   - common questions
   - practical experiences
   - public sentiment

8. NEVER invent a number.

9. If official sources conflict:
   - identify the newer source
   - compare effective dates
   - use the policy that is currently applicable
   - mention the older figure only if useful

10. If the current figure cannot be verified, say:

"Current figure could not be verified from the
available official government sources."

RETURN STRUCTURED EVIDENCE:

CURRENT_POLICY:
<short description>

KEY_FIGURES:
- <figure and what it applies to>

EFFECTIVE_DATE:
<date>

SOURCE_TITLE:
<title>

SOURCE_URL:
<url>

SOURCE_DATE:
<date>

OLDER_CONFLICTING_SOURCE:
<yes/no>

OLDER_VALUE:
<value or N/A>

CONFIDENCE:
HIGH / MEDIUM / LOW

Do not make up missing information.
"""


# ============================================================
# SIMPLE TEST
# ============================================================

if __name__ == "__main__":

    print(
        "Singapore Policy Search Agent"
    )

    print(
        "Type 'quit' to exit.\n"
    )


    while True:

        query = input(
            "Policy question: "
        ).strip()


        if query.lower() == "quit":
            break


        if not query:
            continue


        result = build_search_intelligence(
            query
        )


        print(
            "\n\n========== CURRENT SOURCE ==========\n"
        )


        current = result[
            "current_source"
        ]


        if current:

            print(
                "TITLE:",
                current.get(
                    "title"
                )
            )

            print(
                "URL:",
                current.get(
                    "url"
                )
            )

            print(
                "PUBLICATION DATE:",
                current.get(
                    "publication_date"
                )
            )

            print(
                "EFFECTIVE DATE:",
                current.get(
                    "effective_date"
                )
            )

            print(
                "\nSOURCE TEXT:\n"
            )

            print(
                current.get(
                    "text",
                    ""
                )[:10000]
            )

        else:

            print(
                "No official source found."
            )


        print(
            "\n\n========== SOURCE COUNTS ==========\n"
        )

        print(
            "Official:",
            result[
                "official_source_count"
            ]
        )

        print(
            "Unofficial:",
            result[
                "unofficial_source_count"
            ]
        )

        print(
            "Total:",
            result[
                "source_count"
            ]
        )

        print(
            "\n====================================\n"
        )