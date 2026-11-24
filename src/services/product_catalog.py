import re

from psycopg.rows import dict_row
from rank_bm25 import BM25Okapi

from src.db.postgres import get_database_connection


# 기존 편집 거리 검색 기준값
FUZZY_AUTO_MIN = 0.75
FUZZY_SUGGEST_MIN = 0.6
FUZZY_MARGIN = 0.15

PARTIAL_NAME_SCORE = 0.8
PARTIAL_NAME_MIN_LENGTH = 4
MAX_SUGGESTIONS = 3

# 상품명 뒤에 붙어도 같은 상품으로 보는 표현
ALLOWED_NAME_SUFFIXES = ("", "ETF")

# 편집 거리와 BM25를 결합하는 하이브리드 검색 설정
EDIT_DISTANCE_WEIGHT = 0.55
BM25_WEIGHT = 0.45
CHAR_NGRAM_SIZE = 2
# BM25 점수가 높아도 최소한의 편집 거리 유사도는 충족해야 합니다.
FUZZY_EDIT_GATE = 0.6

# 편집 거리 유사도가 매우 높으면 2위와의 점수 차이가 작아도 오타로 인정합니다.
HIGH_CONFIDENCE_EDIT_MIN = 0.9

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
    """삽입·삭제·교체·인접 글자 순서 변경을 반영한 편집 거리입니다."""

    rows = len(left) + 1
    cols = len(right) + 1
    table = [[0] * cols for _ in range(rows)]

    for row in range(rows):
        table[row][0] = row

    for column in range(cols):
        table[0][column] = column

    for row in range(1, rows):
        for column in range(1, cols):
            cost = (
                0
                if left[row - 1] == right[column - 1]
                else 1
            )

            table[row][column] = min(
                table[row - 1][column] + 1,
                table[row][column - 1] + 1,
                table[row - 1][column - 1] + cost,
            )

            if (
                row > 1
                and column > 1
                and left[row - 1] == right[column - 2]
                and left[row - 2] == right[column - 1]
            ):
                table[row][column] = min(
                    table[row][column],
                    table[row - 2][column - 2] + 1,
                )

    return table[-1][-1]


def _similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0

    return (
        1
        - _edit_distance(left, right)
        / max(len(left), len(right))
    )


def _korean_brand_key(normalized_name: str) -> str:
    """KODEX200을 코덱스200 형태로 변환해 한글 브랜드 오타도 비교합니다."""

    for korean_name, english_name in BRAND_ALIASES.items():
        if normalized_name.startswith(english_name):
            return (
                korean_name
                + normalized_name[len(english_name):]
            )

    return normalized_name


def _character_ngrams(
    text: str,
    size: int = CHAR_NGRAM_SIZE,
) -> list[str]:
    """짧은 상품명 검색을 위해 문자열을 2글자 단위로 나눕니다."""

    compact = "".join(
        character
        for character in str(text or "").upper()
        if character.isalnum()
    )

    if not compact:
        return []

    if len(compact) <= size:
        return [compact]

    return [
        compact[index:index + size]
        for index in range(len(compact) - size + 1)
    ]


def _product_name_tokens(normalized_name: str) -> list[str]:
    """영문·한글 브랜드 표현을 모두 BM25 검색 문서에 포함합니다."""

    variants = {
        normalized_name,
        _korean_brand_key(normalized_name),
    }

    tokens = []

    for variant in variants:
        tokens.extend(
            _character_ngrams(variant)
        )

    return tokens


def _bm25_scores(
    normalized_query: str,
    normalized_names: list[str],
) -> list[float]:
    """질문과 상품명의 BM25 점수를 0~1 범위로 정규화합니다."""

    if not normalized_names:
        return []

    corpus = [
        _product_name_tokens(product_name)
        for product_name in normalized_names
    ]

    query_tokens = _character_ngrams(
        normalized_query
    )

    if not query_tokens or not any(corpus):
        return [0.0] * len(normalized_names)

    model = BM25Okapi(corpus)
    raw_scores = model.get_scores(query_tokens)

    highest_score = max(
        raw_scores,
        default=0.0,
    )

    if highest_score <= 0:
        return [0.0] * len(normalized_names)

    return [
        max(0.0, float(score / highest_score))
        for score in raw_scores
    ]


def _numbers(text: str) -> list:
    return re.findall(r"\d+", text)


def _is_in_order(short: str, long: str) -> bool:
    """short의 글자가 long에 같은 순서로 들어 있는지 확인합니다."""

    remaining = iter(long)

    return all(
        character in remaining
        for character in short
    )


def _name_similarity(
    normalized_query: str,
    normalized_name: str,
) -> float:
    similarity = max(
        _similarity(
            normalized_query,
            normalized_name,
        ),
        _similarity(
            normalized_query,
            _korean_brand_key(normalized_name),
        ),
    )

    if (
        len(normalized_query)
        >= PARTIAL_NAME_MIN_LENGTH
        and _is_in_order(
            normalized_query,
            normalized_name,
        )
    ):
        similarity = max(
            similarity,
            PARTIAL_NAME_SCORE,
        )

    return similarity


