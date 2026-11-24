import csv
import logging
import os
import time
from pathlib import Path
from uuid import uuid4

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

APP_ROOT = Path(__file__).resolve().parent
MASCOT_PATH = APP_ROOT / "assets" / "eti-mascot.png"


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

        .st-key-page_header [data-testid="stImage"] {
            display: flex;
            justify-content: flex-end;
            align-items: center;
        }

        .st-key-page_header img {
            max-height: 118px;
            object-fit: contain;
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

        div[class*="st-key-sample_"] button {
            min-height: 56px;
            width: 100%;
            padding: 0.7rem 1rem;
            white-space: normal;
            line-height: 1.35;
            border-radius: 12px;
            font-size: 0.92rem;
        }

        div[class*="st-key-sample_"] {
            margin-bottom: 0.35rem;
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

        .scroll-latest-button {
            position: fixed;
            right: 2rem;
            bottom: 5.8rem;
            z-index: 9999;
            width: 46px;
            height: 46px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 50%;
            background: #FFFFFF;
            color: #315D96 !important;
            border: 1px solid #C9D9EC;
            box-shadow: 0 6px 18px rgba(29, 67, 116, 0.18);
            text-decoration: none !important;
            font-size: 1.35rem;
            font-weight: 700;
        }

        .scroll-latest-button:hover {
            background: #EAF2FC;
            border-color: #7299D0;
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

# 로그용 가명 대화 ID: 실제 사용자와 연결되지 않는 무작위 값
if "log_session_id" not in st.session_state:
    st.session_state.log_session_id = uuid4().hex

if "faq_view_category" not in st.session_state:
    st.session_state.faq_view_category = None

selected_question = None
selected_faq = False
requested_level = None
faq_rows = load_faq_questions()

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
        st.session_state.log_session_id = uuid4().hex
        st.session_state.faq_view_category = None
        st.rerun()

    st.divider()

    st.subheader("자주 묻는 질문")
    with st.expander(
        "📘 FAQ 카테고리 열기",
        expanded=False,
    ):
        faq_search = st.text_input(
            "FAQ 검색",
            placeholder="예: 분배금, 환율 위험",
            key="faq_search",
        ).strip().casefold()

        grouped_faqs = {}
        for faq in faq_rows:
            category = CATEGORY_LABELS.get(
                faq["category"],
                faq["category"],
            )
            searchable = " ".join(
                (
                    faq["question"],
                    category,
                    faq["keywords"],
                )
            ).casefold()
            if all(
                term in searchable
                for term in faq_search.split()
            ):
                grouped_faqs.setdefault(
                    category,
                    [],
                ).append(faq)

        if grouped_faqs:
            if st.button(
                f"📚 전체 FAQ · {sum(len(rows) for rows in grouped_faqs.values())}",
                key="category_nav_all",
                width="stretch",
            ):
                st.session_state.faq_view_category = "__all__"

            for category_index, (category, rows) in enumerate(grouped_faqs.items()):
                if st.button(
                    f"{category} · {len(rows)}",
                    key=f"category_nav_{category_index}",
                    width="stretch",
                ):
                    st.session_state.faq_view_category = category
        else:
            st.info(
                "일치하는 FAQ가 없습니다. "
                "채팅창에 직접 질문해 보세요."
            )

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
        conversation_title = questions[0]
        if len(conversation_title) > 20:
            conversation_title = conversation_title[:20].rstrip() + "…"

        with st.expander(
            f"💬 {conversation_title} · {len(questions)}",
            expanded=False,
        ):
            for question_index, item in enumerate(questions):
                question_label = item
                if len(question_label) > 28:
                    question_label = question_label[:28].rstrip() + "…"

                if st.button(
                    f"{question_index + 1}. {question_label}",
                    key=f"turn_nav_{question_index}",
                    width="stretch",
                ):
                    st.session_state.faq_view_category = None
                    st.session_state["scroll_target"] = (
                        f"conversation-turn-{question_index}"
                    )
                    st.rerun()

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
    latest = st.session_state.messages[-1] if st.session_state.messages else {}
    if questions and latest.get("role") == "assistant":
        easy, detailed = st.columns(2)
        if easy.button("더 쉽게", width="stretch"):
            requested_level = "입문"
        if detailed.button("더 자세히", width="stretch"):
            requested_level = "고급"
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

faq_view_category = st.session_state.faq_view_category
is_home_screen = (
    not st.session_state.messages
    and not faq_view_category
)

with st.container(key="page_header"):
    header_columns = st.columns(
        [5, 1] if is_home_screen else [5, 1, 1],
        vertical_alignment="center",
    )
    title_column = header_columns[0]
    home_column = None if is_home_screen else header_columns[1]
    mascot_column = header_columns[-1]

    with title_column:
        st.title("ETF AI 상담센터")

    if home_column is not None:
        with home_column:
            if st.button(
                "🏠 홈",
                key="global_home",
                width="stretch",
            ):
                st.session_state.messages = []
                st.session_state.faq_view_category = None
                st.rerun()

    with mascot_column:
        if MASCOT_PATH.exists():
            st.image(
                str(MASCOT_PATH),
                width=112,
            )

# =========================================================
# FAQ 메인 화면
# =========================================================

if faq_view_category:
    st.header("📘 자주 묻는 질문")
    st.caption(
        "궁금한 질문을 선택하면 FAQ DB에 저장된 "
        "검증된 답변을 보여드려요."
    )

    if faq_view_category == "__all__":
        visible_faq_groups = grouped_faqs
    else:
        visible_faq_groups = {
            faq_view_category: grouped_faqs.get(
                faq_view_category,
                [],
            )
        }

    visible_count = sum(
        len(rows)
        for rows in visible_faq_groups.values()
    )

    if faq_search:
        st.info(
            f"‘{faq_search}’ 검색 결과 {visible_count}개입니다."
        )

    for category, rows in visible_faq_groups.items():
        if not rows:
            continue
        st.subheader(f"{category} · {len(rows)}")
        left, right = st.columns(2, gap="medium")
        for faq_index, faq in enumerate(rows):
            column = left if faq_index % 2 == 0 else right
            with column:
                if st.button(
                    faq["question"],
                    key=f"faq_{faq['faq_id']}",
                    width="stretch",
                ):
                    selected_question = faq["question"]
                    selected_faq = True
                    st.session_state.faq_view_category = None

    if visible_count == 0:
        st.info(
            "선택한 조건에 맞는 FAQ가 없습니다. "
            "왼쪽 검색어를 바꾸거나 전체 FAQ를 선택해 주세요."
        )

    if selected_question is None:
        st.stop()

# =========================================================
# 첫 화면 질문 카드
# =========================================================

if not st.session_state.messages and not faq_view_category:
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
        "🗂️ 상품 DB 조회": [
            "TIGER 미국S&P500의 운용사와 기초지수를 알려줘",
            "SOL 미국S&P500의 총보수와 기초지수를 알려줘",
            "KODEX 200의 상품정보를 알려줘",
            "ACE 미국나스닥100의 상품정보를 알려줘",
        ],
        "📊 실제 ETF 자료": [
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
        "시세·공시는 상품 DB에서 정식 상품명과 종목코드·운용사를 "
        "확인한 뒤 외부 API를 조회합니다. 조회 자료가 없으면 "
        "확인되지 않은 값을 생성하지 않습니다."
    )


# =========================================================
# 기존 대화 내용 표시
# =========================================================

if st.session_state.messages:
    st.html('<div id="conversation-start"></div>')

user_turn_index = -1

for message_index, message in enumerate(st.session_state.messages):
    if message["role"] == "user":
        user_turn_index += 1
        st.html(
            f'<div id="conversation-turn-{user_turn_index}"></div>'
        )

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

scroll_target = st.session_state.pop(
    "scroll_target",
    None,
)

if scroll_target:
    if scroll_target != "latest":
        scroll_javascript = """
            const target = window.parent.document.getElementById(
                'SCROLL_TARGET'
            );
            if (target) {
                target.scrollIntoView({behavior: 'smooth', block: 'start'});
            }
        """.replace("SCROLL_TARGET", scroll_target)
    else:
        scroll_javascript = """
            const target = window.parent.document.getElementById(
                'conversation-end'
            );
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'end'
                });
            }
        """

    st.iframe(
        f"""
        <script>
            window.setTimeout(() => {{
                {scroll_javascript}
            }}, 180);
        </script>
        """,
        height=1,
        alt="대화 위치 이동",
    )


# =========================================================
# 사용자 질문 입력
# =========================================================

if st.session_state.messages:
    st.html(
        """
        <a
            class="scroll-latest-button"
            href="#conversation-end"
            title="최신 답변으로 이동"
            aria-label="최신 답변으로 이동"
        >
            ↓
        </a>
        """
    )

st.html(
    '<div id="conversation-end" style="height: 1px;"></div>'
)

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
    conversation_history = list(
        st.session_state.messages
    )

    result = "성공"
    used_tools = []
    tool_inputs = []
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
    st.html('<div id="active-question"></div>')

    with st.chat_message(
        "user",
        avatar="👤",
    ):
        st.markdown(question)

    # 첫 화면이나 이전 대화 상단에서 질문해도 새 질문 위치로 이동
    st.iframe(
        """
        <script>
            window.setTimeout(() => {
                const target = window.parent.document.getElementById(
                    'active-question'
                );
                if (target) {
                    target.scrollIntoView({
                        behavior: 'smooth',
                        block: 'start'
                    });
                }
            }, 120);
        </script>
        """,
        height=1,
        alt="새 질문 위치 이동",
    )

    # AI 에이전트 응답
    with st.chat_message(
        "assistant",
        avatar="🤖",
    ):
        try:
            with st.status(
                "질문 분석 중",
                expanded=True,
                state="running",
            ) as progress_status:
                progress_detail = st.empty()

                def update_progress(stage, detail):
                    progress_status.update(
                        label=stage,
                        state="running",
                        expanded=True,
                    )
                    progress_detail.markdown(detail)

                level = requested_level or knowledge_level
                with OpenAI(timeout=20, max_retries=0) as client:
                    agent_result = consult(
                        question,
                        level,
                        client,
                        selected_faq=selected_faq,
                        progress_callback=update_progress,
                        conversation_history=conversation_history,
                    )

                progress_detail.markdown(
                    "답변을 모두 준비했습니다."
                )
                progress_status.update(
                    label="답변 완료",
                    state="complete",
                    expanded=False,
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

            tool_inputs = agent_result.get(
                "tool_inputs",
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
            if "progress_status" in locals():
                progress_status.update(
                    label="처리 중 문제가 발생했습니다",
                    state="error",
                    expanded=True,
                )
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

    # 응답시간 기록 (질문 원문 대신 길이와 요약만 저장)
    if not save_request_log(
        question_length=len(question),
        elapsed_seconds=elapsed_seconds,
        result=result,
        used_tools=used_tools,
        tool_inputs=tool_inputs,
        session_id=st.session_state.log_session_id,
        status=status,
        error_type=error_type,
    ):
        st.session_state["log_save_failed"] = True

    st.session_state["scroll_target"] = "latest"
    st.rerun()
