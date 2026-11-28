"""최종 서비스의 답변·출처·응답시간·장애 안전성을 통합 평가합니다."""

import argparse
import csv
import json
import math
import os
import statistics
import time
from collections import defaultdict
from contextlib import ExitStack
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from dotenv import load_dotenv
from openai import OpenAI

import consultation
from consultation import consult


ROOT = Path(__file__).resolve().parent
DATASET = ROOT / "data" / "evaluation" / "integrated_service_questions.json"
PRODUCTS = ROOT / "data" / "source" / "etf_products.csv"
RESULT_DIR = ROOT / "data" / "evaluation" / "results"
LATEST_SUMMARY = ROOT / "docs" / "final_integrated_evaluation.md"

SOURCE_RULES = {
    "get_etf_price": lambda source, _case, _urls: "data.go.kr" in source.get("source_url", ""),
    "search_etf_disclosure": lambda source, _case, _urls: "dart.fss.or.kr" in source.get("source_url", ""),
    "search_etf_news": lambda source, _case, _urls: (
        "news.google.com" in source.get("source_url", "")
        or "뉴스" in source.get("source_name", "")
        or "news" in source.get("source_name", "").lower()
    ),
    "search_faq": lambda source, _case, _urls: bool(source.get("source_url")),
    "search_etf_product": lambda source, case, urls: (
        source.get("source_url") in urls.get(case.get("expected_product"), set())
    ),
}


def percentile(values, percentile_value):
    """작은 표본에서도 재현 가능한 nearest-rank 백분위수를 반환합니다."""
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(1, math.ceil(percentile_value * len(ordered)))
    return round(ordered[rank - 1], 4)


def load_product_source_urls():
    urls = defaultdict(set)
    with PRODUCTS.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("product_name") and row.get("source_url"):
                urls[row["product_name"]].add(row["source_url"])
    return urls


def contains_required_terms(answer, required_groups):
    return all(
        any(term.lower() in answer.lower() for term in group)
        for group in required_groups
    )


def has_expected_product(case, result):
    expected = case.get("expected_product")
    if not expected:
        return True
    answer = result.get("answer", "")
    if expected.lower() in answer.lower():
        return True
    for item in result.get("tool_inputs", []):
        if expected in (item.get("args") or {}).values():
            return True
    return False


def source_alignment(case, result, product_urls):
    if not case.get("requires_sources"):
        return len(result.get("sources", [])) == 0
    sources = result.get("sources", [])
    if not sources:
        return False
    for tool_name in case.get("expected_tools", []):
        matcher = SOURCE_RULES.get(tool_name)
        if matcher and not any(matcher(source, case, product_urls) for source in sources):
            return False
    return True


def evaluate_case(case, result, elapsed_seconds, product_urls):
    answer = result.get("answer", "")
    expected_tools = case.get("expected_tools", [])
    used_tools = result.get("used_tools", [])
    tool_pass = set(used_tools) == set(expected_tools)
    product_pass = has_expected_product(case, result)
    required_pass = contains_required_terms(answer, case.get("required_any", []))
    forbidden = case.get("forbidden_terms", [])
    forbidden_pass = not any(term.lower() in answer.lower() for term in forbidden)
    answer_pass = tool_pass and product_pass and required_pass and forbidden_pass
    source_pass = source_alignment(case, result, product_urls)
    return {
        "id": case["id"],
        "category": case["category"],
        "question": case["question"],
        "answer": answer,
        "expected_tools": expected_tools,
        "used_tools": used_tools,
        "tool_pass": tool_pass,
        "product_pass": product_pass,
        "required_terms_pass": required_pass,
        "forbidden_terms_pass": forbidden_pass,
        "answer_pass": answer_pass,
        "source_required": bool(case.get("requires_sources")),
        "source_pass": source_pass,
        "source_count": len(result.get("sources", [])),
        "elapsed_seconds": round(elapsed_seconds, 4),
        "stage_timings": result.get("timings", {}),
        "router_mode": result.get("router_mode"),
        "error": None,
    }


class FailureTool:
    def __init__(self, name, *, raise_error):
        self.name = name
        self.raise_error = raise_error

    def invoke(self, _args):
        if self.raise_error:
            raise RuntimeError("private upstream detail")
        return json.dumps({"success": False, "message": "private upstream detail"})


