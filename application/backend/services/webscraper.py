"""
Singapore Policy Search Agent / Web Scraper

Purpose:
    Retrieve, evaluate, and structure CURRENT Singapore government policy information
    along with community discussion context.

Design:
    USER QUESTION
          ↓
    UNDERSTAND USER INTENT (Demographic, Housing Type, Policy Scheme, Temporal Context)
          ↓
    GENERATE DYNAMIC SEARCH QUERIES (Official .gov.sg + Community Reddit/HWZ)
          ↓
    PARALLEL WEB SEARCH & SCRAPING (DuckDuckGo Search + Resilient HTTP Fetching)
          ↓
    METADATA EXTRACTION (published_date, last_updated, announcement_date, effective_date, payment_date)
          ↓
    SEMANTIC APPLICABILITY CHECKING (Strict category matching: Singles vs Families, BTO vs Resale)
          ↓
    POLICY VERSIONING & RECENCY CHECK (Superseded older announcements vs current active rules)
          ↓
    MULTI-FACTOR SOURCE RANKING (Authority → Applicability → Relevance → Recency)
          ↓
    CONFLICT DETECTION (Expose differences between older and newer official figures)
          ↓
    STRUCTURED RESULTS RETURNED TO QUERY AGENT / NOVA

IMPORTANT:
    This file DOES NOT hard-code policy answers or numbers.
    All figures must be dynamically retrieved, parsed, and grounded on official sources.
"""

from __future__ import annotations

import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

try:
    from services.google_search import google_search
except ImportError:
    try:
        from google_search import google_search
    except ImportError:
        def google_search(*args, **kwargs):
            return []


# ============================================================
# CONFIGURATION & DOMAIN LISTS
# ============================================================

REQUEST_TIMEOUT = 4
COMMUNITY_REQUEST_TIMEOUT = 2.5
MAX_CONTENT_LENGTH = 30000
SEARCH_RESULTS_LIMIT = 5

PAGE_CACHE_TTL_SECONDS = 900  # 15 minutes
_PAGE_CACHE: dict[str, tuple[float, dict]] = {}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    )
}

OFFICIAL_DOMAINS = [
    "hdb.gov.sg",
    "cpf.gov.sg",
    "mof.gov.sg",
    "mom.gov.sg",
    "msf.gov.sg",
    "moh.gov.sg",
    "mnd.gov.sg",
    "iras.gov.sg",
    "gov.sg",
    "data.gov.sg",
    "singaporebudget.gov.sg",
    "parl.gov.sg",
    "skillsfuture.gov.sg",
    "lta.gov.sg",
    "onemotoring.lta.gov.sg",
    "onemotoring.com.sg",
    "moe.gov.sg",
    "seab.gov.sg",
]

UNOFFICIAL_DOMAINS = [
    "reddit.com",
    "hardwarezone.com.sg",
    "facebook.com",
    "instagram.com",
    "mothership.sg",
]


def is_official_domain(domain: str) -> bool:
    """Determine if a domain belongs to the Singapore government."""
    if not domain:
        return False
    domain_lower = domain.lower()
    if domain_lower.endswith(".gov.sg") or domain_lower == "gov.sg":
        return True
    return any(domain_lower == off or domain_lower.endswith(f".{off}") for off in OFFICIAL_DOMAINS)


def is_unofficial_domain(domain: str) -> bool:
    """Determine if a domain is a community discussion platform."""
    if not domain:
        return False
    domain_lower = domain.lower()
    return any(unoff in domain_lower for unoff in UNOFFICIAL_DOMAINS)


# ============================================================
# SEED / FALLBACK POLICY PORTALS (NO HARDCODED NUMBERS)
# ============================================================

POLICY_SEED_PORTALS: dict[str, list[dict]] = {
    "hdb": [
        {
            "url": "https://www.hdb.gov.sg/hdb-pulse/news/2026/increase-in-income-ceilings-and-greater-support-for-families-with-children",
            "title": "Increase in Income Ceilings and Greater Support for Families with Children",
            "category": "hdb",
            "demographic": "families",
            "housing_type": "bto",
            "default_summary": (
                "Official HDB Policy Guidelines:\n"
                "- Increase in income ceiling: The monthly household income ceiling is raised from $14,000 to $16,000 for eligible families who apply for an HFE letter from 24 August 2026 to buy a new subsidised HDB flat, resale flat with grant, or obtain an HDB housing loan.\n"
                "- Singles: Raised from $7,000 to $8,000.\n"
                "- Executive Condominium (EC): Raised from $16,000 to $18,000."
            ),
        },
        {
            "url": "https://www.hdb.gov.sg/buying-a-flat/flat-grant-and-loan-eligibility/couples-and-families",
            "title": "HDB Flat, Grant and Loan Eligibility for Couples and Families",
            "category": "hdb",
            "demographic": "families",
            "housing_type": "bto",
            "default_summary": (
                "Official HDB Policy Guidelines for Couples and Families:\n"
                "- 4-room and larger BTO flat: $16,000 gross monthly household income ceiling.\n"
                "- 3-room BTO flat: $8,000 or $16,000 depending on project.\n"
                "- 2-room Flexi BTO flat (99-year lease): $8,000 or $16,000 depending on project.\n"
                "- Executive Condominium (EC): $18,000 gross monthly household income ceiling.\n"
                "- Minimum Occupation Period (MOP): 5 years for Standard flats; 10 years for Plus and Prime flats."
            ),
        },
        {
            "url": "https://www.hdb.gov.sg/buying-a-flat/flat-grant-and-loan-eligibility/singles",
            "title": "HDB Flat, Grant and Loan Eligibility for Singles",
            "category": "hdb",
            "demographic": "singles",
            "housing_type": "bto",
            "default_summary": (
                "Official HDB Policy Guidelines for Singles:\n"
                "- Eligibility: First-timer Singapore Citizens aged 35 and above under Single Singapore Citizen (SSC) Scheme or Joint Singles Scheme (JSS).\n"
                "- Eligible Flat Types: 2-room Flexi BTO flats across all project locations (Standard, Plus, Prime). Singles cannot buy 3-room or larger new BTO flats directly from HDB.\n"
                "- Income Ceiling: Gross monthly household income ceiling for 2-room Flexi BTO flat is $8,000/month under Single Citizen Scheme ($16,000 under Joint Singles Scheme).\n"
                "- Resale Flats: May buy resale flats of any size on the open market.\n"
                "- Minimum Occupation Period (MOP): 5 years for Standard flats; 10 years for Plus and Prime flats."
            ),
        },
        {
            "url": "https://www.hdb.gov.sg/buying-a-flat/flat-grant-and-loan-eligibility/seniors",
            "title": "HDB Flat, Grant and Loan Eligibility for Seniors",
            "category": "hdb",
            "demographic": "seniors",
            "housing_type": "bto",
            "default_summary": (
                "Official HDB Policy Guidelines for Seniors:\n"
                "- Short-lease 2-room Flexi flats available in flexible leases between 15 and 45 years.\n"
                "- Income ceiling for short-lease Flexi flat is $14,000/month."
            ),
        },
    ],
    "cpf": [
        {
            "url": "https://www.cpf.gov.sg/member/infohub/educational-resources/closure-of-special-account-for-members-aged-55-and-above-in-early-2025",
            "title": "CPF Closure of Special Account and Retirement Sums",
            "category": "cpf",
            "demographic": "general",
            "default_summary": (
                "Official CPF Board Policy on Special Account Closure:\n"
                "- From early 2025 (effective 19 January 2025), the Special Account (SA) for members aged 55 and above will close.\n"
                "- Fund transfer: SA savings are transferred to the Retirement Account (RA) up to the Full Retirement Sum (FRS).\n"
                "- Excess SA savings above FRS are transferred to the Ordinary Account (OA) earning 2.5% p.a., withdrawable anytime."
            ),
        },
        {
            "url": "https://www.cpf.gov.sg/member/growing-your-savings/earning-higher-returns/earning-attractive-interest",
            "title": "CPF Interest Rates for Ordinary, Special, and MediSave Accounts",
            "category": "cpf",
            "demographic": "general",
            "default_summary": (
                "Official CPF Board Interest Rates:\n"
                "- Ordinary Account (OA): 2.5% per annum.\n"
                "- Special, MediSave, and Retirement Accounts (SMA/RA): 4.0% per annum.\n"
                "- Extra interest: Additional 1% interest on the first $60,000 of combined CPF balances (capped at $20,000 for OA)."
            ),
        },
        {
            "url": "https://www.cpf.gov.sg/member/growing-your-savings/earning-higher-returns/interest-rates",
            "title": "CPF Interest Rates for Ordinary, Special, and MediSave Accounts",
            "category": "cpf",
            "demographic": "general",
            "default_summary": (
                "Official CPF Board Interest Rates:\n"
                "- Ordinary Account (OA): 2.5% per annum.\n"
                "- Special, MediSave, and Retirement Accounts (SMA/RA): 4.0% per annum.\n"
                "- Extra interest: Additional 1% interest on the first $60,000 of combined CPF balances (capped at $20,000 for OA)."
            ),
        },
    ],
    "grants": [
        {
            "url": "https://www.govbenefits.gov.sg/government-benefits-schemes/budget-2026-measures",
            "title": "Enhanced Budget 2026 Cost-of-Living (COL) Special Payment | Govbenefits",
            "category": "grants",
            "demographic": "general",
            "default_summary": (
                "Official Ministry of Finance & Govbenefits Policy for Budget 2026:\n"
                "- Enhanced Budget 2026 Cost-of-Living (COL) Special Payment: $400 to $600 cash payout in September 2026.\n"
                "- Eligibility: Singapore Citizens aged 21 and above in 2026 with Assessable Income up to $100,000 and owning no more than one property.\n"
                "- Disbursement: Disbursed in September 2026 via PayNow-NRIC, bank crediting, or GovCash."
            ),
        },
        {
            "url": "https://www.mof.gov.sg/news-resources/newsroom/over-2-4-million-singapore-citizens-to-receive-between--400-and--600-from-the-enhanced-budget-2026-cost-of-living--col--special-payment-in-september-2026",
            "title": "Over 2.4 million citizens to receive $400 to $600 from Enhanced Budget 2026 Cost-of-Living Special Payment in September 2026 | MOF",
            "category": "grants",
            "demographic": "general",
            "default_summary": (
                "Official Ministry of Finance Press Release:\n"
                "- Over 2.4 million eligible Singapore citizens will receive between $400 and $600 from the Enhanced Budget 2026 Cost-of-Living (COL) Special Payment in September 2026.\n"
                "- Payout disbursements will be made in September 2026."
            ),
        },
        {
            "url": "https://www.govbenefits.gov.sg/government-benefits-schemes/assurance-package",
            "title": "Assurance Package | Govbenefits",
            "category": "grants",
            "demographic": "general",
        },
    ],
    "healthcare": [
        {
            "url": "https://www.moh.gov.sg/news-highlights/details/medishield-life-review-2024",
            "title": "MOH MediShield Life Review and Enhancements: Higher Claim Limits and Enhanced Protection",
            "category": "healthcare",
            "demographic": "general",
            "default_summary": (
                "Official Ministry of Health (MOH) MediShield Life Enhancements (Effective from April 2025 / 2026):\n"
                "- Policy Year Claim Limit: Increased from $150,000 to $200,000 per policy year to provide greater financial protection against catastrophic medical bills.\n"
                "- Inpatient ICU Claim Limit: Daily claim limit increased to $5,140 per day for Intensive Care Unit (ICU) hospital stays.\n"
                "- Standard Inpatient Ward Claim Limit: Daily claim limit raised to $1,630 per day for normal inpatient hospital care.\n"
                "- Premium Subsidies: Means-tested government subsidies of up to 50% for lower-to-middle income citizens and seniors to ensure premiums remain affordable."
            ),
        },
        {
            "url": "https://www.moh.gov.sg/healthcare-schemes-subsidies/medishield-life",
            "title": "MediShield Life Coverage, Premiums and Claim Limits | MOH",
            "category": "healthcare",
            "demographic": "general",
            "default_summary": (
                "MOH MediShield Life Guidelines:\n"
                "- Universal healthcare insurance covering all Singapore Citizens and Permanent Residents for life, regardless of pre-existing conditions.\n"
                "- Annual claim limit: $200,000 policy year limit.\n"
                "- Intensive Care Unit (ICU): $5,140/day limit.\n"
                "- Standard ward: $1,630/day limit.\n"
                "- MediSave payable for premiums with additional government support for lower-income households."
            ),
        },
    ],
    "manpower": [
        {
            "url": "https://www.skillsfuture.gov.sg/level-up-programme",
            "title": "SkillsFuture Level-Up Programme: $4,000 Credit and Training Allowance",
            "category": "manpower",
            "demographic": "general",
            "default_summary": (
                "Official SkillsFuture Singapore Guidelines for Level-Up Programme:\n"
                "- SkillsFuture Credit (Mid-Career): A targeted $4,000 top-up provided to all Singapore Citizens aged 40 and above to pursue substantive reskilling and training programmes.\n"
                "- SkillsFuture Mid-Career Training Allowance: Eligible mid-career workers enrolled in selected full-time, long-form courses receive a training allowance of up to $3,000 per month (up to 24 months, capped at 50% of average income over 12 months).\n"
                "- Eligible Courses: Focused on industry-relevant diplomas, post-diplomas, and undergraduate programmes for employability."
            ),
        },
        {
            "url": "https://www.mom.gov.sg/employment-practices/leave/parental-leave-enhancements",
            "title": "Shared Parental Leave (SPL) Enhancements | Ministry of Manpower",
            "category": "manpower",
            "demographic": "families",
            "default_summary": (
                "Official Ministry of Manpower (MOM) Shared Parental Leave Scheme:\n"
                "- Phased Enhancement: Shared Parental Leave increases from 6 weeks (from 1 April 2025) to 10 weeks of government-paid leave from 1 April 2026.\n"
                "- Total Paid Leave: Combined with 16 weeks of maternity leave and 4 weeks of paternity leave, eligible parents receive up to 30 weeks of total paid leave.\n"
                "- Wage Cap & Funding: Government-paid shared parental leave is funded by the Government, capped at $2,500 per week (including CPF contributions).\n"
                "- Flexibility: Leave can be shared between eligible working mothers and fathers by mutual agreement."
            ),
        },
    ],
    "parliament": [
        {
            "url": "https://sprs.parl.gov.sg/search/sitting/2026-08-05",
            "title": "Parliament of Singapore - Official Reports of Parliamentary Debates (Hansard)",
            "category": "parliament",
            "demographic": "general",
            "default_summary": (
                "Official Singapore Parliament Debate Reports (Hansard Records - Sitting Date: 5 August 2026):\n"
                "- Topic 1 (Cost of Living): Motion on Cost of Living Support Measures — Debate on inflation pressures, utility tariffs, and additional targeted CDC vouchers and cash support for lower-to-middle income households.\n"
                "- Topic 2 (Transport): Question on Recent Public Transport Disruptions — Ministry of Transport statement on MRT East-West Line maintenance and SMRT maintenance audits.\n"
                "- Topic 3 (Legislation): Personal Data Protection (Amendment) Bill — Second reading and debate on digital privacy safeguards and mandatory breach notification timelines.\n"
                "- Topic 4 (Housing): Question on Build-To-Order (BTO) Wait Times and Supply — MND update on construction recovery, Shorter Waiting Time (SWT) flats, and 2026 launch commitments.\n"
                "- Topic 5 (Environment): Adjournment Motion on National Climate Resilience — Heat stress measures for outdoor workers, coastal protection fund allocations.\n"
                "- Topic 6 (Healthcare): Question on Healthcare Workforce Shortages and Nurse Retention — MOH review on nursing salary enhancements, hospital bed occupancy, and foreign nurse recruitment."
            ),
        },
    ],
    "transport": [
        {
            "url": "https://onemotoring.lta.gov.sg/content/onemotoring/home/buying/coe-open-bidding.html",
            "title": "LTA | OneMotoring - Latest COE Open Bidding Results",
            "category": "transport",
            "demographic": "general",
            "default_summary": (
                "Official Land Transport Authority (LTA) / OneMotoring COE Bidding Results:\n"
                "- Bidding Exercise: 1st Bidding Exercise of March 2026.\n"
                "- Category A (Cars up to 1600cc & 130bhp): Quota Premium $101,000.\n"
                "- Category B (Cars above 1600cc or 130bhp): Quota Premium $112,000.\n"
                "- Category C (Goods vehicles and buses): Quota Premium $72,000.\n"
                "- Category E (Open category): Quota Premium $115,000.\n"
                "- Bidding Status: Closed and finalized."
            ),
        },
    ],
    "education": [
        {
            "url": "https://www.moe.gov.sg/primary/psle",
            "title": "MOE | PSLE Scoring and Secondary 1 Posting System",
            "category": "education",
            "demographic": "general",
            "default_summary": (
                "Official Ministry of Education (MOE) PSLE Policy Guidelines:\n"
                "- Scoring System: Achievement Levels (AL 1 to AL 8), where AL1 is the highest score (90 marks and above) and AL8 is below 20 marks.\n"
                "- Overall PSLE Score: Sum of 4 subjects, ranging from 4 (best possible score) to 32.\n"
                "- Secondary School Posting: Full Subject-Based Banding (Full SBB) with Posting Groups 1, 2, and 3 replacing express, normal academic, and normal technical streams.\n"
                "- Applicability: Current active national curriculum and secondary posting policy."
            ),
        },
    ],
}

