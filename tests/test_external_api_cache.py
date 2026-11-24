import json
import unittest
from unittest.mock import patch

import api_tools
import news_tools
from src.services.ttl_cache import TTLCache


PRODUCT = {
    "product_code": "069500",
    "product_name": "KODEX 200",
    "asset_manager": "삼성자산운용",
}
RESOLUTION = {
    "success": True,
    "match_type": "exact",
    "product": PRODUCT,
}


class ExternalApiCacheTest(unittest.TestCase):
    def setUp(self):
        news_tools._NEWS_CACHE.clear()
        api_tools._DISCLOSURE_CACHE.clear()

    def test_news_result_is_reused_with_a_fresh_copy(self):
        raw_result = {
            "etf_name": "KODEX 200",
            "start_date": "2026-11-01",
            "end_date": "2026-11-25",
            "checked_at": "2026-11-25 00:00",
            "articles": [
                {
                    "title": "KODEX 200 기사",
                    "press": "테스트 언론",
                    "published_at": "2026-11-24",
                    "url": "https://news.google.com/articles/test",
                    "title_mentions_etf": True,
                }
            ],
        }

        with patch(
            "news_tools.resolve_etf_product",
            return_value=RESOLUTION,
        ), patch(
            "news_tools.find_etf_news",
            return_value=raw_result,
        ) as fetch:
            first = json.loads(
                news_tools.search_etf_news.invoke(
                    {"etf_name": "KODEX 200"}
                )
            )
            second = json.loads(
                news_tools.search_etf_news.invoke(
                    {"etf_name": "KODEX 200"}
                )
            )

        self.assertEqual(fetch.call_count, 1)
        self.assertFalse(first["cache_hit"])
        self.assertTrue(second["cache_hit"])
        self.assertTrue(first["articles"][0]["url"].startswith("NEWS_LINK_"))
        self.assertTrue(second["articles"][0]["url"].startswith("NEWS_LINK_"))
        self.assertEqual(raw_result["articles"][0]["url"], "https://news.google.com/articles/test")

    def test_disclosure_result_is_reused(self):
        raw_result = {
            "etf_name": "KODEX 200",
            "asset_manager": "삼성자산운용",
            "dart_corp_name": "삼성자산운용",
            "matches": [],
            "start_date": "20260828",
            "end_date": "20261125",
            "scanned_pages": 1,
            "total_pages": 1,
            "search_complete": True,
            "stopped_by_limit": False,
            "result_status": "no_results",
            "result_message": "검색 결과가 없습니다.",
        }

        with patch(
            "api_tools.resolve_etf_product",
            return_value=RESOLUTION,
        ), patch(
            "api_tools.find_etf_disclosure_titles",
            return_value=raw_result,
        ) as fetch, patch(
            "api_tools.validate_disclosure_result",
            return_value=(True, "정상"),
        ):
            first = json.loads(
                api_tools.search_etf_disclosure.invoke(
                    {"etf_name": "KODEX 200"}
                )
            )
            second = json.loads(
                api_tools.search_etf_disclosure.invoke(
                    {"etf_name": "KODEX 200"}
                )
            )

        self.assertEqual(fetch.call_count, 1)
        self.assertFalse(first["cache_hit"])
        self.assertTrue(second["cache_hit"])


class TtlCacheTest(unittest.TestCase):
    def test_expired_value_is_refreshed(self):
        now = [100.0]
        calls = []
        cache = TTLCache(maxsize=2, clock=lambda: now[0])

        def factory():
            calls.append(True)
            return {"value": len(calls)}

        first, first_hit = cache.get_or_set(
            "key",
            factory,
            ttl_seconds=10,
        )
        second, second_hit = cache.get_or_set(
            "key",
            factory,
            ttl_seconds=10,
        )
        now[0] = 111.0
        third, third_hit = cache.get_or_set(
            "key",
            factory,
            ttl_seconds=10,
        )

        self.assertEqual(first, {"value": 1})
        self.assertEqual(second, {"value": 1})
        self.assertEqual(third, {"value": 2})
        self.assertFalse(first_hit)
        self.assertTrue(second_hit)
        self.assertFalse(third_hit)


if __name__ == "__main__":
    unittest.main()
