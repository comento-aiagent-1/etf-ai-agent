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
NATURAL_CLUE_MIN_SCORE = 0.72
NATURAL_CLUE_MARGIN = 0.08
STRUCTURED_CLUE_MIN_SCORE = 0.45
STRUCTURED_CLUE_MARGIN = 0.1

BRAND_ALIASES = {
    "코덱스": "KODEX",
    "타이거": "TIGER",
    "에이스": "ACE",
    "라이즈": "RISE",
    "쏠": "SOL",
    "하나로": "HANARO",
}
THEME_ALIASES = {
    "K팝": "KPOP",
    "케이팝": "KPOP",
    "중형주": "미드캡",
    "중소형주": "미드캡",
    "닛케이": "NIKKEI",
    "니케이": "NIKKEI",
}


def _manager_aliases(asset_manager: str) -> tuple:
    """자연어에 자주 쓰는 운용사 축약형을 안전한 길이로 만듭니다."""
    manager = str(asset_manager or "").strip()
    aliases = {manager}
    for suffix in ("자산운용", "투자신탁운용", "운용"):
        if manager.endswith(suffix):
            core = manager[:-len(suffix)].strip()
            # '삼성'처럼 너무 짧은 단어 하나만으로 상품을 좁히지 않습니다.
            if len(core) >= 4:
                aliases.add(core)
    return tuple(alias for alias in aliases if alias)


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


