from __future__ import annotations

from datetime import date, datetime, timedelta

import pandas as pd
import yfinance as yf
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import SecurityPriceDaily


RANGE_TO_DAYS: dict[str, int] = {
    "1D": 2,
    "1W": 8,
    "1M": 31,
    "3M": 92,
    "6M": 183,
    "1Y": 366,
    "3Y": 366 * 3,
    "5Y": 366 * 5,
    "10Y": 366 * 10,
}


def _to_close_series(raw: pd.DataFrame, symbol: str) -> pd.Series:
    if raw.empty:
        return pd.Series(dtype=float, name=symbol)

    if isinstance(raw.columns, pd.MultiIndex):
        if ("Close", symbol) in raw.columns:
            close = raw[("Close", symbol)]
        elif "Close" in raw.columns.get_level_values(0):
            close = raw["Close"].iloc[:, 0]
        else:
            return pd.Series(dtype=float, name=symbol)
    else:
        close = raw.get("Close")
        if close is None:
            return pd.Series(dtype=float, name=symbol)

    close = pd.to_numeric(close, errors="coerce").dropna()
    close.name = symbol
    return close


def fetch_and_cache_history(db: Session, symbol: str, start_date: date, end_date: date) -> pd.Series:
    symbol = symbol.upper()

    try:
        raw = yf.download(
            symbol,
            start=start_date.isoformat(),
            end=(end_date + timedelta(days=1)).isoformat(),
            progress=False,
            auto_adjust=True,
        )
    except Exception:
        raw = pd.DataFrame()

    close_series = _to_close_series(raw, symbol)
    if not close_series.empty:
        now = datetime.utcnow()
        for ts, close in close_series.items():
            px_date = pd.to_datetime(ts).date()
            row = db.get(SecurityPriceDaily, (symbol, px_date))
            if row is None:
                row = SecurityPriceDaily(
                    symbol=symbol,
                    date=px_date,
                    close=float(close),
                    adj_close=float(close),
                    source="yfinance",
                    fetched_at=now,
                )
                db.add(row)
            else:
                row.close = float(close)
                row.adj_close = float(close)
                row.fetched_at = now
        db.flush()

    cached_rows = db.scalars(
        select(SecurityPriceDaily)
        .where(SecurityPriceDaily.symbol == symbol)
        .where(SecurityPriceDaily.date >= start_date)
        .where(SecurityPriceDaily.date <= end_date)
        .order_by(SecurityPriceDaily.date.asc())
    ).all()

    if not cached_rows:
        return pd.Series(dtype=float, name=symbol)

    idx = [row.date for row in cached_rows]
    vals = [row.adj_close for row in cached_rows]
    series = pd.Series(vals, index=pd.to_datetime(idx), name=symbol)
    return series.sort_index()


def get_latest_close(db: Session, symbol: str) -> float | None:
    symbol = symbol.upper()
    row = db.scalar(
        select(SecurityPriceDaily)
        .where(SecurityPriceDaily.symbol == symbol)
        .order_by(SecurityPriceDaily.date.desc())
        .limit(1)
    )
    if row is not None:
        return float(row.adj_close)

    end_date = date.today()
    start_date = end_date - timedelta(days=45)
    series = fetch_and_cache_history(db, symbol, start_date, end_date)
    if series.empty:
        return None
    return float(series.iloc[-1])


def get_symbols_price_frame(db: Session, symbols: list[str], start_date: date, end_date: date) -> pd.DataFrame:
    if not symbols:
        return pd.DataFrame()

    series_list: list[pd.Series] = []
    for sym in sorted({s.upper() for s in symbols}):
        s = fetch_and_cache_history(db, sym, start_date, end_date)
        if not s.empty:
            series_list.append(s)

    if not series_list:
        return pd.DataFrame()

    frame = pd.concat(series_list, axis=1).sort_index()
    frame = frame.ffill().dropna(how="all")
    return frame