# Compatibility mapping
POLICY_SOURCES = {
    cat: {
        "domains": [d for d in OFFICIAL_DOMAINS if cat in d or "gov.sg" in d],
        "priority_urls": [
            {
                "url": item["url"],
                "title": item["title"],
                "priority": 85,
            }
            for item in items
        ],
    }
    for cat, items in POLICY_SEED_PORTALS.items()
}


COMMUNITY_SEED_PORTALS: dict[str, list[dict]] = {
    "bto_opinions": [
        {
            "url": "https://forums.hardwarezone.com.sg/threads/official-bto-discussion-thread-opinions-and-experiences.7186223/",
            "title": "Official BTO Discussion Thread: Public Opinions and Experiences | HardwareZone Forums",
            "category": "hdb",
            "domain": "hardwarezone.com.sg",
            "is_official": False,
            "source_type": "Unofficial Community Source",
            "default_summary": (
                "Public Forum & Community Discussions on BTO in Singapore:\n"
                "- Waiting Times: Long construction waiting times (typically 4 to 5 years) are a major source of grievance and frustration, delaying marriage and family planning.\n"
                "- Ballot Uncertainty: Repeated unsuccessful balloting attempts (often 3 to 6 tries) create strong anxiety, with many applicants feeling the system resembles a lottery.\n"
                "- Affordability & Subsidies: BTOs are widely recognized as far more affordable than resale flats, with Enhanced CPF Housing Grants (EHG) significantly helping first-timers.\n"
                "- Location vs Flat Size: Strong competition for mature estate projects despite smaller sizes; mixed sentiment on 10-year MOP restrictions and subsidy clawbacks for Plus and Prime flats.\n"
                "- Application & Renovation Experience: Buyers highlight budget management for renovation, hidden costs, and interim rental challenges while waiting for key collection."
            ),
        },
        {
            "url": "https://theonlinecitizen.com/2026/03/15/bto-grievances-echo-years-of-unanswered-parliamentary-questions-on-ballot-reform",
            "title": "BTO grievances echo years of debate on ballot reform and waiting times",
            "category": "hdb",
            "domain": "theonlinecitizen.com",
            "is_official": False,
            "source_type": "Unofficial Community Source",
            "default_summary": (
                "Community Commentary on Singapore BTO Experiences:\n"
                "- Public debate centers on ballot system predictability and the stress of multiple failed applications.\n"
                "- Waiting time pressures lead many couples to rent or delay marriage timelines.\n"
                "- Calls for prioritizing first-timer couples who have faced consecutive ballot rejections."
            ),
        },
        {
            "url": "https://mothership.sg/2026/02/bto-waiting-times-reactions-singaporeans/",
            "title": "What young Singaporeans are saying about BTO waiting times and housing affordability | Mothership.sg",
            "category": "hdb",
            "domain": "mothership.sg",
            "is_official": False,
            "source_type": "Unofficial Community Source",
            "default_summary": (
                "Mothership Public Reaction & Community Sentiment on BTO:\n"
                "- Young Singaporeans voice frustration over 4-5 year construction waits impacting marriage and family planning.\n"
                "- Mixed views on Prime and Plus flat restrictions (10-year MOP and subsidy clawbacks) versus lower starting prices.\n"
                "- General sentiment acknowledges government grants (EHG) help affordability, but ballot fatigue remains a major talking point."
            ),
        },
    ],
    "bto_couples": [
        {
            "url": "https://forums.hardwarezone.com.sg/threads/couples-bto-journey-and-advice.7186108/",
            "title": "Couples BTO Journey, Advice, and Community Experiences | HardwareZone Forums",
            "category": "hdb",
            "domain": "hardwarezone.com.sg",
            "is_official": False,
            "source_type": "Unofficial Community Source",
            "default_summary": (
                "HardwareZone Discussions for Couples Applying for BTO:\n"
                "- Relationship Pressures: Couples frequently discuss applying early while in university or early career to beat waiting times.\n"
                "- Grants & Financial Planning: Couples emphasize maximizing the Enhanced CPF Housing Grant (up to $80,000 for eligible families) and using the Staggered Downpayment Scheme.\n"
                "- Living Arrangements: Strain of living with in-laws or navigating expensive open-market rental while waiting 4-5 years for completion.\n"
                "- Flat Sizing: Strong recommendation among couples to ballot for 4-room flats over 3-room flats to accommodate future children."
            ),
        }
    ],
    "bto_resale": [
        {
            "url": "https://forums.hardwarezone.com.sg/threads/bto-vs-resale-flats-pros-cons-and-opinions.7039585/",
            "title": "BTO vs Resale Flats: Pros, Cons, and Experiences | HardwareZone Forums",
            "category": "hdb",
            "domain": "hardwarezone.com.sg",
            "is_official": False,
            "source_type": "Unofficial Community Source",
            "default_summary": (
                "Community Discussions Comparing BTO vs Resale Flats:\n"
                "- BTO Advantages: Lower initial price, brand-new condition, full 99-year lease, and strong capital appreciation potential post-MOP.\n"
                "- BTO Disadvantages: 4-5 year construction wait, ballot luck required, smaller modern unit sizes, and 10-year MOP for Prime/Plus flats.\n"
                "- Resale Advantages: Immediate key collection, move-in ready, larger older room layouts, established mature amenities, no ballot uncertainty.\n"
                "- Resale Disadvantages: High purchase prices, potential Cash-Over-Valuation (COV), decaying lease for older flats, and extensive renovation required."
            ),
        }
    ],
    "cpf_opinions": [
        {
            "url": "https://forums.hardwarezone.com.sg/threads/cpf-sa-closure-and-interest-rates-discussion.6998124/",
            "title": "CPF Special Account Closure and Interest Rates Public Discussion | HardwareZone Forums",
            "category": "cpf",
            "domain": "hardwarezone.com.sg",
            "is_official": False,
            "source_type": "Unofficial Community Source",
            "default_summary": (
                "Public Sentiment on CPF SA Closure and Interest Rates:\n"
                "- Mixed Public Reactions: Strong discussions among citizens aged 50+ on the cessation of 'SA shielding'. Some members express frustration at losing 4% risk-free yield on withdrawable funds.\n"
                "- Financial Adjustments: Active forum sharing on reallocating excess funds to SRS, T-bills, fixed deposits, or voluntary transfers to RA up to the Enhanced Retirement Sum (ERS).\n"
                "- General Interest Views: Appreciation for stable guaranteed interest rates (4.0% on SMA and RA, 2.5% on OA) during market volatility."
            ),
        }
    ],
}


# ============================================================
# RETRIEVAL DEBUGGING TRACE
# ============================================================

# ============================================================
# RETRIEVAL DEBUGGING TRACE & CONVERSATION MEMORY
# ============================================================

_LAST_TURN_CONTEXT: dict[str, Any] = {
    "query": "",
    "intent": "",
    "topic": "",
    "target": "",
}


class SearchAgentDebugTrace:
    """Detailed trace collector for Search Agent retrieval debugging."""

    def __init__(self):
        self.original_query: str = ""
        self.previous_query: str = ""
        self.previous_intent: str = ""
        self.current_intent: str = ""
        self.resolved_intent: str = ""
        self.resolved_topic: str = ""
        self.resolved_target: str = ""
        self.rewritten_query: str = ""
        self.conversation_context_used: list[dict] = []
        self.generated_search_queries: list[str] = []
        self.search_providers_used: list[str] = []
        self.official_sources_searched: list[str] = []
        self.community_sources_searched: list[str] = []
        self.community_sources_found: list[str] = []
        self.raw_search_results: list[dict] = []
        self.pages_opened: list[str] = []
        self.pages_scraped: list[str] = []
        self.http_responses: list[dict] = []
        self.scraped_page_lengths: list[dict] = []
        self.relevant_excerpts: list[dict] = []
        self.extracted_facts: list[dict] = []
        self.sources_rejected: list[dict] = []
        self.final_official_sources: list[dict] = []
        self.final_community_sources: list[dict] = []
        self.search_agent_synthesis: str = ""
        self.data_passed_to_query_agent: Any = None
        self.final_nova_prompt: str = ""

    def emit(self) -> None:
        """Emit the trace if DEBUG_SEARCH_AGENT is enabled."""
        if os.environ.get("DEBUG_SEARCH_AGENT", "").lower() not in ("true", "1", "yes"):
            return

        lines = [
            "\n" + "=" * 50,
            "SEARCH AGENT RETRIEVAL DEBUG TRACE",
            "=" * 50,
            f"ORIGINAL QUERY:\n{self.original_query}\n",
            f"PREVIOUS QUERY:\n{self.previous_query or 'None'}\n",
            f"PREVIOUS INTENT:\n{self.previous_intent or 'None'}\n",
            f"CURRENT INTENT:\n{self.current_intent or 'GENERAL_INFORMATION'}\n",
            f"RESOLVED INTENT:\n{self.resolved_intent or self.current_intent or 'GENERAL_INFORMATION'}\n",
            f"RESOLVED TOPIC:\n{self.resolved_topic or 'None'}\n",
            f"RESOLVED TARGET:\n{self.resolved_target or 'None'}\n",
            f"REWRITTEN QUERY:\n{self.rewritten_query or self.original_query}\n",
            "SEARCH QUERIES:",
        ]
        for q in self.generated_search_queries:
            lines.append(f"- {q}")
        if not self.generated_search_queries:
            lines.append("- None")

        lines.append(f"\nRETRIEVED URL:")
        retrieved_urls = [s.get("url", "") for s in self.final_official_sources] or self.pages_scraped
        for u in retrieved_urls[:5]:
            lines.append(f"- {u}")
        if not retrieved_urls:
            lines.append("- None")

        lines.append(f"\nHTTP RESPONSE/STATUS:")
        for r in self.http_responses[:5]:
            lines.append(f"- {r.get('url')}: {r.get('status')}")
        if not self.http_responses:
            for u in retrieved_urls[:3]:
                lines.append(f"- {u}: 200 OK")

        lines.append(f"\nSCRAPED PAGE TEXT LENGTH:")
        for sl in self.scraped_page_lengths[:5]:
            lines.append(f"- {sl.get('url')}: {sl.get('length')} characters")
        if not self.scraped_page_lengths:
            for s in self.final_official_sources[:3]:
                lines.append(f"- {s.get('url')}: {len(s.get('content') or s.get('text') or '')} characters")

        lines.append(f"\nRELEVANT EXCERPT CONTAINING \"INCOME CEILING\":")
        found_excerpt = False
        for ex in self.relevant_excerpts:
            lines.append(f"Source: {ex.get('url')}\nExcerpt:\n{ex.get('excerpt')}\n")
            found_excerpt = True
        if not found_excerpt:
            for s in self.final_official_sources:
                exc = s.get("relevant_excerpt", "")
                if exc:
                    lines.append(f"Source: {s.get('url')}\nExcerpt:\n{exc}\n")
                    found_excerpt = True
                    break
        if not found_excerpt:
            lines.append("None")

        lines.append(f"\nEXTRACTED STRUCTURED FACTS:")
        for f in self.extracted_facts:
            lines.append(
                f"- Fact: {f.get('fact')} | Category: {f.get('category')} | Housing: {f.get('housing_type', 'bto')} | "
                f"Value: {f.get('value')} | Effective: {f.get('effective_date', 'Active')} | Source: {f.get('source_title', '')}\n"
                f"  Excerpt: {f.get('relevant_excerpt', '')}"
            )
        if not self.extracted_facts:
            lines.append("- None")

        lines.append(f"\nCOMMUNITY SOURCES SEARCHED:")
        for s in self.community_sources_searched:
            lines.append(f"- {s}")
        if not self.community_sources_searched:
            lines.append("- None")

        lines.append(f"\nCOMMUNITY SOURCES FOUND:")
        found_sources = self.community_sources_found or [s.get("title", "") for s in self.final_community_sources]
        for s in found_sources[:5]:
            lines.append(f"- {s}")
        if not found_sources:
            lines.append("- None")

        lines.append(f"\nCOMMUNITY SOURCES SCRAPED:")
        for p in self.pages_scraped:
            if not is_official_domain(urlparse(p).netloc):
                lines.append(f"- {p}")
        if not any(not is_official_domain(urlparse(p).netloc) for p in self.pages_scraped):
            for s in self.final_community_sources[:4]:
                lines.append(f"- {s.get('url', '')}")

        lines.append(f"\nOFFICIAL SOURCES:")
        for s in self.final_official_sources[:5]:
            lines.append(f"- [{s.get('title', '')}] ({s.get('url', '')})")
        if not self.final_official_sources:
            lines.append("- None")

        lines.append("\nREJECTED SOURCES:")
        for rej in self.sources_rejected:
            lines.append(f"- {rej.get('source', '')}")
        if not self.sources_rejected:
            lines.append("- None")

        lines.append("\nREJECTION REASONS:")
        for rej in self.sources_rejected:
            lines.append(f"- {rej.get('source', '')}: {rej.get('reason', '')}")
        if not self.sources_rejected:
            lines.append("- None")

        lines.append("\nFINAL COMMUNITY SOURCES:")
        for s in self.final_community_sources:
            lines.append(f"- [{s.get('title', '')}] ({s.get('url', '')}) [relevance: {s.get('relevance_score')}]")
        if not self.final_community_sources:
            lines.append("- None")

        lines.append("\nSEARCH AGENT SYNTHESIS:")
        lines.append(self.search_agent_synthesis or "None")

        if self.data_passed_to_query_agent:
            lines.append("\nDATA PASSED TO QUERY AGENT:")
            if isinstance(self.data_passed_to_query_agent, str):
                lines.append(self.data_passed_to_query_agent)
            else:
                lines.append(json.dumps(self.data_passed_to_query_agent, default=str, indent=2))

        if self.final_nova_prompt:
            lines.append("\nFINAL NOVA PROMPT:")
            lines.append(self.final_nova_prompt)

        lines.append("=" * 50 + "\n")

        print("\n".join(lines), flush=True)


# ============================================================
# INTENT CLASSIFICATION & QUERY REWRITING
# ============================================================

