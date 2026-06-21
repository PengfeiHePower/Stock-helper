from __future__ import annotations

import re

INVALID_TICKERS = {
    "A", "I", "AI", "US", "UK", "EU", "CEO", "CFO", "IPO", "ETF", "GDP",
    "FED", "SEC", "NYSE", "DOW", "THE", "AND", "FOR", "NEW", "TOP", "ALL",
    "Q1", "Q2", "Q3", "Q4", "PM", "AM", "VS", "IT", "TV", "PC",
    "INC", "CO", "CORP", "LTD", "LLC", "PLC", "SA", "AG", "NV",
    "FORM", "FILED", "ON", "AN", "OR", "AT", "TO", "IN", "OF", "BY",
    "CLASS", "COM", "STOCK", "SHARE", "SHARES", "COMMON", "HOLDING",
}


def is_valid_ticker(ticker: str) -> bool:
    t = ticker.upper().strip()
    if t in INVALID_TICKERS:
        return False
    return bool(re.fullmatch(r"[A-Z]{2,5}", t))
