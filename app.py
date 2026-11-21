import csv
import logging
import os
import time
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(
    dotenv_path=Path(__file__).resolve().parent / ".env",
)

from consultation import LEVELS, consult
from src.services.diagnostic_logging import log_safe_exception
from src.services.request_logger import save_request_log

logger = logging.getLogger(__name__)


# =========================================================
# 기본 설정
# =========================================================

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

KNOWLEDGE_LEVELS = list(LEVELS)
CATEGORY_LABELS = {
    "기본개념": "ETF 기초 개념",
    "가격정보": "ETF 상품 분석 및 비교",
    "거래": "ETF 거래 및 비용",
    "비용": "ETF 거래 및 비용",
    "분배금": "ETF 거래 및 비용",
    "상품정보": "ETF 투자 시작하기",
    "위험": "투자 위험 및 고급 개념",
    "공시": "ETF 상품 분석 및 비교",
    "투자유의": "ETF 투자 시작하기",
}
FAQ_SOURCE_PATH = (
    Path(__file__).resolve().parent
    / "data"
    / "source"
    / "FAQ.csv"
)


def load_faq_questions():
    with FAQ_SOURCE_PATH.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as faq_file:
        return list(csv.DictReader(faq_file))


def render_sources(sources, message_index):
    if sources:
        with st.expander("참조 자료와 출처"):
            for index, source in enumerate(sources):
                name = source.get("source_name", "자료 출처")
                date = source.get("data_date") or source.get("source_date")
                verified_at = source.get("verified_at")
                label = f"{name} · 기준일 {date}" if date else name
                st.text(f"{label} · 확인일 {verified_at}" if verified_at else label)
                url = source.get("source_url", "")
                if isinstance(url, str) and url.startswith(("https://", "http://")):
                    st.link_button("자료 열기", url, key=f"source_{message_index}_{index}")


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
    st.warning(
        ".env 파일에서 "
        "OPENAI_API_KEY를 찾지 못했습니다."
    )


# =========================================================
# 대화 상태
# =========================================================

if "messages" not in st.session_state:
    st.session_state.messages = []

selected_question = None
selected_faq = False
requested_level = None

# =========================================================
# 사이드바
# =========================================================

with st.sidebar:
    st.title("💬 ETF AI")

    st.caption(
        "ETF 질문을 편하게 물어보세요."
    )

    st.subheader("설명 수준")
    knowledge_level = st.segmented_control(
        "ETF 배경지식 수준",
        KNOWLEDGE_LEVELS,
        default="입문",
        key="knowledge_level",
    )
    st.caption(
        "질문에 '입문자예요'처럼 수준을 적으면 "
        "선택한 수준보다 우선해 반영합니다."
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

    st.divider()
    st.subheader("자주 묻는 질문")
    faq_search = st.text_input("FAQ 검색", placeholder="예: 분배금, 환율 위험").strip().casefold()
    grouped_faqs = {}
    for faq in load_faq_questions():
        category = CATEGORY_LABELS.get(faq["category"], faq["category"])
        searchable = " ".join((faq["question"], category, faq["keywords"])).casefold()
        if all(term in searchable for term in faq_search.split()):
            grouped_faqs.setdefault(category, []).append(faq)
    for category, rows in grouped_faqs.items():
        with st.expander(f"{category} · {len(rows)}", expanded=bool(faq_search)):
            for faq in rows:
                if st.button(faq["question"], key=f"faq_{faq['faq_id']}", width="stretch"):
                    selected_question = faq["question"]
                    selected_faq = True
    if not grouped_faqs:
        st.info("일치하는 FAQ가 없습니다. 채팅창에 직접 질문해 보세요.")

    latest = st.session_state.messages[-1] if st.session_state.messages else {}
    if questions and latest.get("role") == "assistant":
        easy, detailed = st.columns(2)
        if easy.button("더 쉽게", width="stretch"):
            requested_level = "입문"
        if detailed.button("더 자세히", width="stretch"):
            requested_level = "심화"
        if requested_level:
            selected_question = questions[-1]
            selected_faq = latest.get("selected_faq", False)
    related = latest.get("related", [])
    if related:
        st.subheader("관련 FAQ")
        for index, related_question in enumerate(related):
            if st.button(related_question, key=f"related_faq_{index}", width="stretch"):
                selected_question = related_question
                selected_faq = True

# =========================================================
# 메인 화면
# =========================================================

st.title("ETF AI 상담센터")

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

    sample_question_groups = {
        "상품 DB 조회": [
            "TIGER 미국S&P500의 운용사와 기초지수를 알려줘",
            "SOL 미국S&P500의 총보수와 기초지수를 알려줘",
            "KODEX 200의 상품정보를 알려줘",
            "ACE 미국나스닥100의 상품정보를 알려줘",
        ],
        "실제 ETF 자료": [
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
    for group_title, group_questions in sample_question_groups.items():
        st.subheader(group_title)
        left, right = st.columns(2, gap="medium")
        for index, sample_question in enumerate(group_questions):
            column = left if index % 2 == 0 else right
            with column:
                if st.button(
                    sample_question,
                    key=f"sample_{card_number}",
                    width="stretch",
                ):
                    selected_question = sample_question
            card_number += 1

    st.caption(
        "상품 DB는 공개 자료 기반 샘플 데이터로 구성되어 있습니다. "
        "ETF 시세는 실시간 가격이 아니라 공공데이터에 등록된 "
        "최근 자료 기준일 가격입니다. "
        "DART 공시 조회는 현재 일부 KODEX 상품을 지원합니다."
    )


# =========================================================
# 기존 대화 내용 표시
# =========================================================

for message_index, message in enumerate(st.session_state.messages):
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
        render_sources(message.get("sources", []), message_index)

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
    sources = []
    related = []
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
                level = requested_level or knowledge_level
                with OpenAI(timeout=20, max_retries=0) as client:
                    agent_result = consult(
                        question,
                        level,
                        client,
                        selected_faq=selected_faq,
                    )

            answer = agent_result.get(
                "answer",
                "답변을 생성하지 못했습니다.",
            )

            used_tools = agent_result.get(
                "used_tools",
                [],
            )
            sources = agent_result.get("sources", [])
            related = agent_result.get("related", [])

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
            log_safe_exception(
                logger,
                "ETF consultation",
                error,
            )
            status = "error"
            error_type = type(error).__name__
            answer = (
                "질문을 처리하는 중 문제가 "
                "발생했습니다. "
                "잠시 후 다시 시도해 주세요."
            )

            result = (
                "ETF 상담 처리 오류: "
                f"{type(error).__name__}"
            )

        # 답변 표시
        st.markdown(answer)
        render_sources(sources, len(st.session_state.messages))

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
                "sources": sources,
                "related": related,
                "selected_faq": selected_faq,
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