class NoAnswerClient:
    class Responses:
        @staticmethod
        def create(**_kwargs):
            raise AssertionError("근거가 없을 때 LLM 답변 생성을 호출하면 안 됩니다.")

    responses = Responses()


def evaluate_external_error_safety():
    scenarios = [
        ("가격 API 예외", "etf_price", "get_etf_price", "시세", "KODEX 200 종가 알려줘", True),
        ("가격 API 실패응답", "etf_price", "get_etf_price", "시세", "KODEX 200 종가 알려줘", False),
        ("DART 예외", "disclosure", "search_etf_disclosure", "공시", "KODEX 200 공시 알려줘", True),
        ("DART 실패응답", "disclosure", "search_etf_disclosure", "공시", "KODEX 200 공시 알려줘", False),
        ("뉴스 API 예외", "news", "search_etf_news", "뉴스", "KODEX 200 뉴스 알려줘", True),
        ("뉴스 API 실패응답", "news", "search_etf_news", "뉴스", "KODEX 200 뉴스 알려줘", False),
    ]
    rows = []
    for name, route, tool_name, label, question, raise_error in scenarios:
        tool = FailureTool(tool_name, raise_error=raise_error)
        with ExitStack() as stack:
            stack.enter_context(
                patch.object(
                    consultation,
                    "_resolve_product_name",
                    return_value=("KODEX 200", None, False),
                )
            )
            stack.enter_context(
                patch.dict(
                    consultation.DATA_ROUTES,
                    {route: (tool, "etf_name", label)},
                    clear=False,
                )
            )
            result = consult(question, "입문", NoAnswerClient())
        expected_message = f"{label} 자료를 확인하지 못했습니다."
        safe = (
            expected_message in result.get("answer", "")
            and "private upstream detail" not in result.get("answer", "")
            and result.get("sources") == []
            and result.get("used_tools") == [tool_name]
        )
        rows.append({
            "scenario": name,
            "safe": safe,
            "answer": result.get("answer", ""),
            "used_tools": result.get("used_tools", []),
            "source_count": len(result.get("sources", [])),
        })
    return rows


def summarize(rows, safety_rows):
    completed = [row for row in rows if not row.get("error")]
    source_cases = [row for row in completed if row.get("source_required")]
    latencies = [row["elapsed_seconds"] for row in completed]
    by_category = {}
    for category in sorted({row["category"] for row in completed}):
        group = [row for row in completed if row["category"] == category]
        group_source_cases = [row for row in group if row.get("source_required")]
        group_times = [row["elapsed_seconds"] for row in group]
        by_category[category] = {
            "count": len(group),
            "answer_accuracy_percent": round(
                100 * sum(row["answer_pass"] for row in group) / len(group), 1
            ),
            "source_match_percent": round(
                100 * sum(row["source_pass"] for row in group_source_cases)
                / len(group_source_cases),
                1,
            ) if group_source_cases else None,
            "mean_seconds": round(statistics.mean(group_times), 4),
            "p95_seconds": percentile(group_times, 0.95),
        }
    return {
        "case_count": len(rows),
        "completed_count": len(completed),
        "execution_error_count": len(rows) - len(completed),
        "final_answer_accuracy_percent": round(
            100 * sum(row["answer_pass"] for row in completed) / len(completed), 1
        ) if completed else 0.0,
        "source_match_percent": round(
            100 * sum(row["source_pass"] for row in source_cases) / len(source_cases), 1
        ) if source_cases else 0.0,
        "source_case_count": len(source_cases),
        "mean_response_seconds": round(statistics.mean(latencies), 4) if latencies else 0.0,
        "p95_response_seconds": percentile(latencies, 0.95),
        "external_api_safe_response_percent": round(
            100 * sum(row["safe"] for row in safety_rows) / len(safety_rows), 1
        ) if safety_rows else 0.0,
        "external_api_scenario_count": len(safety_rows),
        "by_category": by_category,
    }


