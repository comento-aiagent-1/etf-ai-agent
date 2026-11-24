import math
import unittest
from unittest.mock import Mock, patch

from src.services.request_logger import save_request_log


class RequestTimingLogTest(unittest.TestCase):
    def test_stage_timings_keep_only_safe_numeric_fields(self):
        collection = Mock()

        with patch(
            "src.services.request_logger.get_log_collection",
            return_value=collection,
        ):
            saved = save_request_log(
                question_length=12,
                elapsed_seconds=1.23456,
                result="성공",
                used_tools=["search_etf_news"],
                tool_inputs=[
                    {
                        "tool": "search_etf_news",
                        "args": {"etf_name": "KODEX 200"},
                    }
                ],
                stage_timings={
                    "router_seconds": 0.25,
                    "news_seconds": 0.7,
                    "answer_generation_seconds": math.nan,
                    "unknown_private_field": 999,
                },
                cache_hits={
                    "search_etf_news": True,
                    "unknown_tool": True,
                },
                router_mode="rule",
            )

        self.assertTrue(saved)
        document = collection.insert_one.call_args.args[0]
        timings = document["stage_timings"]

        self.assertEqual(timings["router_seconds"], 0.25)
        self.assertEqual(timings["news_seconds"], 0.7)
        self.assertEqual(timings["answer_generation_seconds"], 0.0)
        self.assertEqual(timings["total_seconds"], 1.2346)
        self.assertNotIn("unknown_private_field", timings)
        self.assertEqual(document["router_mode"], "rule")
        self.assertEqual(
            document["cache_hits"],
            {"search_etf_news": True},
        )
        self.assertNotIn("question", document)
        self.assertNotIn("answer", document)


if __name__ == "__main__":
    unittest.main()
