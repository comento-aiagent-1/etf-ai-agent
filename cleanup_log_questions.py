"""예전 요청 로그에 남아 있는 질문·답변 원문을 지웁니다.

기본 실행은 '확인만' 합니다. 몇 개의 로그에 원문이 남아 있는지 개수만 보여주고
아무것도 바꾸지 않습니다. 팀이 확인한 뒤 --apply를 붙여 실행하면
원문 항목(question, answer)만 지우고 나머지 기록(응답 시간, 도구 등)은 남깁니다.
지운 원문은 되돌릴 수 없습니다.

    py cleanup_log_questions.py           # 확인만
    py cleanup_log_questions.py --apply   # 실제로 지우기
"""
import sys

import pymongo

from src.db.mongo import get_log_collection

RAW_TEXT_FIELDS = ("question", "answer")
TIMEOUT_SECONDS = 30


def main():
    apply = "--apply" in sys.argv[1:]
    raw_filter = {"$or": [{field: {"$exists": True}} for field in RAW_TEXT_FIELDS]}

    with pymongo.timeout(TIMEOUT_SECONDS):
        collection = get_log_collection()
        total = collection.count_documents({})
        targets = collection.count_documents(raw_filter)

        # 원문 내용은 화면에 출력하지 않고 개수만 보여줍니다.
        print(f"전체 로그: {total}개")
        print(f"질문·답변 원문이 남은 로그: {targets}개")

        if not apply:
            print("확인만 했습니다. 실제로 지우려면 --apply를 붙여 실행하세요.")
            return

        result = collection.update_many(
            raw_filter,
            {"$unset": {field: "" for field in RAW_TEXT_FIELDS}},
        )
        print(f"원문을 지운 로그: {result.modified_count}개")


if __name__ == "__main__":
    main()
