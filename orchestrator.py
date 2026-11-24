import json

from src.services.conversation_memory import prepare_recent_history


def route_question(
    question,
    client,
    *,
    include_product=False,
    conversation_history=None,
):
    allowed_routes = ["etf_price", "disclosure", "news", "faq", "clarify"]
    product_instructions = ""
    name_schema = {"type": "string"}
    if include_product:
        allowed_routes += ["product", "comparison_unsupported"]
        product_instructions = (
            "특정 ETF 한 종목의 총보수, 추종지수, 운용사 또는 구성 정보를 묻는 경우 product를 선택하고, "
            "질문에 있는 상품명 또는 종목코드를 etf_name에 넣는다. "
            "상품을 임의로 정하지 말고 정보가 부족하면 clarify를 선택한다. "
            "여러 종목 비교나 조건에 맞는 ETF 목록 검색은 comparison_unsupported를 선택한다. "
            "일반 개념도 함께 묻는 경우 faq를 추가한다. "
            "상품정보와 시세 또는 공시를 함께 묻는 경우 필요한 경로를 모두 선택한다."
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
                    },
                    "required": ["routes", "etf_name"],
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

    if not routes:
        routes = ["clarify"]

    etf_name = etf_name.strip() or "none"

    data_routes = {"etf_price", "disclosure", "news", "product"}
    if etf_name == "none" and data_routes.intersection(routes):
        routes = [route for route in routes if route not in data_routes]
        routes.append("clarify")

    return {
        "routes": list(dict.fromkeys(routes)),
        "etf_name": etf_name,
    }
