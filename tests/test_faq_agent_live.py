"""Opt-in smoke test for OpenAI embeddings and PostgreSQL FAQ retrieval."""

import os
import unittest

from faq_agent import run_faq_agent


@unittest.skipUnless(os.getenv("FAQ_RUN_LIVE_TESTS") == "1", "requires OpenAI and PostgreSQL")
class FaqAgentLiveTest(unittest.TestCase):
    def test_known_question_returns_an_answer_and_source(self):
        response = run_faq_agent("ETF와 주식은 어떻게 달라?")
        self.assertTrue(response["success"], response["message"])
        self.assertTrue(any(row.get("answer") for row in response["results"]))
        self.assertTrue(any(source.get("source_url") for source in response["sources"]))
