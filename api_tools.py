import json

from langchain_core.tools import tool

from dart_api import find_etf_disclosure_titles
from etf_api import get_latest_etf
from result_validator import (
    validate_disclosure_result,
    validate_etf_data,
)
from src.services.product_catalog import (
    resolve_etf_product,
)


def _resolution_error(resolution):
    return json.dumps(
        {
            "success": False,
            "message": resolution.get(
                "message",
                "ETF 상품을 확인하지 못했습니다.",
            ),
            "query": resolution.get("query"),
            "candidates": resolution.get(
                "candidates",
                [],
            ),
        },
        ensure_ascii=False,
    )


@tool
def get_etf_price(etf_name: str) -> str:
    """
    특정 ETF의 최근 자료 기준일 종가와 NAV를 조회한다.

    상품 DB에서 정식 상품명과 종목코드를 확정한 뒤
    금융위원회 공공데이터 API를 호출한다.

    반환하는 가격은 실시간 가격이 아니다.
    """

    search_term = str(
        etf_name or ""
    ).strip()

    if not search_term:
        return json.dumps(
            {
                "success": False,
                "message": "조회할 ETF 상품명이 없습니다.",
            },
            ensure_ascii=False,
        )

    resolution = resolve_etf_product(
        search_term
    )

    if not resolution.get("success"):
        return _resolution_error(resolution)

    product = resolution["product"]

    canonical_name = product["product_name"]
    product_code = product["product_code"]

    try:
        data = get_latest_etf(
            canonical_name,
            product_code,
        )

    except RuntimeError as error:
        return json.dumps(
            {
                "success": False,
                "message": str(error),
                "resolved_product": product,
            },
            ensure_ascii=False,
        )

    if data is None:
        return json.dumps(
            {
                "success": False,
                "message": (
                    f"'{canonical_name}'의 시세 자료를 "
                    "공공데이터 API에서 찾지 못했습니다."
                ),
                "resolved_product": product,
            },
            ensure_ascii=False,
        )

    valid, reason = validate_etf_data(
        data,
        canonical_name,
    )

    if not valid:
        return json.dumps(
            {
                "success": False,
                "message": (
                    f"ETF 시세 검증 실패: {reason}"
                ),
                "resolved_product": product,
            },
            ensure_ascii=False,
        )

    return json.dumps(
        {
            "success": True,
            "requested_term": search_term,
            "resolved_product": product,
            "data": {
                "product_name": data.get("name"),
                "product_code": data.get("code"),
                "data_date": data.get("date"),
                "close_price": data.get("close"),
                "nav": data.get("nav"),
                "real_time": False,
                "source_name": data.get("source"),
                "source_url": data.get(
                    "source_url"
                ),
            },
        },
        ensure_ascii=False,
    )


@tool
def search_etf_disclosure(etf_name: str) -> str:
    """
    특정 ETF와 관련된 DART 공시 제목과 원문 링크를 조회한다.

    PostgreSQL 상품 DB에서 정식 상품명과 운용사를 확정한 뒤
    해당 운용사의 DART 회사 고유번호로 공시를 검색한다.

    공시 제목만으로 구체적인 변경 내용을 추측하지 않는다.
    """

    search_term = str(
        etf_name or ""
    ).strip()

    if not search_term:
        return json.dumps(
            {
                "success": False,
                "message": "조회할 ETF 상품명이 없습니다.",
            },
            ensure_ascii=False,
        )

    resolution = resolve_etf_product(
        search_term
    )

    if not resolution.get("success"):
        return _resolution_error(resolution)

    product = resolution["product"]

    canonical_name = product["product_name"]
    asset_manager = product.get(
        "asset_manager"
    )

    if not asset_manager:
        return json.dumps(
            {
                "success": False,
                "message": (
                    f"'{canonical_name}'의 운용사 정보가 "
                    "상품 DB에 없습니다."
                ),
                "resolved_product": product,
            },
            ensure_ascii=False,
        )

    try:
        result = find_etf_disclosure_titles(
            canonical_name,
            asset_manager,
        )

    except (ValueError, RuntimeError) as error:
        return json.dumps(
            {
                "success": False,
                "message": str(error),
                "resolved_product": product,
            },
            ensure_ascii=False,
        )

    valid, reason = validate_disclosure_result(
        result,
        canonical_name,
    )

    if not valid:
        return json.dumps(
            {
                "success": False,
                "message": (
                    f"DART 공시 검증 실패: {reason}"
                ),
                "resolved_product": product,
            },
            ensure_ascii=False,
        )

    result_status = result.get(
        "result_status"
    )

    return json.dumps(
        {
            "success": True,
            "requested_term": search_term,
            "resolved_product": product,
            "result_found": bool(
                result.get("matches")
            ),
            "result_status": result_status,
            "message": result.get(
                "result_message"
            ),
            "search_complete": result.get(
                "search_complete"
            ),
            "search_period": {
                "start_date": result.get(
                    "start_date"
                ),
                "end_date": result.get(
                    "end_date"
                ),
            },
            "issuer": {
                "asset_manager": result.get(
                    "asset_manager"
                ),
                "dart_corp_name": result.get(
                    "dart_corp_name"
                ),
            },
            "disclosures": result.get(
                "matches",
                [],
            ),
            "notice": (
                "공시 제목·날짜·원문 링크만 제공합니다. "
                "공시 제목만으로 구체적인 변경 내용을 "
                "추측하지 않습니다."
            ),
            "source_name": "전자공시시스템 DART",
            "source_url": "https://dart.fss.or.kr/",
        },
        ensure_ascii=False,
    )


EXTERNAL_API_TOOLS = [
    get_etf_price,
    search_etf_disclosure,
]