import os
from datetime import timedelta
from functools import lru_cache
from pathlib import Path
from urllib.parse import unquote

import requests
from dotenv import load_dotenv

from src.services.time_service import seoul_today


BASE_DIR = Path(__file__).resolve().parent

ETF_API_URL = (
    "https://apis.data.go.kr/1160100/"
    "GetSecuritiesProductInfoService_V2/getETFPriceInfo_V2"
)


@lru_cache(maxsize=128)
def _fetch_latest_etf(
    name: str,
    product_code: str,
    cache_date: str,
):
    """
    ETF 시세 API를 호출합니다.

    cache_date는 한국 날짜가 바뀌면 캐시도 새로 생성되도록
    캐시 키에 포함합니다.
    """

    load_dotenv(BASE_DIR / ".env")

    api_key = os.getenv("ETF_DATA_API_KEY")

    if not api_key:
        raise RuntimeError(
            "ETF_DATA_API_KEY가 설정되지 않았습니다."
        )

    today = seoul_today()

    try:
        response = requests.get(
            ETF_API_URL,
            params={
                "serviceKey": unquote(api_key),
                "resultType": "json",
                "numOfRows": 40,
                "pageNo": 1,
                "itmsNm": name,
                "beginBasDt": (
                    today - timedelta(days=30)
                ).strftime("%Y%m%d"),
                "endBasDt": (
                    today + timedelta(days=1)
                ).strftime("%Y%m%d"),
            },
            timeout=20,
        )

    except requests.RequestException as error:
        raise RuntimeError(
            f"ETF API 연결 실패: {type(error).__name__}"
        ) from None

    if response.status_code != 200:
        raise RuntimeError(
            f"ETF API HTTP 오류: {response.status_code}"
        )

    try:
        data = response.json()

    except ValueError:
        raise RuntimeError(
            "ETF API 응답이 JSON 형식이 아닙니다."
        ) from None

    if "OpenAPI_ServiceResponse" in data:
        error = data[
            "OpenAPI_ServiceResponse"
        ].get("cmmMsgHeader", {})

        reason_code = error.get(
            "returnReasonCode",
            "UNKNOWN",
        )

        raise RuntimeError(
            f"ETF API 오류 코드: {reason_code}"
        )

    body = data.get(
        "response",
        {},
    ).get(
        "body",
        {},
    )

    items = body.get("items") or {}

    rows = (
        items.get("item", [])
        if isinstance(items, dict)
        else []
    )

    if isinstance(rows, dict):
        rows = [rows]

    exact_rows = []

    for row in rows:
        if row.get("itmsNm") != name:
            continue

        if (
            product_code
            and row.get("srtnCd") != product_code
        ):
            continue

        exact_rows.append(row)

    if not exact_rows:
        return None

    latest = max(
        exact_rows,
        key=lambda row: row.get("basDt", ""),
    )

    return {
        "name": latest.get("itmsNm"),
        "code": latest.get("srtnCd"),
        "date": latest.get("basDt"),
        "close": latest.get("clpr"),
        "nav": latest.get("nav"),
        "real_time": False,
        "source": "금융위원회 증권상품시세정보",
        "source_url": (
            "https://www.data.go.kr/data/"
            "15094806/openapi.do"
        ),
    }


def get_latest_etf(
    name: str,
    product_code: str = "",
):
    """
    한국 시간 기준 하루 동안 동일 상품의 조회 결과를 재사용합니다.
    반환값은 캐시 내부 데이터가 수정되지 않도록 복사합니다.
    """

    result = _fetch_latest_etf(
        name.strip(),
        str(product_code or "").strip(),
        seoul_today().isoformat(),
    )

    if result is None:
        return None

    return dict(result)