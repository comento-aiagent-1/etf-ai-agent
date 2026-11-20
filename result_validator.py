from datetime import datetime
from decimal import Decimal, InvalidOperation
from urllib.parse import parse_qs, urlparse

from src.services.time_service import seoul_today


def valid_yyyymmdd(value):
    if (
        not isinstance(value, str)
        or len(value) != 8
        or not value.isdigit()
    ):
        return False

    try:
        datetime.strptime(value, "%Y%m%d")
        return True

    except ValueError:
        return False


def valid_positive_number(value):
    try:
        number = Decimal(str(value))

        return (
            number.is_finite()
            and number > 0
        )

    except (InvalidOperation, TypeError):
        return False


def validate_etf_data(data, expected_name):
    """ETF 시세 자료가 답변에 사용 가능한지 검증합니다."""

    if not isinstance(data, dict):
        return False, "시세 자료 형식 오류"

    if data.get("name") != expected_name:
        return False, "요청 상품과 조회 상품 불일치"

    if not data.get("code"):
        return False, "종목코드 누락"

    data_date = data.get("date")

    if not valid_yyyymmdd(data_date):
        return False, "자료 기준일 형식 오류"

    parsed_date = datetime.strptime(
        data_date,
        "%Y%m%d",
    ).date()

    if parsed_date > seoul_today():
        return False, "자료 기준일이 미래 날짜임"

    if not valid_positive_number(
        data.get("close")
    ):
        return False, "종가 오류"

    if not valid_positive_number(
        data.get("nav")
    ):
        return False, "NAV 오류"

    if not data.get("source"):
        return False, "출처 이름 누락"

    source_url = urlparse(
        str(data.get("source_url", ""))
    )

    if (
        source_url.scheme != "https"
        or source_url.hostname != "www.data.go.kr"
    ):
        return False, "출처 링크 오류"

    return True, "정상"


def validate_disclosure_result(
    result,
    expected_name,
):
    """DART 공시 결과의 상태·제목·날짜·링크를 검증합니다."""

    if not isinstance(result, dict):
        return False, "공시 자료 형식 오류"

    if result.get("etf_name") != expected_name:
        return False, "요청 상품과 공시 검색 상품 불일치"

    if not str(
        result.get("asset_manager", "")
    ).strip():
        return False, "ETF 운용사 정보 누락"

    if not str(
        result.get("dart_corp_name", "")
    ).strip():
        return False, "DART 회사명 누락"

    start_date = result.get("start_date")
    end_date = result.get("end_date")

    if (
        not valid_yyyymmdd(start_date)
        or not valid_yyyymmdd(end_date)
    ):
        return False, "공시 검색 기간 형식 오류"

    if start_date > end_date:
        return False, "공시 검색 시작일이 종료일보다 늦음"

    parsed_end_date = datetime.strptime(
        end_date,
        "%Y%m%d",
    ).date()

    if parsed_end_date > seoul_today():
        return False, "공시 검색 종료일이 미래 날짜임"

    matches = result.get("matches")

    if not isinstance(matches, list):
        return False, "공시 목록 형식 오류"

    search_complete = result.get(
        "search_complete"
    )

    if not isinstance(
        search_complete,
        bool,
    ):
        return False, "검색 완료 상태 형식 오류"

    result_status = result.get(
        "result_status"
    )

    if result_status not in {
        "found",
        "no_results",
        "search_incomplete",
    }:
        return False, "공시 검색 결과 상태 오류"

    if matches and result_status != "found":
        return False, "공시 존재 여부 상태 불일치"

    if (
        not matches
        and result_status == "found"
    ):
        return False, "공시 존재 여부 상태 불일치"

    if (
        result_status == "no_results"
        and not search_complete
    ):
        return False, "미완료 검색을 결과 없음으로 표시함"

    for item in matches:
        if not isinstance(item, dict):
            return False, "공시 항목 형식 오류"

        title = str(
            item.get("title", "")
        ).strip()

        if not title:
            return False, "공시 제목 누락"

        filing_date = item.get("date")

        if not valid_yyyymmdd(filing_date):
            return False, "공시 날짜 형식 오류"

        if not (
            start_date
            <= filing_date
            <= end_date
        ):
            return False, "공시 날짜가 검색 기간 밖에 있음"

        link = urlparse(
            str(item.get("url", ""))
        )

        receipt_number = parse_qs(
            link.query
        ).get(
            "rcpNo",
            [""],
        )[0]

        if (
            link.scheme != "https"
            or link.hostname != "dart.fss.or.kr"
            or not receipt_number.isdigit()
        ):
            return False, "DART 공시 링크 오류"

    return True, "정상"