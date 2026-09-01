import unittest
from unittest.mock import patch

from agents.search import (
    build_search_synthesis_prompt,
    gather_and_search,
)
from services.webscraper import (
    detect_policy_categories,
    extract_dates,
    extract_effective_dates,
    get_priority_policy_urls,
    match_policy_urls,
    scrape_page,
)


class SearchAgentTests(unittest.TestCase):
    def test_detect_policy_categories(self):
        cats = detect_policy_categories("What is the BTO income ceiling for families?")
        self.assertIn("hdb", cats)

        cats_cpf = detect_policy_categories("What is the CPF Full Retirement Sum?")
        self.assertIn("cpf", cats_cpf)

    def test_extract_dates(self):
        text = "This policy was published on 22 August 2026 for public consultation."
        dates = extract_dates(text)
        self.assertTrue(len(dates) > 0)
        self.assertEqual(dates[0].year, 2026)

    def test_extract_effective_dates(self):
        text = "The new rules will take effect with effect from 1 January 2026."
        effective = extract_effective_dates(text)
        self.assertTrue(len(effective) > 0)
        self.assertEqual(effective[0].year, 2026)

    def test_priority_policy_urls(self):
        urls = get_priority_policy_urls("What is the BTO income ceiling for singles?")
        self.assertTrue(len(urls) > 0)
        self.assertTrue(any("hdb.gov.sg" in u["url"] for u in urls))

    @patch("services.webscraper.search_web", return_value=[])
    def test_match_policy_urls(self, mock_search):
        off_urls, comm_urls = match_policy_urls("What are HDB BTO singles eligibility criteria?")
        self.assertTrue(len(off_urls) > 0)
        self.assertTrue(any("hdb.gov.sg" in u for u in off_urls))

    @patch("agents.search.ask_nova", return_value="Synthesized Search Summary")
    def test_gather_and_search_with_provided_sources(self, mock_ask):
        result = gather_and_search(
            question="What is the CPF retirement sum?",
            provided_sources=[
                {
                    "title": "CPF Board",
                    "url": "https://www.cpf.gov.sg",
                    "content": "BRS is $106,500.",
                    "source_type": "Official Government Source",
                    "is_official": True,
                    "last_updated": "2025-01-01",
                }
            ],
        )

        self.assertEqual(len(result["official_sources"]), 1)
        self.assertEqual(result["search_summary"], "Synthesized Search Summary")
        self.assertEqual(result["official_sources"][0]["last_updated"], "2025-01-01")

    def test_empty_question_validation(self):
        with self.assertRaises(ValueError):
            gather_and_search(question="")


if __name__ == "__main__":
    unittest.main()
