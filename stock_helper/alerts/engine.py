from __future__ import annotations

import logging
from datetime import date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

from stock_helper.collectors.ingest import ingest_watchlist_news, load_news_since
from stock_helper.collectors.market import fetch_quotes
from stock_helper.config import get_settings, load_yaml, telegram_brief_configured
from stock_helper.storage.db import AlertRecord, get_session
from stock_helper.watchlist import all_watchlist_tickers

logger = logging.getLogger(__name__)

_poll_counter = 0
_VIX_SYMBOLS = ("VIX", "^VIX", "$VIX")


def load_alert_config() -> dict[str, Any]:
    return load_yaml("alerts.yaml")


def is_alert_window(now: datetime | None = None) -> bool:
    cfg = load_alert_config()
    if not cfg.get("enabled", True):
        return False

    hours = cfg.get("market_hours") or {}
    if not hours.get("enabled", True):
        return True

    tz_name = hours.get("timezone") or get_settings().brief_timezone
    tz = ZoneInfo(tz_name)
    now = now or datetime.now(tz)
    if now.weekday() not in (hours.get("weekdays") or [0, 1, 2, 3, 4]):
        return False

    start_parts = (hours.get("start") or "07:00").split(":")
    end_parts = (hours.get("end") or "20:00").split(":")
    start = time(int(start_parts[0]), int(start_parts[1]))
    end = time(int(end_parts[0]), int(end_parts[1]))
    return start <= now.time() <= end


def _already_sent(dedupe_key: str) -> bool:
    session = get_session()
    exists = (
        session.query(AlertRecord)
        .filter(AlertRecord.dedupe_key == dedupe_key)
        .first()
    )
    session.close()
    return exists is not None


def _record_alert(dedupe_key: str, alert_type: str, message: str) -> None:
    session = get_session()
    if session.query(AlertRecord).filter(AlertRecord.dedupe_key == dedupe_key).first():
        session.close()
        return
    session.add(
        AlertRecord(
            dedupe_key=dedupe_key,
            alert_type=alert_type,
            message=message[:2000],
        )
    )
    session.commit()
    session.close()


def send_telegram_alert(message: str) -> bool:
    if not telegram_brief_configured():
        return False
    try:
        from stock_helper.outputs.telegram_bot import TelegramClient

        settings = get_settings()
        client = TelegramClient()
        client.send_message(settings.telegram_chat_id, message)
        return True
    except Exception as e:
        logger.warning("Telegram alert failed: %s", e)
        return False


def _dispatch(alerts: list[tuple[str, str, str]]) -> int:
    sent = 0
    for dedupe_key, alert_type, message in alerts:
        if _already_sent(dedupe_key):
            continue
        if send_telegram_alert(message):
            _record_alert(dedupe_key, alert_type, message)
            sent += 1
    return sent


