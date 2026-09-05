import unittest
from unittest.mock import patch

from agents.search import (
    build_search_synthesis_prompt,
    gather_and_search,
)
from services.webscraper import (
    detect_policy_categories,
    detect_policy_version_and_conflicts,
    extract_dates,
    extract_effective_dates,
    extract_granular_dates,
    get_priority_policy_urls,
    match_policy_urls,
    rank_sources,
    score_applicability,
    scrape_page,
    understand_user_intent,
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

    def test_extract_granular_dates(self):
        text = (
            "Budget 2026 News Release: Announced on 13 August 2026. "
            "Payments will be made in September 2026 to all eligible adult citizens. "
            "Effective from 1 September 2026."
        )
        dates = extract_granular_dates(None, text)
        self.assertEqual(dates["announcement_date"], "2026-08-13")
        self.assertEqual(dates["payment_date"], "2026-09-01")
        self.assertEqual(dates["effective_date"], "2026-09-01")

    def test_understand_user_intent(self):
        intent_singles = understand_user_intent("What's the BTO income ceiling for singles?")
        self.assertEqual(intent_singles["demographic"], "singles")
        self.assertEqual(intent_singles["housing_type"], "bto")
        self.assertEqual(intent_singles["domain"], "hdb")

        intent_payout = understand_user_intent("what about upcoming payout in 2026?")
        self.assertEqual(intent_payout["domain"], "grants")
        self.assertTrue(intent_payout["temporal"]["is_upcoming"])
        self.assertEqual(intent_payout["temporal"]["target_year"], 2026)

        intent_cpf_closure = understand_user_intent("When does CPF Special Account close?")
        self.assertEqual(intent_cpf_closure["domain"], "cpf")
        self.assertTrue(intent_cpf_closure["temporal"]["is_closure"])

    def test_score_applicability_singles_vs_families(self):
        intent = understand_user_intent("What is the BTO income ceiling for singles?")

        source_singles = {
            "title": "HDB Flat Eligibility for Singles",
            "content": "Single Singapore Citizen Scheme: 2-room Flexi BTO income ceiling is $8,000.",
            "is_official": True,
        }
        score_s, reason_s, excerpt_s = score_applicability(source_singles, intent, intent["raw_query"])
        self.assertGreater(score_s, 0.7)
        self.assertIn("singles", reason_s.lower())

        source_families = {
            "title": "HDB Flat Eligibility for Couples and Families",
            "content": "Couples and families: 4-room BTO household income ceiling is $16,000.",
            "is_official": True,
        }
        score_f, reason_f, excerpt_f = score_applicability(source_families, intent, intent["raw_query"])
        self.assertLess(score_f, 0.35)
        self.assertIn("couples and families", reason_f.lower())

    def test_rank_sources_prefers_exact_demographic(self):
        intent = understand_user_intent("What's the BTO income ceiling for singles?")
        source_singles = {
            "title": "HDB Eligibility for Singles",
            "content": "Singles 2-room Flexi BTO ceiling is $8,000.",
            "is_official": True,
            "published_date": "2024-01-01",
        }
        source_families_newer = {
            "title": "HDB Eligibility for Couples and Families",
            "content": "Families 4-room BTO ceiling is $16,000.",
            "is_official": True,
            "published_date": "2026-06-01",
        }
        ranked = rank_sources([source_families_newer, source_singles], intent=intent, query=intent["raw_query"])
        # Even though families source has newer date, singles source is directly applicable
        self.assertEqual(ranked[0]["title"], "HDB Eligibility for Singles")

    def test_policy_conflict_detection(self):
        intent = understand_user_intent("what about upcoming payout 2026?")
        older_source = {
            "title": "Assurance Package 2024",
            "content": "Cost-of-Living payment of $200-$400.",
            "is_official": True,
            "payment_date": "2024-09-01",
            "applicability_score": 0.8,
        }
        newer_source = {
            "title": "MOF 2026 Cost-of-Living Special Payment",
            "content": "Cost-of-Living payment of $400-$600 in September 2026.",
            "is_official": True,
            "payment_date": "2026-09-01",
            "applicability_score": 0.95,
        }
        ranked = rank_sources([older_source, newer_source], intent=intent, query=intent["raw_query"])
        curr, conflicts = detect_policy_version_and_conflicts(ranked, intent)
        self.assertEqual(curr["title"], "MOF 2026 Cost-of-Living Special Payment")
        self.assertEqual(len(conflicts), 1)
        self.assertIn("superseded", conflicts[0]["reason"].lower())

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
