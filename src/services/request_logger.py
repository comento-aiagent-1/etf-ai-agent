"""Best-effort request logging; database failures never replace an answer.

개인정보 보호를 위해 사용자 질문과 답변 원문은 저장하지 않습니다.
대신 질문 길이, 질문 분야, 사용한 도구와 조회한 상품명으로 만든
요약만 저장하고, 요약에 남는 텍스트도 개인정보 형태는 가립니다.
"""
import logging
import re
from datetime import datetime, timezone
from uuid import uuid4

import pymongo
from pymongo.errors import PyMongoError

from src.db.mongo import LOG_TIMEOUT_MS, get_log_collection

logger = logging.getLogger(__name__)

# 도구 이름 → 질문 분야
TOOL_CATEGORIES = {
    "search_etf_product": "상품정보",
    "get_etf_price": "시세",
    "search_etf_disclosure": "공시",
    "search_etf_news": "뉴스",
    "search_faq": "FAQ",
}
NO_TOOL_CATEGORY = "기타"

# 상품명이 들어 있는 도구 입력 항목. search_faq의 user_question처럼
# 사용자 문장이 그대로 들어가는 항목은 요약에 쓰지 않습니다.
PRODUCT_ARG_KEYS = ("etf_name", "search_term")
MAX_PRODUCT_NAME_LENGTH = 40

# 로그에 남는 텍스트에서 가릴 개인정보 형태 (위에서부터 차례로 적용)
MASK = "***"
SENSITIVE_PATTERNS = (
    # 이메일
    re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"),
    # 전화번호·주민등록번호·계좌번호: 하이픈이나 공백으로 끊겨 있어도
    # 숫자가 7개 이상 이어지면 통째로 가립니다 (+82 국제번호 포함).
    # 종목코드(6자리)와 'KODEX 200' 같은 상품명은 그대로 둡니다.
    re.compile(r"\+?\d(?:[\s-]?\d){6,}"),
)


def mask_sensitive(text):
    """이메일·주민번호·전화번호·계좌번호 형태를 ***로 바꿉니다."""
    masked = str(text or "")
    for pattern in SENSITIVE_PATTERNS:
        masked = pattern.sub(MASK, masked)
    return masked


def summarize_tool_inputs(used_tools, tool_inputs):
    """도구 사용 내역으로 질문 분야와 요약을 만듭니다."""
    categories = []
    parts = []

    for tool_name in used_tools:
        category = TOOL_CATEGORIES.get(tool_name, tool_name)
        if category not in categories:
            categories.append(category)

    for item in tool_inputs or []:
        category = TOOL_CATEGORIES.get(item.get("tool"), item.get("tool"))
        args = item.get("args") or {}
        product = next(
            (str(args[key]).strip() for key in PRODUCT_ARG_KEYS if args.get(key)),
            "",
        )
        product = mask_sensitive(product)[:MAX_PRODUCT_NAME_LENGTH]
        part = f"{category} · {product}" if product else str(category)
        if part not in parts:
            parts.append(part)

    if not categories:
        categories = [NO_TOOL_CATEGORY]

    summary = " / ".join(parts) if parts else NO_TOOL_CATEGORY
    return categories, summary


def save_request_log(*, question_length, elapsed_seconds, result, used_tools,
                     tool_inputs=(), status="success", error_type=None,
                     session_id=None):
    """
    요청 로그를 저장합니다.

    session_id는 대화 화면마다 무작위로 만든 가명 ID입니다.
    실제 사용자와 연결되지 않으며, 같은 대화의 질문을 묶어 볼 때만 씁니다.
    """
    categories, summary = summarize_tool_inputs(used_tools, tool_inputs)
    document = {
        "_id": str(uuid4()),
        "session_id": session_id,
        "created_at": datetime.now(timezone.utc),
        "question_length": question_length,
        "question_summary": summary,
        "categories": categories,
        "elapsed_seconds": round(elapsed_seconds, 3),
        "result": result,
        "status": status,
        "error_type": error_type,
        "used_tools": list(used_tools),
        "used_etf_api": "get_etf_price" in used_tools,
    }
    try:
        # Includes index initialization and insertion in one time budget.
        with pymongo.timeout(LOG_TIMEOUT_MS / 1000):
            get_log_collection().insert_one(document)
        return True
    except (PyMongoError, ValueError, TypeError, OSError) as error:
        # Do not include credentials, user questions, or exception messages.
        logger.warning("Request log was not saved (%s)", type(error).__name__)
        return False
