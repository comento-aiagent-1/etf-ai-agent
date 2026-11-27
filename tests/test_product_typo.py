"""상품명 오타·유사 표현 검색 테스트 (DB 없이 상품 목록만 사용)."""
import json
import unittest
from unittest.mock import Mock, patch

from consultation import consult
from src.services.product_catalog import match_products


PRODUCTS = [
    {"product_code": "069500", "product_name": "KODEX 200", "asset_manager": "삼성자산운용"},
    {"product_code": "102110", "product_name": "TIGER 200", "asset_manager": "미래에셋자산운용"},
    {"product_code": "105190", "product_name": "ACE 200", "asset_manager": "한국투자신탁운용"},
    {"product_code": "360750", "product_name": "TIGER 미국S&P500", "asset_manager": "미래에셋자산운용"},
    {"product_code": "133690", "product_name": "TIGER 미국나스닥100", "asset_manager": "미래에셋자산운용"},
    {"product_code": "367380", "product_name": "ACE 미국나스닥100", "asset_manager": "한국투자신탁운용"},
    {"product_code": "411060", "product_name": "ACE KRX금현물", "asset_manager": "한국투자신탁운용"},
]


def resolved_code(query):
    result = match_products(query, PRODUCTS)
    return result["product"]["product_code"] if result["success"] else None


class ExactMatchTest(unittest.TestCase):
    def test_existing_exact_matches_still_work(self):
        self.assertEqual(resolved_code("KODEX 200"), "069500")
        self.assertEqual(resolved_code("kodex200"), "069500")
        self.assertEqual(resolved_code("코덱스 200"), "069500")
        self.assertEqual(resolved_code("069500"), "069500")
        self.assertEqual(resolved_code("KODEX 200 ETF"), "069500")
        self.assertEqual(match_products("KODEX 200", PRODUCTS)["match_type"], "exact")


class TypoCorrectionTest(unittest.TestCase):
    def test_brand_typos_are_corrected(self):
        for query in ("COXEX200", "KODXE 200", "코덱쓰 200"):
            with self.subTest(query=query):
                result = match_products(query, PRODUCTS)
                self.assertTrue(result["success"], result)
                self.assertEqual(result["product"]["product_code"], "069500")
                self.assertEqual(result["match_type"], "typo_corrected")
                self.assertIn("KODEX 200", result["message"])

    def test_name_typos_are_corrected(self):
        self.assertEqual(resolved_code("TIGRE 미국나스닥100"), "133690")
        self.assertEqual(resolved_code("TIGER 미국SNP500"), "360750")
        self.assertEqual(resolved_code("에이스 금현물"), "411060")

    def test_single_extra_digit_is_corrected_when_candidate_is_clear(self):
        result = match_products("코덱스 2000", PRODUCTS)
        self.assertTrue(result["success"], result)
        self.assertEqual(result["product"]["product_code"], "069500")
        self.assertEqual(result["match_type"], "typo_corrected")
        self.assertIn("KODEX 200", result["message"])


class ConfirmationTest(unittest.TestCase):
    def assert_asks(self, query, expected_codes):
        result = match_products(query, PRODUCTS)
        self.assertFalse(result["success"], result)
        self.assertEqual(result["error_type"], "ambiguous_product")
        codes = {item["product_code"] for item in result["candidates"]}
        self.assertTrue(set(expected_codes) <= codes, codes)

    def test_ambiguous_expressions_ask_user(self):
        self.assert_asks("200", ["069500", "102110", "105190"])
        self.assert_asks("나스닥100", ["133690", "367380"])
        self.assert_asks("타이거 나스닥", ["133690"])

    def test_different_number_is_not_auto_corrected(self):
        result = match_products("KODEX 300", PRODUCTS)
        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "product_not_found")
        self.assertEqual(result["candidates"], [])

    def test_same_number_candidate_excludes_different_number_products(self):
        result = match_products("TIGER S&P500", PRODUCTS)
        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "ambiguous_product")
        self.assertEqual(
            [item["product_code"] for item in result["candidates"]],
            ["360750"],
        )

    def test_natural_manager_and_number_clues_offer_a_confirmable_candidate(self):
        products = PRODUCTS + [{
            "product_code": "0000H0",
            "product_name": "KODEX 인도Nifty미드캡100",
            "asset_manager": "삼성자산운용",
        }]
        result = match_products(
            "삼성자산운용에서 하는 코 뭐시기로 시작하고 2000인가로 끝나는 상품",
            products,
        )
        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "ambiguous_product")
        self.assertEqual(
            [item["product_code"] for item in result["candidates"]],
            ["069500"],
        )

    def test_structured_clues_cover_brand_partial_code_index_and_theme(self):
        cases = [
            (
                {"asset_manager": "삼성", "brand": "코덱스", "number_hint": "200"},
                "069500",
            ),
            (
                {"number_hint": "133", "index_hint": "나스닥", "market_or_theme": "미국"},
                "133690",
            ),
            (
                {"asset_manager": "한국투자", "market_or_theme": "금"},
                "411060",
            ),
        ]
        for clues, expected_code in cases:
            with self.subTest(clues=clues):
                from src.services.product_catalog import _structured_clue_match
                result = _structured_clue_match(clues, PRODUCTS)
                self.assertIsNotNone(result)
                self.assertEqual(result["candidates"][0]["product_code"], expected_code)


