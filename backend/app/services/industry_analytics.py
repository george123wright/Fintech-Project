from __future__ import annotations

from datetime import date, datetime
from time import sleep
from typing import Literal

import numpy as np
import pandas as pd
import yfinance as yf


_MAX_RETRIES = 3
_RETRY_DELAY_SECONDS = 0.35
AggregationMethod = Literal["equal_weight_returns", "cap_weight_returns", "rebased_price_index"]


def _normalize_tickers(tickers: list[str] | tuple[str, ...] | set[str]) -> list[str]:
    normalized = [str(t).strip().upper() for t in tickers if str(t).strip()]
    # Preserve stable order while removing duplicates.
    return list(dict.fromkeys(normalized))


def resolve_industry_ticker_map(industry_slugs: list[str]) -> dict[str, str]:
    """Resolve a mapping of representative ETF/industry ticker -> industry slug.

    Uses yfinance's ``Industry(...).ticker.ticker`` pathway with retries and
    defensive handling around transient network/API parsing failures.
    """
    ticker_to_slug: dict[str, str] = {}

    for slug in list(dict.fromkeys(industry_slugs)):
        if not slug:
            continue

        ticker: str | None = None
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                candidate = yf.Industry(slug).ticker.ticker
                if isinstance(candidate, str) and candidate.strip():
                    ticker = candidate.strip().upper()
                    break
            except Exception:
                if attempt < _MAX_RETRIES:
                    sleep(_RETRY_DELAY_SECONDS)

        if ticker and ticker not in ticker_to_slug:
            ticker_to_slug[ticker] = slug

    return ticker_to_slug


def _extract_close_frame(raw: pd.DataFrame, normalized_tickers: list[str]) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame(columns=normalized_tickers, dtype=float)

    if isinstance(raw.columns, pd.MultiIndex):
        if "Close" not in raw.columns.get_level_values(0):
            return pd.DataFrame(columns=normalized_tickers, dtype=float)
        close = raw["Close"]
    else:
        if "Close" in raw.columns:
            close = raw[["Close"]]
        else:
            close = raw

    if isinstance(close, pd.Series):
        symbol = normalized_tickers[0] if normalized_tickers else close.name
        close = close.to_frame(name=symbol)

    close = close.apply(pd.to_numeric, errors="coerce")
    close.columns = [str(col).strip().upper() for col in close.columns]
    if normalized_tickers:
        close = close.reindex(columns=normalized_tickers)

    close.index = pd.to_datetime(close.index)
    return close.sort_index().dropna(how="all")


def fetch_industry_price_panel(
    tickers: list[str] | tuple[str, ...] | set[str],
    start: date | datetime | str,
    end: date | datetime | str,
    auto_adjust: bool = True,
) -> pd.DataFrame:
    """Download close prices for industry tickers in a normalized panel format."""
    normalized_tickers = _normalize_tickers(tickers)
    if not normalized_tickers:
        return pd.DataFrame(dtype=float)

    try:
        raw = yf.download(
            normalized_tickers,
            start=start,
            end=end,
            auto_adjust=auto_adjust,
            progress=False,
            group_by="column",
            threads=False,
        )
    except Exception:
        return pd.DataFrame(columns=normalized_tickers, dtype=float)

    return _extract_close_frame(raw, normalized_tickers)


def map_tickers_to_display_industries(
    df: pd.DataFrame,
    ticker_to_slug: dict[str, str],
    slug_to_display: dict[str, str],
) -> pd.DataFrame:
    """Rename panel columns from ticker -> slug -> display."""
    if df.empty:
        return df.copy()

    working = df.copy()
    ticker_stage = {
        col: ticker_to_slug.get(str(col).strip().upper(), str(col).strip().upper())
        for col in working.columns
    }
    working = working.rename(columns=ticker_stage)

    slug_stage = {col: slug_to_display.get(str(col), str(col)) for col in working.columns}
    working = working.rename(columns=slug_stage)

    return working


