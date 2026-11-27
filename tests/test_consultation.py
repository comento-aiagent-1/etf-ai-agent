import csv
import json
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import streamlit as st

from consultation import consult
from orchestrator import route_question
from streamlit.testing.v1 import AppTest


QUESTION = "ETF란 무엇인가요?"
APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def faq_fixture(*ids):
    with (APP_PATH.parent / "data" / "source" / "FAQ.csv").open(
        encoding="utf-8-sig", newline=""
    ) as file:
        rows = {row["faq_id"]: row for row in csv.DictReader(file)}
    return [rows[faq_id] for faq_id in ids]


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
    def test_exact_faq_question_returns_saved_answer_without_openai(self):
        client = Mock()
        with patch("consultation.route_question") as router, patch(
            "consultation.run_faq_agent"
        ) as faq:
            result = consult(QUESTION, "초급", client)

        router.assert_not_called()
        faq.assert_not_called()
        client.responses.create.assert_not_called()
        self.assertEqual(result["answer"], faq_fixture("F001")[0]["answer"])
        self.assertEqual(result["used_tools"], ["search_faq"])
        self.assertEqual(result["sources"][0]["faq_id"], "F001")

    def test_required_free_questions_use_semantic_faq_evidence(self):
        questions = {
            "ETF가 무엇인지 설명해 주세요.": ("F001",),
            "ETF와 주식의 차이는 무엇인가요?": ("F002",),
            "ETF도 원금손실이 발생하나요?": ("F021",),
            "ETF의 총보수가 뭔가요?": ("F016",),
            "저는 ETF를 처음 배우는데 추적오차가 뭔가요?": ("F010",),
            "ETF와 주식의 차이, 원금보장 여부, 투자 위험을 알려주세요.": ("F002", "F021", "F022"),
            "ETF 투자하면 원금은 무조건 돌려받나요?": ("F021",),
            "ETF 사면 매년 돈이 얼마나 나가나요?": ("F016", "F017"),
            "ETF하고 그냥 주식 사는 건 뭐가 달라요?": ("F002",),
        }
        for question, ids in questions.items():
            with self.subTest(question=question):
                client = Mock()
                client.responses.create.side_effect = [
                    Mock(output_text='{"routes":["faq"],"etf_name":"none"}'),
                    Mock(output_text="근거 기반 답변"),
                ]
                rows = faq_fixture(*ids)
                with patch("agent_tools.search_faq_vectors", return_value=rows) as search:
                    result = consult(question, None, client)

                search.assert_called_once_with(question)
                self.assertEqual(result["used_tools"], ["search_faq"])
                self.assertEqual([source["faq_id"] for source in result["sources"]], list(ids))
                self.assertTrue(all(source["source_url"] for source in result["sources"]))
                self.assertEqual(client.responses.create.call_args_list[0].kwargs["input"], question)
                generation = client.responses.create.call_args.kwargs
                payload = json.loads(generation["input"])
                self.assertEqual(payload["question"], question)
                self.assertEqual([row["faq_id"] for row in payload["evidence"]["faq"]], list(ids))
                self.assertIn("자료가 부족한 질문 부분은 확인할 수 없다고 말한다", generation["instructions"])
                self.assertIn("질문에서 설명 수준을 명시한 경우 반영한다", generation["instructions"])
                if len(ids) > 1:
                    self.assertIn("짧은 소제목으로 나누고", generation["instructions"])

    def test_unverified_product_return_is_withheld(self):
        question = "확인되지 않은 ETF 상품의 정확한 수익률을 알려주세요."
        client = Mock()
        client.responses.create.return_value = Mock(
            output_text='{"routes":["return_unsupported"],"etf_name":"none"}'
        )
        with patch("consultation.run_faq_agent") as faq:
            result = consult(question, "초급", client)

        faq.assert_not_called()
        self.assertEqual(client.responses.create.call_count, 1)
        self.assertEqual(result["sources"], [])
        self.assertIn("정확한 수익률을 확인할 수 없습니다", result["answer"])
        self.assertNotIn("%", result["answer"])

    def test_missing_or_unsourced_faq_never_reaches_generation(self):
        for rows in ([], [{"answer": "출처가 없는 수치 99%"}]):
            with self.subTest(rows=rows):
                client = Mock()
                client.responses.create.return_value = Mock(
                    output_text='{"routes":["faq"],"etf_name":"none"}'
                )
                with patch("agent_tools.search_faq_vectors", return_value=rows):
                    result = consult("ETF 투자 비용이 궁금합니다", "초급", client)
                self.assertEqual(client.responses.create.call_count, 1)
                self.assertFalse(result["sources"])
                self.assertIn("찾지 못했습니다" if not rows else "확인하지 못했습니다", result["answer"])
                self.assertNotIn("99%", result["answer"])

    def test_total_fee_uses_same_evidence_for_all_three_levels(self):
        question = "ETF의 총보수는 무엇인가요?"
        client = Mock()
        client.responses.create.side_effect = [
            Mock(output_text="초급 답변"),
            Mock(output_text="중급 답변"),
            Mock(output_text="고급 답변"),
        ]
        with patch("consultation.route_question") as router, patch(
            "agent_tools.search_faq_vectors", return_value=faq_fixture("F016")
        ):
            results = [
                consult(question, level, client, selected_faq=True)
                for level in ("초급", "중급", "고급")
            ]

        router.assert_not_called()
        prompts = [call.kwargs for call in client.responses.create.call_args_list]
        self.assertTrue(all(prompt["input"] == prompts[0]["input"] for prompt in prompts))
        self.assertEqual(results[0]["sources"][0]["faq_id"], "F016")
        self.assertTrue(all(result["sources"] == results[0]["sources"] for result in results))
        self.assertTrue(all("사용자가 선택한 설명 수준을 적용한다" in prompt["instructions"] for prompt in prompts))
        self.assertIn("ETF를 처음 접하는 사용자", prompts[0]["instructions"])
        self.assertIn("실제 투자 시 고려사항", prompts[1]["instructions"])
        self.assertIn("분석 한계", prompts[2]["instructions"])

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
        question = "ETF에 대해 쉬운 설명을 해주세요."
        client.responses.create.side_effect = [
            Mock(output_text="거래소에서 사고파는 펀드예요."),
            Mock(output_text="ETF는 거래소에서 거래되는 집합투자기구입니다."),
        ]
        with patch("consultation.route_question") as router, patch(
            "consultation.run_faq_agent", return_value=FAQ_RESPONSE
        ) as faq:
            beginner = consult(question, "초급", client, selected_faq=True)
            expert = consult(question, "고급", client, selected_faq=True)

        router.assert_not_called()
        self.assertEqual(faq.call_count, 2)
        beginner_prompt, expert_prompt = [
            call.kwargs for call in client.responses.create.call_args_list
        ]
        self.assertEqual(beginner_prompt["input"], expert_prompt["input"])
        self.assertIn("ETF를 처음 접하는 사용자", beginner_prompt["instructions"])
        self.assertIn("전문 지표의 정의", expert_prompt["instructions"])
        self.assertNotEqual(beginner["answer"], expert["answer"])
        self.assertEqual(beginner["sources"], FAQ_RESPONSE["sources"])
        self.assertEqual(
            expert["related"],
            ["ETF란 무엇인가요?", "ETF와 펀드의 차이는?"],
        )

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
            result = consult("그 ETF 가격 알려줘", "초급", client)
        faq.assert_not_called()
        self.assertEqual(client.responses.create.call_count, 1)
        self.assertIn("상품명이나 종목코드", result["answer"])
        self.assertEqual(result["sources"], [])


