"""Small live retrieval smoke test; calls the OpenAI embeddings API."""
import json

from agent_tools import search_faq


def main():
    cases = [
        ("ETF와 개별 주식을 사는 것은 어떤 차이가 있어?", "F002"),
        ("NAV라는 게 무슨 뜻이야?", "F006"),
        ("ETF에서 받는 분배금은 어디서 나오는 돈이야?", "F018"),
        ("김치찌개 끓이는 요리법 알려줘", None),
    ]
    failures = 0
    for question, expected in cases:
        response = json.loads(search_faq.invoke({"user_question": question}))
        found = response["results"]
        ids = [row["faq_id"] for row in found]
        passed = expected in ids if expected else not found
        # A backend failure must never count as successful rejection.
        if "설정" in response["message"]:
            passed = False
        failures += not passed
        scores = [(row["faq_id"], round(row["match_score"], 3)) for row in found]
        print(f"{'PASS' if passed else 'FAIL'} expected={expected}, results={scores}")
    return int(failures > 0)


if __name__ == "__main__":
    raise SystemExit(main())
