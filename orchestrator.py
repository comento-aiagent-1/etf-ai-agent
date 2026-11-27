import json
import re

from src.services.conversation_memory import prepare_recent_history


FAST_ROUTE_TERMS = {
    "etf_price": ("종가", "시세", "nav", "순자산가치"),
    "disclosure": ("공시", "dart", "투자설명서", "일괄신고서"),
    "news": ("뉴스", "기사", "최근 소식"),
    "product": (
        "상품정보", "상품 정보", "총보수", "운용사", "기초지수",
        "구성종목", "보유종목", "상장일", "위험등급", "자산유형",
        "종목코드",
    ),
}
FAQ_TERMS = (
    "etf란", "etf가 뭐", "etf 뜻", "etf 개념", "etf 설명", "etf를 설명",
    "분배금", "괴리율",
    "추적오차", "환헤지", "레버리지", "인버스", "매매 수수료",
    "거래 수수료", "세금", "과세", "결제일", "운용 방식",
)
FOLLOW_UP_TERMS = (
    "그 etf", "그 상품", "해당 etf", "해당 상품", "아까",
    "앞에서", "방금", "그럼", "그러면", "그건", "그것", "그거는",
)
EXPLICIT_PRODUCT_REFERENCE_TERMS = (
    "그 etf", "그 상품", "그 종목",
    "해당 etf", "해당 상품", "해당 종목",
    "아까 그", "앞에서 말한", "방금 말한",
    "그건", "그것", "그거는",
)
GENERIC_PRODUCT_NAMES = {
    "etf", "상품", "종목", "국내종목", "해외종목",
    "그etf", "그상품", "그종목", "해당etf", "해당상품", "해당종목",
    "이거", "저거", "이것", "저것",
}
GENERIC_PRODUCT_SCOPE_TERMS = (
    "국내", "해외", "미국", "한국", "글로벌",
    "ETF", "상품", "종목", "펀드",
    "하나", "한개", "한 개", "하나만", "한개만", "한 개만",
    "아무거나", "아무거나하나", "좀",
)
BROAD_PRODUCT_SUFFIXES = (
    "어때", "어떤데", "괜찮아", "괜찮은가요", "괜찮나요",
)
INVESTMENT_ADVICE_TERMS = (
    "사도 돼", "사도 될까", "살까", "구매할까", "구매해도",
    "매수", "매도", "팔까", "팔아도", "투자해도",
    "들어가도", "보유할까", "계속 보유", "지금 사", "언제 사",
    "언제 팔", "손절", "익절", "물타기", "추가 매수", "추매",
    "갈아탈까", "진입할까",
)
PRODUCT_RECOMMENDATION_TERMS = (
    "추천", "골라줘", "골라 줘", "뭐가 좋아", "무엇이 좋아",
    "어떤 종목", "어떤 etf", "제일 좋은", "가장 좋은", "1등 etf",
    "유망한 etf", "유망 종목", "베스트 etf",
)
PRICE_FORECAST_TERMS = (
    "오를까", "올라갈까", "상승할까", "내릴까", "떨어질까",
    "하락할까", "가격 전망", "주가 전망", "목표가", "예측해",
    "얼마 될까", "얼마가 될까", "얼마나 오를", "얼마나 내릴",
    "앞으로 오를", "앞으로 내릴",
)
RETURN_GUARANTEE_TERMS = (
    "수익 보장", "원금 보장", "무조건 벌", "확실히 벌", "돈 벌 수",
    "수익 날까", "손해 안", "몇 퍼 벌", "수익 확실", "안전하게 벌",
)
PERSONALIZED_ALLOCATION_TERMS = (
    "얼마 넣", "몇 퍼 넣", "비중", "몰빵", "전재산", "퇴직금 넣",
    "생활비 넣", "대출받아", "대출 받아", "포트폴리오 짜",
    "나한테 맞", "내 상황에 맞",
)
PRODUCT_NAME_RECALL_TERMS = (
    "상품 이름", "상품이름", "상품명", "정식 이름", "정식이름",
    "이름이 뭐", "이름 뭐", "이름 그 뭐", "뭐였지", "뭐였더라",
    "뭐더라", "정확한 이름",
)


def _find_routes(question):
    lowered = str(question or "").casefold()
    positioned = []
    for route, terms in FAST_ROUTE_TERMS.items():
        positions = [lowered.find(term) for term in terms if lowered.find(term) >= 0]
        if positions:
            positioned.append((min(positions), route))
    return [route for _, route in sorted(positioned)]


