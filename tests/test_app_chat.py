import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


class ChatFailureTests(unittest.TestCase):
    def test_agent_and_log_failures_keep_messages_in_session(self):
        with patch(
            "consultation.consult",
            side_effect=RuntimeError("private test detail"),
        ), patch(
            "openai.OpenAI",
        ), patch(
            "src.services.request_logger.save_request_log",
            return_value=False,
        ), patch(
            "faq_agent.list_faq_questions", return_value=[],
        ):
            app = AppTest.from_file(
                str(Path(__file__).resolve().parents[1] / "app.py"),
                default_timeout=90,
            ).run()
            app.chat_input[0].set_value("test question").run()

        self.assertFalse(app.exception)
        messages = app.session_state["messages"]
        self.assertEqual(messages[0]["role"], "user")
        self.assertEqual(messages[0]["content"], "test question")
        self.assertEqual(messages[1]["role"], "assistant")
        self.assertIn("문제가 발생했습니다", messages[1]["content"])
        self.assertTrue(app.warning)


if __name__ == "__main__":
    unittest.main()
