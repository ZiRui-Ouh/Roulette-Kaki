"""Unit tests for the Bedrock tool-use research agent.

Strategy: patch `bedrock.get_client()` to return a stub whose `converse()`
pops from a scripted response queue (tool_use / end_turn frames).
Storage and scraper calls are patched too so no AWS or SPRS hits happen.
"""

import unittest
from unittest.mock import patch, MagicMock

from agents import research
from services import bedrock


def _tool_use_frame(tool_use_id: str, name: str, input_dict: dict) -> dict:
    return {
        "output": {
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "toolUse": {
                            "toolUseId": tool_use_id,
                            "name": name,
                            "input": input_dict,
                        }
                    }
                ],
            }
        },
        "stopReason": "tool_use",
        "usage": {"inputTokens": 100, "outputTokens": 20},
    }


def _end_turn_frame(text: str) -> dict:
    return {
        "output": {
            "message": {
                "role": "assistant",
                "content": [{"text": text}],
            }
        },
        "stopReason": "end_turn",
        "usage": {"inputTokens": 100, "outputTokens": 30},
    }


def _digest_with_topics(topic_ids: list[str]) -> dict:
    return {
        "date": "2025-05-13",
        "title": "Parliament Sitting of 2025-05-13",
        "summary": "Test digest summary.",
        "topics": [
            {
                "topic_id": tid,
                "title": f"Topic {tid}",
                "speakers": [f"Speaker {tid}"],
                "source_url": f"https://sprs.parl.gov.sg/{tid}",
                "format": "html",
            }
            for tid in topic_ids
        ],
    }


class ScriptedConverseClient:
    """Bedrock stub with a scripted converse() response queue."""

    def __init__(self, responses: list[dict]) -> None:
        self._responses = list(responses)
        self.calls: list[dict] = []

    def converse(self, **kwargs) -> dict:  # noqa: ANN003
        self.calls.append(kwargs)
        if not self._responses:
            raise RuntimeError("ScriptedConverseClient: response queue exhausted")
        return self._responses.pop(0)


