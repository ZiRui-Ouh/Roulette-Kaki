import unittest

from agents.search import build_prompt


class SearchAgentTests(unittest.TestCase):
    def test_prompt_restricts_to_unofficial_sources(self):
        prompt = build_prompt(
            question="What are people saying about this policy?",
            unofficial_sources=[
                {
                    "title": "Thread on Reddit Singapore",
                    "url": "https://www.reddit.com/r/singapore/comments/example",
                    "source_type": "Reddit Singapore",
                    "content": "People are frustrated and think the policy is confusing.",
                }
            ],
        )

        self.assertIn("UNOFFICIAL PUBLIC DISCUSSION SOURCES", prompt)
        self.assertIn("Reddit Singapore", prompt)
        self.assertIn("official government websites", prompt)
        self.assertNotIn("official policy sources", prompt)


if __name__ == "__main__":
    unittest.main()
