import unittest
from unittest.mock import patch

from agents.search import gather_and_search
from services.webscraper import (
    detect_policy_version_and_conflicts,
    rank_sources,
    score_applicability,
    understand_user_intent,
)


class PolicyScenarioTests(unittest.TestCase):
    """
    Verification tests corresponding to Section 22 & 23 of the requirements.
    """

    def test_scenario_1_upcoming_payout_recency(self):
        """
        TEST 1 — UPCOMING PAYOUT
        Ensure the system distinguishes current 2026 payout announcements
        from older Assurance Package sources and ranks the current year source highest.
        """
        intent = understand_user_intent("what about upcoming payout")
        self.assertEqual(intent["domain"], "grants")

        sources = [
            {
                "title": "Assurance Package Updates 2024",
                "url": "https://www.gov.sg/features/assurance-package-2024",
                "content": "Eligible citizens receive Cost-of-Living payment of $200-$400 in September 2024.",
                "is_official": True,
                "payment_date": "2024-09-01",
                "published_date": "2024-08-01",
            },
            {
                "title": "MOF 2026 Cost-of-Living Special Payment Announcement",
                "url": "https://www.mof.gov.sg/news-releases/2026-col-special-payment",
                "content": "Eligible adult Singaporeans will receive between $400 and $600 under the 2026 Cost-of-Living Special Payment in September 2026.",
                "is_official": True,
                "payment_date": "2026-09-01",
                "published_date": "2026-08-13",
            },
        ]

        ranked = rank_sources(sources, intent=intent, query=intent["raw_query"])
        curr, conflicts = detect_policy_version_and_conflicts(ranked, intent)

        # Winning source must be the 2026 MOF announcement
        self.assertEqual(curr["title"], "MOF 2026 Cost-of-Living Special Payment Announcement")
        self.assertIn("2026", curr["content"])
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["title"], "Assurance Package Updates 2024")

    def test_scenario_2_bto_singles_category_separation(self):
        """
        TEST 2 — BTO SINGLES
        Ensure the system selects singles-specific figures and rejects
        family income ceilings or resale rules for a singles query.
        """
        intent = understand_user_intent("What's the BTO income ceiling for singles?")
        self.assertEqual(intent["demographic"], "singles")
        self.assertEqual(intent["housing_type"], "bto")

        sources = [
            {
                "title": "HDB Flat Eligibility for Couples and Families",
                "url": "https://www.hdb.gov.sg/couples-and-families",
                "content": "Couples and Families BTO 4-room and larger: Income ceiling is $16,000.",
                "is_official": True,
                "published_date": "2026-01-01",
            },
            {
                "title": "HDB Flat Eligibility for Singles",
                "url": "https://www.hdb.gov.sg/singles",
                "content": "Single Singapore Citizen Scheme: 2-room Flexi BTO income ceiling is $8,000.",
                "is_official": True,
                "published_date": "2025-01-01",
            },
            {
                "title": "HDB Resale Plus Flat Income Ceilings",
                "url": "https://www.hdb.gov.sg/resale-plus",
                "content": "Resale Plus flat income ceiling is $16,000 for families.",
                "is_official": True,
                "published_date": "2026-02-01",
            },
        ]

        ranked = rank_sources(sources, intent=intent, query=intent["raw_query"])
        self.assertEqual(ranked[0]["title"], "HDB Flat Eligibility for Singles")
        self.assertIn("$8,000", ranked[0]["content"])
        # Score for families source must be significantly penalized for singles query
        self.assertLess(ranked[1]["applicability_score"], 0.4)

    def test_scenario_3_cpf_special_account_closure(self):
        """
        TEST 3 — CPF SPECIAL ACCOUNT
        Distinguish SA closure rules and effective dates.
        """
        intent = understand_user_intent("When does CPF Special Account close?")
        self.assertEqual(intent["domain"], "cpf")
        self.assertTrue(intent["temporal"]["is_closure"])

        source = {
            "title": "CPF Closure of Special Account for Members Aged 55",
            "url": "https://www.cpf.gov.sg/sa-closure",
            "content": (
                "News release on 16 February 2024. "
                "From 1 January 2025, the Special Account for members aged 55 and above will be closed. "
                "SA savings will be transferred to RA up to the FRS, and excess to OA."
            ),
            "is_official": True,
            "announcement_date": "2024-02-16",
            "effective_date": "2025-01-01",
        }

        score, reason, excerpt = score_applicability(source, intent, intent["raw_query"])
        self.assertGreater(score, 0.75)
        self.assertIn("special account", reason.lower())

    def test_scenario_4_cpf_interest_rates(self):
        """
        TEST 4 — CPF INTEREST RATES
        Verify current CPF rates retrieval without using historical rates.
        """
        intent = understand_user_intent("What are CPF interest rates now?")
        self.assertEqual(intent["domain"], "cpf")

        source = {
            "title": "CPF Interest Rates",
            "url": "https://www.cpf.gov.sg/interest-rates",
            "content": (
                "Current CPF interest rates: OA yields 2.5% per annum. "
                "Special and MediSave Accounts (SMA) yield 4.0% per annum. "
                "Retirement Account (RA) yields 4.0% per annum."
            ),
            "is_official": True,
            "effective_date": "2026-01-01",
        }

        score, reason, excerpt = score_applicability(source, intent, intent["raw_query"])
        self.assertGreater(score, 0.7)
        self.assertIn("interest rates", reason.lower())

    def test_scenario_5_insufficient_information(self):
        """
        TEST 5 — INSUFFICIENT INFORMATION
        For queries with zero relevant official sources, ensure the system returns
        an insufficient-evidence state rather than hallucinating.
        """
        with patch("services.webscraper.search_web", return_value=[]):
            result = gather_and_search(
                question="What is the government subsidy for buying a private personal helicopter in Singapore?",
                provided_sources=[],
            )

            # When no sources match, gather_and_search provides the standard insufficient-evidence text
            summary = result.get("search_summary", "")
            self.assertIn("The available official sources do not provide enough information.", summary)

    def test_conflict_value_b_supersedes_value_a_same_policy(self):
        """
        TEST SOURCE CONFLICTS:
        Old source: Value A ($200-$400)
        New source: Value B ($400-$600)
        Make sure Value B is selected when both apply to the same policy.
        """
        intent = understand_user_intent("Singapore Cost of Living Special Payment")
        source_a = {
            "title": "MOF Press Release 2024",
            "content": "COL Special Payment is $200-$400.",
            "is_official": True,
            "payment_date": "2024-09-01",
            "published_date": "2024-08-01",
        }
        source_b = {
            "title": "MOF Press Release 2026",
            "content": "COL Special Payment is $400-$600.",
            "is_official": True,
            "payment_date": "2026-09-01",
            "published_date": "2026-08-13",
        }

        ranked = rank_sources([source_a, source_b], intent=intent, query=intent["raw_query"])
        curr, conflicts = detect_policy_version_and_conflicts(ranked, intent)
        self.assertEqual(curr["title"], "MOF Press Release 2026")
        self.assertEqual(len(conflicts), 1)

    def test_conflict_older_applicable_beats_newer_unrelated(self):
        """
        TEST SOURCE CONFLICTS:
        Newer unrelated source: Value C ($18,000 EC income ceiling)
        Older but directly applicable source: Value A ($8,000 Singles BTO ceiling)
        Make sure Value A is selected because Value C is about a different category.
        """
        intent = understand_user_intent("What is the BTO income ceiling for singles?")
        source_a = {
            "title": "HDB Singles BTO Eligibility",
            "content": "2-room Flexi BTO income ceiling for singles is $8,000.",
            "is_official": True,
            "published_date": "2024-05-01",
        }
        source_c = {
            "title": "HDB Executive Condominium Ceilings",
            "content": "Executive Condominium (EC) household income ceiling is $18,000.",
            "is_official": True,
            "published_date": "2026-08-01",
        }

        ranked = rank_sources([source_c, source_a], intent=intent, query=intent["raw_query"])
        self.assertEqual(ranked[0]["title"], "HDB Singles BTO Eligibility")


if __name__ == "__main__":
    unittest.main()
