"""
Pydantic Schemas for the LLM Main Agent, Search Planning, and Verification.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

IntentType = Literal[
    "eligibility",
    "policy_fact",
    "public_opinion",
    "user_experience",
    "pros_cons",
    "comparison",
    "process/how_to",
    "announcement/update",
    "follow_up",
    "unclear",
]

TimeScope = Literal["current", "historical", "upcoming", "general"]

AgentType = Literal["official_search", "community_search", "verification"]


class SearchQueries(BaseModel):
    official: List[str] = Field(default_factory=list, description="Targeted queries for official gov.sg sources")
    community: List[str] = Field(default_factory=list, description="Targeted queries for public forums (Reddit, HardwareZone)")


class MainAgentPlan(BaseModel):
    intent: IntentType = Field(..., description="Classified intent of the question")
    topic: str = Field(..., description="Primary policy or legislative subject, e.g. BTO, CPF, MediShield")
    target: str = Field(default="general", description="Target demographic, group, or scheme, e.g. singles, couples, families, seniors")
    location: str = Field(default="Singapore", description="Geographic jurisdiction")
    time_scope: TimeScope = Field(default="current", description="Temporal scope of inquiry: current, historical, upcoming, or general")
    is_follow_up: bool = Field(default=False, description="Whether this question is an elliptical or contextual follow-up to prior turns")
    resolved_query: str = Field(..., description="Standalone, unambiguous rewritten query incorporating previous conversation context")
    agents_to_invoke: List[AgentType] = Field(
        default_factory=lambda: ["official_search", "verification"],
        description="Sub-agents required for gathering and verifying evidence",
    )
    search_queries: SearchQueries = Field(
        default_factory=SearchQueries,
        description="Specific search query strings generated for each search agent",
    )
    reasoning_summary: str = Field(..., description="Concise rationale for the plan and routing decision")


class PolicyFact(BaseModel):
    fact: str = Field(..., description="Policy parameter or figure description")
    category: str = Field(..., description="Applicable category, e.g. singles, families, ec")
    housing_type: Optional[str] = Field(default="bto", description="Housing scheme or flat type")
    value: str = Field(..., description="Numerical figure or rule, e.g. $8,000, $16,000, 2.5%")
    effective_date: Optional[str] = Field(default=None, description="Date from which this policy became active")
    source_title: Optional[str] = Field(default=None, description="Title of the citing official source")
    source_url: Optional[str] = Field(default=None, description="URL of the citing official source")
    relevant_excerpt: Optional[str] = Field(default=None, description="Direct excerpt containing the fact")
    is_current: bool = Field(default=True, description="True if active/current, False if superseded/historical")


class VerificationResult(BaseModel):
    primary_source: Optional[Dict[str, Any]] = Field(default=None, description="Most authoritative and relevant source")
    conflicts: List[Dict[str, Any]] = Field(default_factory=list, description="Superseded or conflicting older sources detected")
    current_facts: List[PolicyFact] = Field(default_factory=list, description="Active/current policy facts and numerical figures")
    historical_facts: List[PolicyFact] = Field(default_factory=list, description="Historical/previous policy figures")
    community_insights: List[Dict[str, Any]] = Field(default_factory=list, description="Verified public sentiment and themes")
    time_scope_applied: TimeScope = Field(default="current", description="Time scope applied during verification")
    verification_summary: str = Field(default="", description="Summary of verification decisions and applicability")


class SearchPolicyInput(BaseModel):
    question: str = Field(..., description="The user's query or resolved question to search")
    target: str = Field(default="general", description="Target demographic, e.g. singles, couples, families, seniors")
    topic: str = Field(default="Singapore Policy", description="Primary topic, e.g. BTO, CPF, MediShield")
    fact_type: str = Field(default="general", description="Type of fact, e.g. income_ceiling, interest_rate, payout_amount, public_opinion")
    housing_type: Optional[str] = Field(default=None, description="Flat or housing type, e.g. 2-room Flexi, BTO, resale, EC")
    time_scope: TimeScope = Field(default="current", description="Temporal scope: current, historical, upcoming")
    need_official: bool = Field(default=True, description="Whether official government retrieval is required")
    need_community: bool = Field(default=False, description="Whether unofficial public forum sentiment retrieval is required")
    official_queries: List[str] = Field(default_factory=list, description="Targeted query strings for official gov.sg sources")
    community_queries: List[str] = Field(default_factory=list, description="Targeted query strings for Reddit/HardwareZone")


class StructuredEvidenceResult(BaseModel):
    is_sufficient: bool = Field(default=True, description="Whether returned evidence sufficiently answers the question")
    insufficiency_reason: Optional[str] = Field(default=None, description="Reason if evidence is deemed insufficient")
    target: str = Field(default="general", description="Demographic targeted in search")
    topic: str = Field(default="", description="Topic searched")
    fact_type: str = Field(default="", description="Fact type searched")
    primary_source: Optional[Dict[str, Any]] = Field(default=None, description="Primary authoritative source dict")
    extracted_facts: List[PolicyFact] = Field(default_factory=list, description="Fact-level structured evidence")
    official_sources: List[Dict[str, Any]] = Field(default_factory=list, description="All retrieved official sources")
    unofficial_sources: List[Dict[str, Any]] = Field(default_factory=list, description="All retrieved unofficial sources")
    conflicts: List[Dict[str, Any]] = Field(default_factory=list, description="Conflicting or superseded sources")
    community_insights: List[Dict[str, Any]] = Field(default_factory=list, description="Public sentiment themes and discussions")
    search_summary: str = Field(default="", description="Summary synthesized by search agent")