def _extract_product_expression(question, routes):
    """명시적인 의도 단어 앞부분에서 사용자가 쓴 상품 표현을 보존합니다."""
    lowered = str(question or "").casefold()
    positions = [
        lowered.find(term)
        for route in routes
        for term in FAST_ROUTE_TERMS[route]
        if lowered.find(term) >= 0
    ]
    if not positions:
        return "none"

    expression = str(question)[:min(positions)].strip(" ,.?·/:-")
    expression = re.sub(r"^(?:혹시|최근|오늘|현재|실시간)\s+", "", expression)
    # 조사와 시간 표현이 연달아 붙은 경우도 모두 제거합니다.
    # 예: "069500의 최근 종가"에서 한 번만 제거하면 "069500의"가 남습니다.
    expression = re.sub(
        r"(?:(?:에\s*대한|관련|의|최근|오늘|현재|실시간|가격과|가격|정보와|정보)\s*)+$",
        "",
        expression,
    ).strip(" ,.?·/:-")
    normalized = re.sub(r"\s+", "", expression).casefold()
    if not expression or normalized in GENERIC_PRODUCT_NAMES:
        return "none"
    return expression


def _extract_product_before_terms(question, terms):
    lowered = str(question or "").casefold()
    positions = [lowered.find(term) for term in terms if lowered.find(term) >= 0]
    if not positions:
        return "none"
    expression = str(question)[:min(positions)].strip(" ,.?·/:-")
    expression = re.sub(
        r"^(?:그러면|그렇다면|그럼|그래서|혹시|그|이|저|그거|이거|저거|아까|전에)\s+",
        "",
        expression,
    )
    expression = re.sub(
        r"(?:은|는|이|가|을|를|지금|당장|오늘|내일|다음주|향후|현재|요즘|최근)\s*$",
        "",
        expression,
    ).strip(" ,.?·/:-")
    normalized = re.sub(r"\s+", "", expression).casefold()
    generic_scope = normalized
    for term in sorted(GENERIC_PRODUCT_SCOPE_TERMS, key=len, reverse=True):
        generic_scope = generic_scope.replace(
            re.sub(r"\s+", "", term).casefold(),
            "",
        )
    if not expression or normalized in GENERIC_PRODUCT_NAMES or normalized in {
        "지금", "당장", "지금당장", "오늘", "내일", "다음주", "향후",
        "현재", "요즘", "최근",
    } or not generic_scope:
        return "none"
    return expression


def _recent_product_name(conversation_history):
    for message in reversed(prepare_recent_history(conversation_history)):
        if message.get("role") != "user":
            continue
        content = message.get("content", "")
        routes = _find_routes(content)
        product_name = _extract_product_expression(content, routes) if routes else "none"
        if product_name != "none":
            return product_name
        broad_match = re.match(
            rf"^(.+?)\s*(?:은|는|이|가)?\s*(?:{'|'.join(BROAD_PRODUCT_SUFFIXES)})[?.!\s]*$",
            content.strip(),
            flags=re.IGNORECASE,
        )
        if broad_match:
            product_name = broad_match.group(1).strip()
            if re.sub(r"\s+", "", product_name).casefold() not in GENERIC_PRODUCT_NAMES:
                return product_name
    return "none"


