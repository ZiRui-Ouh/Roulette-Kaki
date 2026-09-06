"""Tests for the /debates/{date}/chat web-search fallback.

When research_agent.run_chat returns grounded=False, main.chat_debate
should try the Policy Query Agent's orchestrator + Search Agent bridge.
These tests patch research, main_agent, search bridge, and bedrock so
nothing hits AWS or SPRS.
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from agents.research import ChatResult
from schemas import MainAgentPlan, SearchQueries
import main as main_module


def _plan(intent: str) -> MainAgentPlan:
    return MainAgentPlan(
        intent=intent,
        topic="BTO",
        target="singles",
        location="Singapore",
        time_scope="current",
        is_follow_up=False,
        resolved_query="What is the current BTO income ceiling for singles?",
        agents_to_invoke=["official_search", "verification"],
        search_queries=SearchQueries(
            official=["BTO income ceiling singles site:gov.sg"],
            community=[],
        ),
        reasoning_summary="test",
    )


def _hansard_ungrounded() -> ChatResult:
    return ChatResult(
        reply="This sitting did not cover BTO income ceilings.",
        topics_used=[],
        grounded=False,
        usage={},
    )


def _hansard_grounded() -> ChatResult:
    return ChatResult(
        reply="MPs debated the CDC voucher rollout in this sitting.",
        topics_used=["topic-1"],
        grounded=True,
        usage={},
    )


def _evidence_payload() -> dict:
    return {
        "official_sources": [
            {
                "title": "HDB — BTO Eligibility",
                "url": "https://www.hdb.gov.sg/bto/singles",
                "content": "The income ceiling for singles buying a 2-room Flexi is $8,000.",
            }
        ],
        "unofficial_sources": [],
        "search_summary": "Singles income ceiling for 2-room Flexi BTO is $8,000 (HDB).",
    }


class ResearchWebFallbackTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["ENABLE_WEB_FALLBACK"] = "1"
        # A 200 on the digest lookup is required before /chat; stub it out.
        self._digest_patch = patch(
            "services.storage.get_digest",
            return_value={"date": "2026-08-05", "topics": []},
        )
        self._session_patch = patch(
            "services.storage.get_session",
            return_value={"chat_history": []},
        )
        self._digest_patch.start()
        self._session_patch.start()
        self.client = TestClient(main_module.app)

    def tearDown(self) -> None:
        self._digest_patch.stop()
        self._session_patch.stop()
        os.environ.pop("ENABLE_WEB_FALLBACK", None)

    # ---------------------------------------------------------------
    # Happy path: policy_fact intent → fallback fires
    # ---------------------------------------------------------------
    @patch("main.bedrock_service.ask_nova", return_value="Singles income ceiling is $8,000 per HDB.")
    @patch("main.fetch_from_search_agent", return_value=_evidence_payload())
    @patch("main.create_search_plan", return_value=_plan("policy_fact"))
    @patch("main.research_agent.run_chat", return_value=_hansard_ungrounded())
    def test_fallback_fires_for_policy_intent(self, _run, _plan_mock, _fetch, _nova):
        resp = self.client.post(
            "/debates/2026-08-05/chat",
            json={
                "message": "What is the BTO income ceiling for singles?",
                "session_id": "probe-policy",
            },
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertTrue(body["grounded"], "grounded should flip to True after fallback")
        self.assertIn("This sitting did not cover", body["reply"])
        self.assertIn("Broader web sources indicate", body["reply"])
        self.assertIn("$8,000", body["reply"])

    # ---------------------------------------------------------------
    # Opinion intent must NOT trigger fallback (semantic guard)
    # ---------------------------------------------------------------
    @patch("main.bedrock_service.ask_nova")
    @patch("main.fetch_from_search_agent")
    @patch("main.create_search_plan", return_value=_plan("public_opinion"))
    @patch("main.research_agent.run_chat", return_value=_hansard_ungrounded())
    def test_fallback_skipped_for_opinion_intent(self, _run, _plan_mock, _fetch, _nova):
        resp = self.client.post(
            "/debates/2026-08-05/chat",
            json={"message": "What do people think?", "session_id": "probe-opinion"},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertFalse(body["grounded"])
        self.assertEqual(body["reply"], "This sitting did not cover BTO income ceilings.")
        _fetch.assert_not_called()
        _nova.assert_not_called()

    # ---------------------------------------------------------------
    # ENABLE_WEB_FALLBACK=0 disables the fallback entirely
    # ---------------------------------------------------------------
    @patch("main.bedrock_service.ask_nova")
    @patch("main.fetch_from_search_agent")
    @patch("main.create_search_plan", return_value=_plan("policy_fact"))
    @patch("main.research_agent.run_chat", return_value=_hansard_ungrounded())
    def test_fallback_env_kill_switch(self, _run, _plan_mock, _fetch, _nova):
        os.environ["ENABLE_WEB_FALLBACK"] = "0"
        resp = self.client.post(
            "/debates/2026-08-05/chat",
            json={"message": "What is the BTO income ceiling for singles?"},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertFalse(body["grounded"])
        _plan_mock.assert_not_called()
        _fetch.assert_not_called()
        _nova.assert_not_called()

    # ---------------------------------------------------------------
    # Grounded Hansard replies must not invoke the fallback path
    # ---------------------------------------------------------------
    @patch("main.bedrock_service.ask_nova")
    @patch("main.fetch_from_search_agent")
    @patch("main.create_search_plan")
    @patch("main.research_agent.run_chat", return_value=_hansard_grounded())
    def test_grounded_reply_untouched(self, _run, _plan_mock, _fetch, _nova):
        resp = self.client.post(
            "/debates/2026-08-05/chat",
            json={"message": "What did MPs say about CDC vouchers?"},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertTrue(body["grounded"])
        self.assertEqual(body["reply"], "MPs debated the CDC voucher rollout in this sitting.")
        _plan_mock.assert_not_called()
        _fetch.assert_not_called()
        _nova.assert_not_called()


if __name__ == "__main__":
    unittest.main()
