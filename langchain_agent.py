import os
from pathlib import Path


from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI

from agent_tools import ETF_AGENT_TOOLS
from api_tools import EXTERNAL_API_TOOLS
from news_api import resolve_news_links
from news_tools import NEWS_TOOLS
from src.services.conversation_memory import prepare_recent_history

load_dotenv(
    dotenv_path=Path(__file__).resolve().parent / ".env",
)


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

SYSTEM_PROMPT = """
너는 ETF 질의응답 챗봇의 메인 오케스트레이터 에이전트다.

사용자의 질문을 분석하고 필요한 전문 도구를 선택해야 한다.

현재 사용할 수 있는 도구는 다음과 같다.

1. search_etf_product
- ETF 상품명 또는 종목코드로 상품 DB를 조회한다.
- 운용사, 자산 유형, 기초지수, 총보수, 위험등급,
  상장일, 구성종목과 자료 출처를 확인할 때 사용한다.
- 종가와 NAV 같은 시세 조회에는 사용하지 않는다.

2. search_faq
- ETF 기본 개념, 거래, 가격 용어, 비용, 분배금,
  구성종목과 투자위험을 설명할 때 사용한다.
- FAQ 검색 결과가 여러 개라면 match_score가 가장 높은
  결과를 우선적으로 사용한다.
- match_score는 질문과 FAQ 임베딩의 코사인 유사도이며 정답 확률이 아니다.
- 관련성이 낮은 FAQ 내용을 답변에 섞지 않는다.

3. get_etf_price
- 특정 ETF의 최근 자료 기준일 종가와 NAV를 조회한다.
- 사용자가 종가, 가격, NAV 또는 기준일을 질문할 때 사용한다.
- 조회 결과는 실시간 가격이 아니므로 반드시 자료 기준일을 표시한다.

4. search_etf_disclosure
- 특정 ETF와 관련된 DART 공시 제목과 원문 링크를 조회한다.
- 사용자가 공시, 투자설명서, 일괄신고서 또는 기재정정을
  질문할 때 사용한다.
- 공시 제목만으로 구체적인 변경 내용을 추측하지 않는다.

5. search_etf_news
- 특정 ETF와 관련된 최근 뉴스 기사 제목·언론사·날짜·링크를 조회한다.
- 사용자가 뉴스, 기사, 최근 소식 또는 이슈를 질문할 때 사용한다.
- 기사 제목만으로 기사 내용이나 시장 전망을 추측하지 않는다.
- 기사 제목에 나온 가격·수익률 숫자를 공식 시세처럼 말하지 않는다.
  가격은 get_etf_price 결과만 사용한다.
- 뉴스를 근거로 매수 또는 매도를 권하지 않는다.

종가와 공시를 함께 요청하면 get_etf_price와
search_etf_disclosure를 모두 호출해야 한다.
여러 종류의 자료(예: 종가와 뉴스)를 함께 요청하면
필요한 도구를 모두 호출해야 한다.

반드시 다음 원칙을 지켜라.

- DB에 저장된 정보만 사실로 사용한다.
- DB에 없는 값은 추측하거나 만들어내지 않는다.
- 자료의 출처와 확인일이 있으면 답변에 표시한다.
- 확인하지 못한 실시간 가격이나 수익률을 말하지 않는다.
- 특정 상품의 매수 또는 매도를 추천하지 않는다.
- 투자 판단은 사용자 본인의 책임이라는 점을 지킨다.
- 사용자가 밝힌 배경지식 또는 제공된 설명 수준에 맞춰 어휘와 용어 풀이를 조정한다.
- 답변은 필요 이상으로 길게 작성하지 않는다.
- 공시 조회 결과에 원문 URL이 있으면 각 공시 제목과 링크를 반드시 함께 표시한다.
- 뉴스 조회 결과는 기사마다 한 줄로 "- [기사 제목](url) · 언론사 · 날짜"
  형식으로 표시한다. url 자리에는 조회 결과의 url 값(NEWS_LINK_로 시작)을
  글자 하나 바꾸지 말고 그대로 쓴다. 다른 주소를 만들어 쓰지 않는다.
- 조회 결과에 포함된 출처 URL을 임의로 생략하지 않는다.
- 이미 조회한 자료를 두고 나중에 제공하겠다고 답하지 않는다.
- 질문에 여러 요청이 들어 있으면 각 의도를 나누어 필요한 FAQ·상품·외부 자료 도구를 모두 사용한다.
- 사용자가 입문자, 초보자 또는 숙련자라고 밝히면 그 수준에 맞춰 설명한다.
- 수준을 밝히지 않았다면 제공된 설명 수준 안내를 따르고, 해당 수준의 용어와 설명 방식을 사용한다.
"""


