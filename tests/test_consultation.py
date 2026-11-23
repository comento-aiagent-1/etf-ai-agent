import json
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from consultation import consult
from orchestrator import route_question
from streamlit.testing.v1 import AppTest


QUESTION = "ETF란 무엇인가요?"
FAQ_RESPONSE = {
    "success": True,
    "message": "관련 FAQ를 찾았습니다.",
    "results": [
        {"question": QUESTION, "answer": "ETF는 거래소에서 거래되는 펀드입니다."},
        {"question": "ETF와 펀드의 차이는?", "answer": "ETF는 장중에 거래할 수 있습니다."},
    ],
    "sources": [{"source_name": "테스트 자료", "source_url": "https://example.org/faq"}],
}


class ConsultationTest(unittest.TestCase):
    def test_existing_router_schema_still_uses_original_routes(self):
        client = Mock()
        client.responses.create.return_value.output_text = (
            '{"routes":["faq"],"etf_name":"none"}'
        )
        self.assertEqual(
            route_question(QUESTION, client), {"routes": ["faq"], "etf_name": "none"}
        )
        schema = client.responses.create.call_args.kwargs["text"]["format"]["schema"]
        self.assertNotIn("product", schema["properties"]["routes"]["items"]["enum"])
        self.assertIn("enum", schema["properties"]["etf_name"])

    def test_product_uses_existing_db_tool_and_blocks_unsupported_market_lookup(self):
        client = Mock()
        client.responses.create.side_effect = [
            Mock(output_text='{"routes":["product","etf_price"],"etf_name":"SOL 미국S&P500"}'),
            Mock(output_text="확인된 총보수는 0.05%입니다."),
        ]
        product = Mock()
        product.name = "search_etf_product"
        product.invoke.return_value = json.dumps({
            "success": True,
            "results": [{"total_fee_percent": 0.05, "source_name": "테스트 상품 자료"}],
        })
        with patch.dict(
            "consultation.DATA_ROUTES",
            {"product": (product, "search_term", "ETF 상품"), "etf_price": (Mock(), "etf_name", "시세")},
        ):
            result = consult("SOL 미국S&P500의 총보수와 최근 종가는?", "중급", client)

        product.invoke.assert_called_once_with({"search_term": "SOL 미국S&P500"})
        self.assertEqual(result["used_tools"], ["search_etf_product"])
        self.assertEqual(result["sources"], [{"source_name": "테스트 상품 자료"}])
        self.assertIn("0.05%", result["answer"])
        self.assertIn("현재 시세·공시는", result["answer"])

    def test_selected_faq_uses_same_evidence_with_different_level_instructions(self):
        client = Mock()
        client.responses.create.side_effect = [
            Mock(output_text="거래소에서 사고파는 펀드예요."),
            Mock(output_text="ETF는 거래소에서 거래되는 집합투자기구입니다."),
        ]
        with patch("consultation.route_question") as router, patch(
            "consultation.run_faq_agent", return_value=FAQ_RESPONSE
        ) as faq:
            beginner = consult(QUESTION, "입문", client, selected_faq=True)
            expert = consult(QUESTION, "고급", client, selected_faq=True)

        router.assert_not_called()
        self.assertEqual(faq.call_count, 2)
        beginner_prompt, expert_prompt = [
            call.kwargs for call in client.responses.create.call_args_list
        ]
        self.assertEqual(beginner_prompt["input"], expert_prompt["input"])
        self.assertIn("쉬운 일상어", beginner_prompt["instructions"])
        self.assertIn("지표 정의", expert_prompt["instructions"])
        self.assertNotEqual(beginner["answer"], expert["answer"])
        self.assertEqual(beginner["sources"], FAQ_RESPONSE["sources"])
        self.assertEqual(expert["related"], ["ETF와 펀드의 차이는?"])

    def test_free_question_dispatches_both_paths_and_keeps_partial_results(self):
        client = Mock()
        client.responses.create.side_effect = [
            Mock(output_text='{"routes":["faq","etf_price"],"etf_name":"KODEX 200"}'),
            Mock(output_text="FAQ 자료를 확인했습니다."),
        ]
        price = Mock()
        price.name = "get_etf_price"
        price.invoke.return_value = json.dumps({"success": False, "message": "private detail"})
        question = "ETF를 설명하고 KODEX 200의 종가도 알려줘"
        with patch("consultation.run_faq_agent", return_value=FAQ_RESPONSE) as faq, patch.dict(
            "consultation.DATA_ROUTES", {"etf_price": (price, "etf_name", "시세")}
        ):
            result = consult(question, "초급", client)

        faq.assert_called_once_with(question)
        price.invoke.assert_called_once_with({"etf_name": "KODEX 200"})
        self.assertEqual(result["used_tools"], ["search_faq", "get_etf_price"])
        self.assertIn("시세 자료를 확인하지 못했습니다.", result["answer"])
        self.assertNotIn("private detail", result["answer"])

    def test_ambiguous_question_does_not_fetch_data_or_generate_answer(self):
        client = Mock()
        client.responses.create.return_value.output_text = (
            '{"routes":["clarify"],"etf_name":"none"}'
        )
        with patch("consultation.run_faq_agent") as faq:
            result = consult("그 ETF 가격 알려줘", "입문", client)
        faq.assert_not_called()
        self.assertEqual(client.responses.create.call_count, 1)
        self.assertIn("상품명이나 종목코드", result["answer"])
        self.assertEqual(result["sources"], [])


class ConsultationUiTest(unittest.TestCase):
    def test_faq_click_then_free_question_keep_both_turns(self):
        response = {
            "answer": FAQ_RESPONSE["results"][0]["answer"],
            "sources": FAQ_RESPONSE["sources"],
            "related": ["ETF와 펀드의 차이는?"],
            "used_tools": ["search_faq"],
        }
        with patch("consultation.consult", return_value=response) as consult_mock, patch(
            "openai.OpenAI"
        ), patch("src.services.request_logger.save_request_log", return_value=True):
            app = AppTest.from_file(
                str(Path(__file__).resolve().parents[1] / "app.py")
            , default_timeout=90).run()
            app.button(key="faq_F001").click().run()
            app.chat_input[0].set_value("거래소에서 거래하는 이유는?").run()

        self.assertFalse(app.exception)
        self.assertEqual(len(app.session_state["messages"]), 4)
        first, second = consult_mock.call_args_list
        self.assertEqual(first.args[0], QUESTION)
        self.assertTrue(first.kwargs["selected_faq"])
        self.assertFalse(second.kwargs["selected_faq"])
        self.assertEqual(app.session_state["messages"][1]["sources"], response["sources"])