def aggregate_industry_panel(
    prices: pd.DataFrame,
    ticker_to_industry: dict[str, str],
    method: AggregationMethod = "equal_weight_returns",
    market_caps: dict[str, float] | None = None,
) -> tuple[pd.DataFrame, dict[str, str]]:
    """Aggregate same-industry tickers with an explicit methodology.

    Expected input: columns are ticker symbols, rows are dates, values are prices.
    """
    if prices.empty:
        return pd.DataFrame(dtype=float), {
            "aggregation_method": method,
            "series_type": "returns" if method != "rebased_price_index" else "index_level",
        }

    panel = prices.copy()
    panel.index = pd.to_datetime(panel.index)
    panel = panel.sort_index()
    panel = panel[~panel.index.duplicated(keep="last")]
    panel = panel.apply(pd.to_numeric, errors="coerce").ffill()
    panel.columns = [str(col).strip().upper() for col in panel.columns]

    industry_labels = [ticker_to_industry.get(col, col) for col in panel.columns]

    if method == "equal_weight_returns":
        returns = panel.pct_change(fill_method=None)
        returns.columns = industry_labels
        aggregated = returns.T.groupby(level=0).mean().T
        return (
            aggregated.dropna(axis=0, how="all").dropna(axis=1, how="all").astype(float),
            {"aggregation_method": method, "series_type": "returns"},
        )

    if method == "cap_weight_returns":
        returns = panel.pct_change(fill_method=None)
        safe_caps = {str(k).strip().upper(): float(v) for k, v in (market_caps or {}).items() if float(v) > 0}
        out: dict[str, pd.Series] = {}
        by_industry: dict[str, list[str]] = {}
        for ticker, industry in zip(panel.columns, industry_labels):
            by_industry.setdefault(str(industry), []).append(str(ticker))
        for industry, members in by_industry.items():
            industry_returns = returns.loc[:, members]
            cap_vec = pd.Series([safe_caps.get(sym, 0.0) for sym in members], index=members)
            if cap_vec.sum() <= 0:
                out[str(industry)] = industry_returns.mean(axis=1, skipna=True)
                continue

            def _weighted_row(row: pd.Series) -> float | None:
                valid = row.notna()
                if not valid.any():
                    return None
                active_caps = cap_vec[valid]
                if active_caps.sum() <= 0:
                    return float(row[valid].mean())
                weights = active_caps / active_caps.sum()
                return float((row[valid] * weights).sum())

            out[str(industry)] = industry_returns.apply(_weighted_row, axis=1)

        aggregated = pd.DataFrame(out, index=returns.index)
        return (
            aggregated.dropna(axis=0, how="all").dropna(axis=1, how="all").astype(float),
            {"aggregation_method": method, "series_type": "returns"},
        )

    rebased = panel.divide(panel.ffill().bfill().iloc[0]).mul(100.0)
    rebased.columns = industry_labels
    aggregated = rebased.T.groupby(level=0).mean().T
    return (
        aggregated.dropna(axis=0, how="all").dropna(axis=1, how="all").astype(float),
        {"aggregation_method": "rebased_price_index", "series_type": "index_level"},
    )


def clean_returns_panel(prices: pd.DataFrame) -> pd.DataFrame:
    """Compute a cleaned returns panel from a prices panel.

    - Coerces values to numeric
    - Sorts and forward-fills prices
    - Computes period-over-period returns
    - Removes infinities and all-null rows/columns
    """
    if prices.empty:
        return pd.DataFrame(dtype=float)

    panel = prices.copy()
    panel.index = pd.to_datetime(panel.index)
    panel = panel.sort_index()
    panel = panel[~panel.index.duplicated(keep="last")]
    panel = panel.apply(pd.to_numeric, errors="coerce").ffill()

    returns = panel.pct_change(fill_method=None)
    returns = returns.replace([float("inf"), float("-inf")], pd.NA)
    returns = returns.dropna(axis=0, how="all").dropna(axis=1, how="all")
    return returns.astype(float)