def fast_route_question(question, *, include_product=False, conversation_history=None):
    """확신할 수 있는 명시적 질문만 규칙으로 분류하고, 나머지는 None을 반환합니다.

    None은 실패가 아니라 기존 LLM 라우터가 문맥을 보고 판단해야 한다는 뜻입니다.
    """
    lowered = str(question or "").strip().casefold()
    if not lowered:
        return None

    # 상품명 회상형 문장은 운용사·브랜드·숫자·테마가 섞일 수 있으므로
    # 일부 표현만 규칙으로 잘라내지 않고 LLM 구조화 라우터에 맡깁니다.
    if any(term in lowered for term in PRODUCT_NAME_RECALL_TERMS):
        if any(
            term in lowered
            for term in ("그거", "그 상품", "그 etf", "아까", "앞에서", "방금")
        ):
            recent_product = _recent_product_name(conversation_history)
            if recent_product != "none":
                return {
                    "routes": ["product"],
                    "etf_name": recent_product,
                    "router_mode": "rule",
                }
        return None

    if (
        any(term in lowered for term in PERSONALIZED_ALLOCATION_TERMS)
        or re.search(r"(?:얼마|몇\s*퍼(?:센트)?).{0,12}(?:넣|투자|배분)", lowered)
    ):
        return {
            "routes": ["personalized_allocation"],
            "etf_name": "none",
            "router_mode": "rule",
        }

    if any(term in lowered for term in RETURN_GUARANTEE_TERMS):
        product_name = _extract_product_before_terms(question, RETURN_GUARANTEE_TERMS)
        if product_name == "none" and any(term in lowered for term in FOLLOW_UP_TERMS):
            product_name = _recent_product_name(conversation_history)
            if (
                product_name == "none"
                and conversation_history
                and any(
                    term in lowered
                    for term in EXPLICIT_PRODUCT_REFERENCE_TERMS
                )
            ):
                # 규칙으로 최근 상품을 복원하지 못했더라도 답변 문맥에는
                # 정식 상품명이 있을 수 있으므로 구조화 LLM 라우터에 맡깁니다.
                return None
        return {
            "routes": ["return_guarantee"],
            "etf_name": product_name,
            "router_mode": "rule",
        }

    # 종목 추천은 이전 상품 질문과 분리합니다. '그 상품 추천해?'처럼
    # 명시적인 지시어가 있을 때만 최근 대화의 상품명을 사용합니다.
    if any(term in lowered for term in PRODUCT_RECOMMENDATION_TERMS):
        product_name = _extract_product_before_terms(
            question,
            PRODUCT_RECOMMENDATION_TERMS,
        )
        if product_name == "none" and any(
            term in lowered
            for term in EXPLICIT_PRODUCT_REFERENCE_TERMS
        ):
            product_name = _recent_product_name(conversation_history)
        return {
            "routes": ["product_recommendation"],
            "etf_name": product_name,
            "router_mode": "rule",
        }

    # 미래 가격과 상승·하락 예측은 매매 판단과 다른 안내 문구를 사용합니다.
    if any(term in lowered for term in PRICE_FORECAST_TERMS):
        product_name = _extract_product_before_terms(question, PRICE_FORECAST_TERMS)
        if product_name == "none":
            product_name = _recent_product_name(conversation_history)
        return {
            "routes": ["price_forecast"],
            "etf_name": product_name,
            "router_mode": "rule",
        }

    # 매수·매도·추천 요청은 다른 의도보다 먼저 잡아 LLM이 투자 판단을
    # 생성하지 못하게 합니다. 상품명은 현재 질문, 없으면 최근 대화에서 찾습니다.
    if any(term in lowered for term in INVESTMENT_ADVICE_TERMS):
        product_name = _extract_product_before_terms(question, INVESTMENT_ADVICE_TERMS)
        if product_name == "none":
            product_name = _recent_product_name(conversation_history)
        return {
            "routes": ["investment_guidance"],
            "etf_name": product_name,
            "router_mode": "rule",
        }

    # 지시어가 있는 꼬리 질문은 최근 대화에서 상품을 찾아야 하므로 LLM에 맡깁니다.
    if any(term in lowered for term in FOLLOW_UP_TERMS):
        return None

    # 상품명은 명확하지만 요청 범위가 넓은 질문은 다시 상품명을 묻지 않고
    # 상품 DB의 기본정보를 요약합니다. 매수·매도 판단은 최종 답변 정책에서 제한합니다.
    if include_product:
        broad_match = re.match(
            rf"^(.+?)\s*(?:은|는|이|가)?\s*(?:{'|'.join(BROAD_PRODUCT_SUFFIXES)})[?.!\s]*$",
            str(question or "").strip(),
            flags=re.IGNORECASE,
        )
        if broad_match:
            product_name = re.sub(
                r"(?:요즘|최근|지금|현재)\s*$",
                "",
                broad_match.group(1).strip(),
            ).strip()
            normalized = re.sub(r"\s+", "", product_name).casefold()
            if product_name and normalized not in GENERIC_PRODUCT_NAMES:
                return {
                    "routes": ["product"],
                    "etf_name": product_name,
                    "router_mode": "rule",
                }

    routes = _find_routes(question)
    has_faq_term = any(term in lowered for term in FAQ_TERMS)

    if has_faq_term:
        looks_like_product_search = (
            bool(re.search(r"\d", lowered))
            or any(term in lowered for term in PRODUCT_NAME_RECALL_TERMS)
            or any(
                term in lowered
                for term in (
                    "운용", "브랜드", "따라가는", "상품 이름", "상품명",
                    "코덱스", "타이거", "에이스", "라이즈", "쏠", "하나로",
                )
            )
        )
        if looks_like_product_search:
            return None
        # 일반 개념과 특정 상품 자료를 함께 묻는 복합 문장은 문장 구조 해석이 필요합니다.
        if routes:
            return None
        return {"routes": ["faq"], "etf_name": "none", "router_mode": "rule"}

    if not routes:
        return None

    if not include_product:
        routes = [route for route in routes if route != "product"]
        if not routes:
            return None

    etf_name = _extract_product_expression(question, routes)
    if etf_name == "none":
        # 상품명이 없거나 의도 단어가 문장 앞에 있는 경우 문맥/어순 해석을 맡깁니다.
        return None

    return {
        "routes": list(dict.fromkeys(routes)),
        "etf_name": etf_name,
        "router_mode": "rule",
    }


