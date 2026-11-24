import re

from psycopg.rows import dict_row

from src.db.postgres import get_database_connection


# 오타 대응(편집 거리 유사도) 기준값. eval_product_search.py로 정했습니다.
FUZZY_AUTO_MIN = 0.75     # 이 이상이고 2등과 차이가 크면 바로 그 상품으로 연결
FUZZY_SUGGEST_MIN = 0.6   # 이 이상이면 "혹시 이 상품인가요?" 후보로 제시
FUZZY_MARGIN = 0.15       # 1등과 2등 유사도 차이가 이보다 작으면 사용자에게 확인
# '타이거 나스닥'처럼 일부만 썼어도 글자가 상품명에 순서대로 다 들어 있으면 주는 점수
PARTIAL_NAME_SCORE = 0.8
PARTIAL_NAME_MIN_LENGTH = 4
MAX_SUGGESTIONS = 3
# 상품명 뒤에 붙어도 같은 상품으로 보는 말 (예: KODEX 200 ETF)
ALLOWED_NAME_SUFFIXES = ("", "ETF")

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


def _edit_distance(left: str, right: str) -> int:
    """글자 삽입·삭제·바꾸기·인접 글자 뒤바뀜을 1번으로 세는 편집 거리."""
    rows = len(left) + 1
    cols = len(right) + 1
    table = [[0] * cols for _ in range(rows)]

    for i in range(rows):
        table[i][0] = i
    for j in range(cols):
        table[0][j] = j

    for i in range(1, rows):
        for j in range(1, cols):
            cost = 0 if left[i - 1] == right[j - 1] else 1
            table[i][j] = min(
                table[i - 1][j] + 1,
                table[i][j - 1] + 1,
                table[i - 1][j - 1] + cost,
            )
            if (
                i > 1 and j > 1
                and left[i - 1] == right[j - 2]
                and left[i - 2] == right[j - 1]
            ):
                table[i][j] = min(table[i][j], table[i - 2][j - 2] + 1)

    return table[-1][-1]


def _similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    return 1 - _edit_distance(left, right) / max(len(left), len(right))


def _korean_brand_key(normalized_name: str) -> str:
    """'KODEX200' → '코덱스200'. 한글 브랜드명에 오타가 있을 때 비교용."""
    for korean_name, english_name in BRAND_ALIASES.items():
        if normalized_name.startswith(english_name):
            return korean_name + normalized_name[len(english_name):]
    return normalized_name


def _numbers(text: str) -> list:
    return re.findall(r"\d+", text)


def _is_in_order(short: str, long: str) -> bool:
    """short의 글자가 long 안에 순서대로 모두 들어 있는지 확인합니다."""
    remaining = iter(long)
    return all(character in remaining for character in short)


def _name_similarity(normalized_query: str, normalized_name: str) -> float:
    similarity = max(
        _similarity(normalized_query, normalized_name),
        _similarity(normalized_query, _korean_brand_key(normalized_name)),
    )
    if (
        len(normalized_query) >= PARTIAL_NAME_MIN_LENGTH
        and _is_in_order(normalized_query, normalized_name)
    ):
        similarity = max(similarity, PARTIAL_NAME_SCORE)
    return similarity


def _fuzzy_match(original_term, normalized_query, products):
    """
    정확히 일치하는 상품이 없을 때 편집 거리로 오타 후보를 찾습니다.

    - 종목코드(숫자만)는 오타로 추정하지 않습니다. 다른 실제 종목일 수 있습니다.
    - 숫자가 다르면(예: KODEX 300) 다른 상품일 수 있어 바로 연결하지 않고 확인을 요청합니다.
    """
    if normalized_query.isdigit():
        return None

    scored = []
    for product in products:
        normalized_name = normalize_product_key(product.get("product_name") or "")
        similarity = _name_similarity(normalized_query, normalized_name)
        scored.append((similarity, normalized_name, product))

    scored.sort(key=lambda item: (-item[0], item[2]["product_name"]))

    best_similarity, best_name, best_product = scored[0]
    second_similarity = scored[1][0] if len(scored) > 1 else 0.0

    if best_similarity < FUZZY_SUGGEST_MIN:
        return None

    if (
        best_similarity >= FUZZY_AUTO_MIN
        and best_similarity - second_similarity >= FUZZY_MARGIN
        and _numbers(normalized_query) == _numbers(best_name)
    ):
        product = _candidate(best_product)
        return {
            "success": True,
            "match_type": "typo_corrected",
            "message": (
                f"'{original_term}'을(를) "
                f"'{product['product_name']}'(으)로 해석했습니다."
            ),
            "query": original_term,
            "normalized_query": normalized_query,
            "similarity": round(best_similarity, 3),
            "product": product,
        }

    suggestions = [
        _candidate(product)
        for similarity, _, product in scored
        if similarity >= max(FUZZY_SUGGEST_MIN, best_similarity - FUZZY_MARGIN)
    ][:MAX_SUGGESTIONS]

    return {
        "success": False,
        "error_type": "ambiguous_product",
        "message": (
            f"'{original_term}'과(와) 정확히 일치하는 ETF는 없지만 "
            "비슷한 상품이 있습니다. 어떤 상품인지 확인해 주세요."
        ),
        "query": original_term,
        "normalized_query": normalized_query,
        "candidates": suggestions,
    }


def resolve_etf_product(search_term: str) -> dict:
    """
    사용자가 입력한 상품명 또는 종목코드를 DB의 정식 상품으로 변환합니다.

    예:
    - KODEX200
    - 코덱스 200
    - 069500
    → KODEX 200 / 069500

    정확히 일치하는 상품이 없으면 오타 후보를 찾습니다.
    - COXEX200 → KODEX 200으로 연결
    - 비슷한 후보가 여러 개면 사용자에게 확인을 요청
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

    return match_products(original_term, products)


def match_products(search_term: str, products: list) -> dict:
    """
    DB 없이 상품 목록만으로 상품명을 확정합니다. (테스트·평가에서도 사용)

    1) 종목코드·정식 상품명 정확히 일치
    2) 상품명 포함 관계
    3) 위에서 못 찾으면 오타 후보 검색
    """
    original_term = str(search_term or "").strip()
    normalized_query = normalize_product_key(original_term)

    if not normalized_query:
        return {
            "success": False,
            "error_type": "invalid_query",
            "message": "ETF 상품명을 확인할 수 없습니다.",
            "query": original_term,
            "candidates": [],
        }

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

        elif (
            normalized_name
            and normalized_name in normalized_query
            # 'KODEX 200선물인버스2X'처럼 상품명 뒤에 글자가 더 붙으면
            # 다른 상품일 수 있어 같은 상품으로 보지 않습니다.
            and normalized_query.split(normalized_name, 1)[1]
            in ALLOWED_NAME_SUFFIXES
        ):
            score = 80

        elif normalized_query and normalized_query in normalized_name:
            score = 70

        if score > 0:
            scored_products.append(
                (score, product)
            )

    if not scored_products:
        fuzzy_result = _fuzzy_match(
            original_term,
            normalized_query,
            products,
        )
        if fuzzy_result is not None:
            return fuzzy_result

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
        "match_type": "exact",
        "message": "ETF 상품을 확인했습니다.",
        "query": original_term,
        "normalized_query": normalized_query,
        "product": resolved_product,
    }
