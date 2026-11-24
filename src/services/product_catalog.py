from psycopg.rows import dict_row

from src.db.postgres import get_database_connection


BRAND_ALIASES = {
    "코덱스": "KODEX",
    "타이거": "TIGER",
    "에이스": "ACE",
    "라이즈": "RISE",
    "쏠": "SOL",
    "하나로": "HANARO",
}


def apply_brand_aliases(text: str) -> str:
    converted = str(text or "").strip()

    for korean_name, english_name in BRAND_ALIASES.items():
        converted = converted.replace(
            korean_name,
            english_name,
        )

    return converted


def normalize_product_key(text: str) -> str:
    converted = apply_brand_aliases(text).upper()

    return "".join(
        character
        for character in converted
        if character.isalnum()
    )


def _candidate(product: dict) -> dict:
    return {
        "product_code": product["product_code"],
        "product_name": product["product_name"],
        "asset_manager": product.get("asset_manager"),
    }


def resolve_etf_product(search_term: str) -> dict:
    """
    사용자가 입력한 상품명 또는 종목코드를 DB의 정식 상품으로 변환합니다.

    예:
    - KODEX200
    - 코덱스 200
    - 069500
    → KODEX 200 / 069500
    """

    original_term = str(search_term or "").strip()

    if not original_term:
        return {
            "success": False,
            "error_type": "invalid_query",
            "message": "ETF 상품명 또는 종목코드를 입력해 주세요.",
            "query": original_term,
            "candidates": [],
        }

    normalized_query = normalize_product_key(original_term)

    if not normalized_query:
        return {
            "success": False,
            "error_type": "invalid_query",
            "message": "ETF 상품명을 확인할 수 없습니다.",
            "query": original_term,
            "candidates": [],
        }

    connection = get_database_connection(
        row_factory=dict_row
    )

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                product_code,
                product_name,
                asset_manager
            FROM etf_products
            ORDER BY product_name, product_code
            """
        )

        products = [
            dict(row)
            for row in cursor.fetchall()
        ]

    finally:
        connection.close()

    scored_products = []

    for product in products:
        product_code = str(
            product.get("product_code") or ""
        ).upper()

        normalized_name = normalize_product_key(
            product.get("product_name") or ""
        )

        score = 0

        if normalized_query == product_code:
            score = 100

        elif normalized_query == normalized_name:
            score = 95

        elif normalized_name and normalized_name in normalized_query:
            score = 80

        elif normalized_query and normalized_query in normalized_name:
            score = 70

        if score > 0:
            scored_products.append(
                (score, product)
            )

    if not scored_products:
        return {
            "success": False,
            "error_type": "product_not_found",
            "message": (
                f"'{original_term}'과 일치하는 ETF를 "
                "상품 DB에서 찾지 못했습니다."
            ),
            "query": original_term,
            "normalized_query": normalized_query,
            "candidates": [],
        }

    scored_products.sort(
        key=lambda item: (
            -item[0],
            item[1]["product_name"],
        )
    )

    best_score = scored_products[0][0]

    best_products = [
        product
        for score, product in scored_products
        if score == best_score
    ]

    if len(best_products) > 1:
        return {
            "success": False,
            "error_type": "ambiguous_product",
            "message": (
                "여러 ETF가 검색되었습니다. "
                "정확한 상품명이나 종목코드를 입력해 주세요."
            ),
            "query": original_term,
            "normalized_query": normalized_query,
            "candidates": [
                _candidate(product)
                for product in best_products[:5]
            ],
        }

    resolved_product = _candidate(
        best_products[0]
    )

    return {
        "success": True,
        "message": "ETF 상품을 확인했습니다.",
        "query": original_term,
        "normalized_query": normalized_query,
        "product": resolved_product,
    }
