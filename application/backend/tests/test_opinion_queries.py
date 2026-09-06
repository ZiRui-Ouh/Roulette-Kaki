"""
Acceptance tests for Community / Public Opinion queries and strict source-type separation.

Covers Prompt 37-45:
1. "What are public opinions about BTO in Singapore?"
   - Intent classified as community/opinion
   - Community sources prioritized (Reddit, HardwareZone, forums)
   - Official HDB policy pages are NOT substituted as public opinion
   - Final answer contains actual community sentiment themes (waiting times, ballot uncertainty, affordability)
2. "What is the BTO income ceiling?"
   - Official HDB sources prioritized
   - Authoritative numerical figure provided
   - Community discussions not treated as authoritative policy evidence
3. "What do people think about the BTO income ceiling?"
   - Community sources prioritized for opinions
   - HDB used only for factual context
   - Clear separation between policy fact and public reaction
4. Community search failure fallback
   - If community search finds no discussions, returns explicit insufficient evidence notice
   - Does NOT fall back to an unrelated official policy page merely because of topic keyword
"""

import os
import unittest

os.environ["ROUTER_MODE"] = "llm"
os.environ["USE_LOCAL_STUBS"] = "1"

from agents.query import answer_question
from services.search_service import fetch_from_search_agent
from agents.main_agent import create_search_plan


class TestOpinionQueries(unittest.TestCase):

    def setUp(self):
        os.environ["ROUTER_MODE"] = "llm"
        os.environ["USE_LOCAL_STUBS"] = "1"

    def test_bto_public_opinions_query(self):
        """Test 1: 'What are public opinions about BTO in Singapore?' returns community sentiment, not Priority Schemes."""
        question = "What are public opinions about BTO in Singapore?"
        
        # 1. Check Main Agent classification
        plan = create_search_plan(question)
        self.assertIn(plan.intent, ("public_opinion", "user_experience", "pros_cons"))
        self.assertIn("community_search", plan.agents_to_invoke)
        self.assertNotIn("official_search", plan.agents_to_invoke)

        # 2. Check End-to-End Query Agent answer
        ans = answer_question(question)
        ans_lower = ans.lower()

        # Must contain community sentiment markers
        self.assertTrue(
            "community sentiment" in ans_lower or "common themes" in ans_lower or "public sentiment" in ans_lower,
            f"Expected community sentiment in answer, got: {ans}",
        )
        self.assertTrue(
            any(w in ans_lower for w in ["waiting time", "ballot", "affordab", "delay", "marriage", "couples"]),
            f"Expected discussion themes in answer, got: {ans}",
        )

        # Must NOT treat Priority Schemes or income ceiling as the primary answer
        self.assertNotIn("priority schemes", ans_lower)
        self.assertNotIn("gross monthly household income ceiling", ans_lower)

        # Sources must cite community discussions
        self.assertTrue(
            "hardwarezone" in ans_lower or "reddit" in ans_lower or "forums" in ans_lower,
            f"Expected community source citations in answer, got: {ans}",
        )

    def test_bto_factual_income_ceiling_query(self):
        """Test 2: 'What is the BTO income ceiling?' prioritizes official HDB sources and returns factual figures."""
        question = "What is the BTO income ceiling?"
        
        plan = create_search_plan(question)
        self.assertIn(plan.intent, ("eligibility", "policy_fact", "financial"))
        self.assertIn("official_search", plan.agents_to_invoke)

        ans = answer_question(question)
        ans_lower = ans.lower()

        # Must be grounded in official figures
        self.assertTrue("$16,000" in ans or "$8,000" in ans or "16,000" in ans or "8,000" in ans)
        self.assertTrue("official source" in ans_lower or "hdb" in ans_lower)

    def test_mixed_intent_bto_ceiling_opinions(self):
        """Test 3: 'What do people think about the BTO income ceiling?' separates policy fact from public reaction."""
        question = "What do people think about the BTO income ceiling?"

        plan = create_search_plan(question)
        self.assertIn(plan.intent, ("public_opinion", "user_experience"))
        self.assertIn("community_search", plan.agents_to_invoke)

        ans = answer_question(question)
        ans_lower = ans.lower()

        # Must prioritize community sentiment
        self.assertTrue(
            "community sentiment" in ans_lower or "common themes" in ans_lower or "public sentiment" in ans_lower or "opinions" in ans_lower,
            f"Expected opinion discussion in answer, got: {ans}",
        )

    def test_insufficient_community_evidence_fallback(self):
        """Test 4: Section 43 - community search failure does not fall back to an unrelated official page."""
        # Query with deliberate obscure topic that has no public forum discussions
        res = fetch_from_search_agent(
            question="What are public opinions about obscure unknown policy xyz 999?",
            need_official=False,
            need_community=True,
            community_queries=["obscure unknown policy xyz 999 reddit hardwarezone"],
            provided_sources=[],
        )
        self.assertEqual(len(res.get("unofficial_sources", [])), 0)
        self.assertIsNone(res.get("current_applicable_source"))
        self.assertIn("insufficient", res.get("search_summary", "").lower())


if __name__ == "__main__":
    unittest.main()
