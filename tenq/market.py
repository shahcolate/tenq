"""Optional market-data garnish via yfinance.

Market data is deliberately optional (`pip install tenq[market]`): the core of
tenq is filings-grounded, and everything in the filed-financials table comes
from SEC XBRL with exact values. This module only adds current price context.
"""

from __future__ import annotations


def snapshot(ticker: str) -> dict | None:
    """Return a small dict of market context, or None if unavailable."""
    try:
        import yfinance  # type: ignore
    except ImportError:
        return None
    try:
        info = yfinance.Ticker(ticker).info or {}
    except Exception:
        return None
    fields = {
        "price": info.get("currentPrice") or info.get("regularMarketPrice"),
        "market_cap": info.get("marketCap"),
        "trailing_pe": info.get("trailingPE"),
        "forward_pe": info.get("forwardPE"),
        "52w_low": info.get("fiftyTwoWeekLow"),
        "52w_high": info.get("fiftyTwoWeekHigh"),
    }
    result = {k: v for k, v in fields.items() if v is not None}
    return result or None
