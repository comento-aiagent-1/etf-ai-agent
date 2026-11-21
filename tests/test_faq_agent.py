import unittest
from unittest.mock import Mock, patch

from faq_agent import run_faq_agent
from orchestrator import route_question


class FaqAgentTest(unittest.TestCase):
    def test_router_passes_original_question_and_faq_returns_sources(self):
        question = "ETF와 주식은 어떻게 달라?"
        row = {
            "faq_id": 10,
            "answer": "테스트 답변",
            "source_url": "https://example.org/faq",
            "match_score": 0.8,
        }
        client = Mock()
        client.responses.create.return_value.output_text = (
            '{"routes":["faq"],"etf_name":"none"}'
        )
        with patch("agent_tools.search_faq_vectors", return_value=[row]) as search:
            route = route_question(question, client)
            self.assertEqual(route, {"routes": ["faq"], "etf_name": "none"})
            self.assertEqual(client.responses.create.call_args.kwargs["input"], question)
            response = run_faq_agent(question)

        search.assert_called_once_with(question)
        self.assertTrue(response["success"])
        self.assertEqual(response["results"], [row])
        self.assertEqual(response["sources"], [{"faq_id": 10, "source_url": row["source_url"]}])

    def test_no_results(self):
        with patch("agent_tools.search_faq_vectors", return_value=[]):
            response = run_faq_agent("질문")
        self.assertEqual(response, {
            "success": False,
            "message": "관련 FAQ를 찾지 못했습니다.",
            "results": [],
            "sources": [],
        })

    def test_service_errors_do_not_expose_exception_details(self):
        for dependency in ("embed_texts", "get_database_connection"):
            with self.subTest(dependency=dependency):
                with patch("src.services.vector_search.embed_texts", return_value=[[0.1]]):
                    with patch(
                        f"src.services.vector_search.{dependency}",
                        side_effect=RuntimeError("private-connection-detail"),
                    ):
                        with self.assertLogs("agent_tools", level="ERROR") as logs:
                            response = run_faq_agent("질문")
                self.assertEqual(response, {
                    "success": False,
                    "message": "지금은 FAQ를 검색할 수 없습니다. 잠시 후 다시 시도해 주세요.",
                    "results": [],
                    "sources": [],
                })
                self.assertNotIn("private-connection-detail", str(logs.output))

    def test_invalid_questions_skip_tool(self):
        with patch("faq_agent.search_faq") as tool:
            for question in (None, "  ", "가" * 1001):
                with self.subTest(question_type=type(question)):
                    response = run_faq_agent(question)
                    self.assertFalse(response["success"])
                    self.assertEqual(response["message"], "질문을 1~1000자로 입력해 주세요.")
            tool.invoke.assert_not_called()

    def test_malformed_tool_response_is_handled(self):
        with patch("faq_agent.search_faq") as tool:
            tool.invoke.return_value = "invalid JSON"
            response = run_faq_agent("질문")
        self.assertFalse(response["success"])
        self.assertEqual(response["results"], [])
        self.assertEqual(response["sources"], [])
