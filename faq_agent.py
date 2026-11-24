"""FAQ lookup entry point for the team router."""

import json

from agent_tools import search_faq


_NO_RESULTS_MESSAGE = (
    "관련 FAQ 벡터가 없습니다. 임베딩 생성 여부를 확인하거나 질문을 구체적으로 입력해 주세요."
)
_UNAVAILABLE_MESSAGE = "지금은 FAQ를 검색할 수 없습니다. 잠시 후 다시 시도해 주세요."
_SOURCE_FIELDS = ("faq_id", "source_name", "source_url", "source_date", "verified_at")


def run_faq_agent(question: str) -> dict:
    """Look up the original user question and return FAQ rows and source metadata."""
    failure = {"success": False, "message": _UNAVAILABLE_MESSAGE, "results": [], "sources": []}
    if not isinstance(question, str) or not 1 <= len(question.strip()) <= 1000:
        return dict(failure, message="질문을 1~1000자로 입력해 주세요.")

    try:
        payload = json.loads(search_faq.invoke({"user_question": question}))
    except Exception:
        return failure

    if not isinstance(payload, dict):
        return failure

    results = payload.get("results")
    if payload.get("success") is False and results == []:
        if payload.get("message") == _NO_RESULTS_MESSAGE:
            return dict(failure, message="관련 FAQ를 찾지 못했습니다.")
        return failure

    if (
        payload.get("success") is not True
        or not isinstance(results, list)
        or not results
        or not all(isinstance(row, dict) for row in results)
    ):
        return failure

    sources = [
        {field: row[field] for field in _SOURCE_FIELDS if field in row}
        for row in results
        if any(field in row for field in _SOURCE_FIELDS[1:])
    ]
    return {
        "success": True,
        "message": "관련 FAQ를 찾았습니다.",
        "results": results,
        "sources": sources,
    }
