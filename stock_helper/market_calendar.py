from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from stock_helper.collectors.finnhub import FinnhubClient
from stock_helper.config import get_settings

logger = logging.getLogger(__name__)

_FULL_HOLIDAYS: set[date] | None = None
_HOLIDAYS_FETCHED_AT: datetime | None = None
_HOLIDAYS_TTL = timedelta(hours=24)


def _today_in_market_tz(now: datetime | None = None) -> date:
    tz = ZoneInfo(get_settings().brief_timezone)
    return (now or datetime.now(tz)).date()


def _load_full_holidays() -> set[date]:
    global _FULL_HOLIDAYS, _HOLIDAYS_FETCHED_AT

    now = datetime.utcnow()
    if (
        _FULL_HOLIDAYS is not None
        and _HOLIDAYS_FETCHED_AT is not None
        and now - _HOLIDAYS_FETCHED_AT < _HOLIDAYS_TTL
    ):
        return _FULL_HOLIDAYS

    holidays: set[date] = set()
    try:
        payload = FinnhubClient().market_holidays("US")
        for item in payload.get("data") or []:
            at_date = item.get("atDate")
            trading_hour = (item.get("tradingHour") or "").strip()
            if not at_date or trading_hour:
                continue
            holidays.add(date.fromisoformat(at_date))
        _FULL_HOLIDAYS = holidays
        _HOLIDAYS_FETCHED_AT = now
        return holidays
    except Exception as e:
        logger.warning("Finnhub market-holiday fetch failed: %s", e)
        if _FULL_HOLIDAYS is not None:
            return _FULL_HOLIDAYS
        return set()


def is_us_trading_day(on: date | None = None, *, now: datetime | None = None) -> bool:
    """True when NYSE has a regular or early-close session (not weekend/full holiday)."""
    day = on or _today_in_market_tz(now)
    if day.weekday() >= 5:
        return False
    return day not in _load_full_holidays()


def trading_day_skip_reason(on: date | None = None, *, now: datetime | None = None) -> str:
    day = on or _today_in_market_tz(now)
    if day.weekday() >= 5:
        return f"{day.isoformat()} is a weekend"
    if day in _load_full_holidays():
        return f"{day.isoformat()} is a US market holiday"
    return f"{day.isoformat()} is a US trading day"


def is_first_trading_day_of_month(on: date | None = None, *, now: datetime | None = None) -> bool:
    """True if `on` is the first US trading session of its calendar month."""
    day = on or _today_in_market_tz(now)
    if not is_us_trading_day(day, now=now):
        return False
    probe = day.replace(day=1)
    while probe < day:
        if is_us_trading_day(probe):
            return False
        probe += timedelta(days=1)
    return True


def _first_trading_on_or_after(day_of_month: int, ref: date) -> date | None:
    """First US trading day on or after day_of_month within ref's calendar month."""
    try:
        start = ref.replace(day=day_of_month)
    except ValueError:
        return None
    probe = start
    for _ in range(12):
        if probe.month != ref.month:
            return None
        if is_us_trading_day(probe):
            return probe
        probe += timedelta(days=1)
    return None


def is_biweekly_trading_anchor(on: date | None = None, *, now: datetime | None = None) -> bool:
    """First trading day on/after the 1st or 15th (biweekly pulse)."""
    day = on or _today_in_market_tz(now)
    if not is_us_trading_day(day, now=now):
        return False
    for anchor in (1, 15):
        first = _first_trading_on_or_after(anchor, day)
        if first == day:
            return True
    return False
