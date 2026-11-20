import json
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from zipfile import BadZipFile, ZipFile

import requests
from dotenv import load_dotenv

from src.services.time_service import (
    seoul_now,
    seoul_today,
)


BASE_DIR = Path(__file__).resolve().parent

DART_LIST_URL = (
    "https://opendart.fss.or.kr/api/list.json"
)

DART_CORP_CODE_URL = (
    "https://opendart.fss.or.kr/api/corpCode.xml"
)

CORP_CODE_CACHE_PATH = (
    BASE_DIR
    / "data"
    / "cache"
    / "dart_corp_codes.json"
)

CORP_CODE_CACHE_DAYS = 30


ISSUER_NAME_ALIASES = {
    "삼성자산운용": [
        "삼성자산운용",
    ],
    "미래에셋자산운용": [
        "미래에셋자산운용",
    ],
    "한국투자신탁운용": [
        "한국투자신탁운용",
    ],
    "KB자산운용": [
        "KB자산운용",
        "케이비자산운용",
    ],
    "신한자산운용": [
        "신한자산운용",
    ],
    "NH-Amundi자산운용": [
        "NH-Amundi자산운용",
        "NH아문디자산운용",
        "엔에이치아문디자산운용",
    ],
}


ALLOWED_TITLE_SUFFIXES = (
    "증권",
    "상장지수",
    "ETF",
    "투자신탁",
    "집합투자",
    "주식",
    "채권",
    "혼합",
)


def get_api_key():
    load_dotenv(BASE_DIR / ".env")

    api_key = os.getenv("DART_API_KEY")

    if not api_key:
        raise RuntimeError(
            "DART_API_KEY가 설정되지 않았습니다."
        )

    return api_key


def normalize_name(text):
    """띄어쓰기와 특수문자를 제외하고 비교합니다."""

    return "".join(
        character
        for character in str(text or "").upper()
        if character.isalnum()
    )


def normalize_company_name(text):
    """회사명 비교에 불필요한 법인 표현을 제거합니다."""

    converted = str(text or "")

    for removable in (
        "주식회사",
        "(주)",
        "㈜",
    ):
        converted = converted.replace(
            removable,
            "",
        )

    return normalize_name(converted)


def title_matches_etf(title, etf_name):
    """
    공시 제목에 ETF 상품명이 정확히 포함되는지 확인합니다.

    KODEX 200타겟처럼 이름 일부만 같은 다른 상품이
    KODEX 200으로 잘못 조회되지 않도록 뒤쪽 표현도 확인합니다.
    """

    title_key = normalize_name(title)
    etf_key = normalize_name(etf_name)

    if not etf_key or etf_key not in title_key:
        return False

    following = title_key.split(
        etf_key,
        1,
    )[1]

    if not following:
        return True

    return following.startswith(
        ALLOWED_TITLE_SUFFIXES
    )


def _cache_is_valid(cache_data):
    downloaded_at = cache_data.get(
        "downloaded_at"
    )

    companies = cache_data.get("companies")

    if (
        not downloaded_at
        or not isinstance(companies, list)
    ):
        return False

    try:
        downloaded_datetime = (
            datetime.fromisoformat(downloaded_at)
        )

    except ValueError:
        return False

    if downloaded_datetime.tzinfo is None:
        return False

    cache_age = (
        seoul_now() - downloaded_datetime
    )

    return cache_age < timedelta(
        days=CORP_CODE_CACHE_DAYS
    )


def _read_corp_code_cache():
    if not CORP_CODE_CACHE_PATH.exists():
        return None

    try:
        with CORP_CODE_CACHE_PATH.open(
            "r",
            encoding="utf-8",
        ) as cache_file:
            cache_data = json.load(cache_file)

    except (
        OSError,
        json.JSONDecodeError,
    ):
        return None

    if not _cache_is_valid(cache_data):
        return None

    return cache_data["companies"]


def _write_corp_code_cache(companies):
    CORP_CODE_CACHE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    cache_data = {
        "downloaded_at": (
            seoul_now().isoformat()
        ),
        "companies": companies,
    }

    temporary_path = (
        CORP_CODE_CACHE_PATH.with_suffix(
            ".tmp"
        )
    )

    with temporary_path.open(
        "w",
        encoding="utf-8",
    ) as cache_file:
        json.dump(
            cache_data,
            cache_file,
            ensure_ascii=False,
        )

    temporary_path.replace(
        CORP_CODE_CACHE_PATH
    )


def _download_corp_codes(api_key):
    try:
        response = requests.get(
            DART_CORP_CODE_URL,
            params={
                "crtfc_key": api_key,
            },
            timeout=30,
        )

        response.raise_for_status()

        with ZipFile(
            BytesIO(response.content)
        ) as archive:
            xml_name = next(
                name
                for name in archive.namelist()
                if name.lower().endswith(".xml")
            )

            root = ET.fromstring(
                archive.read(xml_name)
            )

    except (
        requests.RequestException,
        BadZipFile,
        StopIteration,
        ET.ParseError,
    ) as error:
        raise RuntimeError(
            "DART 회사 고유번호 조회 실패: "
            f"{type(error).__name__}"
        ) from None

    companies = []

    for company in root.findall("list"):
        corp_name = company.findtext(
            "corp_name"
        )

        corp_code = company.findtext(
            "corp_code"
        )

        if not corp_name or not corp_code:
            continue

        companies.append(
            {
                "corp_name": corp_name,
                "corp_code": corp_code,
            }
        )

    if not companies:
        raise RuntimeError(
            "DART 회사 고유번호 목록이 비어 있습니다."
        )

    _write_corp_code_cache(companies)

    return companies