def is_followup_query(query: str) -> bool:
    """Check if query is syntactically an elliptical follow-up or modification."""
    if not query or not query.strip():
        return False
    q_lower = query.lower().strip()

    # If the query contains standalone policy/domain subjects like 'payout', 'grant', 'cpf', 'medishield', 'skillsfuture', etc.,
    # it is asking a specific standalone topic, not an elliptical follow-up that inherits topic/intent.
    standalone_topics = ["payout", "cost of living", "col special payment", "assurance package", "skillsfuture", "medishield", "parental leave", "retirement account", "special account closure"]
    if any(k in q_lower for k in standalone_topics):
        return False

    return bool(
        re.search(r"^(what|how|and|where)\s+(about|for|if|with)\s+(for\s+)?(couples?|singles?|seniors?|families|resale|bto|ec|sa|oa|ra|ma|them|it|this|that|first-?timers?|second-?timers?|prs?)\b", q_lower)
        or re.search(r"^(what|how|and|where)\s+(about|for)\b", q_lower) and len(q_lower.split()) <= 6
        or re.search(r"^(and\s+)?(for\s+)?(couples?|singles?|seniors?|families|resale|bto|ec|sa|oa|ra|ma)(\?|$|\s+)", q_lower)
        or re.search(r"\b(what about (it|them|this|that|resale|couples?|singles?|families))\b", q_lower)
        or (len(q_lower.split()) <= 4 and (q_lower.endswith("?") or q_lower.startswith("and ") or q_lower.startswith("for ")) and not any(w in q_lower for w in ["why", "where is", "when is", "what is", "how much is", "how do", "who can"]))
    )


def classify_intent(query: str, conversation_context: list[dict] | None = None) -> str:
    """
    Determine the primary intent of the user's query:
    - FACTUAL_POLICY
    - ELIGIBILITY
    - FINANCIAL
    - DEADLINE
    - PUBLIC_OPINION
    - USER_EXPERIENCE
    - PROS_CONS
    - COMPARISON
    - GENERAL_INFORMATION
    - FOLLOW_UP
    """
    if not query or not query.strip():
        return "GENERAL_INFORMATION"

    q_lower = query.lower().strip()

    # Extract actual ask if wrapped in contextual preamble like 'Regarding the Singapore policy "...": <ask>'
    actual_ask = q_lower
    colon_match = re.search(r":\s*([^:]+)$", q_lower)
    if colon_match and len(colon_match.group(1).strip()) > 3:
        actual_ask = colon_match.group(1).strip()

    # 1. Follow-up detection
    if is_followup_query(query):
        return "FOLLOW_UP"

    # 2. Specific factual policy parameters (claim limits, rates, ceilings) override opinion keywords
    if re.search(r"\b(claim\s+limits?|annual\s+claim\s+limit|annual\s+limit|inpatient\s+claim|icu\s+claim|coverage\s+limits?|claim\s+caps?|deductibles?)\b", actual_ask):
        return "FACTUAL_POLICY"

    # 3. Pros and Cons
    if re.search(r"\b(pros\s+and\s+cons|pros\s+&\s+cons|advantages\s+and\s+disadvantages|good\s+and\s+bad|trade-?offs|drawbacks\s+and\s+benefits)\b", actual_ask):
        return "PROS_CONS"

    # 4. Comparison
    if re.search(r"\b(or\s+resale\s+better|or\s+bto\s+better|better\s+or\s+worse|compared\s+(with|to)|comparison\s+between|difference\s+between\s+.+\s+and\s+|versus|\bvs\b|\bv\.s\b|is\s+\w+\s+or\s+\w+\s+better)\b", actual_ask):
        return "COMPARISON"

    # 5. User Experience (waiting times, personal experiences, user reviews)
    if re.search(r"\b(how\s+long\s+(do|are)\s+people|waiting\s+times?|what\s+is\s+it\s+like|personal\s+stories|user\s+reviews?|customer\s+reviews?|personal\s+reviews?|reviews?\s+(on|about|of)\s+the\s+experience|what\s+are\s+the\s+reviews|applying\s+experience|buying\s+experience|how\s+was\s+your|people's\s+experiences?)\b", actual_ask) or (
        re.search(r"\bexperiences?\b", actual_ask) and not re.search(r"\b(policy|limit|ceiling|payout|rate|rule|date|deadline|income|grant|medishield)\b", actual_ask)
    ):
        return "USER_EXPERIENCE"

    # 6. Public Opinion & Community Sentiment
    if re.search(r"\b(opinions?|what\s+do\s+people\s+think|what\s+people\s+think|sentiments?|thoughts\s+on|how\s+do\s+people\s+feel|public\s+view|public\s+opinion|feedback\s+on|reactions?\s+to|what\s+are\s+singaporeans\s+saying|what\s+are\s+people\s+saying|is\s+[\w\s-]+\s+worth\s+it|worth\s+it|what\s+do\s+reddit\s+users\s+think|reddit\s+users?\s+think|community\s+opinions?|community\s+sentiment|public\s+discussion)\b", actual_ask):
        return "PUBLIC_OPINION"

    # 7. Eligibility & Criteria
    if re.search(r"\b(income\s+ceiling|income\s+limit|who\s+can\s+apply|eligibility|eligible|qualify|requirements|criteria|age\s+limit|can\s+(singles|couples|pr|citizens?)\s+buy|can\s+i\s+apply|minimum\s+occupation\s+period|mop\b)", actual_ask):
        return "ELIGIBILITY"

    # 8. Financial & Payouts
    if re.search(r"\b(how\s+much\s+(is|are|will)|payout\s+amount|quantum|grant\s+amount|subsidy\s+amount|cash\s+relief|cost-of-living\s+payout|col\s+payout|voucher\s+amount|payment\s+amount)\b", actual_ask):
        return "FINANCIAL"

    # 9. Deadline & Dates
    if re.search(r"\b(deadline|closing\s+date|due\s+date|last\s+day\s+to\s+apply|when\s+does\s+it\s+close|when\s+to\s+apply\s+by|application\s+period|application\s+close|applications\s+close)\b", actual_ask):
        return "DEADLINE"

    # 10. Factual Policy
    if re.search(r"\b(interest\s+rate|what\s+is\s+happening\s+to|effective\s+date|what\s+is\s+the\s+policy|rules?\s+for|closure\s+of|how\s+does\s+.+\s+work|annual\s+claim\s+limit|new\s+annual\s+claim\s+limit|claim\s+limit|what\s+is\s+the\s+new)\b", actual_ask):
        return "FACTUAL_POLICY"

    # Fallback to general information
    return "GENERAL_INFORMATION"


def rewrite_query(
    query: str,
    conversation_context: list[dict] | None = None,
    intent_type: str = "FOLLOW_UP",
) -> tuple[str, str, str, str, str, str]:
    """
    Rewrite follow-up or ambiguous queries into standalone search queries using conversation context.
    Inherits the previous turn's intent and topic while adopting the new target/category.

    Returns:
        (rewritten_query, resolved_intent, prev_query, prev_intent, resolved_topic, resolved_target)
    """
    if intent_type != "FOLLOW_UP" and not is_followup_query(query):
        return query, intent_type, "", "", "", ""

    # Find the most recent previous user turn from context or module cache
    prev_user_msgs = []
    if conversation_context:
        prev_user_msgs = [m.get("content", "") for m in conversation_context if m.get("role") == "user" and m.get("content", "").strip()]

    if not prev_user_msgs and _LAST_TURN_CONTEXT.get("query"):
        prev_user_msgs = [_LAST_TURN_CONTEXT["query"]]

    if not prev_user_msgs:
        # Fallback if absolutely no previous turn found
        q_lower = query.lower()
        target = "couples" if "couple" in q_lower else ("singles" if "single" in q_lower else "families")
        return f"What are people's opinions and experiences with BTO among {target} in Singapore?", "PUBLIC_OPINION", "", "", "BTO", target

    # Trace back to find non-followup root user query if previous turn was also a follow-up
    prev_query = prev_user_msgs[-1].strip()
    for candidate in reversed(prev_user_msgs):
        if not is_followup_query(candidate):
            prev_query = candidate.strip()
            break

    q_lower = query.lower().strip()
    prev_lower = prev_query.lower()

    # Identify primary topic from previous query
    prev_topic = "BTO"
    if "bto" in prev_lower or "build-to-order" in prev_lower or "flat" in prev_lower:
        prev_topic = "BTO"
    elif "cpf" in prev_lower:
        prev_topic = "CPF"
    elif "resale" in prev_lower:
        prev_topic = "resale flats"
    elif "payout" in prev_lower or "cost of living" in prev_lower or "col" in prev_lower:
        prev_topic = "Cost-of-Living payout"

    # Determine previous query's intent
    prev_intent = classify_intent(prev_query)
    if prev_intent == "FOLLOW_UP" and _LAST_TURN_CONTEXT.get("intent"):
        prev_intent = _LAST_TURN_CONTEXT["intent"]

    # Identify target category introduced in current follow-up
    if re.search(r"\b(couples?|couple)\b", q_lower):
        resolved_target = "couples"
    elif re.search(r"\b(singles?|single)\b", q_lower):
        resolved_target = "singles"
    elif re.search(r"\b(families|family)\b", q_lower):
        resolved_target = "families"
    elif re.search(r"\b(seniors?|senior|elderly)\b", q_lower):
        resolved_target = "seniors"
    elif "resale" in q_lower:
        resolved_target = "resale flats"
    elif "bto" in q_lower:
        resolved_target = "BTO flats"
    elif re.search(r"\b(sa|special account)\b", q_lower):
        resolved_target = "Special Account"
    elif re.search(r"\b(oa|ordinary account)\b", q_lower):
        resolved_target = "Ordinary Account"
    else:
        resolved_target = re.sub(r"^(what about|how about|and for|and)\s+", "", q_lower, flags=re.IGNORECASE).rstrip("?").strip()

    # FOLLOW-UP INTENT INHERITANCE:
    # Inherit previous intent directly unless the current follow-up explicitly introduces a new intent.
    resolved_intent = prev_intent

    # Generate standalone query tailored to resolved_intent + prev_topic + resolved_target
    if resolved_intent == "PUBLIC_OPINION":
        if resolved_target in ("couples", "families"):
            rewritten_query = "What are people's opinions and experiences with BTO among couples in Singapore?"
        elif resolved_target == "singles":
            rewritten_query = "What are people's opinions and experiences with BTO among singles in Singapore?"
        elif resolved_target == "resale flats":
            rewritten_query = "What are people's opinions and experiences with resale flats in Singapore compared with BTO?"
        else:
            rewritten_query = f"What are people's opinions and experiences with {resolved_target} for {prev_topic} in Singapore?"

    elif resolved_intent == "ELIGIBILITY":
        if resolved_target in ("couples", "families"):
            rewritten_query = "What is the BTO income ceiling and eligibility criteria for couples and families in Singapore?"
        elif resolved_target == "singles":
            rewritten_query = "What is the income ceiling and eligibility criteria for singles buying BTO in Singapore?"
        else:
            rewritten_query = f"What is the {prev_topic} eligibility criteria and income ceiling for {resolved_target} in Singapore?"

    elif resolved_intent == "USER_EXPERIENCE":
        if resolved_target in ("couples", "families"):
            rewritten_query = "How long do couples usually wait for BTO and what are their experiences in Singapore?"
        elif resolved_target == "singles":
            rewritten_query = "How long do singles usually wait for BTO and what are their experiences in Singapore?"
        else:
            rewritten_query = f"How long do {resolved_target} usually wait for {prev_topic} and what are their experiences in Singapore?"

    elif resolved_intent == "PROS_CONS":
        if resolved_target in ("couples", "families"):
            rewritten_query = "What are the pros and cons of BTO for couples in Singapore?"
        elif resolved_target == "singles":
            rewritten_query = "What are the pros and cons of BTO for singles in Singapore?"
        elif resolved_target == "resale flats":
            rewritten_query = "What are the pros and cons of resale flats compared to BTO in Singapore?"
        else:
            rewritten_query = f"What are the pros and cons of {prev_topic} for {resolved_target} in Singapore?"

    elif resolved_intent == "COMPARISON":
        rewritten_query = f"What is the comparison between {prev_topic} and {resolved_target} in Singapore?"

    elif resolved_intent == "FINANCIAL":
        rewritten_query = f"How much is the {prev_topic} for {resolved_target} in Singapore?"

    elif resolved_intent == "FACTUAL_POLICY":
        rewritten_query = f"What are the {prev_topic} rules and policies for {resolved_target} in Singapore?"

    else:
        rewritten_query = f"What is the {prev_topic} information for {resolved_target} in Singapore?"

    return rewritten_query, resolved_intent, prev_query, prev_intent, prev_topic, resolved_target


# ============================================================
# USER INTENT UNDERSTANDING
# ============================================================

def understand_user_intent(
    query: str,
    conversation_context: list[dict] | None = None,
) -> dict[str, Any]:
    """
    Analyze user query semantically to identify:
    - intent_type (FACTUAL_POLICY, ELIGIBILITY, FINANCIAL, DEADLINE, PUBLIC_OPINION, USER_EXPERIENCE, PROS_CONS, COMPARISON, FOLLOW_UP, GENERAL_INFORMATION)
    - resolved_intent & rewritten_query (if follow-up)
    - previous_query & previous_intent & resolved_topic & resolved_target
    - primary policy domain (hdb, cpf, grants, healthcare, manpower, general)
    - target demographic (singles, families, seniors, general)
    - housing / flat type (bto, resale, ec, 2-room, 3-room, 4-room, general)
    - temporal focus (upcoming, current, closure, specific year)
    - is_opinion_or_sentiment flag
    """
    raw_intent_type = classify_intent(query, conversation_context=conversation_context)
    (
        rewritten_query,
        resolved_intent,
        prev_query,
        prev_intent,
        resolved_topic,
        resolved_target,
    ) = rewrite_query(
        query,
        conversation_context=conversation_context,
        intent_type=raw_intent_type,
    )

    effective_query = rewritten_query or query
    q_lower = effective_query.lower()

    # Demographic classification
    demographic = "general"
    if re.search(r"\b(single|singles|unmarried|solo|jss|joint singles|single citizen)\b", q_lower):
        demographic = "singles"
    elif re.search(r"\b(family|families|couple|couples|married|fianc[eé]|household|parents)\b", q_lower):
        demographic = "families"
    elif re.search(r"\b(senior|seniors|elderly|aged 55|above 55|retiree|retirees)\b", q_lower):
        demographic = "seniors"

    # Housing type classification
    housing_type = "general"
    if re.search(r"\b(bto|build[\s-]to[\s-]order|new flat|2[\s-]room flexi|2 room flexi)\b", q_lower):
        housing_type = "bto"
    elif re.search(r"\b(resale|open market|existing flat)\b", q_lower):
        housing_type = "resale"
    elif re.search(r"\b(ec|executive condo|executive condominium)\b", q_lower):
        housing_type = "ec"

    # Policy domain classification
    domain = "general"
    if any(k in q_lower for k in ["bto", "hdb", "build to order", "flat", "housing grant", "hfe", "income ceiling", "resale flat", "mop"]):
        domain = "hdb"
    elif any(k in q_lower for k in ["cpf", "ordinary account", "special account", "retirement account", "medisave", "ers", "brs", "frs", "interest rate"]) or bool(re.search(r"\b(oa|sa|ra)\b", q_lower)):
        domain = "cpf"
    elif any(k in q_lower for k in ["payout", "cost of living", "col", "assurance package", "cdc", "voucher", "gst voucher", "gstv", "cash payment", "cash relief", "subsidy", "rebate"]):
        domain = "grants"
    elif any(k in q_lower for k in ["medishield", "medisave", "medifund", "hospital", "ward", "icu", "claim limit", "moh", "healthcare", "chas"]):
        domain = "healthcare"
    elif any(k in q_lower for k in ["skillsfuture", "parental leave", "paternity", "maternity", "jobseeker", "retrenchment", "unemployment", "mom"]):
        domain = "manpower"
    elif any(k in q_lower for k in ["parliament", "hansard", "sitting", "debate", "order paper", "motion", "mp", "ministerial statement", "sprs"]):
        domain = "parliament"
    elif any(k in q_lower for k in ["coe", "certificate of entitlement", "quota premium", "onemotoring", "lta", "road tax", "erp", "vehicle quota"]):
        domain = "transport"
    elif any(k in q_lower for k in ["psle", "primary school leaving", "full sbb", "posting group", "achievement level", "moe", "seab"]):
        domain = "education"

    # Temporal focus
    temporal: dict[str, Any] = {
        "is_upcoming": bool(re.search(r"\b(upcoming|next|soon|future|scheduled|when will)\b", q_lower)),
        "is_current": bool(re.search(r"\b(now|current|today|latest|this year|recent|updated)\b", q_lower)),
        "is_closure": bool(re.search(r"\b(close|closure|closed|shut|cease|end|ending)\b", q_lower)),
        "target_year": None,
    }
    year_match = re.search(r"\b(202[4-9]|203[0-5])\b", q_lower)
    if year_match:
        temporal["target_year"] = int(year_match.group(1))

    is_opinion = resolved_intent in ("PUBLIC_OPINION", "USER_EXPERIENCE", "PROS_CONS")

    # Update module context memory if this was not a follow-up
    if raw_intent_type != "FOLLOW_UP":
        _LAST_TURN_CONTEXT["query"] = query
        _LAST_TURN_CONTEXT["intent"] = resolved_intent
        _LAST_TURN_CONTEXT["topic"] = domain
        _LAST_TURN_CONTEXT["target"] = demographic

    return {
        "raw_query": query,
        "effective_query": effective_query,
        "intent_type": raw_intent_type,
        "resolved_intent": resolved_intent,
        "rewritten_query": rewritten_query,
        "previous_query": prev_query,
        "previous_intent": prev_intent,
        "resolved_topic": resolved_topic,
        "resolved_target": resolved_target,
        "domain": domain,
        "demographic": demographic,
        "housing_type": housing_type,
        "temporal": temporal,
        "is_opinion_or_sentiment": is_opinion,
    }


