import os
import time

import streamlit as st
from dotenv import load_dotenv

from langchain_agent import run_etf_agent
from src.services.request_logger import save_request_log


# =========================================================
# 기본 설정
# =========================================================

load_dotenv()

st.set_page_config(
    page_title="ETF AI 상담센터",
    page_icon="💬",
    layout="centered",
)

if st.session_state.pop("log_save_failed", False):
    st.warning("답변은 유지되었지만 응답 로그를 저장하지 못했습니다.")


TOOL_LABELS = {
    "search_etf_product": "ETF 상품 DB",
    "search_faq": "ETF FAQ DB",
    "get_etf_price": "ETF 시세 API",
    "search_etf_disclosure": "DART 공시 API",
    "search_etf_news": "뉴스 검색",
}


# =========================================================
# 도구 표시 이름
# =========================================================

def get_tool_display_names(tool_names):
    """
    LangChain 도구 이름을 사용자용 한글 이름으로 바꿉니다.
    """

    return [
        TOOL_LABELS.get(
            tool_name,
            tool_name,
        )
        for tool_name in tool_names
    ]


# =========================================================
# 화면 디자인
# =========================================================

st.html(
    """
    <style>
        .block-container {
            max-width: 950px;
            padding-top: 4rem;
            padding-bottom: 7rem;
        }

        .st-key-hero {
            background:
                linear-gradient(
                    120deg,
                    #355F9D,
                    #7299D0
                );
            padding: 32px 36px;
            border-radius: 20px;
            margin-bottom: 28px;
            box-shadow:
                0 12px 28px
                rgba(43, 88, 151, 0.16);
        }

        .st-key-hero h2,
        .st-key-hero p {
            color: white !important;
        }

        .st-key-hero p {
            margin-bottom: 0;
        }

        div[class*="st-key-faq_"] button {
            min-height: 78px;
            width: 100%;
            white-space: normal;
            text-align: left;
            background: #FFFFFF;
            color: #315D96;
            border: 1px solid #D7E4F3;
            border-radius: 14px;
            font-weight: 600;
            box-shadow:
                0 4px 12px
                rgba(29, 67, 116, 0.06);
        }

        div[class*="st-key-faq_"] button:hover {
            background: #EAF2FC;
            border-color: #7299D0;
            color: #244C83;
        }

        .agent-status {
            background: #F1F6FC;
            border: 1px solid #D7E4F3;
            border-radius: 12px;
            padding: 10px 14px;
            margin-top: 10px;
            color: #315D96;
            font-size: 0.88rem;
        }
    </style>
    """
)


# =========================================================
# 환경변수 확인
# =========================================================

api_key = os.getenv(
    "OPENAI_API_KEY"
)

if not api_key:
    st.error(
        ".env 파일에서 "
        "OPENAI_API_KEY를 찾지 못했습니다."
    )
    st.stop()


# =========================================================
# 대화 상태
# =========================================================

if "messages" not in st.session_state:
    st.session_state.messages = []


# =========================================================
# 사이드바
# =========================================================

with st.sidebar:
    st.title("💬 ETF AI")

    st.caption(
        "ETF 질문을 편하게 물어보세요."
    )

    if st.button(
        "＋ 새 대화",
        width="stretch",
    ):
        st.session_state.messages = []
        st.rerun()

    st.divider()

    st.subheader(
        "현재 대화의 질문"
    )

    questions = [
        message["content"]
        for message
        in st.session_state.messages
        if message["role"] == "user"
    ]

    if questions:
        for item in questions[-5:]:
            st.caption(f"• {item}")

    else:
        st.caption(
            "아직 질문이 없습니다."
        )

    st.divider()

    st.subheader("연결된 전문 기능")

    st.caption("🗂️ ETF 상품 DB")
    st.caption("📘 ETF FAQ DB")
    st.caption("📈 ETF 시세 API")
    st.caption("📢 DART 공시 API")
    st.caption("📰 뉴스 검색")


# =========================================================
# 메인 화면
# =========================================================

st.title("ETF AI 상담센터")

selected_question = None


# =========================================================
# 첫 화면 질문 카드
# =========================================================