def _is_single_digit_number_typo(query_name: str, product_name: str) -> bool:
    """같은 상품명에서 숫자 한 자리가 추가·누락된 경우만 안전한 오타로 봅니다."""
    query_numbers = _numbers(query_name)
    product_numbers = _numbers(product_name)
    if len(query_numbers) != 1 or len(product_numbers) != 1:
        return False

    query_number = query_numbers[0]
    product_number = product_numbers[0]
    if (
        abs(len(query_number) - len(product_number)) != 1
        or _edit_distance(query_number, product_number) != 1
    ):
        return False

    # 브랜드·상품명 문자는 같고 숫자 한 자리만 추가 또는 누락된 경우로 제한합니다.
    return (
        re.sub(r"\d+", "", query_name)
        == re.sub(r"\d+", "", product_name)
    )


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
    - 숫자 한 자리의 단순 추가·누락은 명확한 후보가 하나일 때만 교정합니다.
    - 숫자 치환(예: KODEX 300)은 다른 상품일 수 있어 교정하지 않습니다.
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

    same_numbers = _numbers(normalized_query) == _numbers(best_name)
    single_digit_number_typo = _is_single_digit_number_typo(
        normalized_query,
        best_name,
    )
    if (
        best_similarity >= FUZZY_AUTO_MIN
        and best_similarity - second_similarity >= FUZZY_MARGIN
        and (same_numbers or single_digit_number_typo)
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

    suggestion_pool = scored
    query_numbers = _numbers(normalized_query)
    same_number_pool = [
        item
        for item in scored
        if query_numbers and _numbers(item[1]) == query_numbers
    ]
    # 같은 숫자를 가진 후보가 있으면 숫자가 다른 실제 상품은 제외합니다.
    # 예: TIGER S&P500 질문에 TIGER 200을 함께 제시하지 않습니다.
    if same_number_pool:
        suggestion_pool = same_number_pool
    elif query_numbers:
        # 숫자가 다른 실제 상품을 오타라고 제시하지 않습니다.
        # KODEX 300을 KODEX 200으로 바꾸는 식의 금융상품 오인 방지입니다.
        return None

    suggestions = [
        _candidate(product)
        for similarity, _, product in suggestion_pool
        if similarity >= max(FUZZY_SUGGEST_MIN, best_similarity - FUZZY_MARGIN)
    ][:MAX_SUGGESTIONS]

    if not suggestions:
        return None

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


def _natural_clue_match(original_term, products):
    """운용사와 숫자를 섞어 말한 회상형 질문에서 확인용 후보를 찾습니다.

    한 가지 단서만으로는 후보를 만들지 않으며, 결과는 항상 사용자 확인을
    요구합니다. 따라서 유사 상품을 실제 상품으로 자동 확정하지 않습니다.
    """
    normalized_query = normalize_product_key(original_term)
    query_numbers = _numbers(normalized_query)
    scored = []

    for product in products:
        clue_count = 0
        score = 0.0
        manager_matched = any(
            normalize_product_key(alias) in normalized_query
            for alias in _manager_aliases(product.get("asset_manager"))
        )
        if manager_matched:
            clue_count += 1
            score += 0.6

        product_name = normalize_product_key(product.get("product_name") or "")
        product_numbers = _numbers(product_name)
        number_score = 0.0
        if query_numbers and product_numbers:
            number_score = max(
                0.9 if query_number.startswith(product_number) or product_number.startswith(query_number)
                else _similarity(query_number, product_number)
                for query_number in query_numbers
                for product_number in product_numbers
            )
            if number_score >= 0.5:
                clue_count += 1
                score += 0.4 * number_score

        if clue_count >= 2 and score >= NATURAL_CLUE_MIN_SCORE:
            scored.append((score, product))

    if not scored:
        return None

    scored.sort(key=lambda item: (-item[0], item[1]["product_name"]))
    best_score = scored[0][0]
    candidates = [
        _candidate(product)
        for score, product in scored
        if score >= best_score - NATURAL_CLUE_MARGIN
    ][:MAX_SUGGESTIONS]

    return {
        "success": False,
        "error_type": "ambiguous_product",
        "message": (
            "말씀하신 운용사와 상품 단서에 가까운 ETF를 찾았습니다. "
            "자동으로 확정하지 않고 상품을 확인합니다."
        ),
        "query": original_term,
        "normalized_query": normalized_query,
        "candidates": candidates,
    }


def _structured_clue_match(product_clues, products):
    """LLM이 추출한 서로 다른 단서를 조합해 DB 후보를 찾습니다."""
    clues = {
        key: str((product_clues or {}).get(key) or "").strip()
        for key in (
            "asset_manager", "brand", "number_hint",
            "index_hint", "market_or_theme",
        )
    }
    scored = []
    useful_theme_tokens = {
        "금", "미국", "인도", "중국", "일본", "배당", "반도체",
        "기술주", "주식", "채권", "원유",
    }

    for product in products:
        score = 0.0
        matched_clues = 0
        name_key = normalize_product_key(product.get("product_name") or "")
        manager_key = normalize_product_key(product.get("asset_manager") or "")
        index_key = normalize_product_key(product.get("underlying_index") or "")
        category_key = normalize_product_key(product.get("asset_category") or "")
        searchable = "".join((name_key, index_key, category_key))

        manager_hint = normalize_product_key(clues["asset_manager"])
        if manager_hint:
            if manager_hint in manager_key or manager_key in manager_hint:
                score += 0.3
                matched_clues += 1
            elif name_key.startswith(manager_hint):
                # LLM이 ACE 같은 ETF 브랜드를 운용사 칸에 넣어도 브랜드 단서로 사용합니다.
                score += 0.25
                matched_clues += 1

        brand_hint = normalize_product_key(clues["brand"])
        if brand_hint and name_key.startswith(brand_hint):
            score += 0.25
            matched_clues += 1

        number_hints = _numbers(clues["number_hint"])
        code = str(product.get("product_code") or "").upper()
        name_numbers = _numbers(name_key)
        if number_hints:
            code_match = any(code.startswith(number) for number in number_hints)
            name_match = any(
                number == product_number
                or number.startswith(product_number)
                or product_number.startswith(number)
                for number in number_hints
                for product_number in name_numbers
            )
            if code_match:
                score += 0.45
                matched_clues += 1
            elif name_match:
                score += 0.35
                matched_clues += 1

        index_text = clues["index_hint"]
        for source, target in THEME_ALIASES.items():
            index_text = index_text.replace(source, target)
        index_hint = normalize_product_key(index_text)
        if index_hint and (
            index_hint in searchable or any(
                token and token in searchable
                for token in re.findall(r"[가-힣A-Z]+|\d+", index_hint)
                if len(token) >= 2
            )
        ):
            score += 0.25
            matched_clues += 1

        theme_text = clues["market_or_theme"]
        for source, target in THEME_ALIASES.items():
            theme_text = theme_text.replace(source, target)
        theme_tokens = [
            token
            for token in re.findall(
                r"[가-힣]+|[A-Za-z]+|\d+",
                theme_text,
            )
            if len(token) >= 2 or token in useful_theme_tokens
        ]
        if theme_tokens and any(
            normalize_product_key(token) in searchable
            for token in theme_tokens
        ):
            score += 0.2
            matched_clues += 1

        if matched_clues >= 2 and score >= STRUCTURED_CLUE_MIN_SCORE:
            scored.append((score, product))

    if not scored:
        return None

    scored.sort(key=lambda item: (-item[0], item[1]["product_name"]))
    best_score = scored[0][0]
    candidates = [
        _candidate(product)
        for score, product in scored
        if score >= best_score - STRUCTURED_CLUE_MARGIN
    ][:MAX_SUGGESTIONS]
    return {
        "success": False,
        "error_type": "ambiguous_product",
        "message": "질문의 여러 단서와 일치하는 실제 ETF 후보를 찾았습니다.",
        "query": "structured_clues",
        "candidates": candidates,
    }


def resolve_etf_product(search_term: str, product_clues=None) -> dict:
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
                asset_manager,
                asset_category,
                underlying_index
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

    result = match_products(original_term, products)
    if result.get("success") or not product_clues:
        return result

    structured_result = _structured_clue_match(product_clues, products)
    if structured_result is not None:
        return structured_result

    clue_text = " ".join(
        str(product_clues.get(key) or "").strip()
        for key in (
            "asset_manager", "brand", "number_hint",
            "index_hint", "market_or_theme",
        )
        if str(product_clues.get(key) or "").strip()
    )
    clue_result = _natural_clue_match(clue_text, products) if clue_text else None
    return clue_result or result


def match_products(search_term: str, products: list) -> dict:
    """
    DB 없이 상품 목록만으로 상품명을 확정합니다. (테스트·평가에서도 사용)

    1) 종목코드·정식 상품명 정확히 일치
    2) 상품명 포함 관계
    3) 위에서 못 찾으면 오타 후보 검색
    """
    original_term = str(search_term or "").strip()
    normalized_query = normalize_product_key(original_term)
    # '200 ETF', 'ETF 200'처럼 검색 의미가 없는 일반 단어는 제거합니다.
    if normalized_query.startswith("ETF") and len(normalized_query) > 3:
        normalized_query = normalized_query[3:]
    if normalized_query.endswith("ETF") and len(normalized_query) > 3:
        normalized_query = normalized_query[:-3]

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

        clue_result = _natural_clue_match(original_term, products)
        if clue_result is not None:
            return clue_result

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
        "match_type": "partial_match" if best_score == 70 else "exact",
        "message": "ETF 상품을 확인했습니다.",
        "query": original_term,
        "normalized_query": normalized_query,
        "product": resolved_product,
    }
