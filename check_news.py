"""뉴스 도구 점검: 실제 Google 뉴스 RSS를 호출합니다 (API 키 불필요)."""
import json
from unittest.mock import patch

import requests

from news_tools import search_etf_news


def show(title, etf_name):
    print("=" * 70)
    print(title, "→", repr(etf_name))
    result = json.loads(search_etf_news.invoke({"etf_name": etf_name}))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def check_title_matching():
    from news_api import title_mentions_etf

    assert title_mentions_etf("KODEX 200 2% 상승…코스피 강세", "KODEX 200")
    assert title_mentions_etf("kodex200, 거래대금 1위", "KODEX 200")
    assert not title_mentions_etf("KODEX 200타겟위클리커버드콜 1.93% 하락", "KODEX 200")
    assert not title_mentions_etf("KODEX 2000 신규 상장", "KODEX 200")
    assert title_mentions_etf("TIGER 미국S&P500 1% 하락", "TIGER 미국S&P500")
    print("제목 매칭 점검 통과")


def check_link_tokens():
    from news_api import register_news_link, resolve_news_links

    url = "https://news.google.com/rss/articles/ABC?oc=5"
    token = register_news_link(url)
    assert resolve_news_links(f"- [제목]({token}) · 언론사") == f"- [제목]({url}) · 언론사"
    # 모르는(지어낸) 표시는 링크 없이 제목만 남깁니다.
    assert resolve_news_links("- [제목](NEWS_LINK_00000000)") == "- 제목"
    print("링크 표시 점검 통과")


def main():
    check_title_matching()
    check_link_tokens()

    # 1. 정상: 기사가 있어야 함
    result = show("정상 질문", "KODEX 200")
    assert result["success"], result
    assert result["articles"], result

    # 2. 정상: 다른 상품
    show("다른 상품", "TIGER 미국S&P500")

    # 3. 오류: 존재하지 않는 상품 → 실패 메시지
    result = show("없는 상품", "달토끼 우주여행 ETF")
    assert not result["success"], result

    # 4. 오류: 빈 입력
    result = show("빈 입력", "   ")
    assert not result["success"], result

    # 5. 오류: 네트워크 장애 → 기술 오류 원문이 노출되지 않아야 함
    with patch("news_api.requests.get", side_effect=requests.ConnectionError("secret detail")):
        result = show("네트워크 장애", "KODEX 200")
    assert not result["success"], result
    assert "secret detail" not in result["message"], result

    print("=" * 70)
    print("모든 점검 통과")


if __name__ == "__main__":
    main()
