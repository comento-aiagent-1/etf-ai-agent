"""다중 턴 질문에서 상품 문맥을 이어야 할 때와 끊어야 할 때를 평가합니다."""

import argparse
import csv
import json
import os
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from orchestrator import fast_route_question, route_question
from src.services.product_catalog import resolve_etf_product


ROOT = Path(__file__).resolve().parent
DATASET = ROOT / "data" / "evaluation" / "conversation_context_questions.json"
RESULT_DIR = ROOT / "data" / "evaluation" / "results"


def resolve_code(routed):
    etf_name = str(routed.get("etf_name") or "none").strip()
    if etf_name == "none":
        return None, "none"
    resolution = resolve_etf_product(
        etf_name,
        product_clues=routed.get("product_clues"),
    )
    if resolution.get("success"):
        return resolution["product"]["product_code"], resolution.get("match_type", "exact")
    candidates = resolution.get("candidates") or []
    if len(candidates) == 1:
        return candidates[0]["product_code"], "candidate"
    return None, resolution.get("error_type", "unresolved")


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
            routed = fast_route_question(
                case["question"],
                include_product=True,
                conversation_history=case["conversation_history"],
            )
            if routed is None:
                routed = route_question(
                    case["question"],
                    client,
                    include_product=True,
                    conversation_history=case["conversation_history"],
                )
                router_mode = "llm"
            else:
                router_mode = "rule"

            actual_routes = routed.get("routes", [])
            route_pass = actual_routes == case["expected_routes"]
            actual_code, resolution_mode = resolve_code(routed)
            target_pass = actual_code == case["expected_product_code"]
            overall_pass = route_pass and target_pass
            elapsed = round(time.perf_counter() - started, 4)
            row = {
                "id": case["id"],
                "category": case["category"],
                "question": case["question"],
                "expected_target_mode": case["expected_target_mode"],
                "router_mode": router_mode,
                "expected_routes": "|".join(case["expected_routes"]),
                "actual_routes": "|".join(actual_routes),
                "actual_etf_name": routed.get("etf_name", "none"),
                "expected_product_code": case["expected_product_code"] or "",
                "actual_product_code": actual_code or "",
                "resolution_mode": resolution_mode,
                "route_pass": route_pass,
                "target_pass": target_pass,
                "overall_pass": overall_pass,
                "elapsed_seconds": elapsed,
            }
            rows.append(row)
            mark = "PASS" if overall_pass else "FAIL"
            print(f"[{index:02d}/{len(cases):02d}] {case['id']} {mark} ({elapsed:.2f}s)")

    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_path = RESULT_DIR / f"conversation_context_results_{stamp}.csv"
    with result_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    total = len(rows)
    passed = sum(row["overall_pass"] for row in rows)
    route_passed = sum(row["route_pass"] for row in rows)
    target_passed = sum(row["target_pass"] for row in rows)
    category_counts = Counter(row["category"] for row in rows)
    category_passed = Counter(
        row["category"] for row in rows if row["overall_pass"]
    )
    print("\n=== 대화 문맥 평가 결과 ===")
    print(f"전체 성공: {passed}/{total} ({passed / total:.1%})")
    print(f"의도 분류: {route_passed}/{total} ({route_passed / total:.1%})")
    print(f"상품 문맥: {target_passed}/{total} ({target_passed / total:.1%})")
    for category in sorted(category_counts):
        print(
            f"- {category}: {category_passed[category]}/{category_counts[category]}"
        )
    print(f"결과 파일: {result_path}")


if __name__ == "__main__":
    main()