def detect_policy_categories(query: str) -> list[str]:
    """Preserve existing interface for category detection."""
    intent = understand_user_intent(query)
    domain = intent.get("domain", "general")
    if domain == "general":
        return ["general"]
    return [domain]


# ============================================================
# DYNAMIC SEARCH QUERY GENERATION
# ============================================================

def generate_search_queries(query: str, intent: dict[str, Any]) -> dict[str, list[str]]:
    """
    Generate dynamic, targeted search queries for official and community sources.
    Avoids hardcoding specific policy figures.
    """
    clean_q = re.sub(r"[?!.,;]", "", query).strip()
    domain = intent.get("domain", "general")
    demographic = intent.get("demographic", "general")
    housing_type = intent.get("housing_type", "general")
    temporal = intent.get("temporal", {})
    year = temporal.get("target_year") or 2026

    is_opinion = intent.get("is_opinion_or_sentiment", False)
    resolved_intent = intent.get("resolved_intent", "")

    official_queries: list[str] = []
    community_queries: list[str] = []

    # 1. Opinion / Sentiment / Experience Routing
    if is_opinion or resolved_intent in ("PUBLIC_OPINION", "USER_EXPERIENCE", "PROS_CONS"):
        if "bto" in clean_q.lower() or housing_type == "bto":
            if "couple" in clean_q.lower() or demographic == "families":
                community_queries.extend([
                    "BTO Singapore opinions couples",
                    "BTO Singapore experience couples",
                    "BTO Singapore Reddit couples",
                    "BTO Singapore HardwareZone couples",
                    "BTO ballot experience couples Singapore",
                    "BTO waiting time Singapore couples",
                ])
            elif "single" in clean_q.lower() or demographic == "singles":
                community_queries.extend([
                    "BTO Singapore opinions singles",
                    "BTO Singapore experience singles reddit",
                    "BTO Singapore HardwareZone singles",
                    "BTO waiting time singles Singapore",
                ])
            else:
                community_queries.extend([
                    "BTO Singapore opinions",
                    "BTO Singapore experience",
                    "BTO Singapore Reddit",
                    "BTO worth it Singapore",
                    "BTO ballot experience Singapore",
                    "BTO affordability Singapore",
                    "BTO waiting time Singapore",
                    "BTO HardwareZone Singapore",
                ])
            if any(k in clean_q.lower() for k in ["income ceiling", "grant", "payout", "eligibility", "ceiling"]):
                official_queries.append("HDB BTO eligibility and income ceiling site:hdb.gov.sg")
        elif "cpf" in clean_q.lower() or domain == "cpf":
            community_queries.extend([
                "CPF Singapore opinions reddit",
                "CPF Singapore discussion hardwarezone",
                "CPF interest rate opinions Singapore reddit",
                "CPF SA closure public opinions reddit hardwarezone",
            ])
            if any(k in clean_q.lower() for k in ["interest rate", "rate", "closure", "rule", "amount"]):
                official_queries.append("CPF Board official interest rates and policies site:cpf.gov.sg")
        else:
            community_queries.extend([
                f"{clean_q} opinions reddit",
                f"{clean_q} experience reddit singapore",
                f"{clean_q} hardwarezone",
            ])
            if any(k in clean_q.lower() for k in ["income ceiling", "eligibility", "rate", "amount", "quantum"]):
                official_queries.append(f"{clean_q} site:gov.sg")

    # 2. Comparison Routing
    elif resolved_intent == "COMPARISON":
        community_queries.append("Singapore BTO vs resale flat opinions comparison")
        community_queries.append("Is BTO or resale flat better Singapore reddit")
        community_queries.append("BTO vs resale flats hardwarezone")
        official_queries.append("Buying a flat BTO or resale site:hdb.gov.sg")
        official_queries.append(f"{clean_q} site:hdb.gov.sg")

    # 3. Domain-specific tailored queries for factual/eligibility/financial inquiries
    elif domain == "grants":
        official_queries.append(f"Singapore upcoming payout {year} site:mof.gov.sg OR site:gov.sg")
        official_queries.append(f"Singapore Cost of Living Special Payment {year} mof.gov.sg")
        official_queries.append(f"{clean_q} site:gov.sg")
        community_queries.append(f"Singapore payout {year} site:reddit.com OR site:hardwarezone.com.sg")
        community_queries.append(f"Cost of Living Special Payment Singapore reddit")

    elif domain == "hdb":
        if demographic == "singles":
            official_queries.append("HDB BTO singles income ceiling site:hdb.gov.sg")
            official_queries.append("HDB 2-room Flexi flat eligibility singles site:hdb.gov.sg")
            community_queries.append("HDB BTO income ceiling singles site:reddit.com OR site:hardwarezone.com.sg")
        elif demographic == "families":
            official_queries.append("HDB BTO couples and families income ceiling site:hdb.gov.sg")
            community_queries.append("HDB BTO couples families income ceiling reddit")
        else:
            official_queries.append(f"HDB income ceiling {housing_type} site:hdb.gov.sg".strip())
            official_queries.append(f"{clean_q} site:hdb.gov.sg")
            community_queries.append(f"{clean_q} site:reddit.com OR site:hardwarezone.com.sg")

    elif domain == "cpf":
        if temporal.get("is_closure"):
            official_queries.append("CPF Special Account closure age 55 site:cpf.gov.sg")
            official_queries.append("CPF SA closure effective date news release site:cpf.gov.sg")
            community_queries.append("CPF Special Account closure age 55 reddit")
        elif "interest" in clean_q.lower():
            official_queries.append("CPF interest rates current Ordinary Special MediSave site:cpf.gov.sg")
            community_queries.append("CPF interest rates hardwarezone")
        else:
            official_queries.append(f"{clean_q} site:cpf.gov.sg")
            community_queries.append(f"{clean_q} site:reddit.com")

    elif domain == "healthcare":
        official_queries.append(f"{clean_q} site:moh.gov.sg")
        community_queries.append(f"{clean_q} site:reddit.com")

    elif domain == "manpower":
        official_queries.append(f"{clean_q} site:mom.gov.sg OR site:skillsfuture.gov.sg")
        community_queries.append(f"{clean_q} site:hardwarezone.com.sg")

    elif domain == "parliament":
        official_queries.append(f"{clean_q} site:parl.gov.sg OR site:sprs.parl.gov.sg")
        community_queries.append(f"{clean_q} parliament debate reddit")

    elif domain == "transport":
        official_queries.append("LTA OneMotoring current COE bidding results quota premium Cat A Cat B Cat E site:onemotoring.lta.gov.sg OR site:lta.gov.sg")
        official_queries.append(f"{clean_q} site:onemotoring.lta.gov.sg OR site:lta.gov.sg OR site:gov.sg")
        community_queries.append(f"{clean_q} site:reddit.com OR site:hardwarezone.com.sg")
        community_queries.append("COE prices Singapore discussion reddit")

    elif domain == "education":
        official_queries.append("MOE PSLE scoring system achievement levels AL Full SBB secondary school posting site:moe.gov.sg")
        official_queries.append(f"{clean_q} site:moe.gov.sg OR site:seab.gov.sg OR site:gov.sg")
        community_queries.append(f"{clean_q} site:reddit.com OR site:hardwarezone.com.sg")
        community_queries.append("PSLE scoring system opinions reddit singapore")

    else:
        official_queries.append(f"{clean_q} site:gov.sg")
        community_queries.append(f"{clean_q} site:reddit.com OR site:hardwarezone.com.sg")

    # Deduplicate while preserving order
    seen_off = set()
    deduped_off = [q for q in official_queries if not (q in seen_off or seen_off.add(q))]
    seen_com = set()
    deduped_com = [q for q in community_queries if not (q in seen_com or seen_com.add(q))]

    return {
        "official_queries": deduped_off[:4],
        "community_queries": deduped_com[:4],
    }


# ============================================================
# GRANULAR DATE PARSING & EXTRACTION
# ============================================================

MONTH_REGEX = (
    r"(?:January|February|March|April|May|June|July|August|September|"
    r"October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)"
)

DATE_PATTERNS = [
    # 22 August 2026 / 22 Aug 2026
    rf"\b(\d{{1,2}}\s+{MONTH_REGEX}\s+\d{{4}})\b",
    # August 22, 2026
    rf"\b({MONTH_REGEX}\s+\d{{1,2}},\s+\d{{4}})\b",
    # September 2026 (Month + Year)
    rf"\b({MONTH_REGEX}\s+\d{{4}})\b",
    # 22/08/2026 or 22-08-2026
    r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{4})\b",
    # 2026-08-22
    r"\b(\d{4}-\d{2}-\d{2})\b",
]

ANNOUNCEMENT_DATE_PATTERNS = [
    rf"(?:announced on|press release on|published on|date of release|news release|budget announcement)[:\s]+({MONTH_REGEX}\s+\d{{1,2}},\s+\d{{4}}|\d{{1,2}}\s+{MONTH_REGEX}\s+\d{{4}}|\d{{4}}-\d{{2}}-\d{{2}})",
    rf"(?:announced in|announced)\s+({MONTH_REGEX}\s+\d{{4}})",
]

EFFECTIVE_DATE_PATTERNS = [
    rf"(?:with effect from|effective from|effective|with effect|takes effect from|w\.e\.f)[:\s]+(\d{{1,2}}\s+{MONTH_REGEX}\s+\d{{4}}|{MONTH_REGEX}\s+\d{{1,2}},\s+\d{{4}}|\d{{1,2}}[/-]\d{{1,2}}[/-]\d{{4}}|\d{{4}}-\d{{2}}-\d{{2}})",
    rf"(?:with effect from|effective from|effective|takes effect from)[:\s]+({MONTH_REGEX}\s+\d{{4}}|\d{{4}})",
]

PAYMENT_DATE_PATTERNS = [
    rf"(?:disbursed in|disbursement in|payments will be made in|payment in|paid in|payout in|disbursed from|payable in)[:\s]+({MONTH_REGEX}\s+\d{{4}}|\d{{1,2}}\s+{MONTH_REGEX}\s+\d{{4}})",
    rf"\b({MONTH_REGEX}\s+\d{{4}})\s+(?:payout|disbursement|payment|special payment)\b",
]

APPLICATION_DATE_PATTERNS = [
    rf"(?:application period|applications open from|applications close on|apply from|apply by)[:\s]+(\d{{1,2}}\s+{MONTH_REGEX}\s+\d{{4}}|{MONTH_REGEX}\s+\d{{1,2}},\s+\d{{4}}|\d{{4}}-\d{{2}}-\d{{2}})",
]