def compute_industry_return_metrics(
    returns_panel: pd.DataFrame,
    benchmark_returns: pd.Series | None = None,
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252,
    var_confidence: float = 0.95,
) -> dict[str, dict[str, float | None]]:
    """Compute per-industry risk/return metrics using portfolio-metric conventions."""
    if returns_panel.empty:
        return {}

    panel = returns_panel.copy()
    panel.index = pd.to_datetime(panel.index)
    panel = panel.sort_index().apply(pd.to_numeric, errors="coerce")
    panel = panel.dropna(axis=1, how="all")

    bench = None
    if benchmark_returns is not None and not benchmark_returns.empty:
        bench = pd.to_numeric(benchmark_returns, errors="coerce")
        bench.index = pd.to_datetime(bench.index)
        bench = bench.sort_index().dropna()

    level = float(np.clip(var_confidence, 0.01, 0.999))
    tail_level = 1.0 - level
    rf_period = float((1.0 + max(-0.999, risk_free_rate)) ** (1.0 / periods_per_year) - 1.0)

    def _ann_return(ret: pd.Series) -> float | None:
        cleaned = ret.dropna()
        if len(cleaned) <= 1:
            return None
        growth = float((1.0 + cleaned).prod())
        if growth <= 0:
            return -1.0
        return float(growth ** (periods_per_year / len(cleaned)) - 1.0)

    def _capture_ratio(merged: pd.DataFrame, positive: bool) -> float | None:
        bucket = merged[merged["b"] > 0] if positive else merged[merged["b"] < 0]
        if bucket.empty:
            return None
        bench_mean = float(bucket["b"].mean())
        if abs(bench_mean) <= 1e-12:
            return None
        return float(bucket["p"].mean() / bench_mean)

    out: dict[str, dict[str, float | None]] = {}
    for industry in panel.columns:
        ret = panel[industry].dropna()
        if ret.empty:
            out[str(industry)] = {}
            continue

        periodic_vol = float(ret.std(ddof=1)) if len(ret) > 1 else None
        ann_vol = float(periodic_vol * np.sqrt(periods_per_year)) if periodic_vol is not None else None
        ann_return = _ann_return(ret)

        downside = np.minimum(0.0, ret.to_numpy(dtype=float) - rf_period)
        downside_dev = float(np.sqrt(np.mean(np.square(downside))) * np.sqrt(periods_per_year)) if len(ret) else None

        sharpe = None
        if ann_return is not None and ann_vol and ann_vol > 0:
            sharpe = float((ann_return - risk_free_rate) / ann_vol)

        sortino = None
        if ann_return is not None and downside_dev and downside_dev > 0:
            sortino = float((ann_return - risk_free_rate) / downside_dev)

        q = float(ret.quantile(tail_level)) if len(ret) > 1 else None
        var = float(-q) if q is not None else None
        cvar = None
        if q is not None:
            tail = ret[ret <= q]
            cvar = float(-tail.mean()) if not tail.empty else 0.0

        growth = (1.0 + ret).cumprod()
        running_max = growth.cummax()
        dd = growth / running_max - 1.0
        max_dd = float(dd.min()) if len(dd) else None

        industry_metrics: dict[str, float | None] = {
            "window_return": float((1.0 + ret).prod() - 1.0),
            "volatility_periodic": periodic_vol,
            "volatility_annualized": ann_vol,
            "skewness": float(ret.skew()) if len(ret) > 2 else None,
            "kurtosis": float(ret.kurtosis() + 3.0) if len(ret) > 3 else None,
            "var_95": var,
            "cvar_95": cvar,
            "sharpe": sharpe,
            "sortino": sortino,
            "max_drawdown": max_dd,
            "hit_rate": float((ret > 0).mean()),
        }

        if bench is not None:
            merged = pd.concat([ret.rename("p"), bench.rename("b")], axis=1).dropna()
            if len(merged) >= 2:
                bench_var = float(merged["b"].var(ddof=1))
                beta = float(merged["p"].cov(merged["b"]) / bench_var) if bench_var > 0 else None
                active = merged["p"] - merged["b"]
                te = float(active.std(ddof=1)) if len(active) > 1 else None
                info_ratio = float(active.mean() / te * np.sqrt(periods_per_year)) if te and te > 0 else None

                industry_metrics.update(
                    {
                        "upside_capture": _capture_ratio(merged, positive=True),
                        "downside_capture": _capture_ratio(merged, positive=False),
                        "beta": beta,
                        "tracking_error": te,
                        "information_ratio": info_ratio,
                    }
                )
            else:
                industry_metrics.update(
                    {
                        "upside_capture": None,
                        "downside_capture": None,
                        "beta": None,
                        "tracking_error": None,
                        "information_ratio": None,
                    }
                )
        else:
            industry_metrics.update(
                {
                    "upside_capture": None,
                    "downside_capture": None,
                    "beta": None,
                    "tracking_error": None,
                    "information_ratio": None,
                }
            )

        out[str(industry)] = industry_metrics

    return out
