"""Google 뉴스 RSS에서 ETF 관련 최근 뉴스 제목·언론사·날짜·링크를 가져옵니다.

API 키가 필요 없습니다. 기사 본문은 가져오지 않습니다.
"""
import re
import secrets
import xml.etree.ElementTree as ET
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import requests

from dart_api import normalize_name


GOOGLE_NEWS_RSS_URL = "https://news.google.com/rss/search"
SOURCE_NAME = "Google 뉴스 RSS"
SOURCE_URL = "https://news.google.com/"

KST = timezone(timedelta(hours=9))
MAX_NAME_LENGTH = 50
MAX_ARTICLES = 5

# 구글 뉴스 링크는 300자가 넘어서 LLM이 그대로 옮겨 쓰다 망가뜨립니다.
# 링크 매핑은 서버 전역에 저장하지 않고 상담 요청 안에서만 사용합니다.
LINK_TOKEN_PATTERN = re.compile(r"NEWS_LINK_[0-9a-f]{8}")
MARKDOWN_LINK_PATTERN = re.compile(r"\[([^\]\n]+)\]\(\s*(NEWS_LINK_[0-9a-f]{8})\s*\)")


def tokenize_news_links(articles):
    """기사 목록을 복사해 URL을 요청 범위 토큰으로 바꿉니다."""
    tokenized = deepcopy(articles)
    link_map = {}
    for article in tokenized:
        url = article.get("url")
        if not url:
            continue
        token = f"NEWS_LINK_{secrets.token_hex(4)}"
        while token in link_map:
            token = f"NEWS_LINK_{secrets.token_hex(4)}"
        link_map[token] = url
        article["url"] = token
    return tokenized, link_map


def resolve_news_links(text, link_map):
    """요청 범위 매핑으로 링크 표시를 복원하고 모르는 표시는 지웁니다."""
    link_map = link_map or {}

    def replace_markdown(match):
        url = link_map.get(match.group(2))
        return f"[{match.group(1)}]({url})" if url else match.group(1)

    text = MARKDOWN_LINK_PATTERN.sub(replace_markdown, text)
    return LINK_TOKEN_PATTERN.sub(lambda m: link_map.get(m.group(0), ""), text)
SEARCH_DAYS = (7, 30)  # 7일 안에 기사가 없으면 30일까지 넓혀서 찾습니다.


class NewsFetchError(RuntimeError):
    """뉴스를 가져오지 못했을 때 사용합니다. 메시지는 사용자에게 보여도 안전합니다."""


def clean_etf_name(etf_name):
    """검색어로 쓸 상품명을 정리합니다. 따옴표 등 검색 연산자는 제거합니다."""
    text = " ".join(str(etf_name or "").replace('"', " ").split())
    return text[:MAX_NAME_LENGTH]


def remove_press_suffix(title, press):
    """'기사 제목 - 언론사' 형식에서 끝의 언론사 이름을 뗍니다."""
    suffix = f" - {press}"
    while press and title.endswith(suffix):
        title = title[: -len(suffix)].strip()
    return title


def title_mentions_etf(title, etf_name):
    """
    제목에 상품명이 '그 상품 그대로' 나오는지 확인합니다.

    띄어쓰기 차이는 무시하고, 상품명 바로 뒤에 글자·숫자가 이어지면
    (예: 'KODEX 200타겟위클리커버드콜') 다른 상품으로 봅니다.
    """
    characters = [re.escape(c) for c in etf_name if not c.isspace()]
    if not characters:
        return False
    pattern = r"\s*".join(characters) + r"(?![0-9A-Za-z가-힣])"
    return re.search(pattern, title, flags=re.IGNORECASE) is not None


def parse_published_at(text):
    try:
        published = parsedate_to_datetime(text)
    except (TypeError, ValueError):
        return None
    if published.tzinfo is None:
        published = published.replace(tzinfo=timezone.utc)
    return published.astimezone(KST)


def fetch_rss_items(etf_name, days):
    params = {
        "q": f'"{etf_name}" when:{days}d',
        "hl": "ko",
        "gl": "KR",
        "ceid": "KR:ko",
    }
    try:
        response = requests.get(
            GOOGLE_NEWS_RSS_URL,
            params=params,
            headers={"User-Agent": "Mozilla/5.0 (etf-ai-agent)"},
            timeout=10,
        )
        response.raise_for_status()
        root = ET.fromstring(response.content)
    except (requests.RequestException, ET.ParseError) as error:
        raise NewsFetchError("뉴스 정보를 불러오지 못했습니다.") from error

    return root.findall("./channel/item")


def parse_item(item, etf_name, start, now):
    source = item.find("source")
    press = (source.text or "").strip() if source is not None else ""

    title = remove_press_suffix((item.findtext("title") or "").strip(), press)
    url = (item.findtext("link") or "").strip()
    published = parse_published_at(item.findtext("pubDate"))

    if not title or not url or published is None:
        return None
    # 검색 기간 밖이거나 미래 날짜(시계 오차 1시간 허용)인 기사는 버립니다.
    if published < start or published > now + timedelta(hours=1):
        return None

    return {
        "title": title,
        "press": press or "미확인",
        "published_at": published.strftime("%Y-%m-%d"),
        "url": url,
        "title_mentions_etf": title_mentions_etf(title, etf_name),
        "_published": published,
    }


def find_etf_news(etf_name, limit=MAX_ARTICLES):
    """
    ETF 관련 최근 뉴스를 찾습니다.

    제목에 상품명이 들어간 기사를 먼저, 그다음 최신순으로 정렬합니다.
    """
    etf_name = clean_etf_name(etf_name)
    if not etf_name:
        raise ValueError("조회할 ETF 상품명이 없습니다.")

    now = datetime.now(KST)

    for days in SEARCH_DAYS:
        start = now - timedelta(days=days)
        articles = []
        seen = set()

        for item in fetch_rss_items(etf_name, days):
            article = parse_item(item, etf_name, start, now)
            if article is None:
                continue
            key = (normalize_name(article["title"]), article["press"])
            if key in seen:
                continue
            seen.add(key)
            articles.append(article)

        if articles:
            break

    articles.sort(
        key=lambda a: (a["title_mentions_etf"], a["_published"]),
        reverse=True,
    )
    for article in articles:
        del article["_published"]

    return {
        "etf_name": etf_name,
        "start_date": start.strftime("%Y-%m-%d"),
        "end_date": now.strftime("%Y-%m-%d"),
        "checked_at": now.strftime("%Y-%m-%d %H:%M"),
        "articles": articles[:limit],
    }
