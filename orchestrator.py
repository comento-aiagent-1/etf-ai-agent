import json


def route_question(question, client, *, include_product=False):
    market_products = ["KODEX 200", "KODEX 인도Nifty미드캡100"]
    allowed_routes = ["etf_price", "disclosure", "faq", "unsupported", "clarify"]
    product_instructions = ""
    name_schema = {"type": "string", "enum": [*market_products, "none"]}
    if include_product:
        allowed_routes += ["product", "comparison_unsupported"]
        name_schema = {"type": "string"}
        product_instructions = (
            "상품정보 DB는 시세·공시 지원 목록 밖의 상품도 조회할 수 있다. "
            "특정 ETF 한 종목의 총보수, 추종지수, 운용사 또는 구성 정보를 묻는 경우 product를 선택하고, "
            "질문에 있는 상품명 또는 종목코드를 etf_name에 넣는다. "
            "상품을 임의로 정하지 말고 정보가 부족하면 clarify를 선택한다. "
            "여러 종목 비교나 조건에 맞는 ETF 목록 검색은 comparison_unsupported를 선택한다. "
            "일반 개념도 함께 묻는 경우 faq를 추가한다. "
            "시세·공시는 위 두 상품의 정식 이름만 etf_name에 사용한다."
        )
    response = client.responses.create(
        model="gpt-5.4-mini",
        instructions=(
            "너는 ETF 챗봇의 메인 오케스트레이터다. "
            "사용자에게 답하지 말고, 질문에 필요한 기능만 선택하라. "
            "etf_price는 지원 ETF의 종가, NAV, 기준일 질문에 사용한다. "
            "disclosure는 지원 ETF의 DART 공시 질문에 사용한다. "
            "faq는 ETF의 일반 개념과 용어 설명에 사용한다. "
            "unsupported는 특정 ETF 상품의 시세나 공시를 요청했지만 "
            "그 상품이 지원 ETF 목록에 없는 경우에 사용한다. "
            "clarify는 어떤 상품을 말하는지 알 수 없거나 "
            "무엇을 묻는지 불분명한 경우에만 사용한다. "
            "예를 들어 '달토끼 우주여행 ETF의 종가'는 unsupported이고, "
            "'ETF 가격 알려줘'는 clarify다. "
            "종가와 공시를 모두 요청하면 두 경로를 모두 선택한다. "
            "지원 ETF는 KODEX 200과 "
            "KODEX 인도Nifty미드캡100뿐이다. "
            "지원하지 않는 상품의 etf_name은 none으로 설정하라. "
            "자료 조회 결과나 수치를 만들어내지 마라."
        ) + product_instructions,
        input=question,
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

    if include_product:
        etf_name = etf_name.strip() or "none"
        if etf_name not in market_products:
            blocked = {"etf_price", "disclosure"}
            if blocked.intersection(routes):
                routes = [route for route in routes if route not in blocked]
                routes.append("unsupported" if etf_name != "none" else "clarify")
        if etf_name == "none":
            routes = ["clarify" if route == "product" else route for route in routes]
        return {"routes": list(dict.fromkeys(routes)), "etf_name": etf_name}

    if etf_name == "none" and any(
        route in routes for route in ["etf_price", "disclosure"]
    ):
        routes = ["clarify"]

    return {
        "routes": routes,
        "etf_name": etf_name,
    }
