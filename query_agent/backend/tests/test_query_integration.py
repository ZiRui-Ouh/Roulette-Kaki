import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient

from main import app
from agents.query import build_prompt, answer_question


class QueryIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_build_prompt_structure(self):
        prompt = build_prompt(
            question="Can singles buy 3-room BTO?",
            official_sources=[
                {
                    "title": "HDB Flat Eligibility",
                    "url": "https://www.hdb.gov.sg/singles",
                    "content": "Singles can buy 2-room Flexi flats in all locations.",
                    "source_type": "Housing & Development Board (Official)",
                }
            ],
            unofficial_sources=[
                {
                    "title": "Reddit Singapore Discussion",
                    "url": "https://reddit.com/r/singapore",
                    "content": "Singles hope 3-room flats will be allowed in future.",
                    "source_type": "Reddit Singapore",
                }
            ],
            search_agent_data="Search Agent summary: HDB official policy allows 2-room flexi.",
        )

        self.assertIn("RETRIEVED OFFICIAL SOURCES", prompt)
        self.assertIn("SEARCH AGENT SYNTHESIS", prompt)
        self.assertIn("Can singles buy 3-room BTO?", prompt)

    @patch("agents.query.fetch_from_search_agent")
    @patch("agents.query.ask_nova")
    def test_answer_question_invokes_search_agent(self, mock_ask, mock_search):
        mock_search.return_value = {
            "official_sources": [
                {
                    "title": "CPF LIFE Schemes",
                    "url": "https://www.cpf.gov.sg/cpf-life",
                    "content": "Standard, Basic, and Escalating plans available.",
                    "source_type": "CPF Board (Official)",
                    "is_official": True,
                }
            ],
            "unofficial_sources": [
                {
                    "title": "HWZ Discussion",
                    "url": "https://forums.hardwarezone.com.sg",
                    "content": "Many prefer the Escalating plan for inflation.",
                    "source_type": "HardwareZone Forum",
                    "is_official": False,
                }
            ],
            "search_summary": "CPF LIFE provides lifelong monthly payouts from age 65.",
        }
        mock_ask.return_value = "CPF LIFE offers three plans: Standard, Basic, and Escalating.\n- Payouts start from age 65.\n- Lifelong monthly income."

        answer = answer_question(
            question="How do CPF LIFE plans differ?",
            enable_search=True,
        )

        mock_search.assert_called_once()
        mock_ask.assert_called_once()
        self.assertIn("CPF LIFE", answer)
        self.assertIn("Standard", answer)

    @patch("agents.query.fetch_from_search_agent")
    @patch("agents.query.ask_nova")
    def test_api_endpoint_post_query(self, mock_ask, mock_search):
        mock_search.return_value = {
            "official_sources": [
                {
                    "title": "SkillsFuture Level-Up",
                    "url": "https://www.skillsfuture.gov.sg",
                    "content": "$4,000 credit for Singaporeans aged 40 and above.",
                    "source_type": "SkillsFuture SG (Official)",
                    "is_official": True,
                }
            ],
            "unofficial_sources": [],
            "search_summary": "SkillsFuture Level-Up programme provides $4k credit.",
        }
        mock_ask.return_value = "Singaporeans aged 40 and above receive a $4,000 SkillsFuture Credit top-up."

        response = self.client.post("/query", json={"question": "What is the SkillsFuture Level-Up top up?"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("answer", data)
        self.assertIn("SkillsFuture", data["answer"])

    def test_api_home_health_endpoint(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("search_agent_integrated"))

    def test_empty_question_raises(self):
        with self.assertRaises(ValueError):
            answer_question(question="   ")


if __name__ == "__main__":
    unittest.main()
