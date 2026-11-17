import json
from datetime import date
from decimal import Decimal

from langchain_core.tools import tool
from psycopg.rows import dict_row

from src.db.postgres import get_database_connection
from src.services.vector_search import search_faq_vectors


def json_value(value):
    """Keep the existing JSON contract: ISO dates and numeric fees."""
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def remove_empty_values(data):
    """조회 결과에서 비어 있는 값을 제외합니다."""

    return {
        key: json_value(value)
        for key, value in data.items()
        if value not in (None, "")
    }


@tool
def search_etf_product(search_term: str) -> str:
    """
    ETF 상품명 또는 6자리 종목코드로 ETF 상품 DB를 검색한다.

    상품의 운용사, 자산 유형, 기초지수, 총보수, 위험등급,
    상장일, 구성종목과 자료 출처가 필요할 때 사용한다.

    실시간 가격이나 종가, NAV 조회에는 사용하지 않는다.
    """

    search_term = search_term.strip()

    if not search_term:
        return json.dumps(
            {
                "success": False,
                "message": "검색할 ETF 상품명이나 종목코드가 없습니다.",
                "results": [],
            },
            ensure_ascii=False,
        )

    connection = get_database_connection(row_factory=dict_row)

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
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
            FROM etf_products
            WHERE
                product_code = %s
                OR product_name = %s
                OR product_name ILIKE %s
            ORDER BY
                CASE
                    WHEN product_code = %s THEN 1
                    WHEN product_name = %s THEN 2
                    ELSE 3
                END,
                product_name, product_code
            LIMIT 5
            """,
            (
                search_term,
                search_term,
                f"%{search_term}%",
                search_term,
                search_term,
            ),
        )

        rows = cursor.fetchall()

        results = [
            remove_empty_values(dict(row))
            for row in rows
        ]

        if not results:
            return json.dumps(
                {
                    "success": False,
                    "message": (
                        f"'{search_term}'과 일치하는 ETF 상품을 "
                        "DB에서 찾지 못했습니다."
                    ),
                    "results": [],
                },
                ensure_ascii=False,
            )

        return json.dumps(
            {
                "success": True,
                "message": f"{len(results)}개 상품을 찾았습니다.",
                "results": results,
            },
            ensure_ascii=False,
        )

    finally:
        connection.close()


@tool
def search_faq(user_question: str) -> str:
    """Search ETF concepts, fees, trading and risks by semantic FAQ similarity.

    Returns source-backed FAQs ranked by cosine match_score, not live prices.
    """
    question = user_question.strip()
    if not question or len(question) > 1000:
        return json.dumps({"success": False, "message": "질문을 1~1000자로 입력해 주세요.",
                           "results": []}, ensure_ascii=False)
    try:
        results = [remove_empty_values(row) for row in search_faq_vectors(question)]
    except Exception:
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
