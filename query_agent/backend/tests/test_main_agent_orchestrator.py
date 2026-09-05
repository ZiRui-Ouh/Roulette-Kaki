"""
Unit and Integration Tests for Main Agent / LLM Orchestrator and Verification.

Covers the 8 core scenarios:
1. BTO income ceiling singles (eligibility / policy_fact, official_search + verification)
2. BTO opinions (public_opinion, community_search)
3. Follow-up opinion inheritance ("What about for couples?" -> public_opinion)
4. Follow-up eligibility inheritance ("What about for couples?" -> eligibility)
5. Follow-up pros_cons inheritance ("What about for couples?" -> pros_cons)
6. Dual query ("BTO income ceiling and what do people think" -> official + community + verification)
7. Historical singles ceiling ($7,000)
8. Current singles ceiling ($8,000)
"""

import unittest
from unittest.mock import patch, MagicMock

from schemas import MainAgentPlan, SearchQueries, PolicyFact, VerificationResult
from agents.main_agent import create_search_plan
from services.verification import verify_evidence, extract_policy_facts_from_sources
from agents.query import answer_question, build_prompt


class MainAgentOrchestratorTests(unittest.TestCase):

    # =========================================================================
    # Test 1: BTO Income Ceiling for Singles (Eligibility / Policy Fact)
    # =========================================================================
    def test_01_bto_income_ceiling_singles_plan(self):
        plan = create_search_plan("What is the BTO income ceiling for singles?")
        self.assertIn(plan.intent, ("eligibility", "policy_fact"))
        self.assertIn("singles", plan.target.lower())
        self.assertEqual(plan.time_scope, "current")
        self.assertIn("official_search", plan.agents_to_invoke)
        self.assertIn("verification", plan.agents_to_invoke)
        self.assertTrue(len(plan.search_queries.official) > 0)

    # =========================================================================
    # Test 2: BTO Opinions (Public Opinion / Community Sentiment)
    # =========================================================================
    def test_02_bto_opinions_plan(self):
        plan = create_search_plan("What are people's opinions on BTO in Singapore?")
        self.assertEqual(plan.intent, "public_opinion")
        self.assertIn("community_search", plan.agents_to_invoke)
        self.assertTrue(len(plan.search_queries.community) > 0)

    # =========================================================================
    # Test 3: Follow-Up Opinion Inheritance ("What about for couples?")
    # =========================================================================
    def test_03_followup_opinion_inheritance(self):
        history = [
            {"role": "user", "content": "What are people's opinions on BTO in Singapore?"},
            {"role": "assistant", "content": "Core Answer: Many Singaporeans feel waiting times are long and balloting is stressful."},
        ]
        plan = create_search_plan("What about for couples?", conversation_context=history)
        self.assertEqual(plan.intent, "public_opinion", "Must inherit public_opinion, NOT switch to eligibility!")
        self.assertIn("couples", plan.target.lower())
        self.assertTrue(plan.is_follow_up)
        self.assertIn("community_search", plan.agents_to_invoke)
        self.assertNotIn("official_search", plan.agents_to_invoke)

    # =========================================================================
    # Test 4: Follow-Up Eligibility Inheritance ("What about for couples?")
    # =========================================================================
    def test_04_followup_eligibility_inheritance(self):
        history = [
            {"role": "user", "content": "What is the BTO income ceiling?"},
            {"role": "assistant", "content": "The BTO income ceiling depends on the household structure."},
        ]
        plan = create_search_plan("What about for couples?", conversation_context=history)
        self.assertIn(plan.intent, ("eligibility", "policy_fact"), "Must inherit eligibility intent!")
        self.assertIn("couples", plan.target.lower())
        self.assertTrue(plan.is_follow_up)
        self.assertIn("official_search", plan.agents_to_invoke)

    # =========================================================================
    # Test 5: Follow-Up Pros & Cons Inheritance ("What about for couples?")
    # =========================================================================
    def test_05_followup_pros_cons_inheritance(self):
        history = [
            {"role": "user", "content": "What are the pros and cons of BTO?"},
            {"role": "assistant", "content": "The pros include subsidies and new leases; cons include construction wait times."},
        ]
        plan = create_search_plan("What about for couples?", conversation_context=history)
        self.assertIn(plan.intent, ("pros_cons", "public_opinion"), "Must inherit pros_cons or opinion intent!")
        self.assertIn("couples", plan.target.lower())
        self.assertTrue(plan.is_follow_up)
        self.assertIn("community_search", plan.agents_to_invoke)

    # =========================================================================
    # Test 6: Dual Query (Policy Fact + Public Opinion)
    # =========================================================================
    def test_06_dual_query_agents_invoked(self):
        plan = create_search_plan("What is the BTO income ceiling and what do people think about it?")
        self.assertIn("official_search", plan.agents_to_invoke)
        self.assertIn("community_search", plan.agents_to_invoke)
        self.assertIn("verification", plan.agents_to_invoke)
        self.assertTrue(len(plan.search_queries.official) > 0)
        self.assertTrue(len(plan.search_queries.community) > 0)

    # =========================================================================
    # Test 7: Historical Singles Ceiling ($7,000)
    # =========================================================================
    def test_07_historical_singles_ceiling_verification(self):
        plan = create_search_plan("What was the previous BTO income ceiling for singles?")
        self.assertEqual(plan.time_scope, "historical")

        sample_sources = [
            {
                "title": "HDB Pulse: Income Ceilings Revision",
                "url": "https://www.hdb.gov.sg/news/income-ceilings",
                "domain": "hdb.gov.sg",
                "is_official": True,
                "content": (
                    "The monthly household income ceiling for eligible first-timer singles buying a new "
                    "2-room Flexi flat has been raised from $7,000 to $8,000. Previously, the ceiling was $7,000 for singles."
                ),
            }
        ]

        verification = verify_evidence(
            official_sources=sample_sources,
            unofficial_sources=[],
            plan=plan,
        )

        self.assertEqual(verification.time_scope_applied, "historical")
        self.assertTrue(len(verification.historical_facts) > 0)
        hist_values = [f.value for f in verification.historical_facts if f.category == "singles"]
        self.assertIn("$7,000", hist_values)

    # =========================================================================
    # Test 8: Current Singles Ceiling ($8,000)
    # =========================================================================
    def test_08_current_singles_ceiling_verification(self):
        plan = create_search_plan("What is the current BTO income ceiling for singles?")
        self.assertEqual(plan.time_scope, "current")

        sample_sources = [
            {
                "title": "HDB Pulse: Income Ceilings Revision",
                "url": "https://www.hdb.gov.sg/news/income-ceilings",
                "domain": "hdb.gov.sg",
                "is_official": True,
                "content": (
                    "The monthly household income ceiling for eligible first-timer singles buying a new "
                    "2-room Flexi flat has been raised from $7,000 to $8,000."
                ),
            }
        ]

        verification = verify_evidence(
            official_sources=sample_sources,
            unofficial_sources=[],
            plan=plan,
        )

        self.assertEqual(verification.time_scope_applied, "current")
        self.assertTrue(len(verification.current_facts) > 0)
        curr_values = [f.value for f in verification.current_facts if f.category == "singles"]
        self.assertIn("$8,000", curr_values)


if __name__ == "__main__":
    unittest.main()