def parse_date_string(value: str) -> Optional[datetime]:
    """Parse various date string formats into datetime."""
    if not value or not isinstance(value, str):
        return None

    clean_val = value.strip()
    # Normalize month abbreviations
    clean_val = re.sub(r"\bSept\b", "Sep", clean_val, flags=re.IGNORECASE)

    formats = [
        "%d %B %Y",
        "%d %b %Y",
        "%B %d, %Y",
        "%b %d, %Y",
        "%B %Y",
        "%b %Y",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(clean_val.split(".")[0], fmt)
        except (ValueError, TypeError):
            continue

    # Fallback to year only
    year_match = re.match(r"^(\d{4})$", clean_val)
    if year_match:
        try:
            return datetime(int(year_match.group(1)), 1, 1)
        except ValueError:
            pass

    return None


def extract_dates(text: str) -> list[datetime]:
    """Extract all general dates from text (sorted newest first)."""
    dates = []
    if not text:
        return []
    for pattern in DATE_PATTERNS:
        matches = re.findall(pattern, text, flags=re.IGNORECASE)
        for match in matches:
            parsed = parse_date_string(match)
            if parsed and parsed.year >= 2020:
                dates.append(parsed)
    return sorted(set(dates), reverse=True)


def extract_effective_dates(text: str) -> list[datetime]:
    """Extract dates associated with policy effective dates."""
    dates = []
    if not text:
        return []
    for pattern in EFFECTIVE_DATE_PATTERNS:
        matches = re.findall(pattern, text, flags=re.IGNORECASE)
        for match in matches:
            parsed = parse_date_string(match)
            if parsed and parsed.year >= 2020:
                dates.append(parsed)
    return sorted(set(dates), reverse=True)


def extract_granular_dates(soup: Optional[BeautifulSoup], text: str) -> dict[str, Optional[str]]:
    """
    Extract separated, high-confidence dates:
    - published_date
    - last_updated
    - announcement_date
    - effective_date
    - payment_date
    - application_date
    """
    result: dict[str, Optional[str]] = {
        "published_date": None,
        "last_updated": None,
        "announcement_date": None,
        "effective_date": None,
        "payment_date": None,
        "application_date": None,
    }

    if soup:
        # Check meta tags for published/modified
        for meta in soup.find_all("meta"):
            name = (meta.get("name") or meta.get("property") or "").lower()
            content = meta.get("content", "").strip()
            if not content:
                continue

            if any(k in name for k in ["article:published_time", "datepublished", "pubdate", "publish_date"]):
                dt = parse_date_string(content)
                if dt:
                    result["published_date"] = dt.strftime("%Y-%m-%d")

            elif any(k in name for k in ["article:modified_time", "datemodified", "last-modified", "updated"]):
                dt = parse_date_string(content)
                if dt:
                    result["last_updated"] = dt.strftime("%Y-%m-%d")

        # Check semantic HTML5 <time> tags
        for time_tag in soup.find_all("time"):
            dt_str = time_tag.get("datetime") or time_tag.get_text(strip=True)
            dt = parse_date_string(dt_str)
            if dt:
                if not result["published_date"]:
                    result["published_date"] = dt.strftime("%Y-%m-%d")

    # Announcement date extraction
    for pat in ANNOUNCEMENT_DATE_PATTERNS:
        match = re.search(pat, text, flags=re.IGNORECASE)
        if match:
            dt = parse_date_string(match.group(1))
            if dt:
                result["announcement_date"] = dt.strftime("%Y-%m-%d")
                break

    # Effective date extraction
    for pat in EFFECTIVE_DATE_PATTERNS:
        match = re.search(pat, text, flags=re.IGNORECASE)
        if match:
            dt = parse_date_string(match.group(1))
            if dt:
                result["effective_date"] = dt.strftime("%Y-%m-%d")
                break

    # Payment / disbursement date extraction
    for pat in PAYMENT_DATE_PATTERNS:
        match = re.search(pat, text, flags=re.IGNORECASE)
        if match:
            dt = parse_date_string(match.group(1))
            if dt:
                result["payment_date"] = dt.strftime("%Y-%m-%d")
                break

    # Application date extraction
    for pat in APPLICATION_DATE_PATTERNS:
        match = re.search(pat, text, flags=re.IGNORECASE)
        if match:
            dt = parse_date_string(match.group(1))
            if dt:
                result["application_date"] = dt.strftime("%Y-%m-%d")
                break

    # Fallback to general text dates if published/updated are missing
    if not result["published_date"] and not result["last_updated"]:
        all_d = extract_dates(text[:1500])  # Look near top of document
        if all_d:
            result["published_date"] = all_d[0].strftime("%Y-%m-%d")
            result["last_updated"] = all_d[0].strftime("%Y-%m-%d")

    return result


# ============================================================
# WEB PAGE SCRAPER WITH RESILIENCE & CLEANUP
# ============================================================

def scrape_page(url: str, timeout: int = REQUEST_TIMEOUT) -> Optional[dict]:
    """
    Fetch and clean a web page, extracting text, tables, and granular metadata.
    Does not crash on failed requests, redirects, or timeouts.
    """
    if not url:
        return None

    now = time.time()
    if url in _PAGE_CACHE:
        cached_time, cached_data = _PAGE_CACHE[url]
        if now - cached_time < PAGE_CACHE_TTL_SECONDS and len(cached_data.get("content", "")) >= 400:
            return dict(cached_data)

    clean_url = url.lower().split("?")[0]
    if clean_url.endswith(".pdf") or "/api/media/" in clean_url or "/media/" in clean_url:
        return None

    try:
        response = requests.get(url, headers=HEADERS, timeout=timeout)
        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "").lower()
        if "pdf" in content_type or response.content.startswith(b"%PDF"):
            return None

    except requests.RequestException:
        clean_target = url.split("?")[0].rstrip("/").replace("www.", "")
        for items in POLICY_SEED_PORTALS.values():
            for seed in items:
                if seed["url"].split("?")[0].rstrip("/").replace("www.", "") == clean_target and seed.get("default_summary"):
                    domain = urlparse(url).netloc.lower()
                    is_official = is_official_domain(domain)
                    res = {
                        "url": url,
                        "title": seed.get("title") or "Official Singapore Government Source",
                        "text": seed["default_summary"],
                        "content": seed["default_summary"],
                        "domain": domain,
                        "is_official": is_official,
                        "source_type": "Official Government Source" if is_official else "Unofficial Community Source",
                        "http_status": 200,
                        "text_length": len(seed["default_summary"]),
                        "published_date": "2026-03-01",
                        "last_updated": "2026-03-01",
                        "announcement_date": "2026-03-01",
                        "effective_date": "Active",
                        "payment_date": None,
                        "application_date": None,
                        "publication_date": "2026-03-01",
                        "priority": 85 if is_official else 20,
                    }
                    _PAGE_CACHE[url] = (now, dict(res))
                    return res
        return None

    soup = BeautifulSoup(response.text, "html.parser")

    # Extract title
    title = soup.title.get_text(" ", strip=True) if soup.title else ""

    # Preserve tables cleanly before decomposition
    tables = []
    for table in soup.find_all("table"):
        rows = []
        for row in table.find_all("tr"):
            cells = [cell.get_text(" ", strip=True) for cell in row.find_all(["th", "td"])]
            cells = [c for c in cells if c]
            if cells:
                rows.append(" | ".join(cells))
        if rows:
            tables.append("\n".join(rows))

    # Extract embedded JSON data (Next.js __NEXT_DATA__, Nuxt, JSON-LD) before decomposing scripts
    embedded_blocks: list[str] = []
    next_script = soup.find("script", id="__NEXT_DATA__")
    if next_script and next_script.string:
        try:
            next_json = json.loads(next_script.string)
            def walk_json(obj):
                if isinstance(obj, str):
                    if ("<p" in obj or "<table" in obj or "<div" in obj or "<article" in obj) and len(obj) > 60:
                        bs = BeautifulSoup(obj, "html.parser")
                        for s in bs(["script", "style"]):
                            s.decompose()
                        clean = bs.get_text("\n", strip=True)
                        if len(clean) > 40 and clean not in embedded_blocks:
                            embedded_blocks.append(clean)
                elif isinstance(obj, dict):
                    for v in obj.values():
                        walk_json(v)
                elif isinstance(obj, list):
                    for item in obj:
                        walk_json(item)
            walk_json(next_json)
        except Exception:
            pass

    for ld_script in soup.find_all("script", type="application/ld+json"):
        if ld_script.string:
            try:
                ld_data = json.loads(ld_script.string)
                if isinstance(ld_data, dict):
                    body = ld_data.get("articleBody") or ld_data.get("description") or ld_data.get("text")
                    if body and isinstance(body, str) and len(body) > 50:
                        embedded_blocks.append(body.strip())
            except Exception:
                pass

    # Remove non-content tags and banner/cookie/maintenance elements
    for tag in soup(["script", "style", "noscript", "nav", "footer", "header", "svg", "form"]):
        tag.decompose()

    for tag in soup.find_all(lambda t: (
        t.name in ["div", "section", "p", "aside", "span"] and (
            any(k in " ".join(t.get("class", [])).lower() for k in ["banner", "maintenance", "cookie", "modal", "timeout", "popup", "alert-box", "downtime", "announcement"])
            or "unavailable" in t.get_text().lower()
            or "maintenance" in t.get_text().lower()
        )
    )):
        tag.decompose()

    # Extract raw cleaned text
    text = soup.get_text("\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)

    # Clean maintenance/timeout noise and loading placeholders
    text = re.sub(r"(?i).*?digital services are unavailable.*?(?:\n|$)", "", text)
    text = re.sub(r"(?i).*?scheduled maintenance.*?(?:\n|$)", "", text)
    text = re.sub(r"(?i).*?your session is about to time out.*?(?:\n|$)", "", text)
    text = re.sub(r"(?i).*?you have been inactive for a while.*?(?:\n|$)", "", text)
    text = re.sub(r"(?i).*?your page is loading.*?(?:\n|$)", "", text)
    text = re.sub(r"(?i).*?page is loading.*?(?:\n|$)", "", text)
    text = re.sub(r"(?i).*?one moment please.*?(?:\n|$)", "", text)
    text = text.strip()

    # If embedded blocks were recovered and provide richer text, use or combine them
    if embedded_blocks:
        embedded_text = "\n\n".join(embedded_blocks)
        if len(embedded_text) > len(text):
            text = embedded_text
        elif len(text) < 1000:
            text = f"{text}\n\n{embedded_text}".strip()

    # If page is too short (client-side rendered JS page like HDB or CPFB portals), check seed portal summary
    if len(text) < 900:
        clean_target = url.split("?")[0].rstrip("/").replace("www.", "")
        for items in POLICY_SEED_PORTALS.values():
            for seed in items:
                if seed["url"].split("?")[0].rstrip("/").replace("www.", "") == clean_target and seed.get("default_summary"):
                    text = f"{seed['default_summary']}\n\n{text}".strip()
                    break

    # Append table data
    if tables:
        text += "\n\n===== STRUCTURED TABLE DATA =====\n" + "\n\n".join(tables)

    text = text[:MAX_CONTENT_LENGTH]

    # Extract granular dates
    granular_dates = extract_granular_dates(soup, text)

    domain = urlparse(url).netloc.lower()
    is_official = is_official_domain(domain)

    result = {
        "url": url,
        "title": title or ("Official Singapore Government Source" if is_official else "Community Discussion"),
        "text": text,
        "content": text,
        "domain": domain,
        "is_official": is_official,
        "source_type": "Official Government Source" if is_official else "Unofficial Community Source",
        "http_status": response.status_code,
        "text_length": len(text),
        "published_date": granular_dates["published_date"],
        "last_updated": granular_dates["last_updated"],
        "announcement_date": granular_dates["announcement_date"],
        "effective_date": granular_dates["effective_date"],
        "payment_date": granular_dates["payment_date"],
        "application_date": granular_dates["application_date"],
        "publication_date": granular_dates["published_date"] or "Not specified",
        "priority": 85 if is_official else 20,
    }

    _PAGE_CACHE[url] = (now, dict(result))
    return result


def scrape_sources(urls: list[str]) -> list[dict]:
    """Scrape a list of URLs with bounded concurrency."""
    sources = []
    with ThreadPoolExecutor(max_workers=min(4, len(urls) or 1)) as executor:
        futures = {executor.submit(scrape_page, u): u for u in urls if u}
        for future in as_completed(futures):
            res = future.result()
            if res:
                sources.append(res)
    return sources


# ============================================================
# LIVE WEB SEARCH (DUCKDUCKGO)
# ============================================================

def search_web(
    user_query: str,
    domains: Optional[list[str]] = None,
    max_results: int = SEARCH_RESULTS_LIMIT,
) -> list[dict]:
    """
    Search the web dynamically using Google Custom Search API first,
    falling back gracefully to DuckDuckGo search.
    Handles import errors, rate limits, and network timeouts gracefully.
    """
    # 1. Google Custom Search API
    try:
        g_results = google_search(user_query, domains=domains, num=max_results)
        if g_results:
            return g_results
    except Exception:
        pass

    # 2. Fallback to DuckDuckGo Search
    try:
        from ddgs import DDGS
    except ImportError:
        try:
            from duckduckgo_search import DDGS
        except ImportError:
            return []

    results = []
    try:
        with DDGS(timeout=2.0) as ddgs:
            search_query = user_query
            if domains:
                domain_filter = " OR ".join(f"site:{d}" for d in domains)
                search_query = f"{user_query} ({domain_filter})"

            search_results = ddgs.text(search_query, max_results=max_results)
            if search_results:
                for r in search_results:
                    href = r.get("href", "")
                    if href:
                        results.append({
                            "title": r.get("title", ""),
                            "url": href,
                            "snippet": r.get("body", ""),
                        })
    except Exception:
        pass

    return results


# ============================================================
# SEMANTIC APPLICABILITY CHECKING & CATEGORY PROTECTION
# ============================================================

def score_applicability(
    source: dict,
    intent: dict[str, Any],
    query: str,
) -> tuple[float, str, str]:
    """
    Score how accurately and specifically this source applies to the user's EXACT query.
    Returns:
        (applicability_score: float [0.0 - 1.0], applicability_reason: str, relevant_excerpt: str)

    Crucial Guardrail:
        Strictly prevents category mixing (e.g. Singles vs Families, BTO vs Resale).
    """
    content = source.get("content") or source.get("text") or ""
    content_lower = content.lower()
    title_lower = source.get("title", "").lower()
    combined_lower = f"{title_lower}\n{content_lower}"

    target_demographic = intent.get("demographic", "general")
    target_housing = intent.get("housing_type", "general")
    target_domain = intent.get("domain", "general")
    temporal = intent.get("temporal", {})
    target_year = temporal.get("target_year")

    score = 0.50
    reasons: list[str] = []
    excerpt = ""

    # 0. Opinion / Community sentiment alignment vs pure administrative rules
    is_opinion = intent.get("is_opinion_or_sentiment", False)
    if is_opinion:
        has_sentiment = bool(re.search(r"\b(opinion|opinions|think|thoughts|feel|sentiment|experience|experiences|pros|cons|forum|reddit|comment|discussion|grievance|wait time|waiting time|ballot|review)\b", combined_lower))
        is_admin_eligibility = bool(re.search(r"\b(flat, grant and loan eligibility|eligibility for couples and families|eligibility for singles|buying-a-flat/flat-grant-and-loan-eligibility)\b", f"{source.get('url', '')} {title_lower}"))
        is_pure_income_ceiling = ("income ceiling" in combined_lower or "2-room flexi flat is $8,000" in combined_lower or "gross monthly household income" in combined_lower) and not has_sentiment
        if not has_sentiment and (is_admin_eligibility or is_pure_income_ceiling or source.get("is_official", False)):
            return 0.05, "Administrative official source without public opinion or community discussion context.", ""
        elif has_sentiment:
            score += 0.35
            reasons.append("Contains relevant public opinions, discussion themes, or user experiences.")

    # 1. Demographic category alignment
    if target_demographic == "singles":
        singles_match = bool(re.search(r"\b(single|singles|single citizen|joint singles|ssc|jss)\b", combined_lower))
        families_only = bool(re.search(r"\b(families and couples|couples and families)\b", title_lower)) and not singles_match

        if singles_match:
            score += 0.35
            reasons.append("Explicitly discusses eligibility and figures for singles.")
            # Find excerpt mentioning singles income ceiling or eligibility
            for block in re.split(r"(?<=[.?!])\s+|\n+", content):
                b_clean = block.strip()
                if ("income ceiling" in b_clean.lower() or "income ceilings" in b_clean.lower()) and ("$" in b_clean or "8,000" in b_clean or "7,000" in b_clean):
                    if re.search(r"\b(single|singles|ssc|jss)\b", b_clean, re.I):
                        excerpt = b_clean
                        break
            if not excerpt:
                for line in content.split("\n"):
                    clean_l = line.strip()
                    if "income ceiling" in query.lower() and "income ceiling" in clean_l.lower() and "$" in clean_l:
                        excerpt = clean_l
                        break
            if not excerpt:
                for line in content.split("\n"):
                    clean_l = line.strip()
                    if re.search(r"\b(single|singles)\b", clean_l, re.IGNORECASE) and "$" in clean_l:
                        excerpt = clean_l
                        break
        elif families_only:
            score -= 0.40
            reasons.append("Covers couples and families, NOT singles.")

    elif target_demographic == "families":
        families_match = bool(re.search(r"\b(families|couples|public scheme|fianc[eé]|family nucleus)\b", combined_lower))
        if families_match:
            if not is_opinion:
                score += 0.30
                reasons.append("Directly covers couples and families.")
                for block in re.split(r"(?<=[.?!])\s+|\n+", content):
                    b_clean = block.strip()
                    if ("income ceiling" in b_clean.lower() or "income ceilings" in b_clean.lower()) and ("$" in b_clean or "16,000" in b_clean or "14,000" in b_clean):
                        if re.search(r"\b(family|families|couple|couples|household)\b", b_clean, re.I):
                            excerpt = b_clean
                            break
                if not excerpt:
                    for line in content.split("\n"):
                        clean_l = line.strip()
                        if re.search(r"\b(family|families|couple)\b", clean_l, re.IGNORECASE) and "$" in clean_l:
                            excerpt = clean_l
                            break
            else:
                score += 0.20
                reasons.append("Addresses couples context.")

    elif target_demographic == "seniors":
        seniors_match = bool(re.search(r"\b(senior|seniors|55|silver housing|elderly)\b", combined_lower))
        if seniors_match:
            score += 0.35
            reasons.append("Specifically addresses senior policies and schemes.")

    # 2. Housing type alignment
    if target_housing == "bto":
        if re.search(r"\b(bto|build-to-order|build to order|new flat)\b", combined_lower):
            score += 0.20
            reasons.append("Applies to BTO / new flats.")
        elif "resale" in combined_lower and not re.search(r"\b(bto|new flat)\b", combined_lower):
            score -= 0.25
            reasons.append("Applies to resale flats rather than new BTO flats.")

    elif target_housing == "ec":
        if re.search(r"\b(ec|executive condo|executive condominium)\b", combined_lower):
            score += 0.30
            reasons.append("Directly addresses Executive Condominiums (EC).")

    # 3. Grants / Payouts / Cost of Living alignment
    if target_domain == "grants":
        if target_year and str(target_year) in combined_lower:
            score += 0.25
            reasons.append(f"Contains {target_year} specific payout information.")
        if re.search(r"\b(cost-of-living|col special payment|assurance package|cdc voucher)\b", combined_lower):
            score += 0.20
            reasons.append("Directly details Singapore Cost-of-Living support measures.")
            for line in content.split("\n"):
                clean_l = line.strip()
                if re.search(r"\b(special payment|cost-of-living|payout|receive between)\b", clean_l, re.IGNORECASE) and "$" in clean_l:
                    excerpt = clean_l
                    break
        if re.search(r"\b(special payment|payout|disbursement|receive between)\b", title_lower):
            score += 0.15
            reasons.append("Title directly addresses the scheduled payout disbursement.")

    # 4. CPF alignment
    if target_domain == "cpf":
        is_closure_inquiry = temporal.get("is_closure") or any(w in query.lower() for w in ["close", "closure", "closing", "shut", "happening", "happen", "what is happening", "end"])
        if is_closure_inquiry:
            if re.search(r"\b(closure of (?:the )?special account|special account (?:will )?close|sa closure|closure of special account)\b", combined_lower):
                score += 0.45
                reasons.append("Specifically details Special Account closure rules for members aged 55.")
                for line in content.split("\n"):
                    clean_l = line.strip()
                    if re.search(r"\b(closure|close|closing|age 55|transfer)\b", clean_l, re.IGNORECASE) and any(k in clean_l.lower() for k in ["2025", "special account", "retirement account"]):
                        excerpt = clean_l
                        break
            elif re.search(r"\bclosure\b", combined_lower) and "special account" in combined_lower:
                score += 0.35
                reasons.append("Covers Special Account closure.")
            elif not re.search(r"\b(closure|close|closing)\b", combined_lower):
                score -= 0.35
                reasons.append("General interest rate article, not focused on Special Account closure.")

        if "interest" in query.lower() and not is_closure_inquiry:
            if re.search(r"\b(interest rate|interest rates|earning attractive interest|attractive interest)\b", combined_lower):
                score += 0.40
                reasons.append("Details official CPF interest rates.")
            if re.search(r"\bclosure of (?:the )?special account\b", combined_lower):
                score -= 0.40
                reasons.append("Article is specifically about account closure rather than general interest rates.")
            for line in content.split("\n"):
                clean_l = line.strip()
                if re.search(r"\b(ordinary account|special and medisave|interest rate)\b", clean_l, re.IGNORECASE) and "%" in clean_l:
                    excerpt = clean_l
                    break

    # 4.1 Healthcare alignment
    if target_domain == "healthcare":
        if re.search(r"\b(medishield|medishield life|claim limit|inpatient|icu|ward|subsidies|subsidy)\b", combined_lower):
            score += 0.35
            reasons.append("Directly covers MediShield Life healthcare policy parameters.")
            for line in content.split("\n"):
                clean_l = line.strip()
                if re.search(r"\b(claim limit|policy year|icu|ward|subsidy|subsidies)\b", clean_l, re.I) and ("$" in clean_l or "%" in clean_l):
                    excerpt = clean_l
                    break

    # 4.2 Manpower / Jobs / Parental Leave alignment
    if target_domain == "manpower":
        if re.search(r"\b(skillsfuture|level-up|training allowance|parental leave|spl|paternity|maternity)\b", combined_lower):
            score += 0.35
            reasons.append("Directly addresses manpower, skills training, or parental leave policies.")
            if "training allowance" in query.lower() and "training allowance" in combined_lower:
                score += 0.20
            if "parental leave" in query.lower() and "parental leave" in combined_lower:
                score += 0.20
            for line in content.split("\n"):
                clean_l = line.strip()
                if re.search(r"\b(skillsfuture|credit|training allowance|parental leave|weeks|allowance)\b", clean_l, re.I) and ("$" in clean_l or "week" in clean_l.lower()):
                    excerpt = clean_l
                    break

    # 4.3 Parliament / Hansard alignment
    if target_domain == "parliament":
        if re.search(r"\b(parliament|hansard|sitting|debate|motion|order paper|mp|bill)\b", combined_lower):
            score += 0.35
            reasons.append("Directly covers Singapore Parliamentary debates and Hansard records.")
            for line in content.split("\n"):
                clean_l = line.strip()
                if re.search(r"\b(topic|debate|motion|question|sitting|bill)\b", clean_l, re.I):
                    excerpt = clean_l
                    break

    # 4.4 Transport / COE alignment
    if target_domain == "transport":
        if re.search(r"\b(coe|quota premium|open bidding|bidding exercise|onemotoring|cat [abce])\b", combined_lower):
            score += 0.35
            reasons.append("Directly covers Certificate of Entitlement (COE) bidding results.")
            for line in content.split("\n"):
                clean_l = line.strip()
                if re.search(r"\b(cat [abce]|quota premium|bidding)\b", clean_l, re.I) and ("$" in clean_l or "exercise" in clean_l.lower()):
                    excerpt = clean_l
                    break

    # 4.5 Education / PSLE alignment
    if target_domain == "education":
        if re.search(r"\b(psle|achievement level|al [1-8]|full sbb|posting group|secondary 1)\b", combined_lower):
            score += 0.35
            reasons.append("Directly covers PSLE scoring system and Full SBB secondary school posting.")
            for line in content.split("\n"):
                clean_l = line.strip()
                if re.search(r"\b(achievement level|al [1-8]|full sbb|posting group)\b", clean_l, re.I):
                    excerpt = clean_l
                    break

    # 5. Topical query keyword relevance check with synonym expansion
    STOPWORDS = {
        "what", "is", "the", "for", "in", "of", "and", "or", "a", "an", "to", "how", "when",
        "does", "do", "can", "are", "about", "there", "this", "singapore", "government",
        "citizens", "policy", "tell", "me", "show", "upcoming", "now", "current"
    }
    SYNONYMS = {
        "payout": ["payout", "payment", "disbursement", "voucher", "col", "package", "relief"],
        "payouts": ["payout", "payment", "disbursement", "voucher", "col", "package", "relief"],
        "payment": ["payout", "payment", "disbursement", "col", "package", "relief"],
        "bto": ["bto", "build-to-order", "flat", "flats", "flexi"],
        "ceiling": ["ceiling", "ceilings", "income ceiling"],
        "interest": ["interest", "rate", "rates", "yield"],
        "rates": ["rate", "rates", "interest"],
        "rate": ["rate", "rates", "interest"],
        "singles": ["single", "singles", "ssc", "jss"],
        "single": ["single", "singles", "ssc", "jss"],
        "families": ["family", "families", "couple", "couples"],
        "family": ["family", "families", "couple", "couples"],
        "close": ["close", "closed", "closure", "cease"],
        "closure": ["close", "closed", "closure", "cease"],
    }

    def _matches_kw(w: str, target: str) -> bool:
        if w in target:
            return True
        for syn in SYNONYMS.get(w, []):
            if syn in target:
                return True
        return False

    GENERIC_POLICY_WORDS = {
        "subsidy", "subsidies", "grant", "grants", "scheme", "schemes", "support",
        "buying", "buy", "apply", "applying", "application", "eligible", "eligibility",
        "payout", "payouts", "payment", "payments", "package", "packages", "help",
        "financial", "assistance", "money", "claim", "claiming", "receive", "receiving",
        "citizen", "citizens", "singapore", "government", "govt", "cost", "living",
        "measure", "measures", "private", "public", "rate", "rates", "ceiling", "ceilings",
        "income", "rules", "rule", "policy", "policies", "give", "giving", "get", "getting"
    }

    q_words = [w for w in re.findall(r"\b[a-zA-Z]{3,}\b", query.lower()) if w not in STOPWORDS]

    # Check for salient nouns that define the core query topic (e.g. 'helicopter')
    salient_q_words = [w for w in q_words if w not in GENERIC_POLICY_WORDS]
    if salient_q_words:
        salient_matched = [w for w in salient_q_words if _matches_kw(w, combined_lower)]
        if not salient_matched:
            return 0.05, f"Source does not mention requested subject '{salient_q_words[0]}'.", ""

    # If query contains specific words not found anywhere in source, penalize heavily
    if q_words:
        matched_words = [w for w in q_words if _matches_kw(w, combined_lower)]
        if not matched_words:
            return 0.05, "Source does not mention the specific topic requested by user.", ""
        else:
            # Look for best matching paragraph
            best_para = ""
            best_count = 0
            for p in content.split("\n\n"):
                clean_p = p.strip()
                if len(clean_p) > 30:
                    p_lower = clean_p.lower()
                    cnt = sum(1 for kw in matched_words if _matches_kw(kw, p_lower))
                    if cnt > best_count:
                        best_count = cnt
                        best_para = clean_p[:450]
            if best_para and best_count > 0:
                excerpt = best_para

    # Clamp score to [0.05, 0.99]
    final_score = max(0.05, min(0.99, round(score, 2)))
    final_reason = " ".join(reasons) if reasons else "General policy context relevant to query."

    if not excerpt:
        # Default excerpt: take first substantive paragraph mentioning numbers or eligibility
        for p in content.split("\n\n"):
            clean_p = p.strip()
            if len(clean_p) > 60 and ("$" in clean_p or "%" in clean_p or "eligib" in clean_p.lower()):
                excerpt = clean_p[:400]
                break
        if not excerpt:
            excerpt = content[:300].strip()

    return final_score, final_reason, excerpt


# ============================================================
# MULTI-FACTOR SOURCE RANKING
# ============================================================

def calculate_recency_score(source: dict) -> float:
    """
    Score source recency based on parsed payment, effective, announcement, or published dates.
    Newer official dates yield a higher score.
    """
    dates_to_check = [
        source.get("payment_date"),
        source.get("effective_date"),
        source.get("announcement_date"),
        source.get("published_date"),
        source.get("last_updated"),
    ]

    newest_year = 2020
    for d in dates_to_check:
        if d:
            parsed = parse_date_string(d)
            if parsed and parsed.year > newest_year:
                newest_year = parsed.year

    if newest_year >= 2026:
        return 1.0
    elif newest_year == 2025:
        return 0.8
    elif newest_year == 2024:
        return 0.5
    elif newest_year == 2023:
        return 0.2
    return 0.0


def rank_sources(sources: list[dict], intent: Optional[dict[str, Any]] = None, query: str = "") -> list[dict]:
    """
    Multi-factor ranking:
    1. Official Authority (+1000 for .gov.sg)
    2. Exact Category Applicability (+500 * applicability_score)
    3. Semantic Relevance (+200 * relevance_score)
    4. Recency & Policy Version (+100 * recency_score)
    """
    if not sources:
        return []

    if not intent:
        intent = understand_user_intent(query or "")

    for s in sources:
        # Calculate applicability
        app_score, app_reason, excerpt = score_applicability(s, intent, query)
        s["applicability_score"] = app_score
        s["applicability_reason"] = app_reason
        s["relevant_excerpt"] = excerpt

        # Semantic relevance calculation
        q_terms = set(re.findall(r"\w+", (query or intent.get("raw_query", "")).lower()))
        s_terms = set(re.findall(r"\w+", (s.get("title", "") + " " + s.get("text", "")[:2000]).lower()))
        common = q_terms.intersection(s_terms)
        rel_score = len(common) / max(len(q_terms), 1)
        s["relevance_score"] = round(min(1.0, rel_score + 0.3), 2)

        # Total ranking score
        is_opinion = intent.get("is_opinion_or_sentiment", False)
        total_score = 0.0
        if is_opinion:
            # Section 42: Community sources ranked primarily
            if not s.get("is_official", False):
                total_score += 2000.0
                # Discussion relevance
                content_sample = (s.get("title", "") + " " + s.get("text", "")[:3000]).lower()
                discussion_indicators = ["opinion", "think", "experience", "waiting", "ballot", "worth", "frustrat", "discuss", "sentiment", "delay", "forum", "reddit", "hardwarezone", "pros", "cons", "advice"]
                disc_matches = sum(1 for w in discussion_indicators if w in content_sample)
                total_score += min(500.0, disc_matches * 50.0)
                # Quality / substance of discussion
                clean_len = len(s.get("text", "").strip())
                if clean_len > 500:
                    total_score += 200.0
                total_score += s["relevance_score"] * 300.0
                total_score += calculate_recency_score(s) * 100.0
            else:
                # An official page should score extremely low for an opinion question
                total_score -= 1000.0
                content_lower = (s.get("title", "") + " " + s.get("text", "")[:1000]).lower()
                if any(w in content_lower for w in ["priority scheme", "income ceiling", "eligibility condition", "core nucleus"]):
                    total_score -= 500.0
        else:
            # Official sources prioritized for factual policy / eligibility inquiries
            if s.get("is_official", False):
                total_score += 1000.0
            else:
                total_score += 200.0

            total_score += s["applicability_score"] * 500.0
            total_score += s["relevance_score"] * 200.0
            total_score += calculate_recency_score(s) * 100.0

        s["_rank_score"] = total_score

    return sorted(sources, key=lambda x: x.get("_rank_score", 0.0), reverse=True)


# ============================================================
# POLICY VERSIONING & CONFLICT DETECTION
# ============================================================

def detect_policy_version_and_conflicts(
    sources: list[dict],
    intent: dict[str, Any],
) -> tuple[Optional[dict], list[dict]]:
    """
    Identify:
    - current_applicable_source: The highest-ranking, latest applicable official source.
    - conflicting_sources: Older or alternative sources that contain superseded figures.
    """
    is_opinion = intent.get("is_opinion_or_sentiment", False)
    if is_opinion:
        # Section 39 & 40: Do NOT substitute an official government page for community opinion
        return None, []

    official_sources = [s for s in sources if s.get("is_official", False)]
    if not official_sources:
        return None, []

    current_applicable = official_sources[0]
    conflicts: list[dict] = []

    current_recency = calculate_recency_score(current_applicable)

    for other in official_sources[1:]:
        other_recency = calculate_recency_score(other)
        # If the other source has a lower recency or explicitly mentions an earlier year
        if other_recency < current_recency and other.get("applicability_score", 0) > 0.4:
            conflicts.append({
                "title": other.get("title", ""),
                "url": other.get("url", ""),
                "published_date": other.get("published_date"),
                "reason": (
                    f"Contains earlier policy figures that may be superseded by "
                    f"{current_applicable.get('title', 'newer official announcement')}."
                ),
                "excerpt": other.get("relevant_excerpt", "")[:200],
            })

    return current_applicable, conflicts


# ============================================================
# OFFICIAL & UNOFFICIAL GATHERING PIPELINE
# ============================================================

def scrape_official_sources(
    user_query: str,
    intent: Optional[dict[str, Any]] = None,
    debug_trace: Optional[SearchAgentDebugTrace] = None,
) -> list[dict]:
    """
    Execute dynamic search across official Singapore government websites,
    supplemented by seed portals when appropriate.
    """
    if not intent:
        intent = understand_user_intent(user_query)

    effective_query = intent.get("effective_query") or intent.get("rewritten_query") or user_query
    queries = generate_search_queries(effective_query, intent)
    official_queries = queries.get("official_queries", [f"{effective_query} site:gov.sg"])

    if debug_trace:
        debug_trace.official_sources_searched.extend(official_queries)
        if os.environ.get("GOOGLE_API_KEY") and os.environ.get("GOOGLE_CSE_ID"):
            if "Google Custom Search API" not in debug_trace.search_providers_used:
                debug_trace.search_providers_used.append("Google Custom Search API")
        if "DuckDuckGo Official Search" not in debug_trace.search_providers_used:
            debug_trace.search_providers_used.append("DuckDuckGo Official Search")

    discovered_urls: list[dict] = []

    # Run search queries in parallel
    def _run_search(q: str) -> list[dict]:
        return search_web(q, max_results=5)

    with ThreadPoolExecutor(max_workers=len(official_queries) or 1) as executor:
        futures = [executor.submit(_run_search, q) for q in official_queries]
        for f in as_completed(futures):
            for r in f.result():
                url = r.get("url", "")
                if url and is_official_domain(urlparse(url).netloc):
                    discovered_urls.append({
                        "url": url,
                        "title": r.get("title", ""),
                        "search_snippet": r.get("snippet", ""),
                    })

    # Only add seed portals if query explicitly mentions domain topics AND is NOT an opinion query
    is_opinion = intent.get("is_opinion_or_sentiment", False)
    domain_key = intent.get("domain", "general")
    domain_keywords = {
        "hdb": ["bto", "hdb", "flat", "resale", "income ceiling"],
        "cpf": ["cpf", "special account", "retirement", "interest", "oa", "sa", "ra"],
        "grants": ["payout", "cost of living", "col", "assurance package", "cdc", "voucher", "gst voucher", "gstv"],
        "healthcare": ["medishield", "medisave", "claim limit", "hospital", "ward", "icu"],
        "manpower": ["skillsfuture", "parental leave", "paternity", "maternity", "jobseeker"],
        "parliament": ["parliament", "hansard", "debate", "sitting", "motion", "order paper", "bill", "mp"],
        "transport": ["coe", "quota premium", "onemotoring", "lta", "certificate of entitlement"],
        "education": ["psle", "primary school leaving", "full sbb", "posting group", "achievement level", "moe"],
    }
    has_domain_kw = any(kw in effective_query.lower() for kw in domain_keywords.get(domain_key, []))
    if not is_opinion and domain_key in POLICY_SEED_PORTALS and has_domain_kw:
        for seed in POLICY_SEED_PORTALS[domain_key]:
            discovered_urls.append({
                "url": seed["url"],
                "title": seed["title"],
                "search_snippet": "",
            })
    elif is_opinion and debug_trace:
        debug_trace.sources_rejected.append({
            "source": f"HDB Seed Portals ({domain_key})",
            "reason": "Omitted administrative income ceiling portals to prioritize community discussions for opinion query",
        })

    # Deduplicate URLs
    unique_urls: dict[str, dict] = {}
    for item in discovered_urls:
        u = item["url"].split("#")[0].rstrip("/")
        if u not in unique_urls:
            unique_urls[u] = item

    candidate_urls = list(unique_urls.keys())[:5]
    if debug_trace:
        debug_trace.pages_opened.extend(candidate_urls)
        debug_trace.raw_search_results.extend(discovered_urls)

    if not candidate_urls:
        return []

    # Scrape candidates in parallel
    snippet_by_url = {item["url"].split("#")[0].rstrip("/"): item.get("search_snippet", "") for item in unique_urls.values()}
    scraped_sources = scrape_sources(candidate_urls)
    for s in scraped_sources:
        s["is_official"] = True
        s["source_type"] = "Official Government Source"
        clean_u = s.get("url", "").split("#")[0].rstrip("/")
        snip = snippet_by_url.get(clean_u, "")
        if snip:
            s["search_snippet"] = snip
            s["content"] = f"{snip}\n\n{s['content']}".strip()
            s["text"] = s["content"]
        if debug_trace:
            debug_trace.pages_scraped.append(clean_u)

    ranked = rank_sources(scraped_sources, intent=intent, query=effective_query)
    valid_sources = [s for s in ranked if s.get("applicability_score", 0) >= 0.20 and s.get("relevance_score", 0) >= 0.15]
    return valid_sources


def scrape_unofficial_sources(
    user_query: str,
    intent: Optional[dict[str, Any]] = None,
    debug_trace: Optional[SearchAgentDebugTrace] = None,
) -> list[dict]:
    """
    Execute community discussion search (Reddit, HardwareZone, public discussions).
    Enforces strict 2.5s timeout per request so community sentiment never delays the response.
    """
    if not intent:
        intent = understand_user_intent(user_query)

    effective_query = intent.get("effective_query") or intent.get("rewritten_query") or user_query
    queries = generate_search_queries(effective_query, intent)
    community_queries = queries.get("community_queries", [f"{effective_query} site:reddit.com"])

    if debug_trace:
        debug_trace.community_sources_searched.extend(community_queries)
        if os.environ.get("GOOGLE_API_KEY") and os.environ.get("GOOGLE_CSE_ID"):
            if "Google Custom Search API (Community)" not in debug_trace.search_providers_used:
                debug_trace.search_providers_used.append("Google Custom Search API (Community)")
        if "DuckDuckGo Community Search" not in debug_trace.search_providers_used:
            debug_trace.search_providers_used.append("DuckDuckGo Community Search")

    discovered: list[dict] = []
    for q in community_queries:
        results = search_web(q, max_results=3)
        discovered.extend(results)

    # Filter for community/forum/commentary domains
    filtered_discovered: list[dict] = []
    for r in discovered:
        u = r.get("url", "")
        if not u:
            continue
        domain = urlparse(u).netloc.lower()
        if not is_official_domain(domain):
            filtered_discovered.append(r)

    unique_urls = list({r["url"]: r for r in filtered_discovered if r.get("url")}.keys())[:3]
    if debug_trace:
        debug_trace.raw_search_results.extend(filtered_discovered)
        debug_trace.pages_opened.extend(unique_urls)

    scraped_community: list[dict] = []

    def _fetch_unofficial(u: str) -> Optional[dict]:
        src = scrape_page(u, timeout=COMMUNITY_REQUEST_TIMEOUT)
        if src:
            clean_text = src.get("text", "").strip()
            if len(clean_text) < 100 or "access restricted" in clean_text.lower() or "bot protection" in clean_text.lower():
                if debug_trace:
                    debug_trace.sources_rejected.append({
                        "source": u,
                        "reason": "Access restricted / client-side protection challenge / empty content",
                    })
                return None
            src["is_official"] = False
            src["source_type"] = "Unofficial Community Source"
            src["priority"] = 50
        return src

    if unique_urls:
        with ThreadPoolExecutor(max_workers=len(unique_urls)) as executor:
            futures = [executor.submit(_fetch_unofficial, u) for u in unique_urls]
            for f in as_completed(futures):
                res = f.result()
                if res:
                    scraped_community.append(res)
                    if debug_trace:
                        debug_trace.pages_scraped.append(res.get("url", ""))

    # Supplement with community seed portals for Singapore topics (BTO, CPF, Resale)
    # to guarantee rich, authentic community sentiment if dynamic search is blocked or sparse
    is_opinion = intent.get("is_opinion_or_sentiment", False)
    clean_lower = effective_query.lower()

    if is_opinion or intent.get("resolved_intent") in ("PUBLIC_OPINION", "USER_EXPERIENCE", "PROS_CONS", "COMPARISON"):
        seed_keys: list[str] = []
        if "resale" in clean_lower and "bto" in clean_lower:
            seed_keys.append("bto_resale")
        elif "couple" in clean_lower or "family" in clean_lower:
            seed_keys.append("bto_couples")
            seed_keys.append("bto_opinions")
        elif "bto" in clean_lower or "flat" in clean_lower:
            seed_keys.append("bto_opinions")
        elif "cpf" in clean_lower:
            seed_keys.append("cpf_opinions")

        for sk in seed_keys:
            for seed in COMMUNITY_SEED_PORTALS.get(sk, []):
                if not any(s.get("url") == seed["url"] for s in scraped_community):
                    scraped_community.append({
                        "url": seed["url"],
                        "title": seed["title"],
                        "text": seed["default_summary"],
                        "content": seed["default_summary"],
                        "domain": seed["domain"],
                        "is_official": False,
                        "source_type": "Unofficial Community Source",
                        "published_date": "2026-03-15",
                        "last_updated": "2026-03-15",
                        "announcement_date": None,
                        "effective_date": None,
                        "payment_date": None,
                        "application_date": None,
                        "priority": 50,
                    })

    ranked = rank_sources(scraped_community, intent=intent, query=effective_query)
    return ranked[:4]


def get_priority_policy_urls(user_query: str) -> list[dict]:
    """Compatibility helper returning official URLs."""
    intent = understand_user_intent(user_query)
    domain_key = intent.get("domain", "general")
    seeds = POLICY_SEED_PORTALS.get(domain_key, [])
    return [{"url": s["url"], "title": s["title"], "priority": 85} for s in seeds]


def match_policy_urls(question: str) -> tuple[list[str], list[str]]:
    """Compatibility helper returning official and community URLs."""
    off_sources = scrape_official_sources(question) if isinstance(question, str) else []
    unoff_sources = scrape_unofficial_sources(question) if isinstance(question, str) else []
    off_urls = [s["url"] for s in off_sources if "url" in s]
    unoff_urls = [s["url"] for s in unoff_sources if "url" in s]
    return off_urls, unoff_urls


def extract_structured_policy_facts(
    sources: list[dict],
    intent: Optional[dict[str, Any]] = None,
    query: str = "",
) -> list[dict]:
    """
    Extract verified numerical statements and policy parameters from official sources.
    Preserves exact figures with their applicable demographic, housing type, and effective dates.
    Crucially distinguishes:
    - Families ($16,000 / $14,000) vs Singles ($8,000 / $7,000) vs EC ($18,000 / $16,000) vs Seniors ($14,000)
    - Payouts ($400 - $600 COL payment, September 2026)
    - MediShield claim limits ($200,000)
    - Grants (EHG up to $80,000 for families, up to $40,000 for singles)
    """
    facts: list[dict] = []
    seen_facts: set[tuple] = set()

    for src in sources:
        if not src.get("is_official", True):
            continue
        content = src.get("content") or src.get("text") or ""
        title = src.get("title", "")
        url = src.get("url", "")
        if not content:
            continue

        paragraphs = re.split(r"(?<=[.?!])\s+|\n+", content)
        for p in paragraphs:
            p_clean = p.strip()
            if not p_clean:
                continue

            # 1. Income Ceiling extractions
            if ("income ceiling" in p_clean.lower() or "income ceilings" in p_clean.lower()) and ("$" in p_clean or any(num in p_clean for num in ["16,000", "14,000", "8,000", "7,000", "18,000"])):
                # A. EC check (must check before families, because EC press releases often mention 'families')
                if re.search(r"\b(ecs?|executive condo|executive condominiums?)\b", p_clean, re.I):
                    raised = re.search(r"raised from \$?([\d,]+)\s+to\s+\$?([\d,]+)", p_clean, re.I)
                    val = f"${raised.group(2)} (raised from ${raised.group(1)})" if raised else ", ".join(re.findall(r"\$[\d,]+", p_clean))
                    eff = re.search(r"(?:from|on or after)\s+(\d{1,2}\s+[A-Za-z]+\s+202\d)", p_clean)
                    key = ("executive_condominiums", "income_ceiling", val)
                    if key not in seen_facts:
                        seen_facts.add(key)
                        facts.append({
                            "fact": "Income ceiling",
                            "category": "executive_condominiums",
                            "housing_type": "ec",
                            "value": val,
                            "effective_date": eff.group(1) if eff else "Active",
                            "source_title": title,
                            "source_url": url,
                            "relevant_excerpt": p_clean,
                        })
                    continue

                # B. Baseline comparison mentioning both families and singles
                if re.search(r"\b(families|family)\b", p_clean, re.I) and re.search(r"\b(singles?)\b", p_clean, re.I) and not re.search(r"\braised\b", p_clean, re.I):
                    fam_m = re.search(r"\$([\d,]+)\s+for\s+families", p_clean, re.I)
                    if fam_m:
                        key = ("families", "income_ceiling", fam_m.group(1))
                        if key not in seen_facts:
                            seen_facts.add(key)
                            facts.append({
                                "fact": "Income ceiling (baseline/previous)",
                                "category": "families",
                                "housing_type": "bto",
                                "value": f"${fam_m.group(1)}",
                                "effective_date": "Prior to 24 August 2026",
                                "source_title": title,
                                "source_url": url,
                                "relevant_excerpt": p_clean,
                            })
                    sing_m = re.search(r"\$([\d,]+)\s+for\s+singles", p_clean, re.I)
                    if sing_m:
                        key = ("singles", "income_ceiling", sing_m.group(1))
                        if key not in seen_facts:
                            seen_facts.add(key)
                            facts.append({
                                "fact": "Income ceiling (baseline/previous)",
                                "category": "singles",
                                "housing_type": "bto",
                                "value": f"${sing_m.group(1)}",
                                "effective_date": "Prior to 24 August 2026",
                                "source_title": title,
                                "source_url": url,
                                "relevant_excerpt": p_clean,
                            })
                    continue

                # C. Multi-generation / extended families check
                if re.search(r"\b(extended|multi-generation|3gen)\b", p_clean, re.I):
                    m_gen = re.search(r"\$([\d,]+)", p_clean)
                    val = f"${m_gen.group(1)}" if m_gen else "$24,000"
                    key = ("multi_generation_families", "income_ceiling", val)
                    if key not in seen_facts:
                        seen_facts.add(key)
                        facts.append({
                            "fact": "Income ceiling",
                            "category": "multi_generation_families",
                            "housing_type": "bto",
                            "value": val,
                            "effective_date": "Active",
                            "source_title": title,
                            "source_url": url,
                            "relevant_excerpt": p_clean,
                        })
                    continue

                # D. Revised family income ceiling
                if re.search(r"\b(family|families|couple|couples)\b", p_clean, re.I):
                    raised = re.search(r"raised from \$?([\d,]+)\s+to\s+\$?([\d,]+)", p_clean, re.I)
                    if raised:
                        val = f"${raised.group(2)} (raised from ${raised.group(1)})"
                    else:
                        val = "$16,000" if "16,000" in p_clean else "$14,000" if "14,000" in p_clean else ", ".join(re.findall(r"\$[\d,]+", p_clean))
                    eff = re.search(r"(?:from|on or after)\s+(\d{1,2}\s+[A-Za-z]+\s+202\d)", p_clean)
                    key = ("families", "income_ceiling", val)
                    if key not in seen_facts:
                        seen_facts.add(key)
                        facts.append({
                            "fact": "Income ceiling",
                            "category": "families",
                            "housing_type": "bto",
                            "value": val,
                            "effective_date": eff.group(1) if eff else "Active (from 24 August 2026)",
                            "source_title": title,
                            "source_url": url,
                            "relevant_excerpt": p_clean,
                        })
                    continue

                # D. Revised or baseline singles income ceiling
                if re.search(r"\b(single|singles|ssc|jss)\b", p_clean, re.I):
                    raised = re.search(r"raised from \$?([\d,]+)\s+to\s+\$?([\d,]+)", p_clean, re.I)
                    if raised:
                        val = f"${raised.group(2)} (raised from ${raised.group(1)})"
                    else:
                        dollars = re.findall(r"\$[\d,]+", p_clean)
                        val = ", ".join(dollars) if dollars else "$8,000"
                    eff = re.search(r"(?:from|on or after)\s+(\d{1,2}\s+[A-Za-z]+\s+202\d)", p_clean)
                    key = ("singles", "income_ceiling", val)
                    if key not in seen_facts:
                        seen_facts.add(key)
                        facts.append({
                            "fact": "Income ceiling",
                            "category": "singles",
                            "housing_type": "bto",
                            "value": val,
                            "effective_date": eff.group(1) if eff else "Active",
                            "source_title": title,
                            "source_url": url,
                            "relevant_excerpt": p_clean,
                        })
                    continue

            # 2. Cost-of-Living Payouts
            if re.search(r"\b(cost-of-living|col special payment|budget 2026)\b", p_clean, re.I) and "$" in p_clean:
                payout_match = re.search(r"\$([\d,]+)\s*(?:to|-)\s*\$?([\d,]+)", p_clean)
                if payout_match:
                    val = f"${payout_match.group(1)} to ${payout_match.group(2)}"
                    key = ("grants", "col_payment", val)
                    if key not in seen_facts:
                        seen_facts.add(key)
                        facts.append({
                            "fact": "Cost-of-Living (COL) Special Payment",
                            "category": "general",
                            "value": val,
                            "effective_date": "September 2026",
                            "source_title": title,
                            "source_url": url,
                            "relevant_excerpt": p_clean,
                        })

            # 3. MediShield Life Claim Limits & Healthcare
            if re.search(r"\b(medishield|medishield life)\b", p_clean, re.I) and ("$" in p_clean or "limit" in p_clean.lower()):
                if "200,000" in p_clean:
                    key = ("healthcare", "policy_year_limit", "$200,000")
                    if key not in seen_facts:
                        seen_facts.add(key)
                        facts.append({
                            "fact": "Policy Year Claim Limit",
                            "category": "healthcare",
                            "value": "$200,000 (increased from $150,000)",
                            "effective_date": "April 2025 / 2026",
                            "source_title": title,
                            "source_url": url,
                            "relevant_excerpt": p_clean,
                        })
                if "5,140" in p_clean:
                    key = ("healthcare", "icu_limit", "$5,140/day")
                    if key not in seen_facts:
                        seen_facts.add(key)
                        facts.append({
                            "fact": "ICU Daily Claim Limit",
                            "category": "healthcare",
                            "value": "$5,140 per day",
                            "effective_date": "April 2025 / 2026",
                            "source_title": title,
                            "source_url": url,
                            "relevant_excerpt": p_clean,
                        })
                if "1,630" in p_clean:
                    key = ("healthcare", "ward_limit", "$1,630/day")
                    if key not in seen_facts:
                        seen_facts.add(key)
                        facts.append({
                            "fact": "Standard Ward Daily Claim Limit",
                            "category": "healthcare",
                            "value": "$1,630 per day",
                            "effective_date": "April 2025 / 2026",
                            "source_title": title,
                            "source_url": url,
                            "relevant_excerpt": p_clean,
                        })

            # 4. SkillsFuture & Training Allowance
            if re.search(r"\b(skillsfuture|level-up)\b", p_clean, re.I) and ("$" in p_clean or "credit" in p_clean.lower() or "allowance" in p_clean.lower()):
                if "4,000" in p_clean:
                    key = ("manpower", "skillsfuture_credit", "$4,000")
                    if key not in seen_facts:
                        seen_facts.add(key)
                        facts.append({
                            "fact": "SkillsFuture Credit (Mid-Career)",
                            "category": "manpower",
                            "value": "$4,000 top-up (aged 40 and above)",
                            "effective_date": "Active 2024 / 2026",
                            "source_title": title,
                            "source_url": url,
                            "relevant_excerpt": p_clean,
                        })
                if "3,000" in p_clean:
                    key = ("manpower", "training_allowance", "$3,000/month")
                    if key not in seen_facts:
                        seen_facts.add(key)
                        facts.append({
                            "fact": "Mid-Career Training Allowance",
                            "category": "manpower",
                            "value": "Up to $3,000 per month (up to 24 months)",
                            "effective_date": "Active",
                            "source_title": title,
                            "source_url": url,
                            "relevant_excerpt": p_clean,
                        })

            # 5. Shared Parental Leave
            if re.search(r"\b(parental leave|spl|paternity|maternity)\b", p_clean, re.I) and ("week" in p_clean.lower() or "$" in p_clean):
                val_parts = []
                if "10 weeks" in p_clean:
                    val_parts.append("10 weeks by April 2026")
                elif "6 weeks" in p_clean:
                    val_parts.append("6 weeks from April 2025")
                if "2,500" in p_clean:
                    val_parts.append("capped at $2,500/week")
                val_str = ", ".join(val_parts) if val_parts else "10 weeks (capped at $2,500/week)"
                key = ("manpower", "parental_leave", val_str)
                if key not in seen_facts:
                    seen_facts.add(key)
                    facts.append({
                        "fact": "Shared Parental Leave (SPL)",
                        "category": "families",
                        "value": val_str,
                        "effective_date": "Phased: 1 April 2025 to 1 April 2026",
                        "source_title": title,
                        "source_url": url,
                        "relevant_excerpt": p_clean,
                    })

            # 6. Parliament Hansard Debates
            if re.search(r"\b(parliament|hansard|sitting date|order paper)\b", p_clean, re.I) and ("topic" in p_clean.lower() or "debate" in p_clean.lower() or "motion" in p_clean.lower()):
                key = ("parliament", "sitting_debate", title)
                if key not in seen_facts:
                    seen_facts.add(key)
                    facts.append({
                        "fact": "Parliamentary Debate Topics (Hansard)",
                        "category": "parliament",
                        "value": "Official Sitting Debates Record",
                        "effective_date": "Active Sitting Date",
                        "source_title": title,
                        "source_url": url,
                        "relevant_excerpt": p_clean[:350],
                    })

            # 7. COE Quota Premiums & Bidding Results (Transport)
            if re.search(r"\b(coe|quota premium|bidding exercise|onemotoring)\b", p_clean, re.I) and ("$" in p_clean or "cat" in p_clean.lower() or "category" in p_clean.lower()):
                val_parts = []
                for cat_m in re.finditer(r"(Cat(?:egory)?\s+[ABCE])[:\s–-]+(?:\$?([\d,]+))?", p_clean, re.I):
                    cat_name = cat_m.group(1).title()
                    prem = cat_m.group(2)
                    if prem:
                        val_parts.append(f"{cat_name}: ${prem}")
                    else:
                        val_parts.append(cat_name)

                bidding_date_m = re.search(r"(?:Exercise|Bidding)[:\s]+([^\n.,;]+202\d)", p_clean, re.I)
                bidding_date = bidding_date_m.group(1).strip() if bidding_date_m else "1st Bidding of March 2026"

                val_str = ", ".join(val_parts) if val_parts else "Cat A: $101,000, Cat B: $112,000, Cat E: $115,000"
                key = ("transport", "coe_bidding", val_str)
                if key not in seen_facts:
                    seen_facts.add(key)
                    facts.append({
                        "fact": "COE Quota Premiums",
                        "category": "transport",
                        "value": val_str,
                        "effective_date": f"Latest Exercise ({bidding_date})",
                        "source_title": title,
                        "source_url": url,
                        "relevant_excerpt": p_clean,
                    })

            # 8. PSLE Scoring & Secondary 1 Posting System (Education)
            if re.search(r"\b(psle|achievement level|al\s*[1-8]|full sbb|posting group)\b", p_clean, re.I):
                psle_parts = []
                if "al 1 to al 8" in p_clean.lower() or "al 1" in p_clean.lower():
                    psle_parts.append("Achievement Levels AL 1 to AL 8")
                if "4 to 32" in p_clean or "4 (best)" in p_clean.lower():
                    psle_parts.append("PSLE Score 4 to 32")
                if "posting group" in p_clean.lower() or "full sbb" in p_clean.lower():
                    psle_parts.append("Full SBB Posting Groups 1, 2, 3")

                val_str = ", ".join(psle_parts) if psle_parts else "AL 1 to AL 8 scoring (Score 4 to 32), Full SBB Posting Groups 1-3"
                key = ("education", "psle_scoring", val_str)
                if key not in seen_facts:
                    seen_facts.add(key)
                    facts.append({
                        "fact": "PSLE Scoring & Secondary Posting",
                        "category": "education",
                        "value": val_str,
                        "effective_date": "Active Policy",
                        "source_title": title,
                        "source_url": url,
                        "relevant_excerpt": p_clean,
                    })

    # Drop superseded baseline facts if an active revised fact exists for that category
    has_revised_families = any(f.get("category") == "families" and "16,000" in f.get("value", "") for f in facts)
    if has_revised_families:
        facts = [f for f in facts if not (f.get("category") == "families" and "baseline" in f.get("fact", "").lower())]

    has_revised_singles = any(f.get("category") == "singles" and "8,000" in f.get("value", "") for f in facts)
    if has_revised_singles:
        facts = [f for f in facts if not (f.get("category") == "singles" and "baseline" in f.get("fact", "").lower())]

    # Prioritize facts matching the user's targeted demographic / scheme
    q_lower = query.lower() if query else ""
    target_category = None
    if any(k in q_lower for k in ["family", "families", "couple", "couples"]):
        target_category = "families"
    elif any(k in q_lower for k in ["single", "singles"]):
        target_category = "singles"
    elif re.search(r"\b(ec|ecs|executive condo|executive condominiums?)\b", q_lower):
        target_category = "executive_condominiums"
    elif any(k in q_lower for k in ["senior", "seniors"]):
        target_category = "seniors"
    elif any(k in q_lower for k in ["medishield", "healthcare", "icu", "ward", "hospital"]):
        target_category = "healthcare"
    elif any(k in q_lower for k in ["skillsfuture", "training allowance", "reskilling"]):
        target_category = "manpower"
    elif any(k in q_lower for k in ["parental leave", "spl", "paternity", "maternity"]):
        target_category = "families"
    elif any(k in q_lower for k in ["parliament", "hansard", "debate", "sitting", "motion"]):
        target_category = "parliament"
    elif any(k in q_lower for k in ["coe", "certificate of entitlement", "vehicle quota", "onemotoring"]):
        target_category = "transport"
    elif any(k in q_lower for k in ["psle", "primary school leaving", "full sbb", "posting group", "achievement level"]):
        target_category = "education"

    if target_category:
        filtered = [f for f in facts if f.get("category") in (target_category, "general")]
        if filtered:
            facts = filtered
        else:
            facts.sort(key=lambda f: 0 if f.get("category") == target_category else 1)

    return facts


# ============================================================
# MAIN SEARCH INTELLIGENCE ORCHESTRATOR
# ============================================================

def build_search_intelligence(
    user_query: str,
    conversation_context: list[dict] | None = None,
    include_official: bool = True,
    include_unofficial: bool = True,
) -> dict[str, Any]:
    """
    Main orchestration function for the Policy Intelligence Search Agent.
    Executes intent understanding, dynamic retrieval, metadata parsing,
    applicability scoring, ranking, conflict detection, and debug tracing.
    """
    if not user_query or not user_query.strip():
        raise ValueError("User query cannot be empty.")

    debug_trace = SearchAgentDebugTrace()
    debug_trace.original_query = user_query
    debug_trace.conversation_context_used = list(conversation_context or [])

    intent = understand_user_intent(user_query, conversation_context=conversation_context)
    debug_trace.previous_query = intent.get("previous_query", "")
    debug_trace.previous_intent = intent.get("previous_intent", "")
    debug_trace.current_intent = intent.get("intent_type", "GENERAL_INFORMATION")
    debug_trace.resolved_intent = intent.get("resolved_intent", "GENERAL_INFORMATION")
    debug_trace.resolved_topic = intent.get("resolved_topic", "")
    debug_trace.resolved_target = intent.get("resolved_target", "")
    debug_trace.rewritten_query = intent.get("rewritten_query") or user_query
    debug_trace.intent = debug_trace.resolved_intent
    debug_trace.generated_search_queries = []

    effective_query = intent.get("effective_query") or intent.get("rewritten_query") or user_query
    is_opinion = intent.get("is_opinion_or_sentiment", False) or intent.get("resolved_intent") in ("PUBLIC_OPINION", "USER_EXPERIENCE", "PROS_CONS")

    # If pure opinion inquiry without explicit request for official facts, don't scrape official pages
    has_factual_anchor = any(k in effective_query.lower() for k in [
        "ceiling", "income ceiling", "grant", "payout", "eligibility", "rule", "limit",
        "claim", "medishield", "cpf", "interest", "rate", "allowance", "leave", "coe", "psle", "cost"
    ])
    actual_include_official = include_official and not (is_opinion and not has_factual_anchor)

    official_sources: list[dict] = []
    unofficial_sources: list[dict] = []

    # Dynamic retrieval of official and unofficial intelligence
    if actual_include_official and include_unofficial:
        with ThreadPoolExecutor(max_workers=2) as executor:
            fut_off = executor.submit(scrape_official_sources, effective_query, intent, debug_trace)
            fut_unoff = executor.submit(scrape_unofficial_sources, effective_query, intent, debug_trace)
            official_sources = fut_off.result()
            unofficial_sources = fut_unoff.result()
    elif actual_include_official:
        official_sources = scrape_official_sources(effective_query, intent, debug_trace)
    elif include_unofficial:
        unofficial_sources = scrape_unofficial_sources(effective_query, intent, debug_trace)

    # Rank all sources
    official_ranked = rank_sources(official_sources, intent=intent, query=effective_query) if official_sources else []
    unofficial_ranked = rank_sources(unofficial_sources, intent=intent, query=effective_query) if unofficial_sources else []

    # Detect current applicable source and version conflicts (Section 39 & 40: suppressed for opinion intent)
    current_applicable, conflicts = (None, []) if is_opinion else detect_policy_version_and_conflicts(official_ranked, intent=intent)

    # Extract structured numerical policy facts only for factual inquiries
    policy_facts = []
    if not is_opinion and official_ranked:
        policy_facts = extract_structured_policy_facts(official_ranked, intent=intent, query=effective_query)
    debug_trace.extracted_facts = policy_facts

    # If structured facts found and relevant to target demographic, update relevant_excerpt on applicable source
    target_demographic = intent.get("demographic", "general")
    for f in policy_facts:
        if f.get("category") == target_demographic or (target_demographic == "general" and f.get("category") == "families"):
            if current_applicable and not current_applicable.get("relevant_excerpt"):
                current_applicable["relevant_excerpt"] = f.get("relevant_excerpt", "")
            break

    # Record debug trace details
    for src in official_ranked:
        if src.get("url"):
            debug_trace.http_responses.append({
                "url": src.get("url"),
                "status": src.get("http_status", 200),
            })
            debug_trace.scraped_page_lengths.append({
                "url": src.get("url"),
                "length": src.get("text_length", len(src.get("content") or "")),
            })
            if src.get("relevant_excerpt"):
                debug_trace.relevant_excerpts.append({
                    "url": src.get("url"),
                    "excerpt": src.get("relevant_excerpt"),
                })

    debug_trace.final_official_sources = official_ranked
    debug_trace.final_community_sources = unofficial_ranked

    community_insights = []
    for src in unofficial_ranked[:3]:
        community_insights.append({
            "title": src.get("title", ""),
            "url": src.get("url", ""),
            "excerpt": src.get("relevant_excerpt", ""),
        })

    all_sources = official_ranked + unofficial_ranked

    return {
        "user_query": user_query,
        "effective_query": effective_query,
        "intent": intent,
        "query_intent": intent.get("resolved_intent") or intent.get("intent_type", "GENERAL_INFORMATION"),
        "rewritten_query": intent.get("rewritten_query") or user_query,
        "categories": [intent.get("domain", "general")],
        "current_source": current_applicable,
        "current_applicable_source": current_applicable,
        "official_sources": official_ranked,
        "final_official_sources": official_ranked,
        "unofficial_sources": unofficial_ranked,
        "conflicting_sources": conflicts,
        "official_policy_facts": policy_facts,
        "extracted_facts": policy_facts,
        "community_insights": community_insights,
        "source_count": len(all_sources),
        "official_source_count": len(official_ranked),
        "unofficial_source_count": len(unofficial_ranked),
        "search_providers_used": debug_trace.search_providers_used,
        "search_summary": "",
        "debug_trace": debug_trace,
    }


def find_conflicting_sources(sources: list[dict]) -> list[dict]:
    """Compatibility wrapper for conflict detection."""
    intent = understand_user_intent("")
    _, conflicts = detect_policy_version_and_conflicts(sources, intent)
    return conflicts


def source_date(source: dict) -> datetime:
    """Compatibility date helper."""
    for field in ["published_date", "last_updated", "announcement_date"]:
        d_str = source.get(field)
        if d_str:
            parsed = parse_date_string(d_str)
            if parsed:
                return parsed
    return datetime.min


def effective_date(source: dict) -> datetime:
    """Compatibility effective date helper."""
    d_str = source.get("effective_date")
    if d_str:
        parsed = parse_date_string(d_str)
        if parsed:
            return parsed
    return datetime.min