def _price_rules(cfg: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rules: dict[str, dict[str, Any]] = {}
    default_pct = float((cfg.get("price") or {}).get("default_move_pct") or 5.0)
    for item in (cfg.get("price") or {}).get("rules") or []:
        symbol = (item.get("symbol") or "").upper()
        if not symbol:
            continue
        rules[symbol] = {
            "move_pct": float(item.get("move_pct", default_pct)),
            "direction": (item.get("direction") or "both").lower(),
        }
    return rules


def _quote_symbols(rules: dict[str, dict[str, Any]]) -> list[str]:
    symbols = set(all_watchlist_tickers(include_agent=True))
    symbols.update(rules.keys())
    for vix_sym in _VIX_SYMBOLS:
        if "VIX" in rules:
            symbols.add(vix_sym)
            break
    return sorted(symbols)


def _resolve_quote(symbol: str, by_symbol: dict[str, dict]) -> dict | None:
    sym = symbol.upper()
    if sym == "VIX":
        for alt in _VIX_SYMBOLS:
            quote = by_symbol.get(alt.upper()) or by_symbol.get(alt)
            if quote:
                return quote
        return None
    return by_symbol.get(sym)


def check_price_alerts(cfg: dict[str, Any] | None = None) -> list[tuple[str, str, str]]:
    cfg = cfg or load_alert_config()
    rules = _price_rules(cfg)
    default_pct = float((cfg.get("price") or {}).get("default_move_pct") or 5.0)
    today = date.today().isoformat()
    alerts: list[tuple[str, str, str]] = []

    symbols = _quote_symbols(rules)
    quotes = fetch_quotes(symbols)
    by_symbol = {q["symbol"].upper(): q for q in quotes}
    for q in quotes:
        by_symbol[q["symbol"]] = q

    watch = set(all_watchlist_tickers(include_agent=True))
    targets = sorted(watch | set(rules.keys()))

    for symbol in targets:
        quote = _resolve_quote(symbol, by_symbol)
        if not quote:
            continue

        rule = rules.get(symbol.upper(), rules.get("VIX", {}))
        threshold = float(rule.get("move_pct", default_pct))
        direction = rule.get("direction", "both")
        change = float(quote.get("change_pct") or 0.0)

        if direction == "up" and change < threshold:
            continue
        if direction == "down" and change > -threshold:
            continue
        if direction == "both" and abs(change) < threshold:
            continue

        move_dir = "up" if change >= 0 else "down"
        dedupe_key = f"price:{symbol.upper()}:{today}:{move_dir}"
        sign = "+" if change >= 0 else ""
        emoji = "🔺" if change >= 0 else "🔻"
        message = (
            f"{emoji} Price alert — {symbol.upper()}\n"
            f"{sign}{change:.2f}% today · ${quote.get('price', 0):.2f}\n"
            f"Threshold: {threshold:.1f}%"
        )
        alerts.append((dedupe_key, "price", message))

    return alerts


def _is_material_news(item: dict[str, Any], cfg: dict[str, Any]) -> tuple[bool, str]:
    news_cfg = cfg.get("news") or {}
    source = (item.get("source") or "").lower()
    event_type = (item.get("event_type") or "").lower().replace("-", "_")
    headline = (item.get("headline") or "").lower()

    if source == "sec_edgar":
        for form in news_cfg.get("sec_forms") or ["8-K"]:
            token = form.lower().replace("-", "_")
            if token in event_type or form.lower() in headline:
                return True, f"SEC {form}"

    if event_type in {t.lower() for t in (news_cfg.get("classified_types") or [])}:
        return True, event_type.replace("_", " ")

    for kw in news_cfg.get("material_keywords") or []:
        if kw.lower() in headline:
            return True, kw

    return False, ""


def check_news_alerts(
    cfg: dict[str, Any] | None = None,
    since: datetime | None = None,
) -> list[tuple[str, str, str]]:
    cfg = cfg or load_alert_config()
    if since is None:
        since = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    alerts: list[tuple[str, str, str]] = []
    for item in load_news_since(since, limit=50):
        external_id = item.get("external_id")
        if not external_id:
            continue
        dedupe_key = f"news:{external_id}"
        if _already_sent(dedupe_key):
            continue

        material, reason = _is_material_news(item, cfg)
        if not material:
            continue

        tickers = item.get("tickers") or "?"
        headline = item.get("headline") or "News update"
        tag = "📄 SEC" if (item.get("source") or "") == "sec_edgar" else "📰"
        message = (
            f"{tag} News alert — {reason}\n"
            f"[{tickers}] {headline[:240]}"
        )
        url = item.get("url")
        if url:
            message += f"\n{url}"
        alerts.append((dedupe_key, "news", message))

    return alerts


def run_alert_cycle(force: bool = False) -> int:
    global _poll_counter

    cfg = load_alert_config()
    if not cfg.get("enabled", True):
        return 0
    if not force and not is_alert_window():
        return 0
    if not telegram_brief_configured():
        return 0

    _poll_counter += 1
    ingest_every = int(cfg.get("news_ingest_every_n_polls") or 3)
    since = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    if force or _poll_counter % ingest_every == 1:
        try:
            added = ingest_watchlist_news()
            if added:
                logger.info("Alert ingest added %s news items", added)
        except Exception as e:
            logger.warning("Alert ingest failed: %s", e)

    alerts: list[tuple[str, str, str]] = []
    alerts.extend(check_price_alerts(cfg))
    alerts.extend(check_news_alerts(cfg, since=since))
    sent = _dispatch(alerts)
    if sent:
        logger.info("Sent %s Telegram alert(s)", sent)
    return sent