class ResearchAgentToolUseTests(unittest.TestCase):
    def setUp(self) -> None:
        # storage: empty session, no cached reports, put_session/put_report are no-ops.
        self.get_session = patch(
            "agents.research.storage.get_session", return_value=None
        ).start()
        self.put_session = patch(
            "agents.research.storage.put_session", return_value=None
        ).start()
        self.get_report = patch(
            "agents.research.storage.get_report", return_value=None
        ).start()
        self.put_report = patch(
            "agents.research.storage.put_report", return_value=None
        ).start()
        # scraper: default = real fetch returns bytes, tests override as needed.
        self.fetch_report = patch(
            "agents.research.scraper.fetch_report",
            return_value=b"<html><body>Full transcript body.</body></html>",
        ).start()
        self.addCleanup(patch.stopall)

    def _install_client(self, responses: list[dict]) -> ScriptedConverseClient:
        client = ScriptedConverseClient(responses)
        # bedrock.chat_with_tools calls bedrock.get_client(); patch that
        # module-level function so we don't need real AWS creds.
        patch.object(bedrock, "get_client", return_value=client).start()
        return client

    # 1 --------------------------------------------------------------
    def test_overview_only_no_tool_call(self):
        patch(
            "agents.research.storage.get_digest",
            return_value=_digest_with_topics(["t1", "t2", "t3"]),
        ).start()
        client = self._install_client(
            [_end_turn_frame("The sitting covered three topics: t1, t2, t3.")]
        )

        result = research.run_chat(
            session_id="s1", date="2025-05-13", message="What topics were covered?"
        )

        self.assertEqual(result.topics_used, [])
        self.assertTrue(result.grounded)
        self.assertEqual(len(client.calls), 1)
        self.fetch_report.assert_not_called()
        # `run_chat` uses converse_with_tools, which passes the message
        # transcript as-is — no proactive document or cachePoint attach.
        # Message 0 is just the built user-prompt text block.
        msg0_content = client.calls[0]["messages"][0]["content"]
        self.assertEqual(len(msg0_content), 1)
        self.assertIn("text", msg0_content[0])
        # And the toolConfig for the research tools is included.
        self.assertIn("toolConfig", client.calls[0])

    # 2 --------------------------------------------------------------
    def test_model_calls_fetch_topic_report(self):
        patch(
            "agents.research.storage.get_digest",
            return_value=_digest_with_topics(["t1", "t2"]),
        ).start()
        client = self._install_client([
            _tool_use_frame("tu_1", "fetch_topic_report", {"topic_id": "t1"}),
            _end_turn_frame("MP said X about topic t1."),
        ])

        result = research.run_chat(
            session_id="s2", date="2025-05-13", message="What did the MP say on t1?"
        )

        self.assertEqual(result.topics_used, ["t1"])
        self.assertTrue(result.grounded)
        # Two converse calls; scraper hit once for t1.
        self.assertEqual(len(client.calls), 2)
        self.get_report.assert_called_with("2025-05-13", "t1", "html")
        self.fetch_report.assert_called_once()
        self.put_report.assert_called_once()
        # Second converse call must still carry the toolConfig plus a
        # transcript that ends with the toolResult wrap the loop appended.
        second_call = client.calls[1]
        self.assertIn("toolConfig", second_call)
        last_msg = second_call["messages"][-1]
        self.assertEqual(last_msg["role"], "user")
        self.assertIn("toolResult", last_msg["content"][0])
        tool_result_json = last_msg["content"][0]["toolResult"]["content"][0]["json"]
        self.assertEqual(tool_result_json["topic_id"], "t1")
        self.assertTrue(tool_result_json["is_sufficient"])

    # 3 --------------------------------------------------------------
    def test_fetch_failure_placeholder_path(self):
        patch(
            "agents.research.storage.get_digest",
            return_value=_digest_with_topics(["t1"]),
        ).start()
        self.fetch_report.side_effect = NotImplementedError(
            "fixture mode has no transcript bodies"
        )
        client = self._install_client([
            _tool_use_frame("tu_1", "fetch_topic_report", {"topic_id": "t1"}),
            _end_turn_frame(
                "The transcript isn't available. <grounded>false</grounded>"
            ),
        ])

        result = research.run_chat(
            session_id="s3", date="2025-05-13", message="Details on t1?"
        )

        # Placeholder attaches — topic is in loaded, but NOT cached to S3
        # because the exception path skips put_report.
        self.assertEqual(result.topics_used, ["t1"])
        self.assertFalse(result.grounded)
        self.put_report.assert_not_called()
        # The tool_result the loop fed back should mark the placeholder as
        # insufficient and the returned text should carry the "could not be
        # retrieved" fallback string.
        second_call_messages = client.calls[1]["messages"]
        tool_result_msg = second_call_messages[-1]
        self.assertEqual(tool_result_msg["role"], "user")
        tr_block = tool_result_msg["content"][0]["toolResult"]
        result_json = tr_block["content"][0]["json"]
        self.assertEqual(result_json["topic_id"], "t1")
        self.assertFalse(result_json["is_sufficient"])
        self.assertIn("could not be retrieved", result_json["text"])

    # 4 --------------------------------------------------------------
    def test_cap_eviction(self):
        # Session already has 5 preloaded topics. Model fetches a 6th.
        preloaded = ["t1", "t2", "t3", "t4", "t5"]
        self.get_session.return_value = {
            "session_id": "s4",
            "date": "2025-05-13",
            "topics_loaded": preloaded,
            "chat_history": [],
        }
        patch(
            "agents.research.storage.get_digest",
            return_value=_digest_with_topics(preloaded + ["t6"]),
        ).start()
        client = self._install_client([
            _tool_use_frame("tu_1", "fetch_topic_report", {"topic_id": "t6"}),
            _end_turn_frame("Talking about t6 now; t1 was dropped."),
        ])

        result = research.run_chat(
            session_id="s4", date="2025-05-13", message="What about t6?"
        )

        # Oldest (t1) evicted, t6 attached — the cap logic in
        # execute_fetch_topic_report drops loaded[0] once len > 5.
        self.assertEqual(len(result.topics_used), 5)
        self.assertNotIn("t1", result.topics_used)
        self.assertIn("t6", result.topics_used)

        # The tool_result payload the loop fed back for the fetch call
        # describes the newly-loaded topic (t6). The current implementation
        # doesn't surface the evicted id in the tool result — the eviction
        # is only observable via `result.topics_used`, which is asserted
        # above.
        tool_result_msg = client.calls[1]["messages"][-1]
        tr_block = tool_result_msg["content"][0]["toolResult"]
        result_json = tr_block["content"][0]["json"]
        self.assertEqual(result_json["topic_id"], "t6")

    # 5 --------------------------------------------------------------
    def test_unknown_topic_id(self):
        patch(
            "agents.research.storage.get_digest",
            return_value=_digest_with_topics(["t1", "t2"]),
        ).start()
        client = self._install_client([
            _tool_use_frame("tu_1", "fetch_topic_report", {"topic_id": "bogus"}),
            _end_turn_frame("That topic isn't in this sitting."),
        ])

        result = research.run_chat(
            session_id="s5", date="2025-05-13", message="Anything on bogus?"
        )

        self.assertEqual(result.topics_used, [])
        self.fetch_report.assert_not_called()
        # Unknown topic_id → tool result carries an `error` message and
        # `is_sufficient=False`; loop still ran to end_turn (2 calls total).
        self.assertEqual(len(client.calls), 2)
        tool_result_msg = client.calls[1]["messages"][-1]
        tr_block = tool_result_msg["content"][0]["toolResult"]
        result_json = tr_block["content"][0]["json"]
        self.assertIn("error", result_json)
        self.assertIn("bogus", result_json["error"])
        self.assertFalse(result_json["is_sufficient"])

    # 6a --------------------------------------------------------------
    def test_reasoning_tags_stripped_from_reply(self):
        patch(
            "agents.research.storage.get_digest",
            return_value=_digest_with_topics(["t1"]),
        ).start()
        leaky_reply = (
            "<thinking>The user wants a summary. Let me check the "
            "overview.</thinking>\n\nThe sitting covered transport and "
            "recycling."
        )
        self._install_client([_end_turn_frame(leaky_reply)])

        result = research.run_chat(
            session_id="s7", date="2025-05-13", message="What was covered?"
        )

        self.assertNotIn("<thinking>", result.reply)
        self.assertNotIn("</thinking>", result.reply)
        self.assertNotIn("Let me check", result.reply)
        self.assertTrue(result.reply.startswith("The sitting covered"))

    # 6 --------------------------------------------------------------
    def test_iteration_cap_synthesises_fallback_reply(self):
        patch(
            "agents.research.storage.get_digest",
            return_value=_digest_with_topics(["t1", "t2", "t3", "t4", "t5", "t6"]),
        ).start()
        # MAX_RESEARCH_ITERATIONS = 3 in the current loop. Feed 3 tool_use
        # frames — one per iteration — using `search_sitting_topics` (a real
        # tool that doesn't hit the topics_loaded cap). The loop exits the
        # `for` without ever producing `text`, and the fallback synthesis
        # path in run_chat generates the reply.
        responses = [
            _tool_use_frame(
                f"tu_{i}", "search_sitting_topics", {"query": f"t{i + 1}"}
            )
            for i in range(3)
        ]
        client = self._install_client(responses)

        result = research.run_chat(
            session_id="s6", date="2025-05-13", message="Poke every topic please."
        )

        # Exactly MAX_RESEARCH_ITERATIONS converse calls — the loop never
        # gets an end_turn stop reason.
        self.assertEqual(len(client.calls), 3)
        # Every call carries toolConfig — the message transcript contains
        # toolUse/toolResult blocks after the first iteration, and Bedrock
        # rejects those without a toolConfig on the request.
        for call in client.calls:
            self.assertIn("toolConfig", call)
        # Reply is the fallback synthesis text produced by run_chat when
        # the loop exhausts iterations without a final answer.
        self.assertIn("According to the official Hansard", result.reply)
        self.assertTrue(result.grounded)

    # 7 --------------------------------------------------------------
    @unittest.skip(
        "Structured-block emission tools (emit_summary_card) are not "
        "wired into the current research agent. `ChatResult` has no "
        "`blocks` field and no `emit_*` tool is registered in "
        "get_research_tool_specs(). Re-enable when the feature lands."
    )
    def test_emit_summary_card(self):
        patch(
            "agents.research.storage.get_digest",
            return_value=_digest_with_topics(["t1"]),
        ).start()
        card_args = {
            "title": "Recycling Rates",
            "tldr": "Domestic recycling rates fell in 2025.",
            "key_points": ["3.36M tonnes disposed", "Zero Waste review under way"],
            "speakers": ["Dr Janil Puthucheary"],
            "citations": ["t1"],
        }
        self._install_client([
            _tool_use_frame("tu_1", "emit_summary_card", card_args),
            _end_turn_frame(""),
        ])

        result = research.run_chat(
            session_id="s8", date="2025-05-13", message="Summarise recycling."
        )

        self.assertEqual(len(result.blocks), 1)
        b = result.blocks[0]
        self.assertEqual(b["kind"], "summary_card")
        self.assertEqual(b["title"], "Recycling Rates")
        self.assertEqual(b["tldr"], "Domestic recycling rates fell in 2025.")
        self.assertEqual(b["key_points"], card_args["key_points"])
        self.assertEqual(b["citations"], ["t1"])

    # 8 --------------------------------------------------------------
    @unittest.skip(
        "Structured-block emission tools (emit_comparison_table) are not "
        "wired into the current research agent. Re-enable when the "
        "feature lands."
    )
    def test_emit_comparison_table(self):
        patch(
            "agents.research.storage.get_digest",
            return_value=_digest_with_topics(["t1", "t2"]),
        ).start()
        table_args = {
            "title": "Bills Introduced",
            "columns": ["Bill", "Status"],
            "rows": [
                ["Road Traffic Amendment", "First Reading"],
                ["Statutes Miscellaneous Amendment", "First Reading"],
                ["CPF Amendment", "Second Reading"],
            ],
        }
        self._install_client([
            _tool_use_frame("tu_1", "emit_comparison_table", table_args),
            _end_turn_frame(""),
        ])

        result = research.run_chat(
            session_id="s9", date="2025-05-13", message="List all bills with status."
        )

        self.assertEqual(len(result.blocks), 1)
        b = result.blocks[0]
        self.assertEqual(b["kind"], "comparison_table")
        self.assertEqual(b["columns"], ["Bill", "Status"])
        self.assertEqual(len(b["rows"]), 3)

    # 9 --------------------------------------------------------------
    @unittest.skip(
        "Structured-block emission tools (emit_summary_card + "
        "emit_follow_up_chips) are not wired into the current research "
        "agent. Re-enable when the feature lands."
    )
    def test_emit_summary_card_then_follow_up_chips(self):
        patch(
            "agents.research.storage.get_digest",
            return_value=_digest_with_topics(["t1"]),
        ).start()
        card_args = {"title": "T1", "tldr": "Short."}
        chip_args = {"suggestions": ["Who spoke?", "Any bills?", "Full text please"]}
        self._install_client([
            _tool_use_frame("tu_1", "emit_summary_card", card_args),
            _tool_use_frame("tu_2", "emit_follow_up_chips", chip_args),
            _end_turn_frame(""),
        ])

        result = research.run_chat(
            session_id="s10", date="2025-05-13", message="Give me the summary."
        )

        # Order must be preserved: card first, chips second.
        self.assertEqual(len(result.blocks), 2)
        self.assertEqual(result.blocks[0]["kind"], "summary_card")
        self.assertEqual(result.blocks[1]["kind"], "follow_up_chips")
        self.assertEqual(len(result.blocks[1]["suggestions"]), 3)


if __name__ == "__main__":
    unittest.main()
