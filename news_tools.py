"""뉴스 에이전트: 챗봇이 쓰는 뉴스 검색 도구와 결과 검증.

기사를 가져오는 부분은 news_api.py에 있습니다.
"""
import json
from datetime import datetime
from urllib.parse import urlparse

from langchain_core.tools import tool

from news_api import SOURCE_NAME as NEWS_SOURCE_NAME
from news_api import SOURCE_URL as NEWS_SOURCE_URL
from news_api import (
    NewsFetchError,
    clean_etf_name,
    find_etf_news,
    register_news_link,
)
from src.services.product_catalog import resolve_etf_product


def _resolution_error(resolution):
    return json.dumps(
        {
            "success": False,
            "error_type": resolution.get(
                "error_type",
                "product_resolution_failed",
            ),
            "message": resolution.get(
                "message",
                "ETF 상품을 확인하지 못했습니다.",
            ),
            "query": resolution.get("query"),
            "candidates": resolution.get("candidates", []),
        },
        ensure_ascii=False,
    )


def valid_iso_date(value):
    try:
        datetime.strptime(str(value), "%Y-%m-%d")
        return True
    except ValueError:
        return False


def validate_news_result(result, expected_name):
    """뉴스 목록의 제목·언론사·날짜·링크를 확인합니다."""
    if not isinstance(result, dict):
        return False, "뉴스 자료 형식 오류"

    if result.get("etf_name") != expected_name:
        return False, "요청한 상품과 뉴스 검색 상품이 다름"

    start_date = result.get("start_date")
    end_date = result.get("end_date")

    if not valid_iso_date(start_date) or not valid_iso_date(end_date):
        return False, "뉴스 검색 기간 오류"

    if start_date > end_date:
        return False, "뉴스 검색 시작일이 종료일보다 늦음"

    articles = result.get("articles")
    if not isinstance(articles, list):
        return False, "뉴스 목록 형식 오류"

    for item in articles:
        if not isinstance(item, dict):
            return False, "뉴스 항목 형식 오류"

        if not str(item.get("title", "")).strip():
            return False, "뉴스 제목 누락"

        if not str(item.get("press", "")).strip():
            return False, "언론사 누락"

        published_at = item.get("published_at")
        if not valid_iso_date(published_at):
            return False, "뉴스 날짜 오류"

        if not start_date <= published_at <= end_date:
            return False, "뉴스 날짜가 검색 기간 밖에 있음"

        link = urlparse(str(item.get("url", "")))
        if link.scheme != "https" or link.hostname != "news.google.com":
            return False, "뉴스 링크 오류"

    return True, "정상"


@tool
def search_etf_news(etf_name: str) -> str:
    """
    특정 ETF 상품과 관련된 최근 뉴스 기사 목록을 조회한다.

    사용자가 ETF의 뉴스, 기사, 최근 소식, 이슈를 질문할 때 사용한다.
    최근 7일(없으면 30일) 기사의 제목·언론사·날짜·링크만 제공하며
    기사 본문은 포함하지 않는다.
    """

    search_term = clean_etf_name(etf_name)

    if not search_term:
        return json.dumps(
            {
                "success": False,
                "error_type": "invalid_query",
                "message": "뉴스를 검색할 ETF 상품명이 없습니다.",
            },
            ensure_ascii=False,
        )

    resolution = resolve_etf_product(search_term)

    if not resolution.get("success"):
        return _resolution_error(resolution)

    product = resolution["product"]
    canonical_name = product["product_name"]

    try:
        result = find_etf_news(canonical_name)

    except NewsFetchError:
        return json.dumps(
            {
                "success": False,
                "message": (
                    "지금은 뉴스 정보를 불러오지 못했습니다. "
                    "잠시 후 다시 시도해 주세요."
                ),
            },
            ensure_ascii=False,
        )

    valid, reason = validate_news_result(
        result,
        canonical_name,
    )

    if not valid:
        return json.dumps(
            {
                "success": False,
                "message": f"뉴스 검증 실패: {reason}",
            },
            ensure_ascii=False,
        )

    if not result["articles"]:
        return json.dumps(
            {
                "success": False,
                "message": (
                    f"최근 30일 동안 '{canonical_name}' 관련 뉴스를 "
                    "찾지 못했습니다. 상품명을 정확히 입력했는지 "
                    "확인해 주세요."
                ),
            },
            ensure_ascii=False,
        )

    # 검증이 끝난 진짜 링크는 저장해 두고, LLM에는 짧은 표시만 줍니다.
    for article in result["articles"]:
        article["url"] = register_news_link(article["url"])

    return json.dumps(
        {
            "success": True,
            "requested_term": search_term,
            "resolved_product": product,
            "etf_name": result["etf_name"],
            "search_period": {
                "start_date": result["start_date"],
                "end_date": result["end_date"],
            },
            "checked_at": result["checked_at"],
            "articles": result["articles"],
            "notice": (
                "기사 제목·언론사·날짜만 확인한 자료입니다. "
                "title_mentions_etf가 false인 기사는 본문에서만 "
                "상품이 언급된 기사입니다. 자세한 내용은 기사 원문에서 "
                "확인해야 합니다."
            ),
            "source_name": NEWS_SOURCE_NAME,
            "source_url": NEWS_SOURCE_URL,
        },
        ensure_ascii=False,
    )


NEWS_TOOLS = [
    search_etf_news,
]