def _fuzzy_match(
    original_term,
    normalized_query,
    products,
):
    """
    정확히 일치하는 상품이 없으면 편집 거리와 BM25를 결합해 검색합니다.

    종목코드만 입력한 경우에는 다른 종목으로 자동 보정하지 않습니다.
    숫자가 다른 상품도 자동 확정하지 않고 사용자에게 확인합니다.
    """

    if normalized_query.isdigit():
        return None

    normalized_names = [
        normalize_product_key(
            product.get("product_name") or ""
        )
        for product in products
    ]

    bm25_scores = _bm25_scores(
        normalized_query,
        normalized_names,
    )

    scored = []

    for product, normalized_name, bm25_score in zip(
        products,
        normalized_names,
        bm25_scores,
    ):
        edit_score = _name_similarity(
            normalized_query,
            normalized_name,
        )

        weighted_score = (
            EDIT_DISTANCE_WEIGHT * edit_score
            + BM25_WEIGHT * bm25_score
        )

        # 기존 검색보다 성능이 떨어지지 않도록 편집 거리 점수도 유지합니다.
        hybrid_score = max(
            edit_score,
            weighted_score,
        )

        scored.append(
            (
                hybrid_score,
                edit_score,
                bm25_score,
                normalized_name,
                product,
            )
        )

    if not scored:
        return None

    scored.sort(
        key=lambda item: (
            -item[0],
            item[4]["product_name"],
        )
    )

    (
        best_score,
        best_edit_score,
        best_bm25_score,
        best_name,
        best_product,
    ) = scored[0]

    second_score = (
        scored[1][0]
        if len(scored) > 1
        else 0.0
    )

    if (
        best_score < FUZZY_SUGGEST_MIN
        or best_edit_score < FUZZY_EDIT_GATE
    ):
        return None

    same_numbers = (
        _numbers(normalized_query)
        == _numbers(best_name)
    )

    if (
        best_score >= FUZZY_AUTO_MIN
        and (
            best_score - second_score >= FUZZY_MARGIN
            or best_edit_score >= HIGH_CONFIDENCE_EDIT_MIN
        )
        and same_numbers   
    ):
        product = _candidate(best_product)

        return {
            "success": True,
            "match_type": "typo_corrected",
            "search_method": "hybrid_bm25_edit_distance",
            "message": (
                f"'{original_term}'을(를) "
                f"'{product['product_name']}'(으)로 해석했습니다."
            ),
            "query": original_term,
            "normalized_query": normalized_query,
            "similarity": round(best_score, 3),
            "score_details": {
                "edit_distance": round(
                    best_edit_score,
                    3,
                ),
                "bm25": round(
                    best_bm25_score,
                    3,
                ),
                "hybrid": round(
                    best_score,
                    3,
                ),
            },
            "product": product,
        }

    candidate_threshold = max(
        FUZZY_SUGGEST_MIN,
        best_score - FUZZY_MARGIN,
    )

    suggestions = [
        _candidate(product)
        for (
            hybrid_score,
            edit_score,
            _,
            _,
            product,
        ) in scored
        if (
            hybrid_score >= candidate_threshold
            and edit_score >= FUZZY_EDIT_GATE
        )
    ][:MAX_SUGGESTIONS]

    return {
        "success": False,
        "error_type": "ambiguous_product",
        "search_method": "hybrid_bm25_edit_distance",
        "message": (
            f"'{original_term}'과(와) 정확히 일치하는 ETF는 없지만 "
            "비슷한 상품이 있습니다. 어떤 상품인지 확인해 주세요."
        ),
        "query": original_term,
        "normalized_query": normalized_query,
        "score_details": {
            "edit_distance": round(
                best_edit_score,
                3,
            ),
            "bm25": round(
                best_bm25_score,
                3,
            ),
            "hybrid": round(
                best_score,
                3,
            ),
        },
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
    """

    original_term = str(
        search_term or ""
    ).strip()

    if not original_term:
        return {
            "success": False,
            "error_type": "invalid_query",
            "message": (
                "ETF 상품명 또는 종목코드를 입력해 주세요."
            ),
            "query": original_term,
            "candidates": [],
        }

    normalized_query = normalize_product_key(
        original_term
    )

    if not normalized_query:
        return {
            "success": False,
            "error_type": "invalid_query",
            "message": (
                "ETF 상품명을 확인할 수 없습니다."
            ),
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

    return match_products(
        original_term,
        products,
    )


def match_products(
    search_term: str,
    products: list,
) -> dict:
    """
    상품 목록에서 입력값과 일치하는 상품을 찾습니다.

    검색 순서:
    1. 종목코드·정식 상품명 정확히 일치
    2. 상품명 포함 관계
    3. 편집 거리와 BM25 하이브리드 검색
    """

    original_term = str(
        search_term or ""
    ).strip()

    normalized_query = normalize_product_key(
        original_term
    )

    if not normalized_query:
        return {
            "success": False,
            "error_type": "invalid_query",
            "message": (
                "ETF 상품명을 확인할 수 없습니다."
            ),
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
            and normalized_query.split(
                normalized_name,
                1,
            )[1] in ALLOWED_NAME_SUFFIXES
        ):
            score = 80

        elif (
            normalized_query
            and normalized_query in normalized_name
        ):
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
        "search_method": "exact",
        "message": "ETF 상품을 확인했습니다.",
        "query": original_term,
        "normalized_query": normalized_query,
        "product": resolved_product,
    }