class NotFoundTest(unittest.TestCase):
    def test_products_not_in_db_are_not_matched(self):
        for query in (
            "KODEX 레버리지",
            "KODEX 200선물인버스2X",
            "삼성전자",
            "069501",
            "달토끼 우주여행 ETF",
        ):
            with self.subTest(query=query):
                result = match_products(query, PRODUCTS)
                self.assertFalse(result["success"], result)
                self.assertEqual(result["error_type"], "product_not_found")


class ConsultationProductResolutionTest(unittest.TestCase):
    def _client(self, route_json, answer="확인한 자료로 답변합니다."):
        client = Mock()
        client.responses.create.side_effect = [
            Mock(output_text=route_json),
            Mock(output_text=answer),
        ]
        return client

    def test_typo_is_corrected_before_tool_call_and_user_is_told(self):
        news = Mock()
        news.name = "search_etf_news"
        news.invoke.return_value = json.dumps({"success": True, "articles": []})
        client = self._client('{"routes":["news"],"etf_name":"COXEX200"}')

        with patch(
            "consultation.resolve_etf_product",
            side_effect=lambda name: match_products(name, PRODUCTS),
        ), patch.dict(
            "consultation.DATA_ROUTES",
            {"news": (news, "etf_name", "뉴스")},
        ):
            result = consult("COXEX200 뉴스", "입문", client)

        news.invoke.assert_called_once_with({"etf_name": "KODEX 200"})
        self.assertTrue(result["answer"].startswith("'COXEX200'을(를) 'KODEX 200'"))
        self.assertEqual(
            result["tool_inputs"],
            [{"tool": "search_etf_news", "args": {"etf_name": "KODEX 200"}}],
        )

    def test_extra_digit_typo_is_corrected_before_price_lookup(self):
        price = Mock()
        price.name = "get_etf_price"
        price.invoke.return_value = json.dumps({
            "success": True,
            "data": {
                "product_name": "KODEX 200",
                "product_code": "069500",
                "data_date": "2026-11-27",
                "close_price": 73770,
            },
        })
        client = Mock()
        client.responses.create.return_value = Mock(
            output_text="KODEX 200의 기준일 종가는 73,770원입니다."
        )

        with patch(
            "consultation.resolve_etf_product",
            side_effect=lambda name: match_products(name, PRODUCTS),
        ), patch.dict(
            "consultation.DATA_ROUTES",
            {"etf_price": (price, "etf_name", "시세")},
        ):
            result = consult("코덱스 2000 종가 알려줘", "입문", client)

        price.invoke.assert_called_once_with({"etf_name": "KODEX 200"})
        self.assertTrue(
            result["answer"].startswith(
                "'코덱스 2000'을(를) 'KODEX 200'(으)로 해석했습니다."
            )
        )

    def test_ambiguous_product_asks_instead_of_guessing(self):
        price = Mock()
        price.name = "get_etf_price"
        client = self._client('{"routes":["etf_price"],"etf_name":"200"}')

        with patch(
            "consultation.resolve_etf_product",
            side_effect=lambda name: match_products(name, PRODUCTS),
        ), patch.dict(
            "consultation.DATA_ROUTES",
            {"etf_price": (price, "etf_name", "시세")},
        ):
            result = consult("200 종가 알려줘", "입문", client)

        price.invoke.assert_not_called()
        self.assertIn("비슷한 ETF 후보가 여러 개", result["answer"])
        self.assertIn("KODEX 200(069500)", result["answer"])


if __name__ == "__main__":
    unittest.main()
