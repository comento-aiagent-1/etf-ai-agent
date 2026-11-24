"""Run Streamlit app flows with real APIs/DBs; logs remain for inspection."""
from datetime import datetime, timezone
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from src.db.mongo import get_log_collection


def check_app():
    app = AppTest.from_file("app.py", default_timeout=90).run()
    assert not app.exception, [error.message for error in app.exception]
    collection = get_log_collection()
    cases = [
        ("TIGER 미국S&P500의 운용사와 기초지수를 알려줘", "search_etf_product", "S&P 500"),
        ("ETF와 개별 주식을 사는 것은 어떤 차이가 있어?", "search_faq", "ETF"),
    ]
    for question, tool, answer_part in cases:
        started = datetime.now(timezone.utc)
        app.chat_input[0].set_value(question).run()
        assert not app.exception, [error.message for error in app.exception]
        answer = app.session_state["messages"][-1]
        assert answer["role"] == "assistant"
        assert tool in answer["used_tools"], answer
        assert answer_part in answer["content"], answer
        records = list(collection.find({"created_at": {"$gte": started}}))
        assert len(records) == 1, f"Expected exactly one log, got {len(records)}"
        assert records[0]["status"] == "success", records[0]["result"]
        assert tool in records[0]["used_tools"]
        assert "question" not in records[0], "Question text must not be logged"
        assert records[0]["question_length"] == len(question)
        assert not app.warning
        print(f"PASS live flow: {tool}; answer={len(answer['content'])} chars; MongoDB log saved", flush=True)

    # Fault injection exercises the app without stopping shared DB services.
    with patch("langchain_agent.run_etf_agent", return_value={"answer": "E2E retained answer", "used_tools": []}), \
         patch("src.services.request_logger.save_request_log", return_value=False):
        app.chat_input[0].set_value("E2E log failure test").run()
        assert not app.exception
        assert app.session_state["messages"][-1]["content"] == "E2E retained answer"
        assert app.warning, "Expected visible log failure warning after rerun"
    print("PASS log failure: answer retained and warning rendered", flush=True)

    started = datetime.now(timezone.utc)
    with patch("langchain_agent.run_etf_agent", side_effect=RuntimeError("E2E injected failure")):
        app.chat_input[0].set_value("E2E agent failure test").run()
        assert not app.exception
        record = collection.find_one({"created_at": {"$gte": started}})
        assert record and record["status"] == "error"
        assert record["error_type"] == "RuntimeError"
    print("PASS agent failure: error response and MongoDB error log", flush=True)


if __name__ == "__main__":
    check_app()
