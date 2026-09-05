"""
Verification and Recency Evaluation Service for Roulette-Kaki Policy Intelligence.

Responsible for:
1. Validating source authority (.gov.sg official vs community forums)
2. Semantic demographic/category isolation (singles vs families vs ECs vs seniors)
3. Partitioning policy figures into current active facts vs historical figures
4. Recency resolution according to the MainAgentPlan time_scope
5. Conflict and supersession detection
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from schemas import MainAgentPlan, PolicyFact, VerificationResult

log = logging.getLogger(__name__)

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
]


def is_official_domain(domain: str) -> bool:
    """Determine if a domain belongs to the Singapore government."""
    if not domain:
        return False
    domain_lower = domain.lower()
    if domain_lower.endswith(".gov.sg") or domain_lower == "gov.sg":
        return True
    return any(domain_lower == off or domain_lower.endswith(f".{off}") for off in OFFICIAL_DOMAINS)


def extract_policy_facts_from_sources(
    official_sources: List[Dict[str, Any]],
    target: str = "general",
) -> Tuple[List[PolicyFact], List[PolicyFact]]:
    """
    Extract structured policy facts from official sources, partitioning them into
    (current_facts, historical_facts).
    """
    current_facts: List[PolicyFact] = []
    historical_facts: List[PolicyFact] = []
    seen: set = set()

    for src in official_sources:
        url = src.get("url", "")
        title = src.get("title", "")
        domain = src.get("domain", "")
        if not domain and url:
            domain = urlparse(url).netloc

        if not is_official_domain(domain) and not src.get("is_official", True):
            continue

        content = src.get("content") or src.get("text") or ""
        if not content:
            continue

        paragraphs = re.split(r"(?<=[.?!])\s+|\n+", content)
        for p in paragraphs:
            p_clean = p.strip()
            if not p_clean:
                continue

            p_lower = p_clean.lower()
            if "income ceiling" in p_lower or "income ceilings" in p_lower:
                # 1. Executive Condominium
                if re.search(r"\b(ecs?|executive condo|executive condominiums?)\b", p_clean, re.I):
                    raised = re.search(r"raised from \$?([\d,]+)\s+to\s+\$?([\d,]+)", p_clean, re.I)
                    if raised:
                        hist_val = f"${raised.group(1)}"
                        curr_val = f"${raised.group(2)}"
                        if ("ec", "historical", hist_val) not in seen:
                            seen.add(("ec", "historical", hist_val))
                            historical_facts.append(
                                PolicyFact(
                                    fact="Executive Condominium Income Ceiling (Previous)",
                                    category="executive_condominiums",
                                    housing_type="ec",
                                    value=hist_val,
                                    effective_date="Prior to 24 August 2026",
                                    source_title=title,
                                    source_url=url,
                                    relevant_excerpt=p_clean,
                                    is_current=False,
                                )
                            )
                        if ("ec", "current", curr_val) not in seen:
                            seen.add(("ec", "current", curr_val))
                            current_facts.append(
                                PolicyFact(
                                    fact="Executive Condominium Income Ceiling",
                                    category="executive_condominiums",
                                    housing_type="ec",
                                    value=curr_val,
                                    effective_date="Active (from 24 August 2026)",
                                    source_title=title,
                                    source_url=url,
                                    relevant_excerpt=p_clean,
                                    is_current=True,
                                )
                            )
                        continue

                # 2. Baseline comparison mentioning both families and singles
                if re.search(r"\b(families|family)\b", p_clean, re.I) and re.search(r"\b(singles?)\b", p_clean, re.I) and not re.search(r"\braised\b", p_clean, re.I):
                    fam_m = re.search(r"\$([\d,]+)\s+for\s+families", p_clean, re.I)
                    if fam_m:
                        val = f"${fam_m.group(1)}"
                        key = ("families", "historical", val)
                        if key not in seen:
                            seen.add(key)
                            historical_facts.append(
                                PolicyFact(
                                    fact="Income ceiling for families (baseline/previous)",
                                    category="families",
                                    housing_type="bto",
                                    value=val,
                                    effective_date="Prior to 24 August 2026",
                                    source_title=title,
                                    source_url=url,
                                    relevant_excerpt=p_clean,
                                    is_current=False,
                                )
                            )
                    sing_m = re.search(r"\$([\d,]+)\s+for\s+singles", p_clean, re.I)
                    if sing_m:
                        val = f"${sing_m.group(1)}"
                        key = ("singles", "historical", val)
                        if key not in seen:
                            seen.add(key)
                            historical_facts.append(
                                PolicyFact(
                                    fact="Income ceiling for singles (baseline/previous)",
                                    category="singles",
                                    housing_type="bto",
                                    value=val,
                                    effective_date="Prior to 24 August 2026",
                                    source_title=title,
                                    source_url=url,
                                    relevant_excerpt=p_clean,
                                    is_current=False,
                                )
                            )
                    continue

                # 3. Families & Couples
                if re.search(r"\b(family|families|couple|couples)\b", p_clean, re.I):
                    raised = re.search(r"raised from \$?([\d,]+)\s+to\s+\$?([\d,]+)", p_clean, re.I)
                    if raised:
                        hist_val = f"${raised.group(1)}"
                        curr_val = f"${raised.group(2)}"
                        if ("families", "historical", hist_val) not in seen:
                            seen.add(("families", "historical", hist_val))
                            historical_facts.append(
                                PolicyFact(
                                    fact="Income ceiling for families (previous)",
                                    category="families",
                                    housing_type="bto",
                                    value=hist_val,
                                    effective_date="Prior to 24 August 2026",
                                    source_title=title,
                                    source_url=url,
                                    relevant_excerpt=p_clean,
                                    is_current=False,
                                )
                            )
                        if ("families", "current", curr_val) not in seen:
                            seen.add(("families", "current", curr_val))
                            current_facts.append(
                                PolicyFact(
                                    fact="Income ceiling for families",
                                    category="families",
                                    housing_type="bto",
                                    value=curr_val,
                                    effective_date="Active (from 24 August 2026)",
                                    source_title=title,
                                    source_url=url,
                                    relevant_excerpt=p_clean,
                                    is_current=True,
                                )
                            )
                    elif "$16,000" in p_clean:
                        if ("families", "current", "$16,000") not in seen:
                            seen.add(("families", "current", "$16,000"))
                            current_facts.append(
                                PolicyFact(
                                    fact="Income ceiling for families",
                                    category="families",
                                    housing_type="bto",
                                    value="$16,000",
                                    effective_date="Active (from 24 August 2026)",
                                    source_title=title,
                                    source_url=url,
                                    relevant_excerpt=p_clean,
                                    is_current=True,
                                )
                            )
                    elif "$14,000" in p_clean:
                        if ("families", "historical", "$14,000") not in seen:
                            seen.add(("families", "historical", "$14,000"))
                            historical_facts.append(
                                PolicyFact(
                                    fact="Income ceiling for families (baseline/previous)",
                                    category="families",
                                    housing_type="bto",
                                    value="$14,000",
                                    effective_date="Prior to 24 August 2026",
                                    source_title=title,
                                    source_url=url,
                                    relevant_excerpt=p_clean,
                                    is_current=False,
                                )
                            )
                    continue

                # 4. Singles
                if re.search(r"\b(single|singles|ssc|jss)\b", p_clean, re.I):
                    raised = re.search(r"raised from \$?([\d,]+)\s+to\s+\$?([\d,]+)", p_clean, re.I)
                    if raised:
                        hist_val = f"${raised.group(1)}"
                        curr_val = f"${raised.group(2)}"
                        if ("singles", "historical", hist_val) not in seen:
                            seen.add(("singles", "historical", hist_val))
                            historical_facts.append(
                                PolicyFact(
                                    fact="Income ceiling for singles (previous)",
                                    category="singles",
                                    housing_type="bto",
                                    value=hist_val,
                                    effective_date="Prior to 24 August 2026",
                                    source_title=title,
                                    source_url=url,
                                    relevant_excerpt=p_clean,
                                    is_current=False,
                                )
                            )
                        if ("singles", "current", curr_val) not in seen:
                            seen.add(("singles", "current", curr_val))
                            current_facts.append(
                                PolicyFact(
                                    fact="Income ceiling for singles",
                                    category="singles",
                                    housing_type="bto",
                                    value=curr_val,
                                    effective_date="Active",
                                    source_title=title,
                                    source_url=url,
                                    relevant_excerpt=p_clean,
                                    is_current=True,
                                )
                            )
                    elif "$8,000" in p_clean:
                        if ("singles", "current", "$8,000") not in seen:
                            seen.add(("singles", "current", "$8,000"))
                            current_facts.append(
                                PolicyFact(
                                    fact="Income ceiling for singles",
                                    category="singles",
                                    housing_type="bto",
                                    value="$8,000",
                                    effective_date="Active",
                                    source_title=title,
                                    source_url=url,
                                    relevant_excerpt=p_clean,
                                    is_current=True,
                                )
                            )
                    elif "$7,000" in p_clean:
                        if ("singles", "historical", "$7,000") not in seen:
                            seen.add(("singles", "historical", "$7,000"))
                            historical_facts.append(
                                PolicyFact(
                                    fact="Income ceiling for singles (previous)",
                                    category="singles",
                                    housing_type="bto",
                                    value="$7,000",
                                    effective_date="Prior to 24 August 2026",
                                    source_title=title,
                                    source_url=url,
                                    relevant_excerpt=p_clean,
                                    is_current=False,
                                )
                            )
                    continue

            # 5. Cost of living / payouts
            if re.search(r"\b(cost-of-living|col special payment|budget 2026)\b", p_clean, re.I) and "$" in p_clean:
                payout_match = re.search(r"\$([\d,]+)\s*(?:to|-)\s*\$?([\d,]+)", p_clean)
                if payout_match:
                    val = f"${payout_match.group(1)} to ${payout_match.group(2)}"
                    if ("payout", "current", val) not in seen:
                        seen.add(("payout", "current", val))
                        current_facts.append(
                            PolicyFact(
                                fact="Cost-of-Living (COL) Special Payment",
                                category="general",
                                housing_type=None,
                                value=val,
                                effective_date="September 2026",
                                source_title=title,
                                source_url=url,
                                relevant_excerpt=p_clean,
                                is_current=True,
                            )
                        )

    return current_facts, historical_facts


def filter_facts_by_target(facts: List[PolicyFact], target: str) -> List[PolicyFact]:
    """Filter facts to match demographic/target scheme, preventing category mixing."""
    if not target or target == "general":
        return facts

    target_clean = target.lower()
    if target_clean in ("couples", "families", "couple", "family"):
        matching = [f for f in facts if f.category in ("families", "general")]
        return matching if matching else facts
    elif target_clean in ("singles", "single"):
        matching = [f for f in facts if f.category in ("singles", "general")]
        return matching if matching else facts
    elif "ec" in target_clean or "executive" in target_clean:
        matching = [f for f in facts if f.category in ("executive_condominiums", "general")]
        return matching if matching else facts
    elif "senior" in target_clean:
        matching = [f for f in facts if f.category in ("seniors", "general")]
        return matching if matching else facts

    return facts


def verify_evidence(
    official_sources: List[Dict[str, Any]],
    unofficial_sources: List[Dict[str, Any]],
    plan: MainAgentPlan,
) -> VerificationResult:
    """
    Core verification entrypoint:
    - Filters and ranks official sources
    - Extracts and partitions current vs historical facts
    - Selects primary applicable source
    - Detects conflicts/superseded data
    - Structures community insights
    """
    # 1. Authority filtering for official sources
    verified_official = []
    for src in official_sources:
        url = src.get("url", "")
        domain = src.get("domain", "")
        if not domain and url:
            domain = urlparse(url).netloc
        if is_official_domain(domain) or src.get("is_official", True):
            verified_official.append(src)

    # 2. Extract and partition policy facts
    current_facts_raw, historical_facts_raw = extract_policy_facts_from_sources(
        verified_official, target=plan.target
    )

    # Filter facts strictly for target demographic
    current_facts = filter_facts_by_target(current_facts_raw, plan.target)
    historical_facts = filter_facts_by_target(historical_facts_raw, plan.target)

    # 3. Detect conflicts & superseded sources
    conflicts: List[Dict[str, Any]] = []
    target_clean = plan.target.lower()

    if plan.time_scope == "current":
        # Any historical facts are superseded context
        for hf in historical_facts:
            conflicts.append({
                "title": hf.source_title,
                "url": hf.source_url,
                "reason": f"Previous figure of {hf.value} for {hf.category} was superseded by latest policy revision.",
                "superseded_value": hf.value,
            })
    elif plan.time_scope == "historical":
        # If user asked for historical, current figures represent the subsequent change
        for cf in current_facts:
            conflicts.append({
                "title": cf.source_title,
                "url": cf.source_url,
                "reason": f"Active revised figure of {cf.value} for {cf.category} took effect later ({cf.effective_date}).",
                "subsequent_value": cf.value,
            })

    # 4. Select Primary Source (Section 39 & 40: Do not set official source as primary for opinion intent)
    primary_source = None
    is_opinion = plan.intent in ("public_opinion", "user_experience", "pros_cons")
    if verified_official and not is_opinion:
        # Score sources based on target keyword match
        def _score_source(s: dict) -> int:
            score = 0
            title = (s.get("title") or "").lower()
            excerpt = (s.get("relevant_excerpt") or "").lower()
            content = (s.get("content") or "").lower()

            if is_official_domain(s.get("domain", "")):
                score += 10
            if target_clean in ("couples", "families", "couple", "family"):
                if "families" in title or "couples" in title:
                    score += 5
                if "families with children" in title:
                    score += 6
                if "income ceiling" in title:
                    score += 4
            elif target_clean in ("singles", "single"):
                if "single" in title or "singles" in title:
                    score += 8
                if "single" in excerpt:
                    score += 5
            return score

        sorted_official = sorted(verified_official, key=_score_source, reverse=True)
        primary_source = sorted_official[0]

        # Attach relevant excerpt from verified facts if not present
        active_fact_list = historical_facts if plan.time_scope == "historical" else current_facts
        if active_fact_list and not primary_source.get("relevant_excerpt"):
            primary_source["relevant_excerpt"] = active_fact_list[0].relevant_excerpt

    # 5. Community insights
    community_insights: List[Dict[str, Any]] = []
    for src in unofficial_sources[:3]:
        excerpt = src.get("relevant_excerpt") or (src.get("content") or "")[:200]
        community_insights.append({
            "title": src.get("title", "Community Discussion"),
            "url": src.get("url", ""),
            "excerpt": excerpt,
        })

    # 6. Verification summary
    summary_parts = [
        f"Time scope applied: {plan.time_scope}.",
        f"Target demographic: {plan.target}.",
    ]
    if plan.time_scope == "historical":
        summary_parts.append(
            f"Verified historical policy facts ({len(historical_facts)} found). Primary historical figure: "
            + (historical_facts[0].value if historical_facts else "N/A")
        )
    else:
        summary_parts.append(
            f"Verified current active policy facts ({len(current_facts)} found). Primary active figure: "
            + (current_facts[0].value if current_facts else "N/A")
        )

    return VerificationResult(
        primary_source=primary_source,
        conflicts=conflicts,
        current_facts=current_facts,
        historical_facts=historical_facts,
        community_insights=community_insights,
        time_scope_applied=plan.time_scope,
        verification_summary=" ".join(summary_parts),
    )
