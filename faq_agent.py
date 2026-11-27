"""FAQ lookup entry point for the team router."""

import csv
import json
import unicodedata
from pathlib import Path
from urllib.parse import urlsplit

from psycopg.rows import dict_row

from agent_tools import search_faq
from src.db.postgres import get_database_connection


_NO_RESULTS_MESSAGE = (
    "관련 FAQ 벡터가 없습니다. 임베딩 생성 여부를 확인하거나 질문을 구체적으로 입력해 주세요."
)
_UNAVAILABLE_MESSAGE = "지금은 FAQ를 검색할 수 없습니다. 잠시 후 다시 시도해 주세요."
_SEARCH_UNAVAILABLE_MESSAGE = (
    "FAQ 검색 서비스를 사용할 수 없습니다. PostgreSQL 실행 상태와 "
    ".env의 OpenAI·DB 설정을 확인해 주세요."
)
_SOURCE_FIELDS = ("faq_id", "source_name", "source_url", "source_date", "verified_at")
_FAQ_SOURCE_PATH = Path(__file__).resolve().parent / "data" / "source" / "FAQ.csv"


def list_faq_questions():
    """Read the current FAQ directory without invoking the embedding service."""
    with get_database_connection(row_factory=dict_row) as connection:
        connection.execute("SET LOCAL statement_timeout = '2s'")
        return connection.execute("""
            SELECT faq_id, category, question, keywords
            FROM faq
            ORDER BY faq_id
        """).fetchall()


def has_faq_evidence(row):
    answer, url = row.get("answer"), row.get("source_url")
    if not isinstance(answer, str) or not answer.strip() or not isinstance(url, str):
        return False
    try:
        source = urlsplit(url)
        return source.scheme in ("http", "https") and bool(source.hostname)
    except ValueError:
        return False


def _normalize_faq_text(value):
    return "".join(
        character
        for character in unicodedata.normalize("NFKC", value).casefold()
        if character.isalnum()
    )


def find_local_faq(question):
    """Return a high-confidence FAQ match from the bundled CSV, without API calls."""
    if not isinstance(question, str) or not question.strip():
        return None

    normalized_question = _normalize_faq_text(question)
    if not normalized_question:
        return None

    with _FAQ_SOURCE_PATH.open(encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source))

    exact_matches = []
    for row in rows:
        normalized_title = _normalize_faq_text(row.get("question", ""))
        if normalized_question == normalized_title or (
            len(normalized_title) >= 8 and normalized_title in normalized_question
        ):
            if has_faq_evidence(row):
                exact_matches.append(row)

    if len(exact_matches) == 1:
        return exact_matches[0]
    if exact_matches:
        return None

    scores = []
    for row in rows:
        keywords = [
            _normalize_faq_text(keyword)
            for keyword in (row.get("keywords") or "").split(";")
            if any(character.isspace() for character in keyword)
        ]
        matched = {
            keyword
            for keyword in keywords
            if len(keyword) >= 5
            and keyword in normalized_question
        }
        score = sum(len(keyword) for keyword in matched)
        if score and has_faq_evidence(row):
            scores.append((score, row))

    if not scores:
        return None

    best_score = max(score for score, _ in scores)
    best_matches = [row for score, row in scores if score == best_score]
    return best_matches[0] if best_score >= 4 and len(best_matches) == 1 else None


def faq_sources(results):
    return [
        {field: row[field] for field in _SOURCE_FIELDS if field in row}
        for row in results
    ]


def run_faq_agent(question: str) -> dict:
    """Look up the original user question and return FAQ rows and source metadata."""
    failure = {"success": False, "message": _UNAVAILABLE_MESSAGE, "results": [], "sources": []}
    if not isinstance(question, str) or not 1 <= len(question.strip()) <= 1000:
        return dict(failure, message="질문을 1~1000자로 입력해 주세요.")

    local_match = find_local_faq(question)
    if local_match:
        return {
            "success": True,
            "message": "관련 FAQ를 찾았습니다.",
            "results": [local_match],
            "sources": faq_sources([local_match]),
        }

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
        if payload.get("error_code") == "FAQ_SEARCH_UNAVAILABLE":
            return dict(failure, message=_SEARCH_UNAVAILABLE_MESSAGE)
        return failure

    if (
        payload.get("success") is not True
        or not isinstance(results, list)
        or not results
        or not all(isinstance(row, dict) for row in results)
    ):
        return failure

    results = [row for row in results if has_faq_evidence(row)]
    if not results:
        return dict(failure, message="출처가 있는 FAQ 자료를 확인하지 못했습니다. 질문을 조금 더 구체적으로 적어 주세요.")

    return {
        "success": True,
        "message": "관련 FAQ를 찾았습니다.",
        "results": results,
        "sources": faq_sources(results),
    }
