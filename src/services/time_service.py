from datetime import datetime
from zoneinfo import ZoneInfo


SEOUL_TIMEZONE = ZoneInfo("Asia/Seoul")


def seoul_now():
    """현재 한국 표준시를 반환합니다."""
    return datetime.now(SEOUL_TIMEZONE)


def seoul_today():
    """한국 표준시 기준 오늘 날짜를 반환합니다."""
    return seoul_now().date()