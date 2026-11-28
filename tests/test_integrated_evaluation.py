import unittest

from eval_integrated_service import (
    contains_required_terms,
    evaluate_external_error_safety,
    percentile,
    source_alignment,
)


class IntegratedEvaluationTest(unittest.TestCase):
    def test_nearest_rank_p95(self):
        self.assertEqual(percentile([1, 2, 3, 4, 5], 0.95), 5)
        self.assertEqual(percentile([], 0.95), 0.0)

    def test_required_term_groups_accept_alternatives(self):
        self.assertTrue(
            contains_required_terms(
                "최근 종가는 확인했고 기준일도 표시했습니다.",
                [["종가"], ["기준일", "조회일"]],
            )
        )
        self.assertFalse(
            contains_required_terms("최근 종가입니다.", [["종가"], ["기준일"]])
        )

    def test_product_source_must_match_registered_url(self):
        case = {
            "requires_sources": True,
            "expected_tools": ["search_etf_product"],
            "expected_product": "KODEX 200",
        }
        urls = {"KODEX 200": {"https://official.example/product.pdf"}}
        self.assertTrue(
            source_alignment(
                case,
                {"sources": [{"source_url": "https://official.example/product.pdf"}]},
                urls,
            )
        )
        self.assertFalse(
            source_alignment(
                case,
                {"sources": [{"source_url": "https://untrusted.example/post"}]},
                urls,
            )
        )

    def test_all_external_error_scenarios_are_safe(self):
        rows = evaluate_external_error_safety()
        self.assertEqual(len(rows), 6)
        self.assertTrue(all(row["safe"] for row in rows))


if __name__ == "__main__":
    unittest.main()