if not st.session_state.messages:
    with st.container(key="hero"):
        st.markdown(
            "## ETF, 무엇이 궁금하세요?"
        )

        st.markdown(
            "처음 시작하는 개념부터 "
            "실제 ETF 자료까지 "
            "궁금한 주제를 골라보세요."
        )

    faq_groups = {
        "🌱 ETF 시작하기": [
            "ETF란 무엇인가요?",
            "ETF와 주식은 어떻게 다른가요?",
            "ETF는 어떻게 거래하나요?",
            "ETF는 원금이 보장되나요?",
        ],

        "🔎 ETF 상품 이해하기": [
            "ETF의 기초지수란 무엇인가요?",
            "ETF 총보수란 무엇인가요?",
            "ETF 분배금은 무엇인가요?",
            "해외 ETF에는 환율 위험이 있나요?",
        ],

        "🛡️ 투자 전 확인하기": [
            "ETF 괴리율은 무엇인가요?",
            "추적오차는 무엇인가요?",
            "ETF 구성종목은 어디서 확인하나요?",
            "레버리지 ETF와 인버스 ETF는 무엇인가요?",
        ],

        "📊 상품 DB 조회": [
            "TIGER 미국S&P500의 운용사와 기초지수를 알려줘",
            "SOL 미국S&P500의 총보수와 기초지수를 알려줘",
            "KODEX 200의 상품정보를 알려줘",
            "ACE 미국나스닥100의 상품정보를 알려줘",
        ],

        "📈 실제 ETF 자료": [
            "KODEX 200의 최근 종가와 NAV를 알려줘",
            "KODEX 인도Nifty미드캡100의 최근 종가와 NAV를 알려줘",
            "KODEX 200의 관련 공시를 알려줘",
            "KODEX 200의 종가와 관련 공시를 같이 알려줘",
        ],

        "📰 ETF 뉴스": [
            "KODEX 200 최근 뉴스 알려줘",
            "TIGER 미국S&P500 최근 뉴스 알려줘",
            "KODEX 미국S&P500 최근 뉴스 알려줘",
            "KODEX 200의 종가와 최근 뉴스를 같이 알려줘",
        ],
    }

    card_number = 0

    for (
        group_title,
        group_questions,
    ) in faq_groups.items():

        st.subheader(group_title)

        left, right = st.columns(
            2,
            gap="medium",
        )

        for (
            index,
            faq,
        ) in enumerate(group_questions):

            column = (
                left
                if index % 2 == 0
                else right
            )

            with column:
                if st.button(
                    faq,
                    key=f"faq_{card_number}",
                    width="stretch",
                ):
                    selected_question = faq

            card_number += 1

        st.write("")

    st.caption(
        "상품 DB는 공개 자료 기반 샘플 데이터로 구성되어 있습니다. "
        "ETF 시세는 실시간 가격이 아니라 공공데이터에 등록된 "
        "최근 자료 기준일 가격입니다. "
        "DART 공시 조회는 현재 일부 KODEX 상품을 지원합니다."
    )


# =========================================================
# 기존 대화 내용 표시
# =========================================================

for message in st.session_state.messages:
    avatar = (
        "👤"
        if message["role"] == "user"
        else "🤖"
    )

    with st.chat_message(
        message["role"],
        avatar=avatar,
    ):
        st.markdown(
            message["content"]
        )

        used_tools = message.get(
            "used_tools",
            [],
        )

        if used_tools:
            displayed_tools = (
                get_tool_display_names(
                    used_tools
                )
            )

            st.caption(
                "작동한 전문 도구: "
                + " · ".join(
                    displayed_tools
                )
            )


# =========================================================
# 사용자 질문 입력
# =========================================================

typed_question = st.chat_input(
    "ETF에 대해 질문해 보세요"
)

question = (
    selected_question
    or typed_question
)


# =========================================================
# LangChain 에이전트 실행
# =========================================================

if question:
    started_at = time.perf_counter()

    result = "성공"
    used_tools = []
    status = "success"
    error_type = None

    # 사용자 질문 저장
    st.session_state.messages.append(
        {
            "role": "user",
            "content": question,
        }
    )

    # 사용자 질문 표시
    with st.chat_message(
        "user",
        avatar="👤",
    ):
        st.markdown(question)

    # AI 에이전트 응답
    with st.chat_message(
        "assistant",
        avatar="🤖",
    ):
        try:
            with st.spinner(
                "AI 에이전트가 질문을 분석하고 "
                "필요한 자료를 조회하고 있어요..."
            ):
                agent_result = (
                    run_etf_agent(question)
                )

            answer = agent_result.get(
                "answer",
                "답변을 생성하지 못했습니다.",
            )

            used_tools = agent_result.get(
                "used_tools",
                [],
            )

            if not answer.strip():
                answer = (
                    "답변을 생성하지 못했습니다."
                )

                result = "빈 답변"
                status = "empty_answer"

            elif used_tools:
                result = (
                    "성공 | "
                    + ", ".join(used_tools)
                )

        except Exception as error:
            status = "error"
            error_type = type(error).__name__
            answer = (
                "질문을 처리하는 중 문제가 "
                "발생했습니다. "
                "잠시 후 다시 시도해 주세요."
            )

            result = (
                "LangChain 에이전트 오류: "
                f"{type(error).__name__}"
            )

        # 답변 표시
        st.markdown(answer)

        # 작동한 전문 도구 표시
        if used_tools:
            displayed_tools = (
                get_tool_display_names(
                    used_tools
                )
            )

            st.caption(
                "작동한 전문 도구: "
                + " · ".join(
                    displayed_tools
                )
            )

        # 답변 저장
        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": answer,
                "used_tools": used_tools,
            }
        )

    elapsed_seconds = (
        time.perf_counter()
        - started_at
    )

    # 응답시간 기록
    if not save_request_log(
        question=question,
        elapsed_seconds=elapsed_seconds,
        result=result,
        used_tools=used_tools,
        status=status,
        error_type=error_type,
    ):
        st.session_state["log_save_failed"] = True

    st.rerun()