etf_agent = None

if OPENAI_API_KEY:
    model = ChatOpenAI(
        model="gpt-5.4-mini",
        api_key=OPENAI_API_KEY,
        use_responses_api=True,
        reasoning_effort="low",
        verbosity="low",
        max_completion_tokens=700,
        max_retries=2,
        store=False,
    )

    etf_agent = create_agent(
        model=model,
        tools=ETF_AGENT_TOOLS + EXTERNAL_API_TOOLS + NEWS_TOOLS,
        system_prompt=SYSTEM_PROMPT,
        name="etf_orchestrator",
    )


def extract_answer(message):
    """LangChain의 최종 메시지에서 답변 텍스트를 꺼냅니다."""

    content = message.content

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        text_parts = []

        for item in content:
            if isinstance(item, str):
                text_parts.append(item)

            elif isinstance(item, dict):
                text = (
                    item.get("text")
                    or item.get("content")
                    or item.get("output_text")
                )

                if text:
                    text_parts.append(str(text))

        return "\n".join(text_parts)

    return str(content)


KNOWLEDGE_LEVEL_GUIDANCE = {
    "입문": (
        "ETF를 처음 접하는 사용자입니다. 쉬운 일상어와 짧은 예시를 우선하고, "
        "전문 용어는 쉬운 풀이를 바로 덧붙이세요."
    ),
    "초급": (
        "주식이나 ETF의 기본 개념을 아는 사용자입니다. 매매, 지수, 총보수, "
        "분배금의 뜻과 실제 투자 과정의 연결을 설명하세요."
    ),
    "중급": (
        "ETF를 실제로 거래하거나 비교해 본 사용자입니다. 추적오차·괴리율·유동성·"
        "총비용 등 분석 요소와 상품 간 장단점을 중심으로 설명하세요."
    ),
    "고급": (
        "금융상품과 시장구조를 깊이 이해한 사용자입니다. NAV·iNAV·추적오차·"
        "기초지수 구성과 위험 요인에 대해 지표 정의, 계산 기준, 출처와 한계를 명시하세요."
    ),
}


def run_etf_agent(
    question,
    knowledge_level=None,
    conversation_history=None,
):
    """
    사용자 질문을 LangChain 에이전트에 전달하고
    최종 답변과 사용한 도구 목록을 반환합니다.
    """

    question = question.strip()

    if not question:
        return {
            "answer": "질문을 입력해 주세요.",
            "used_tools": [],
        }

    if etf_agent is None:
        return {
            "answer": (
                "현재 시연 환경에 OpenAI API 키가 설정되지 않아 "
                "AI 답변을 생성할 수 없습니다. "
                ".env 파일에 OPENAI_API_KEY를 설정한 뒤 다시 실행해 주세요."
            ),
            "used_tools": [],
        }

    messages = []
    if knowledge_level is not None:
        if knowledge_level not in KNOWLEDGE_LEVEL_GUIDANCE:
            raise ValueError(
                f"지원하지 않는 ETF 설명 수준입니다: {knowledge_level}"
            )
        messages.append(
            {
                "role": "system",
                "content": (
                    "사용자의 선택한 설명 수준은 "
                    f"'{knowledge_level}'입니다. "
                    f"{KNOWLEDGE_LEVEL_GUIDANCE[knowledge_level]} "
                    "단, 사용자가 현재 질문에서 다른 배경지식 수준을 "
                    "명시하면 그 표현을 우선 적용하세요."
                ),
            }
        )
    messages.extend(
        prepare_recent_history(conversation_history)
    )
    messages.append(
        {
            "role": "user",
            "content": question,
        }
    )

    result = etf_agent.invoke({"messages": messages})

    messages = result.get("messages", [])

    if not messages:
        return {
            "answer": "답변을 생성하지 못했습니다.",
            "used_tools": [],
        }

    used_tools = []
    # 로그 요약용: 에이전트가 어떤 도구를 어떤 입력으로 불렀는지 모읍니다.
    tool_inputs = []

    for message in messages:
        message_type = getattr(message, "type", "")

        if message_type == "tool":
            tool_name = getattr(message, "name", None)

            if tool_name and tool_name not in used_tools:
                used_tools.append(tool_name)

        for call in getattr(message, "tool_calls", None) or []:
            tool_inputs.append(
                {
                    "tool": call.get("name"),
                    "args": call.get("args") or {},
                }
            )

    final_message = messages[-1]
    answer = resolve_news_links(extract_answer(final_message))

    return {
        "answer": answer,
        "used_tools": used_tools,
        "tool_inputs": tool_inputs,
    }
