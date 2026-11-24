"""50개 자연어 질문으로 라우팅과 상품 후보 검색을 평가합니다."""

import argparse
import csv
import json
import os
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from orchestrator import fast_route_question, route_question
from src.services.product_catalog import resolve_etf_product


ROOT = Path(__file__).resolve().parent
DATASET = ROOT / "data" / "evaluation" / "natural_language_questions.json"
RESULT_DIR = ROOT / "data" / "evaluation" / "results"
PRODUCT_ROUTES = {"etf_price", "disclosure", "news", "product"}


def evaluate_behavior(expected, actual_behavior):
    if expected == "route_only":
        return True
    if expected == "resolved":
        return actual_behavior in {"exact", "candidate"}
    if expected == "not_found":
        return actual_behavior in {"not_found", "product_not_found"}
    return expected == actual_behavior


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError(".env에서 OPENAI_API_KEY를 찾지 못했습니다.")

    cases = json.loads(DATASET.read_text(encoding="utf-8"))
    if args.limit:
        cases = cases[:args.limit]

    rows = []
    with OpenAI(timeout=20, max_retries=0) as client:
        for index, case in enumerate(cases, start=1):
            started = time.perf_counter()
            history = case.get("conversation_history") or []
            routed = fast_route_question(
                case["question"],
                include_product=True,
                conversation_history=history,
            )
            if routed is None:
                routed = route_question(
                    case["question"],
                    client,
                    include_product=True,
                    conversation_history=history,
                )
                router_mode = "llm"
            else:
                router_mode = "rule"

            actual_routes = routed.get("routes", [])
            route_pass = actual_routes == case["expected_routes"]
            resolution = None
            actual_codes = []
            if PRODUCT_ROUTES.intersection(actual_routes) and routed.get("etf_name") != "none":
                resolution = resolve_etf_product(
                    routed["etf_name"],
                    product_clues=routed.get("product_clues"),
                )
                if resolution.get("success"):
                    actual_codes = [resolution["product"]["product_code"]]
                else:
                    actual_codes = [
                        item["product_code"]
                        for item in resolution.get("candidates", [])
                    ]

            expected_codes = case.get("expected_product_codes", [])
            product_pass = (
                not expected_codes
                or set(expected_codes).issubset(set(actual_codes))
            )
            if resolution and resolution.get("success"):
                if (
                    routed.get("product_clues")
                    and resolution.get("match_type") in {"typo_corrected", "partial_match"}
                ):
                    actual_behavior = "candidate"
                else:
                    actual_behavior = "exact"
            elif resolution and resolution.get("candidates"):
                actual_behavior = "candidate"
            elif resolution:
                actual_behavior = resolution.get("error_type", "route_only")
            else:
                actual_behavior = "route_only"
            behavior_pass = evaluate_behavior(
                case["expected_behavior"],
                actual_behavior,
            )
            overall_pass = route_pass and product_pass and behavior_pass
            elapsed = round(time.perf_counter() - started, 4)

            rows.append({
                "id": case["id"],
                "question": case["question"],
                "router_mode": router_mode,
                "expected_routes": "|".join(case["expected_routes"]),
                "actual_routes": "|".join(actual_routes),
                "expected_codes": "|".join(expected_codes),
                "actual_codes": "|".join(actual_codes),
                "expected_behavior": case["expected_behavior"],
                "actual_behavior": actual_behavior,
                "route_pass": route_pass,
                "product_pass": product_pass,
                "behavior_pass": behavior_pass,
                "overall_pass": overall_pass,
                "elapsed_seconds": elapsed,
            })
            mark = "PASS" if overall_pass else "FAIL"
            print(f"[{index:02d}/{len(cases):02d}] {case['id']} {mark} ({elapsed:.2f}s)")

    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_path = RESULT_DIR / f"natural_language_results_{stamp}.csv"
    with result_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    total = len(rows)
    passed = sum(row["overall_pass"] for row in rows)
    route_passed = sum(row["route_pass"] for row in rows)
    product_passed = sum(row["product_pass"] for row in rows)
    average_time = sum(row["elapsed_seconds"] for row in rows) / total
    print("\n=== 평가 결과 ===")
    print(f"전체 성공: {passed}/{total} ({passed / total:.1%})")
    print(f"의도 분류: {route_passed}/{total} ({route_passed / total:.1%})")
    print(f"상품 후보: {product_passed}/{total} ({product_passed / total:.1%})")
    print(f"평균 시간: {average_time:.3f}초")
    print(f"결과 파일: {result_path}")


if __name__ == "__main__":
    main()