def route_question(
    question,
    client,
    *,
    include_product=False,
    conversation_history=None,
):
    allowed_routes = [
        "etf_price", "disclosure", "news", "faq", "clarify",
        "investment_guidance", "product_recommendation", "price_forecast",
        "return_guarantee", "personalized_allocation",
    ]
    product_instructions = ""
    name_schema = {"type": "string"}
    if include_product:
        allowed_routes += ["product", "comparison_unsupported", "return_unsupported"]
        product_instructions = (
            "특정 ETF 한 종목의 총보수, 추종지수, 운용사 또는 구성 정보를 묻는 경우 product를 선택하고, "
            "질문에 있는 상품명 또는 종목코드를 etf_name에 넣는다. "
            "상품을 임의로 정하지 말고 정보가 부족하면 clarify를 선택한다. "
            "여러 종목 비교나 조건에 맞는 ETF 목록 검색은 comparison_unsupported를 선택한다. "
            "'KODEX 200 어때?'처럼 상품명은 명확하지만 질문 범위가 넓으면 "
            "clarify 대신 product를 선택한다. "
            "일반 개념도 함께 묻는 경우 faq를 추가한다. "
            "상품정보와 시세 또는 공시를 함께 묻는 경우 필요한 경로를 모두 선택한다. "
            "ETF 상품이 특정되었는지와 무관하게 상품의 실제 또는 예상 수익률 수치를 요구하면 return_unsupported를 선택한다. "
            "수익률의 의미나 투자 위험 같은 일반 교육 질문만 faq로 분류한다. "
            "예: 'ETF 사면 매년 어떤 돈이 빠져나가요?', 'ETF 투자하면 원금을 날릴 수도 있나요?'는 faq다. "
            "'KODEX ETF의 총보수'처럼 운용 브랜드만 있으면 상품명 또는 코드를 묻도록 clarify를 선택한다. "
            "시세·공시는 위 두 상품의 정식 이름만 etf_name에 사용한다."
        )
    recent_history = prepare_recent_history(conversation_history)
    route_input = question

    if recent_history:
        route_input = json.dumps(
            {
                "recent_conversation": recent_history,
                "current_question": question,
            },
            ensure_ascii=False,
        )

    response = client.responses.create(
        model="gpt-5.4-mini",
        instructions=(
            "너는 ETF 챗봇의 메인 오케스트레이터다. "
            "사용자에게 답하지 말고, 질문에 필요한 기능만 선택하라. "
            "etf_price는 특정 ETF의 종가, NAV, 기준일 질문에 사용한다. "
            "disclosure는 특정 ETF의 DART 공시 질문에 사용한다. "
            "news는 특정 ETF의 뉴스, 기사, 최근 소식 또는 이슈 질문에 사용한다. "
            "faq는 ETF의 일반 개념과 용어 설명에 사용한다. "
            "investment_guidance는 매수·매도·보유·상품 추천 또는 투자 판단을 "
            "요청할 때 사용하며, 다른 자료 경로를 함께 선택하지 않는다. "
            "product_recommendation은 ETF나 종목 추천을 요청할 때 사용한다. "
            "price_forecast는 미래 가격, 상승·하락, 목표가 예측을 요청할 때 사용한다. "
            "return_guarantee는 수익·원금 보장이나 확실한 수익을 요청할 때 사용한다. "
            "personalized_allocation은 개인 투자금액·비중·포트폴리오 결정을 요청할 때 사용한다. "
            "clarify는 어떤 상품을 말하는지 알 수 없거나 "
            "무엇을 묻는지 불분명한 경우에만 사용한다. "
            "존재 여부가 의심되는 상품도 라우터가 임의로 차단하지 말고, "
            "질문에 적힌 상품명 또는 종목코드를 그대로 etf_name에 넣어 "
            "시세·공시·뉴스 도구가 상품 DB에서 확인하게 한다. "
            "예를 들어 '달토끼 우주여행 ETF의 종가'는 etf_price이고, "
            "'ETF 가격 알려줘'처럼 상품명이 없는 질문만 clarify다. "
            "종가와 공시를 모두 요청하면 두 경로를 모두 선택한다. "
            "종가와 뉴스를 모두 요청하면 etf_price와 news를 모두 선택한다. "
            "etf_name은 질문에 나타난 표현을 그대로 사용하고, "
            "상품명이 없을 때만 none을 사용한다. "
            "recent_conversation이 제공되면 현재 질문의 '그 ETF', '그 상품', "
            "'아까 상품' 같은 지칭을 해석하는 데만 사용한다. "
            "현재 질문에 새 상품명이 있으면 과거 상품보다 현재 상품을 우선한다. "
            "현재 질문이 요청하지 않은 과거 의도나 도구를 다시 선택하지 않는다. "
            "최근 대화에서도 상품을 특정할 수 없을 때만 clarify를 선택한다. "
            "사용자가 상품명을 정확히 기억하지 못해 운용사, 브랜드 일부, 숫자, "
            "기초지수나 시장을 말하면 clarify로 버리지 말고 product를 선택한다. "
            "이때 etf_name에는 장황한 문장 대신 검색에 필요한 핵심 표현만 넣고, "
            "product_clues에는 사용자가 실제로 말한 단서만 구조화한다. "
            "확실하지 않은 상품명은 완성하거나 만들어내지 않는다. "
            "브랜드에는 KODEX·코덱스, TIGER·타이거, ACE·에이스, "
            "RISE·라이즈, SOL·쏠, HANARO·하나로 표현을 빠뜨리지 않는다. "
            "'133으로 시작'처럼 종목코드 일부를 말하면 number_hint에 넣는다. "
            "질문에 숫자가 있으면 상품명에 포함된 숫자라도 number_hint에 반드시 넣는다. "
            "자료 조회 결과나 수치를 만들어내지 마라."
        ) + product_instructions,
        input=route_input,
        text={
            "format": {
                "type": "json_schema",
                "name": "etf_question_route",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "routes": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "enum": allowed_routes,
                            },
                        },
                        "etf_name": name_schema,
                        "product_clues": {
                            "type": "object",
                            "properties": {
                                "asset_manager": {"type": "string"},
                                "brand": {"type": "string"},
                                "number_hint": {"type": "string"},
                                "index_hint": {"type": "string"},
                                "market_or_theme": {"type": "string"},
                            },
                            "required": [
                                "asset_manager", "brand", "number_hint",
                                "index_hint", "market_or_theme",
                            ],
                            "additionalProperties": False,
                        },
                    },
                    "required": ["routes", "etf_name", "product_clues"],
                    "additionalProperties": False,
                },
            }
        },
        max_output_tokens=300,
        store=False,
    )

    if not response.output_text:
        raise RuntimeError("질문 분류 결과가 비어 있습니다.")

    result = json.loads(response.output_text)

    routes = list(dict.fromkeys(result["routes"]))
    etf_name = result["etf_name"]
    product_clues = {
        key: str(value or "").strip()
        for key, value in (result.get("product_clues") or {}).items()
        if str(value or "").strip()
    }
    # LLM이 상품명 숫자를 단서 필드에서 누락해도 질문 원문의 숫자는 보존합니다.
    # 금융상품 번호를 임의의 다른 숫자로 보정하지 않기 위한 안전장치입니다.
    original_numbers = re.findall(r"\d+", str(question or ""))
    if original_numbers and not product_clues.get("number_hint"):
        product_clues["number_hint"] = " ".join(original_numbers)

    if not routes:
        routes = ["clarify"]

    etf_name = etf_name.strip() or "none"

    data_routes = {"etf_price", "disclosure", "news", "product"}
    if etf_name == "none" and data_routes.intersection(routes):
        routes = [route for route in routes if route not in data_routes]
        routes.append("clarify")

    routed = {
        "routes": list(dict.fromkeys(routes)),
        "etf_name": etf_name,
    }
    if product_clues:
        routed["product_clues"] = product_clues
    return routed