class ConsultationUiTest(unittest.TestCase):
    def setUp(self):
        # AppTest sessions share the process-level FAQ directory cache.
        st.cache_data.clear()
        self.addCleanup(st.cache_data.clear)

    def test_faq_click_then_free_question_keep_both_turns(self):
        response = {
            "answer": FAQ_RESPONSE["results"][0]["answer"],
            "sources": FAQ_RESPONSE["sources"],
            "related": ["ETF와 펀드의 차이는?"],
            "used_tools": ["search_faq"],
        }
        with patch("consultation.consult", return_value=response) as consult_mock, patch(
            "openai.OpenAI"
        ), patch("src.services.request_logger.save_request_log", return_value=True) as log, patch(
            "faq_agent.list_faq_questions", return_value=faq_fixture("F001", "F016")
        ):
            app = AppTest.from_file(str(APP_PATH), default_timeout=90).run()
            self.assertIsNone(app.session_state["knowledge_level"])
            app.segmented_control(key="knowledge_level").set_value("중급").run()
            app.button(key="faq_F001").click().run()
            app.chat_input[0].set_value("거래소에서 거래하는 이유는?").run()

        self.assertFalse(app.exception)
        self.assertEqual(len(app.session_state["messages"]), 4)
        first, second = consult_mock.call_args_list
        self.assertEqual(first.args[0], QUESTION)
        self.assertTrue(first.kwargs["selected_faq"])
        self.assertFalse(second.kwargs["selected_faq"])
        self.assertEqual(first.args[1], "중급")
        self.assertEqual(second.args[1], "중급")
        self.assertEqual(app.session_state["messages"][1]["sources"], response["sources"])
        self.assertTrue(all("question" not in call.kwargs for call in log.call_args_list))

    def test_csv_fallback_is_labeled_and_searchable(self):
        from psycopg import OperationalError

        with patch("faq_agent.list_faq_questions", side_effect=OperationalError):
            app = AppTest.from_file(str(APP_PATH), default_timeout=90).run()
            self.assertFalse(app.exception)
            self.assertTrue(any("원본 CSV" in caption.value for caption in app.caption))
            app.text_input(key="faq_search").set_value("총보수").run()
        self.assertFalse(app.exception)
        self.assertIn("ETF 총보수", app.button(key="faq_F016").label)
        self.assertNotIn("faq_F001", [button.key for button in app.button])

    def test_related_faq_click_and_feedback_stays_in_session(self):
        related_question = "ETF 총보수란 무엇인가요?"
        response = {
            "answer": FAQ_RESPONSE["results"][0]["answer"],
            "sources": FAQ_RESPONSE["sources"],
            "related": [related_question],
            "used_tools": ["search_faq"],
        }
        with patch("consultation.consult", return_value=response) as consult_mock, patch(
            "openai.OpenAI"
        ), patch("src.services.request_logger.save_request_log", return_value=True) as log, patch(
            "faq_agent.list_faq_questions", return_value=faq_fixture("F001", "F016")
        ):
            app = AppTest.from_file(str(APP_PATH), default_timeout=90).run()
            app.button(key="faq_F001").click().run()
            app.segmented_control(key="faq_feedback_1").set_value("도움이 됐어요").run()
            self.assertEqual(consult_mock.call_count, 1)
            self.assertEqual(log.call_count, 1)
            app.button(key="related_faq_0").click().run()

        self.assertFalse(app.exception)
        self.assertEqual(app.session_state["faq_feedback_1"], "도움이 됐어요")
        self.assertEqual(consult_mock.call_args.args[0], related_question)
        self.assertTrue(consult_mock.call_args.kwargs["selected_faq"])
