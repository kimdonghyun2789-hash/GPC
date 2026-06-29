"""
utils/date_utils.py
날짜/요일 관련 공통 유틸리티.
- 오늘 날짜, 한글 요일, 월(year_month) 문자열, 영업요일 판별, 남은 근무일 계산 등을 제공한다.
"""

from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta

# 파이썬 weekday(): 월=0 ~ 일=6
_KOR_WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]


def today() -> date:
    """오늘 날짜(date)를 반환한다."""
    return date.today()


def to_date(value) -> date:
    """문자열/None/date를 date로 변환한다. None이면 오늘 날짜."""
    if value is None:
        return today()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    # 문자열 처리 (YYYY-MM-DD)
    return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()


def korean_weekday(d=None) -> str:
    """한글 요일 한 글자를 반환한다. (예: '월')"""
    d = to_date(d)
    return _KOR_WEEKDAYS[d.weekday()]


def format_korean_date(d=None) -> str:
    """'2026-06-29 월요일' 형식으로 반환한다."""
    d = to_date(d)
    return f"{d.isoformat()} {korean_weekday(d)}요일"


def year_month(d=None) -> str:
    """'YYYY-MM' 형식의 월 문자열을 반환한다."""
    d = to_date(d)
    return d.strftime("%Y-%m")


def is_open_today(open_days: str, d=None) -> bool:
    """
    영업요일 문자열('월,화,수,목,금')을 기준으로 해당 날짜에 영업하는지 판별한다.
    open_days가 비어 있으면 항상 영업으로 간주한다.
    """
    if not open_days:
        return True
    wd = korean_weekday(d)
    tokens = [t.strip() for t in str(open_days).replace("/", ",").split(",") if t.strip()]
    if not tokens:
        return True
    return wd in tokens


def days_between(d1, d2) -> int:
    """두 날짜 사이의 일수 차이(절대값)를 반환한다."""
    return abs((to_date(d1) - to_date(d2)).days)


def remaining_workdays(d=None) -> int:
    """
    해당 날짜가 속한 달에서 오늘 포함 남은 평일(월~금) 수를 계산한다.
    예산 조언(소진 속도 추정)에 사용한다.
    """
    d = to_date(d)
    _, last_day = calendar.monthrange(d.year, d.month)
    count = 0
    cur = d
    end = date(d.year, d.month, last_day)
    while cur <= end:
        if cur.weekday() < 5:  # 월~금
            count += 1
        cur += timedelta(days=1)
    return count


def workdays_elapsed(d=None) -> int:
    """해당 날짜가 속한 달에서 1일부터 오늘(포함)까지의 평일 수."""
    d = to_date(d)
    count = 0
    cur = date(d.year, d.month, 1)
    while cur <= d:
        if cur.weekday() < 5:
            count += 1
        cur += timedelta(days=1)
    return count


def month_range(year_month_str: str):
    """'YYYY-MM' 문자열을 받아 (월 첫날, 월 마지막날) date 튜플을 반환한다."""
    y, m = (int(x) for x in year_month_str.split("-"))
    _, last_day = calendar.monthrange(y, m)
    return date(y, m, 1), date(y, m, last_day)