def markdown_report(generated_at, summary, rows, safety_rows):
    lines = [
        "# 최종 통합 평가 결과",
        "",
        f"- 실행 시각: {generated_at}",
        f"- 평가 질문: {summary['case_count']}개",
        f"- 최종 답변 정확도: **{summary['final_answer_accuracy_percent']}%**",
        f"- 출처 일치율: **{summary['source_match_percent']}%** "
        f"({summary['source_case_count']}개 출처 필요 문항)",
        f"- 전체 평균 응답시간: **{summary['mean_response_seconds']}초**",
        f"- 전체 P95 응답시간: **{summary['p95_response_seconds']}초**",
        f"- 외부 API 오류 시 안전 응답률: **{summary['external_api_safe_response_percent']}%** "
        f"({summary['external_api_scenario_count']}개 시나리오)",
        "",
        "## 질문 유형별 결과",
        "",
        "| 유형 | 문항 수 | 답변 정확도 | 출처 일치율 | 평균(초) | P95(초) |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for category, item in summary["by_category"].items():
        source_display = (
            f"{item['source_match_percent']}%"
            if item["source_match_percent"] is not None
            else "해당 없음"
        )
        lines.append(
            f"| {category} | {item['count']} | {item['answer_accuracy_percent']}% | "
            f"{source_display} | {item['mean_seconds']} | {item['p95_seconds']} |"
        )
    failed = [row for row in rows if not row.get("answer_pass") or not row.get("source_pass") or row.get("error")]
    lines.extend(["", "## 미통과 문항", ""])
    if failed:
        for row in failed:
            causes = []
            if row.get("error"):
                causes.append(f"실행 오류: {row['error']}")
            else:
                if not row.get("tool_pass"):
                    causes.append("도구 선택")
                if not row.get("product_pass"):
                    causes.append("상품 식별")
                if not row.get("required_terms_pass"):
                    causes.append("필수 내용")
                if not row.get("forbidden_terms_pass"):
                    causes.append("금지 표현")
                if not row.get("source_pass"):
                    causes.append("출처")
            lines.append(f"- {row['id']} ({row['category']}): {', '.join(causes)}")
    else:
        lines.append("- 없음")
    lines.extend(["", "## 외부 API 오류 시나리오", ""])
    for row in safety_rows:
        lines.append(f"- {'통과' if row['safe'] else '실패'} · {row['scenario']}")
    lines.extend([
        "",
        "## 판정 기준",
        "",
        "- 답변 정확도: 예상 도구, 대상 상품, 필수 사실, 금지 표현을 모두 만족한 문항 비율",
        "- 출처 일치율: 도구별 공식 출처 도메인 또는 상품 DB의 등록 출처와 일치한 문항 비율",
        "- P95: 전체 응답시간을 오름차순으로 정렬한 뒤 95% 지점의 nearest-rank 값",
        "- 장애 안전성: 외부 오류 세부정보와 근거 없는 결과를 노출하지 않고 실패를 명확히 안내한 비율",
        "",
    ])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError(".env에서 OPENAI_API_KEY를 찾지 못했습니다.")

    cases = json.loads(DATASET.read_text(encoding="utf-8"))
    if args.limit:
        cases = cases[: args.limit]
    product_urls = load_product_source_urls()
    rows = []

    with OpenAI(timeout=args.timeout, max_retries=0) as client:
        for index, case in enumerate(cases, start=1):
            print(f"[{index:02d}/{len(cases):02d}] {case['id']} {case['question']}", flush=True)
            started = time.perf_counter()
            try:
                result = consult(
                    case["question"],
                    "입문",
                    client,
                    conversation_history=case.get("conversation_history"),
                )
                rows.append(
                    evaluate_case(
                        case,
                        result,
                        time.perf_counter() - started,
                        product_urls,
                    )
                )
            except Exception as error:
                rows.append({
                    "id": case["id"],
                    "category": case["category"],
                    "question": case["question"],
                    "answer_pass": False,
                    "source_pass": False,
                    "elapsed_seconds": round(time.perf_counter() - started, 4),
                    "error": f"{type(error).__name__}: {error}",
                })

    safety_rows = evaluate_external_error_safety()
    summary = summarize(rows, safety_rows)
    generated_at = datetime.now().astimezone().isoformat(timespec="seconds")
    report = {
        "generated_at": generated_at,
        "dataset": str(DATASET.relative_to(ROOT)),
        "summary": summary,
        "cases": rows,
        "external_api_error_scenarios": safety_rows,
    }

    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_path = RESULT_DIR / f"integrated_service_{timestamp}.json"
    result_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    LATEST_SUMMARY.write_text(
        markdown_report(generated_at, summary, rows, safety_rows),
        encoding="utf-8",
    )

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"JSON: {result_path}")
    print(f"요약: {LATEST_SUMMARY}")


if __name__ == "__main__":
    main()
