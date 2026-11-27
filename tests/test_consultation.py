import csv
import json
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import streamlit as st

from consultation import consult
from orchestrator import fast_route_question, route_question
from src.services.conversation_memory import prepare_recent_history
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
                generation = client.responses.create.call_args.kwargs
                payload = json.loads(generation["input"])
                self.assertEqual(payload["question"], question)
                self.assertEqual([row["faq_id"] for row in payload["evidence"]["faq"]], list(ids))
                self.assertIn("자료가 부족한 질문 부분은 확인할 수 없다고 말한다", generation["instructions"])
                self.assertIn(
                    "질문에서 명시한 수준이나 쉽게/자세히 설명해 달라는 요청을 우선한다",
                    generation["instructions"],
                )
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
        self.assertTrue(all("기본 설명 수준:" in prompt["instructions"] for prompt in prompts))
        self.assertIn("주식이나 ETF의 기본 용어", prompts[0]["instructions"])
        self.assertIn("추적오차·괴리율·유동성", prompts[1]["instructions"])
        self.assertIn("계산 기준, 데이터 출처와 기준일", prompts[2]["instructions"])

    def test_recent_history_keeps_only_text_from_last_three_turns(self):
        messages = [
            {"role": "user", "content": f"질문 {index}", "sources": ["제외"]}
            if index % 2 == 0
            else {"role": "assistant", "content": f"답변 {index}", "used_tools": ["제외"]}
            for index in range(8)
        ]

        history = prepare_recent_history(messages)

        self.assertEqual(len(history), 6)
        self.assertEqual(history[0], {"role": "user", "content": "질문 2"})
        self.assertEqual(history[-1], {"role": "assistant", "content": "답변 7"})

    def test_router_receives_recent_context_for_follow_up_product_reference(self):
        client = Mock()
        client.responses.create.return_value.output_text = (
            '{"routes":["news"],"etf_name":"KODEX 200"}'
        )
        history = [
            {"role": "user", "content": "KODEX 200의 종가를 알려줘"},
            {"role": "assistant", "content": "기준일 종가는 73,770원입니다."},
        ]

        result = route_question(
            "그럼 그 ETF 뉴스는?",
            client,
            include_product=True,
            conversation_history=history,
        )

        self.assertEqual(
            result,
            {"routes": ["news"], "etf_name": "KODEX 200"},
        )
        route_input = json.loads(
            client.responses.create.call_args.kwargs["input"]
        )
        self.assertEqual(route_input["recent_conversation"], history)
        self.assertEqual(route_input["current_question"], "그럼 그 ETF 뉴스는?")

    def test_llm_router_structures_spoken_product_clues_for_database_search(self):
        client = Mock()
        client.responses.create.return_value.output_text = json.dumps({
            "routes": ["product"],
            "etf_name": "삼성자산운용 KODEX 2000",
            "product_clues": {
                "asset_manager": "삼성자산운용",
                "brand": "KODEX",
                "number_hint": "2000",
                "index_hint": "",
                "market_or_theme": "",
            },
        }, ensure_ascii=False)

        result = route_question(
            "그 삼성자산운용에서 하는 거 코 뭐시기로 시작하고 2000인가로 끝나는 이름 뭐지",
            client,
            include_product=True,
        )

        self.assertEqual(result["routes"], ["product"])
        self.assertEqual(result["etf_name"], "삼성자산운용 KODEX 2000")
        self.assertEqual(result["product_clues"]["asset_manager"], "삼성자산운용")
        self.assertEqual(result["product_clues"]["number_hint"], "2000")

    def test_router_preserves_question_number_when_llm_omits_number_hint(self):
        client = Mock()
        client.responses.create.return_value.output_text = json.dumps({
            "routes": ["product"],
            "etf_name": "KODEX 상품",
            "product_clues": {
                "asset_manager": "",
                "brand": "KODEX",
                "number_hint": "",
                "index_hint": "",
                "market_or_theme": "",
            },
        })
        result = route_question(
            "KODEX 300이라는 상품 맞아?",
            client,
            include_product=True,
        )
        self.assertEqual(result["product_clues"]["number_hint"], "300")

    def test_progress_callback_reports_real_processing_stages(self):
        client = Mock()
        client.responses.create.return_value = Mock(
            output_text="ETF는 거래소에서 거래되는 펀드입니다."
        )
        progress = []

        with patch(
            "consultation.run_faq_agent",
            return_value=FAQ_RESPONSE,
        ):
            result = consult(
                QUESTION,
                "입문",
                client,
                selected_faq=True,
                progress_callback=lambda stage, detail: progress.append(
                    (stage, detail)
                ),
            )

        stages = [stage for stage, _ in progress]
        self.assertEqual(stages[0], "질문 분석 중")
        self.assertIn("자료 조회 중", stages)
        self.assertEqual(stages[-1], "답변 생성 중")
        self.assertEqual(result["timings"]["router_seconds"], 0.0)
        self.assertGreaterEqual(result["timings"]["faq_seconds"], 0.0)
        self.assertGreaterEqual(
            result["timings"]["answer_generation_seconds"],
            0.0,
        )
        self.assertGreaterEqual(result["timings"]["consultation_seconds"], 0.0)

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
        self.assertIn("news", schema["properties"]["routes"]["items"]["enum"])
        self.assertNotIn("enum", schema["properties"]["etf_name"])

    def test_news_route_reaches_news_tool_and_keeps_article_sources(self):
        client = Mock()
        client.responses.create.return_value = Mock(
            output_text="최근 ETF 뉴스 제목을 확인했습니다."
        )
        news = Mock()
        news.name = "search_etf_news"
        news.invoke.return_value = json.dumps({
            "success": True,
            "source_name": "Google 뉴스 RSS",
            "source_url": "https://news.google.com/",
            "articles": [{
                "title": "KODEX 200 관련 기사",
                "press": "테스트 언론",
                "published_at": "2026-11-24",
                "url": "https://news.google.com/articles/test",
            }],
        })

        with patch.dict(
            "consultation.DATA_ROUTES",
            {"news": (news, "etf_name", "뉴스")},
        ):
            result = consult("KODEX 200 최근 뉴스 알려줘", "입문", client)

        news.invoke.assert_called_once_with({"etf_name": "KODEX 200"})
        self.assertEqual(result["used_tools"], ["search_etf_news"])
        self.assertIn(
            {
                "source_name": "KODEX 200 관련 기사",
                "source_url": "https://news.google.com/articles/test",
                "data_date": "2026-11-24",
            },
            result["sources"],
        )

    def test_product_and_price_both_reach_database_backed_tools(self):
        client = Mock()
        client.responses.create.return_value = Mock(
            output_text="확인된 총보수는 0.05%입니다."
        )
        product = Mock()
        product.name = "search_etf_product"
        product.invoke.return_value = json.dumps({
            "success": True,
            "results": [{"total_fee_percent": 0.05, "source_name": "테스트 상품 자료"}],
        })
        price = Mock()
        price.name = "get_etf_price"
        price.invoke.return_value = json.dumps({
            "success": False,
            "message": "공공데이터 API에서 시세를 찾지 못했습니다.",
        })
        with patch.dict(
            "consultation.DATA_ROUTES",
            {"product": (product, "search_term", "ETF 상품"), "etf_price": (price, "etf_name", "시세")},
        ):
            result = consult("SOL 미국S&P500의 총보수와 최근 종가는?", "중급", client)

        product.invoke.assert_called_once_with({"search_term": "SOL 미국S&P500"})
        price.invoke.assert_called_once_with({"etf_name": "SOL 미국S&P500"})
        self.assertEqual(result["used_tools"], ["search_etf_product", "get_etf_price"])
        self.assertEqual(result["sources"], [{"source_name": "테스트 상품 자료"}])
        self.assertIn("0.05%", result["answer"])
        self.assertIn("시세 자료를 확인하지 못했습니다.", result["answer"])

    def test_unknown_product_is_sent_to_tool_for_database_validation(self):
        client = Mock()
        client.responses.create.return_value.output_text = (
            '{"routes":["etf_price"],"etf_name":"달토끼 우주여행 ETF"}'
        )

        result = route_question("달토끼 우주여행 ETF의 종가를 알려줘", client)

        self.assertEqual(
            result,
            {"routes": ["etf_price"], "etf_name": "달토끼 우주여행 ETF"},
        )

    def test_fast_router_handles_explicit_single_and_combined_requests(self):
        self.assertEqual(
            fast_route_question(
                "KODEX 200 최근 뉴스 알려줘",
                include_product=True,
            ),
            {"routes": ["news"], "etf_name": "KODEX 200", "router_mode": "rule"},
        )
        self.assertEqual(
            fast_route_question(
                "KODEX 200의 종가와 공시를 같이 알려줘",
                include_product=True,
            ),
            {
                "routes": ["etf_price", "disclosure"],
                "etf_name": "KODEX 200",
                "router_mode": "rule",
            },
        )

    def test_fast_router_summarizes_named_product_but_defers_missing_context(self):
        self.assertEqual(
            fast_route_question("KODEX 200 어때?", include_product=True),
            {
                "routes": ["product"],
                "etf_name": "KODEX 200",
                "router_mode": "rule",
            },
        )
        self.assertIsNone(fast_route_question("요즘 어때?", include_product=True))
        self.assertIsNone(
            fast_route_question(
                "그럼 그 ETF 뉴스는?",
                include_product=True,
                conversation_history=[{"role": "user", "content": "KODEX 200 알려줘"}],
            )
        )

    def test_investment_advice_is_blocked_and_uses_recent_product_context(self):
        history = [
            {"role": "user", "content": "KODEX 200 어때?"},
            {"role": "assistant", "content": "KODEX 200 상품정보입니다."},
        ]
        self.assertEqual(
            fast_route_question(
                "지금 당장 구매할까?",
                include_product=True,
                conversation_history=history,
            ),
            {
                "routes": ["investment_guidance"],
                "etf_name": "KODEX 200",
                "router_mode": "rule",
            },
        )

        client = Mock()
        result = consult(
            "지금 당장 구매할까?",
            "입문",
            client,
            conversation_history=history,
        )

        client.responses.create.assert_not_called()
        self.assertEqual(result["used_tools"], [])
        self.assertIn("KODEX 200", result["answer"])
        self.assertIn("매수·매도", result["answer"])
        self.assertIn("상품 추천은 제공하지 않습니다", result["answer"])

    def test_generated_recommendation_is_removed_before_display(self):
        client = Mock()
        client.responses.create.return_value = Mock(
            output_text="지금 KODEX 200 매수를 추천합니다."
        )
        product = Mock()
        product.name = "search_etf_product"
        product.invoke.return_value = json.dumps({
            "success": True,
            "results": [{"product_name": "KODEX 200", "source_name": "테스트"}],
        })

        with patch.dict(
            "consultation.DATA_ROUTES",
            {"product": (product, "search_term", "ETF 상품")},
        ):
            result = consult("KODEX 200 어때?", "입문", client)

        self.assertNotIn("매수를 추천합니다", result["answer"])
        self.assertIn("추천하거나", result["answer"])
        self.assertIn("적합한 상품인지 판단하지 않습니다", result["answer"])

    @patch("consultation.resolve_etf_product")
    def test_recommendation_and_price_forecast_use_separate_safe_messages(
        self,
        resolve_product,
    ):
        resolve_product.return_value = {
            "success": True,
            "match_type": "exact",
            "message": "ETF 상품을 확인했습니다.",
            "product": {
                "product_code": "069500",
                "product_name": "KODEX 200",
                "asset_manager": "삼성자산운용",
            },
        }
        history = [
            {"role": "user", "content": "KODEX 200 어때?"},
            {"role": "assistant", "content": "KODEX 200 상품정보입니다."},
        ]
        client = Mock()

        recommendation = consult(
            "종목 추천해줘 국내",
            "입문",
            client,
            conversation_history=history,
        )
        forecast = consult(
            "코덱스200 내일 올라갈까 가격",
            "입문",
            client,
            conversation_history=history,
        )

        client.responses.create.assert_not_called()
        self.assertIn("국내외 ETF나 종목을 골라 추천", recommendation["answer"])
        self.assertNotIn("앞서 문의하신", recommendation["answer"])
        self.assertIn("KODEX 200", forecast["answer"])
        self.assertIn("미래 가격이 오를지 내릴지", forecast["answer"])
        self.assertNotIn("매수·매도", forecast["answer"])

    def test_common_high_risk_phrasings_are_caught_without_llm(self):
        expected_routes = {
            "지금 물타기할까?": "investment_guidance",
            "수익률 높은 1등 ETF 골라줘": "product_recommendation",
            "KODEX 200 목표가 얼마야?": "price_forecast",
            "이거 원금 보장돼?": "return_guarantee",
            "퇴직금 얼마 넣는 게 좋아?": "personalized_allocation",
        }
        for question, expected_route in expected_routes.items():
            with self.subTest(question=question):
                routed = fast_route_question(question, include_product=True)
                self.assertEqual(routed["routes"], [expected_route])
                self.assertEqual(routed["router_mode"], "rule")

        client = Mock()
        guarantee = consult("이거 원금 보장돼?", "입문", client)
        allocation = consult("퇴직금 얼마 넣는 게 좋아?", "입문", client)
        client.responses.create.assert_not_called()
        self.assertIn("원금이나 수익을 보장할 수 없", guarantee["answer"])
        self.assertIn("투자금액", allocation["answer"])
        self.assertIn("맞춤형 포트폴리오", allocation["answer"])

    def test_code_with_particle_is_reduced_to_exact_product_code(self):
        routed = fast_route_question(
            "069500의 최근 종가를 알려줘",
            include_product=True,
        )
        self.assertEqual(routed["routes"], ["etf_price"])
        self.assertEqual(routed["etf_name"], "069500")

    def test_generic_recommendation_scope_is_not_treated_as_product_name(self):
        routed = fast_route_question(
            "그러면 국내 ETF 하나만 추천해줘",
            include_product=True,
            conversation_history=[
                {"role": "user", "content": "KODEX 200 상품정보를 알려줘"},
                {"role": "assistant", "content": "KODEX 200 상품정보입니다."},
                {"role": "user", "content": "KODEX 200 지금 사도 돼?"},
                {"role": "assistant", "content": "매수 추천은 제공하지 않습니다."},
            ],
        )
        self.assertEqual(routed["routes"], ["product_recommendation"])
        self.assertEqual(routed["etf_name"], "none")

    def test_explicit_product_reference_can_reuse_recent_product_for_recommendation(self):
        routed = fast_route_question(
            "그 ETF 추천해?",
            include_product=True,
            conversation_history=[
                {"role": "user", "content": "KODEX 200 상품정보를 알려줘"},
                {"role": "assistant", "content": "KODEX 200 상품정보입니다."},
            ],
        )
        self.assertEqual(routed["routes"], ["product_recommendation"])
        self.assertEqual(routed["etf_name"], "KODEX 200")

    def test_unresolved_explicit_reference_defers_to_context_router(self):
        history = [
            {"role": "user", "content": "ACE 미국S&P500 알려줘"},
            {"role": "assistant", "content": "ACE 미국S&P500 상품정보입니다."},
        ]
        self.assertIsNone(
            fast_route_question(
                "그 ETF 원금 보장돼?",
                include_product=True,
                conversation_history=history,
            )
        )
        self.assertIsNone(
            fast_route_question(
                "그건 어느 운용사 상품이야?",
                include_product=True,
                conversation_history=history,
            )
        )

    @patch("consultation.resolve_etf_product")
    def test_unknown_policy_target_is_not_displayed_as_real_product(self, resolve):
        resolve.return_value = {
            "success": False,
            "error_type": "product_not_found",
            "query": "KODEX 300",
            "candidates": [],
        }
        result = consult("KODEX 300 지금 사도 돼?", "입문", Mock())
        self.assertIn("상품 DB에 존재하지 않습니다", result["answer"])
        self.assertNotIn("대상 상품: KODEX 300", result["answer"])

    def test_product_name_recall_defers_to_structured_llm_router(self):
        questions = (
            "타이거 200? 상품 이름 뭐였지",
            "그 TIGER S&P500 이름 그 뭐였더라",
            "069500 상품명이 뭐야",
        )
        for question in questions:
            with self.subTest(question=question):
                routed = fast_route_question(question, include_product=True)
                self.assertIsNone(routed)

    def test_pronoun_name_recall_uses_recent_product_without_llm(self):
        routed = fast_route_question(
            "그거 정식 이름이 뭐였지?",
            include_product=True,
            conversation_history=[
                {"role": "user", "content": "069500 종가 알려줘"},
                {"role": "assistant", "content": "KODEX 200의 종가입니다."},
            ],
        )
        self.assertEqual(
            routed,
            {
                "routes": ["product"],
                "etf_name": "069500",
                "router_mode": "rule",
            },
        )

    def test_similar_recalled_product_asks_for_confirmation_before_lookup(self):
        client = Mock()
        client.responses.create.return_value.output_text = json.dumps({
            "routes": ["product"],
            "etf_name": "TIGER S&P500",
            "product_clues": {
                "asset_manager": "",
                "brand": "TIGER",
                "number_hint": "500",
                "index_hint": "S&P500",
                "market_or_theme": "",
            },
        })
        product = Mock()
        product.name = "search_etf_product"
        resolution = {
            "success": True,
            "match_type": "typo_corrected",
            "product": {
                "product_name": "TIGER 미국S&P500",
                "product_code": "360750",
            },
            "message": "유사 상품",
        }
        with patch(
            "consultation.resolve_etf_product",
            return_value=resolution,
        ), patch.dict(
            "consultation.DATA_ROUTES",
            {"product": (product, "search_term", "ETF 상품")},
        ):
            result = consult(
                "그 TIGER S&P500 이름 그 뭐였더라",
                "입문",
                client,
            )

        product.invoke.assert_not_called()
        client.responses.create.assert_called_once()
        self.assertIn("TIGER 미국S&P500", result["answer"])
        self.assertIn("혹시 이 상품이 맞으세요?", result["answer"])

    def test_explicit_news_skips_llm_router_but_still_generates_answer(self):
        client = Mock()
        client.responses.create.return_value = Mock(output_text="최근 뉴스를 확인했습니다.")
        news = Mock()
        news.name = "search_etf_news"
        news.invoke.return_value = json.dumps({
            "success": True,
            "articles": [],
            "source_name": "Google 뉴스 RSS",
            "source_url": "https://news.google.com/",
        })

        with patch.dict(
            "consultation.DATA_ROUTES",
            {"news": (news, "etf_name", "뉴스")},
        ):
            result = consult("KODEX 200 최근 뉴스 알려줘", "입문", client)

        self.assertEqual(client.responses.create.call_count, 1)
        self.assertEqual(result["router_mode"], "rule")
        news.invoke.assert_called_once_with({"etf_name": "KODEX 200"})

    def test_unknown_product_is_clearly_reported_as_not_in_database(self):
        client = Mock()
        client.responses.create.return_value.output_text = (
            '{"routes":["etf_price","disclosure"],"etf_name":"달토끼 우주여행 ETF"}'
        )
        price = Mock()
        price.name = "get_etf_price"
        price.invoke.return_value = json.dumps({
            "success": False,
            "error_type": "product_not_found",
            "query": "달토끼 우주여행 ETF",
            "message": "내부 검색 결과 없음",
        })
        disclosure = Mock()
        disclosure.name = "search_etf_disclosure"
        disclosure.invoke.return_value = price.invoke.return_value

        with patch.dict(
            "consultation.DATA_ROUTES",
            {
                "etf_price": (price, "etf_name", "시세"),
                "disclosure": (disclosure, "etf_name", "공시"),
            },
        ):
            result = consult("달토끼 우주여행 ETF의 종가와 공시를 알려줘", "입문", client)

        self.assertEqual(result["answer"].count("상품 DB에 존재하지 않습니다"), 1)
        self.assertIn("확인되지 않은 상품 정보·시세·공시·뉴스는 제공하지 않습니다", result["answer"])
        self.assertNotIn("내부 검색 결과 없음", result["answer"])
        self.assertEqual(
            result["used_tools"],
            ["get_etf_price", "search_etf_disclosure"],
        )

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
        self.assertIn("주식이나 ETF의 기본 용어", beginner_prompt["instructions"])
        self.assertIn("지표 정의", expert_prompt["instructions"])
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
            app.button(key="category_nav_0").click().run()
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
        self.assertTrue(all("question" not in call.kwargs for call in log.call_args_list))
        self.assertTrue(callable(first.kwargs["progress_callback"]))
        self.assertTrue(callable(second.kwargs["progress_callback"]))
        self.assertEqual(first.kwargs["conversation_history"], [])
        self.assertEqual(
            second.kwargs["conversation_history"],
            [
                {"role": "user", "content": QUESTION},
                {
                    "role": "assistant",
                    "content": response["answer"],
                    "used_tools": response["used_tools"],
                    "sources": response["sources"],
                    "related": response["related"],
                    "selected_faq": True,
                },
            ],
        )
        self.assertEqual(app.session_state["messages"][1]["sources"], response["sources"])

        conversation_expanders = [
            expander
            for expander in app.expander
            if expander.label.startswith("💬")
        ]
        self.assertEqual(len(conversation_expanders), 1)

        turn_buttons = [
            button
            for button in app.button
            if str(button.key).startswith("turn_nav_")
        ]
        self.assertEqual(len(turn_buttons), 2)

        turn_buttons[0].click().run()
        self.assertEqual(len(app.session_state["messages"]), 4)

        app.button(key="global_home").click().run()
        self.assertEqual(app.session_state["messages"], [])
        self.assertIsNone(app.session_state["faq_view_category"])

    def test_csv_fallback_is_labeled_and_searchable(self):
        from psycopg import OperationalError

        with patch("faq_agent.list_faq_questions", side_effect=OperationalError):
            app = AppTest.from_file(str(APP_PATH), default_timeout=90).run()
            self.assertFalse(app.exception)
            self.assertTrue(any("원본 CSV" in caption.value for caption in app.caption))
            app.text_input(key="faq_search").set_value("총보수").run()
            app.button(key="category_nav_0").click().run()
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
            app.button(key="category_nav_0").click().run()
            app.button(key="faq_F001").click().run()
            app.segmented_control(key="faq_feedback_1").set_value("도움이 됐어요").run()
            self.assertEqual(consult_mock.call_count, 1)
            self.assertEqual(log.call_count, 1)
            app.button(key="related_faq_0").click().run()

        self.assertFalse(app.exception)
        self.assertEqual(app.session_state["faq_feedback_1"], "도움이 됐어요")
        self.assertEqual(consult_mock.call_args.args[0], related_question)
        self.assertTrue(consult_mock.call_args.kwargs["selected_faq"])