@lru_cache(maxsize=1)
def get_cached_corp_codes():
    """
    메모리 캐시를 먼저 사용합니다.

    프로그램을 다시 실행한 경우에는 로컬 JSON 캐시를 확인하고,
    캐시가 없거나 30일이 지난 경우에만 DART에서 다시 받습니다.
    """

    cached_companies = (
        _read_corp_code_cache()
    )

    if cached_companies is not None:
        return tuple(
            (
                company["corp_name"],
                company["corp_code"],
            )
            for company in cached_companies
        )

    api_key = get_api_key()

    downloaded_companies = (
        _download_corp_codes(api_key)
    )

    return tuple(
        (
            company["corp_name"],
            company["corp_code"],
        )
        for company in downloaded_companies
    )


def find_issuer_corp_code(asset_manager):
    """
    상품 DB에서 확인한 운용사명으로 DART 고유번호를 찾습니다.
    """

    if not asset_manager:
        raise RuntimeError(
            "ETF 상품 DB에 운용사 정보가 없습니다."
        )

    aliases = ISSUER_NAME_ALIASES.get(
        asset_manager,
        [asset_manager],
    )

    normalized_aliases = {
        normalize_company_name(alias)
        for alias in aliases
    }

    for corp_name, corp_code in (
        get_cached_corp_codes()
    ):
        normalized_corp_name = (
            normalize_company_name(corp_name)
        )

        if (
            normalized_corp_name
            in normalized_aliases
        ):
            return {
                "corp_code": corp_code,
                "corp_name": corp_name,
            }

    raise RuntimeError(
        f"DART에서 '{asset_manager}'의 "
        "회사 고유번호를 찾지 못했습니다."
    )


def find_etf_disclosure_titles(
    etf_name,
    asset_manager,
    max_pages=10,
    limit=3,
    search_days=90,
):
    """
    상품 DB에서 확인한 ETF 상품명과 운용사를 이용하여
    최근 DART 펀드 공시 제목을 검색합니다.
    """

    canonical_name = str(
        etf_name or ""
    ).strip()

    manager_name = str(
        asset_manager or ""
    ).strip()

    if not canonical_name:
        raise ValueError(
            "ETF 상품명이 없습니다."
        )

    if not manager_name:
        raise ValueError(
            "ETF 운용사 정보가 없습니다."
        )

    api_key = get_api_key()

    issuer = find_issuer_corp_code(
        manager_name
    )

    today = seoul_today()

    start = today - timedelta(
        days=search_days - 1
    )

    matches = []
    total_pages = 0
    scanned_pages = 0
    no_data_response = False
    stopped_by_limit = False

    for page_no in range(
        1,
        max_pages + 1,
    ):
        try:
            response = requests.get(
                DART_LIST_URL,
                params={
                    "crtfc_key": api_key,
                    "corp_code": issuer[
                        "corp_code"
                    ],
                    "bgn_de": start.strftime(
                        "%Y%m%d"
                    ),
                    "end_de": today.strftime(
                        "%Y%m%d"
                    ),
                    "pblntf_ty": "G",
                    "sort": "date",
                    "sort_mth": "desc",
                    "page_no": page_no,
                    "page_count": 100,
                },
                timeout=20,
            )

            response.raise_for_status()

            data = response.json()

        except requests.RequestException as error:
            raise RuntimeError(
                "DART 공시 조회 실패: "
                f"{type(error).__name__}"
            ) from None

        except ValueError:
            raise RuntimeError(
                "DART 공시 응답을 읽지 못했습니다."
            ) from None

        status = data.get("status")

        if status == "013":
            no_data_response = True
            break

        if status != "000":
            raise RuntimeError(
                "DART 조회 오류: "
                f"{status} "
                f"{data.get('message', '')}"
            )

        scanned_pages += 1

        total_pages = int(
            data.get("total_page") or 0
        )

        for item in data.get("list", []):
            title = item.get(
                "report_nm",
                "",
            )

            if not title_matches_etf(
                title,
                canonical_name,
            ):
                continue

            receipt_no = item.get(
                "rcept_no",
                "",
            )

            matches.append(
                {
                    "date": item.get(
                        "rcept_dt",
                        "",
                    ),
                    "company": item.get(
                        "corp_name",
                        "",
                    ),
                    "title": title,
                    "url": (
                        "https://dart.fss.or.kr/"
                        "dsaf001/main.do"
                        f"?rcpNo={receipt_no}"
                    ),
                }
            )

            if len(matches) >= limit:
                stopped_by_limit = True
                break

        if stopped_by_limit:
            break

        if (
            total_pages > 0
            and page_no >= total_pages
        ):
            break

    search_complete = (
        no_data_response
        or (
            total_pages > 0
            and scanned_pages >= total_pages
        )
    )

    if matches:
        result_status = "found"
        result_message = (
            f"{len(matches)}개의 공시 후보를 "
            "찾았습니다."
        )

    elif search_complete:
        result_status = "no_results"
        result_message = (
            "검색을 완료했지만 해당 기간에 "
            "상품명이 일치하는 공시가 없습니다."
        )

    else:
        result_status = "search_incomplete"
        result_message = (
            "정해진 페이지까지 검색했지만 "
            "전체 검색은 완료되지 않았습니다."
        )

    return {
        "etf_name": canonical_name,
        "asset_manager": manager_name,
        "dart_corp_name": issuer[
            "corp_name"
        ],
        "matches": matches,
        "start_date": start.strftime(
            "%Y%m%d"
        ),
        "end_date": today.strftime(
            "%Y%m%d"
        ),
        "scanned_pages": scanned_pages,
        "total_pages": total_pages,
        "search_complete": search_complete,
        "stopped_by_limit": stopped_by_limit,
        "result_status": result_status,
        "result_message": result_message,
    }