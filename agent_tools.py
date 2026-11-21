import json
import logging
from datetime import date
from decimal import Decimal

from langchain_core.tools import tool
from psycopg.rows import dict_row

from src.db.postgres import get_database_connection
from src.services.diagnostic_logging import log_safe_exception
from src.services.vector_search import search_faq_vectors

logger = logging.getLogger(__name__)


BRAND_ALIASES = {
    "코덱스": "KODEX",
    "타이거": "TIGER",
    "에이스": "ACE",
    "라이즈": "RISE",
    "쏠": "SOL",
    "하나로": "HANARO",
}


def json_value(value):
    """날짜와 Decimal 값을 JSON으로 변환할 수 있게 정리합니다."""

    if isinstance(value, date):
        return value.isoformat()

    if isinstance(value, Decimal):
        return float(value)

    return value


def remove_empty_values(data):
    """
    FAQ 결과 등에서 기존과 동일하게
    비어 있는 값을 제외합니다.
    """

    return {
        key: json_value(value)
        for key, value in data.items()
        if value not in (None, "")
    }


def normalize_product_values(data):
    """
    ETF 상품 DB의 빈 필드를 삭제하지 않고
    '미확인'으로 명시합니다.
    """

    return {
        key: (
            "미확인"
            if value is None
            or (
                isinstance(value, str)
                and not value.strip()
            )
            else json_value(value)
        )
        for key, value in data.items()
    }


def apply_brand_aliases(text):
    """
    사용자가 입력한 한글 ETF 브랜드명을
    DB의 영문 브랜드명으로 변환합니다.
    """

    converted = str(text or "").strip()

    for korean_name, english_name in BRAND_ALIASES.items():
        converted = converted.replace(
            korean_name,
            english_name,
        )

    return converted


def normalize_product_key(text):
    """
    상품명 비교를 위해 영문 대소문자, 공백,
    괄호와 특수문자의 영향을 제거합니다.
    """

    converted = apply_brand_aliases(text).upper()

    return "".join(
        character
        for character in converted
        if character.isalnum()
    )


@tool
def search_etf_product(search_term: str) -> str:
    """
    ETF 상품명, 상품명 일부 또는 종목코드로
    PostgreSQL ETF 상품 DB를 검색한다.

    상품의 운용사, 자산 유형, 기초지수, 총보수,
    위험등급, 상장일, 구성종목과 자료 출처가
    필요할 때 사용한다.

    KODEX200처럼 띄어쓰기가 없는 입력과
    코덱스 200 같은 일부 한글 브랜드 표현을 지원한다.

    실시간 가격이나 종가, NAV 조회에는 사용하지 않는다.
    """

    original_term = str(
        search_term or ""
    ).strip()

    if not original_term:
        return json.dumps(
            {
                "success": False,
                "message": (
                    "검색할 ETF 상품명이나 "
                    "종목코드가 없습니다."
                ),
                "query": original_term,
                "results": [],
            },
            ensure_ascii=False,
        )

    converted_term = apply_brand_aliases(
        original_term
    )

    normalized_term = normalize_product_key(
        original_term
    )

    if not normalized_term:
        return json.dumps(
            {
                "success": False,
                "message": (
                    "검색어에서 ETF 상품명이나 "
                    "종목코드를 확인하지 못했습니다."
                ),
                "query": original_term,
                "results": [],
            },
            ensure_ascii=False,
        )

    product_code_term = (
        converted_term.upper()
    )

    product_name_term = (
        converted_term.upper()
    )

    connection = get_database_connection(
        row_factory=dict_row
    )

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            WITH searchable_products AS (
                SELECT
                    product_code,
                    product_name,
                    asset_manager,
                    asset_category,
                    underlying_index,
                    total_fee_percent,
                    risk_grade,
                    listing_date,
                    top_holdings,
                    holdings_date,
                    source_name,
                    source_url,
                    source_date,
                    verified_at,
                    regexp_replace(
                        upper(product_name),
                        '[^A-Z0-9가-힣]',
                        '',
                        'g'
                    ) AS normalized_name
                FROM etf_products
            )
            SELECT
                product_code,
                product_name,
                asset_manager,
                asset_category,
                underlying_index,
                total_fee_percent,
                risk_grade,
                listing_date,
                top_holdings,
                holdings_date,
                source_name,
                source_url,
                source_date,
                verified_at
            FROM searchable_products
            WHERE
                upper(product_code) = %s
                OR upper(product_name) = %s
                OR normalized_name = %s
                OR normalized_name LIKE %s
            ORDER BY
                CASE
                    WHEN upper(product_code) = %s
                        THEN 1
                    WHEN upper(product_name) = %s
                        THEN 2
                    WHEN normalized_name = %s
                        THEN 3
                    ELSE 4
                END,
                product_name,
                product_code
            LIMIT 5
            """,
            (
                product_code_term,
                product_name_term,
                normalized_term,
                f"%{normalized_term}%",
                product_code_term,
                product_name_term,
                normalized_term,
            ),
        )

        rows = cursor.fetchall()

        results = [
            normalize_product_values(
                dict(row)
            )
            for row in rows
        ]

        if not results:
            return json.dumps(
                {
                    "success": False,
                    "message": (
                        f"'{original_term}'과 일치하는 "
                        "ETF 상품을 DB에서 찾지 못했습니다."
                    ),
                    "query": original_term,
                    "normalized_query": normalized_term,
                    "results": [],
                },
                ensure_ascii=False,
            )

        response = {
            "success": True,
            "message": (
                f"{len(results)}개 상품을 찾았습니다."
            ),
            "query": original_term,
            "normalized_query": normalized_term,
            "results": results,
        }

        if len(results) == 1:
            response["resolved_product"] = {
                "product_code": results[0][
                    "product_code"
                ],
                "product_name": results[0][
                    "product_name"
                ],
            }

        return json.dumps(
            response,
            ensure_ascii=False,
        )

    finally:
        connection.close()


@tool
def search_faq(user_question: str) -> str:
    """
    ETF 기본 개념, 비용, 거래 및 위험 관련 질문을
    FAQ 벡터 유사도로 검색한다.

    실시간 가격이나 종가, NAV 검색에는 사용하지 않는다.
    """

    question = str(
        user_question or ""
    ).strip()

    if not question or len(question) > 1000:
        return json.dumps(
            {
                "success": False,
                "message": (
                    "질문을 1~1000자로 입력해 주세요."
                ),
                "results": [],
            },
            ensure_ascii=False,
        )

    try:
        results = [remove_empty_values(row) for row in search_faq_vectors(question)]
    except Exception as error:
        log_safe_exception(
            logger,
            "FAQ retrieval",
            error,
        )
        return json.dumps({"success": False,
                           "message": "FAQ 벡터 검색을 사용할 수 없습니다. 임베딩 생성, API 키와 DB 설정을 확인해 주세요.",
                           "results": []}, ensure_ascii=False)
    return json.dumps({"success": bool(results),
                       "message": "관련 FAQ를 찾았습니다." if results else "관련 FAQ 벡터가 없습니다. 임베딩 생성 여부를 확인하거나 질문을 구체적으로 입력해 주세요.",
                       "results": results}, ensure_ascii=False)


ETF_AGENT_TOOLS = [
    search_etf_product,
    search_faq,
]