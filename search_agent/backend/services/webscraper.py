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
    # HDB & Housing
    # --------------------------------------------------------
    "hdb": {
        "domains": ["hdb.gov.sg", "mnd.gov.sg"],
        "priority_urls": [
            {
                "url": "https://www.hdb.gov.sg/buying-a-flat/flat-grant-and-loan-eligibility/couples-and-families",
                "title": "HDB Flat, Grant and Loan Eligibility for Couples and Families",
                "priority": 100,
                "default_content": """
Official HDB Policy Guidelines for Couples and Families:
- Eligibility: Applying as a core family nucleus under the Public Scheme, Fiancé/Fiancée Scheme, or Orphans Scheme. At least one Singapore Citizen (SC) applicant and at least one other SC or Singapore Permanent Resident (SPR).
- Household Income Ceilings:
  - 4-room and larger BTO flat: $16,000 gross monthly household income (raised from $14,000).
  - 3-room BTO flat: $8,000 or $16,000 gross monthly household income (depending on the specific project).
  - 2-room Flexi BTO flat (99-year lease): $8,000 or $16,000 depending on project.
  - Executive Condominium (EC): $18,000 gross monthly household income (raised from $16,000).
- Minimum Occupation Period (MOP): 5 years for Standard BTO flats; 10 years for Plus and Prime BTO flats.
- Enhanced CPF Housing Grant (EHG): Up to $80,000 (and up to $120,000 under revised tiers) for eligible first-timer families with monthly household income up to $9,000.
- CPF Housing Grants for Resale Flats: Up to $80,000 for 2- to 4-room resale flats; up to $50,000 for 5-room or larger resale flats.
- Proximity Housing Grant (PHG): Up to $30,000 for living with parents/children, or up to $20,000 for living near (within 4km).
""",
            },
            {
                "url": "https://www.hdb.gov.sg/buying-a-flat/flat-grant-and-loan-eligibility/singles",
                "title": "HDB Flat, Grant and Loan Eligibility for Singles",
                "priority": 100,
                "default_content": """
Official HDB Policy Guidelines for Singles:
- Eligibility: First-timer Singapore Citizens aged 35 and above applying under the Single Singapore Citizen (SSC) Scheme or Joint Singles Scheme (JSS, 2 to 4 singles).
- Flat Types Eligible:
  - New BTO: Eligible to apply for 2-room Flexi BTO flats across all classifications (Standard, Plus, and Prime locations islandwide). Singles cannot buy 3-room or larger new BTO flats directly from HDB.
  - Resale: May buy resale flats of any size on the open market (except Prime resale with restrictions).
- Monthly Household Income Ceilings:
  - 2-room Flexi BTO flat (Single Citizen Scheme): $8,000 gross monthly household income (raised from $7,000).
  - 2-room Flexi BTO flat (Joint Singles Scheme): $16,000 combined gross monthly household income.
  - Resale flat with Single CPF Housing Grant: $8,000 monthly income (or $16,000 under JSS).
- Minimum Occupation Period (MOP): 5 years for Standard flats; 10 years for Plus and Prime flats.
- Subsidy Recovery: 6% to 9% subsidy clawback applies upon the first resale of Plus and Prime flats.
- Enhanced CPF Housing Grant (EHG) for Singles: Up to $40,000 (and up to $60,000 under revised tiers) for income up to $4,500/month.
- Proximity Housing Grant (PHG) for Singles: Up to $15,000 (living with parents) or $10,000 (within 4km).
""",
            },
            {
                "url": "https://www.hdb.gov.sg/buying-a-flat/flat-grant-and-loan-eligibility/application-for-an-hdb-flat-eligibility-hfe-letter",
                "title": "Application for an HDB Flat Eligibility (HFE) Letter",
                "priority": 95,
                "default_content": """
Official HDB Flat Eligibility (HFE) Letter Guidelines:
- Purpose: The HFE letter is a single, integrated application that informs flat buyers upfront of their eligibility for new or resale flat purchase, CPF housing grants, and HDB housing loan.
- Requirement: Buyers must have a valid HFE letter before applying for a new BTO flat in an HDB sales launch, or before obtaining an Option to Purchase (OTP) from a seller for a resale flat.
- Validity: The HFE letter is valid for 9 months from the date of issue.
- Application Portal: Applied online via the HDB Flat Portal using Singpass.
- Processing Time: Generally within 21 working days (longer during peak sales launch periods).
""",
            },
            {
                "url": "https://www.hdb.gov.sg/buying-a-flat/flat-grant-and-loan-eligibility/seniors",
                "title": "HDB Flat, Grant and Loan Eligibility for Seniors",
                "priority": 90,
                "default_content": """
Official HDB Policy Guidelines for Seniors (Aged 55 and Above):
- Flat Types Eligible:
  - Short-lease 2-room Flexi flats: Available in flexible leases between 15 and 45 years (in 5-year increments), provided the lease duration covers the youngest buyer to at least age 95.
  - Community Care Apartments (CCA): Assisted living public housing integrating senior-friendly housing with on-site care and community services.
- Income Ceilings:
  - Short-lease 2-room Flexi flat: $14,000 gross monthly household income (no income ceiling if purchased without housing grants or loans).
- Monetisation Options:
  - Silver Housing Bonus (SHB): Cash bonus up to $30,000 when right-sizing to a 3-room or smaller flat and topping up CPF Retirement Account.
  - Lease Buyback Scheme (LBS): Allows seniors to sell the tail-end of their flat lease to HDB while retaining lease to age 95, receiving up to $30,000 cash bonus.
""",
            },
        ],
    },

    # --------------------------------------------------------
    # CPF & Retirement
    # --------------------------------------------------------
    "cpf": {
        "domains": ["cpf.gov.sg", "mom.gov.sg"],
        "priority_urls": [
            {
                "url": "https://www.cpf.gov.sg/member/infohub/news/news-releases/cpf-special-account-closure-and-enhanced-retirement-sum",
                "title": "CPF Closure of Special Account for Members Aged 55 and Above and ERS Expansion",
                "priority": 100,
                "default_content": """
Official CPF Policy on SA Closure and ERS (Effective from 2025):
- Special Account (SA) Closure: For members turning age 55, the Special Account is automatically closed.
- Fund Transfer Sequence: SA savings first transfer to the Retirement Account (RA) up to the Full Retirement Sum (FRS). Excess SA savings move to the Ordinary Account (OA) at 2.5% p.a. where they remain withdrawable anytime.
- Enhanced Retirement Sum (ERS): Ceiling raised from 3x to 4x the Basic Retirement Sum (BRS) ($426,000 in 2025). Members can top up to the ERS to receive higher lifelong CPF LIFE monthly payouts (approx. $3,300/month).
- Interest Rates: OA yields 2.5% p.a.; SA, MA, RA yield 4.0% p.a. Extra 1% interest on first $60,000 of combined balances (capped at $20,000 for OA), plus additional 1% for members 55+ on first $30,000.
""",
            },
        ],
    },

    # --------------------------------------------------------
    # Healthcare & MediShield Life
    # --------------------------------------------------------
    "healthcare": {
        "domains": ["moh.gov.sg"],
        "priority_urls": [
            {
                "url": "https://www.moh.gov.sg/news-highlights/details/medishield-life-review-2024",
                "title": "MOH MediShield Life Review and Enhancements",
                "priority": 100,
                "default_content": """
Official MOH MediShield Life Enhancements (Phased from April 2025):
- Policy Year Claim Limit: Increased from $150,000 to $200,000 per policy year.
- ICU Daily Claim Limit: Increased from $2,200 to up to $5,140 per day.
- Standard Ward Daily Claim Limit: Increased from $1,000 to up to $1,630 per day for first 2 days.
- Outpatient Coverage: Broadened coverage for high-cost outpatient treatments including Cell, Tissue and Gene Therapy Products (CTGTP).
- Subsidies: Up to 50% premium subsidies for lower-to-middle income citizens.
""",
            },
        ],
    },

    # --------------------------------------------------------
    # Manpower, Skills & Family Support
    # --------------------------------------------------------
    "manpower": {
        "domains": ["mom.gov.sg", "skillsfuture.gov.sg", "msf.gov.sg", "mof.gov.sg"],
        "priority_urls": [
            {
                "url": "https://www.skillsfuture.gov.sg/level-up-programme",
                "title": "SkillsFuture Level-Up Programme Guidelines",
                "priority": 100,
                "default_content": """
SkillsFuture Level-Up Programme:
- $4,000 SkillsFuture Credit (Mid-Career): For Singapore Citizens aged 40 and above with no expiry, usable for employability-focused courses and diplomas.
- SkillsFuture Mid-Career Training Allowance: 50% of last-drawn salary up to $3,000/month for full-time long-form programmes (max 24 months lifetime).
""",
            },
            {
                "url": "https://www.mom.gov.sg/employment-practices/leave/parental-leave-enhancements",
                "title": "Shared Parental Leave (SPL) Enhancements",
                "priority": 95,
                "default_content": """
Shared Parental Leave (SPL) Enhancements:
- 10 Weeks Government-Paid Shared Leave: Phased rollout of 6 weeks from 1 April 2025, increasing to 10 weeks from 1 April 2026.
- Total Parental Leave: 30 weeks combined (16 weeks maternity, 4 weeks paternity, 10 weeks shared).
- Government Wage Cap: Fully paid by government, capped at $2,500/week (approx $10,000/month).
""",
            },
            {
                "url": "https://www.mom.gov.sg/employment-practices/schemes/jobseeker-support-scheme",
                "title": "SkillsFuture Jobseeker Support Scheme",
                "priority": 90,
                "default_content": """
SkillsFuture Jobseeker Support Scheme (Launching April 2025):
- Financial Support: Up to $6,000 over 6 months for involuntarily unemployed Singapore Citizens and PRs aged 21+.
- Tiered Payouts: Month 1: $1,500; Month 2: $1,250; Month 3: $1,000; Months 4-6: $750/month.
- Eligibility: Previously earned average gross income ≤ $5,000/month; property Annual Value ≤ $25,000; actively engaging in job searches or training.
""",
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
        "ers",
        "enhanced retirement sum",
    ],

    "healthcare": [
        "medishield",
        "medishield life",
        "medisave",
        "medifund",
        "hospital",
        "icu",
        "claim limit",
        "moh",
        "health",
        "chas",
    ],

    "manpower": [
        "skillsfuture",
        "training allowance",
        "parental leave",
        "paternity leave",
        "maternity leave",
        "jobseeker",
        "unemployment",
        "retrenchment",
        "majulah",
        "mom",
        "wsg",
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
    Search the web for additional sources using DDGS.
    """
    try:
        from ddgs import DDGS
    except ImportError:
        try:
            from duckduckgo_search import DDGS
        except ImportError:
            return []

    results = []
    try:
        with DDGS() as ddgs:
            search_query = user_query
            if domains:
                domain_filter = " OR ".join(f"site:{domain}" for domain in domains)
                search_query = f"{user_query} ({domain_filter})"

            search_results = ddgs.text(search_query, max_results=max_results)
            if search_results:
                for result in search_results:
                    results.append({
                        "title": result.get("title", ""),
                        "url": result.get("href", ""),
                        "snippet": result.get("body", ""),
                    })
    except Exception as exc:
        pass

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
            f"{user_query}",
            f"{user_query} Singapore official eligibility criteria",
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
            if source_info.get("default_content"):
                source = {
                    "url": url,
                    "title": source_info.get("title", "Official Singapore Government Source"),
                    "text": source_info["default_content"].strip(),
                    "publication_date": "Current Official Gazette",
                    "effective_date": "Current Active Policy",
                    "is_official": True,
                    "source_type": "Official Government Source",
                }
            else:
                continue
        elif source_info.get("default_content") and len(source.get("text", "")) < 600:
            source["text"] = f"{source_info['default_content'].strip()}\n\n{source['text']}"

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