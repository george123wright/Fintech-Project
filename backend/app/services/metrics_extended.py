from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf
from scipy.stats import norm
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models import HoldingsPosition, SecurityAnalystSnapshot, SecurityFundamentalSnapshot
from app.services.pricing import get_symbols_price_frame

TRADING_DAYS = 252
INTERVAL_TO_TRADING_PERIODS: dict[str, int] = {
    "daily": 252,
    "weekly": 52,
    "monthly": 12,
}
WINDOW_PRESET_TO_DAYS: dict[str, int] = {
    "1d": 1,
    "1w": 7,
    "1m": 31,
    "3m": 93,
    "1y": 366,
    "3y": 365 * 3 + 1,
    "5y": 365 * 5 + 2,
    "10y": 365 * 10 + 3,
}

FACTOR_PROXY_SYMBOLS: dict[str, list[str]] = {
    "market": ["SPY"],
    "size": ["IWM", "SPY"],
    "value": ["IWD", "IWF"],
    "momentum": ["MTUM", "SPY"],
    "investment": ["SPLV", "SPHB"],
    "profitability": ["QUAL", "SPY"],
}

MACRO_PROXY_SYMBOLS: dict[str, str] = {
    "rates": "^TNX",
    "oil_prices": "CL=F",
    "inflation": "TIP",
    "gdp": "IWM",
    "retail_spending": "XRT",
    "unemployment": "^VIX",
    "government_spending": "ITA",
    "market": "SPY",
}


@dataclass
class ExtendedMetricResult:
    metrics: dict[str, Any]
    warnings: list[str]


def _to_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(number):
        return None
    return number


def _as_python(value: Any) -> Any:
    if isinstance(value, (np.floating,)):
        number = float(value)
        return number if np.isfinite(number) else None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (pd.Timestamp,)):
        return value.date().isoformat()
    if isinstance(value, (pd.Series,)):
        return {str(k): _as_python(v) for k, v in value.items()}
    if isinstance(value, (dict,)):
        return {str(k): _as_python(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_as_python(v) for v in value]
    if isinstance(value, (np.ndarray,)):
        return [_as_python(v) for v in value.tolist()]
    if isinstance(value, (float,)):
        return value if np.isfinite(value) else None
    return value


def _annualized_return(returns: pd.Series, periods_per_year: int = TRADING_DAYS) -> float | None:
    cleaned = returns.dropna()
    n = len(cleaned)
    if n <= 1:
        return None
    growth = float((1.0 + cleaned).prod())
    if growth <= 0:
        return -1.0
    return float(growth ** (periods_per_year / n) - 1.0)


def _annualized_vol(returns: pd.Series, periods_per_year: int = TRADING_DAYS) -> float | None:
    cleaned = returns.dropna()
    if len(cleaned) <= 1:
        return None
    sigma = float(cleaned.std(ddof=1))
    if not np.isfinite(sigma):
        return None
    return float(sigma * np.sqrt(periods_per_year))


def _drawdown_series(returns: pd.Series) -> pd.Series:
    growth = (1.0 + returns.fillna(0.0)).cumprod()
    running_max = growth.cummax()
    dd = growth / running_max - 1.0
    return dd


def _max_streaks(returns: pd.Series) -> tuple[float | None, int, int]:
    cleaned = returns.dropna()
    if cleaned.empty:
        return None, 0, 0
    is_pos = cleaned > 0
    percent_pos = float(is_pos.mean())

    max_win = 0
    max_loss = 0
    current_win = 0
    current_loss = 0

    for up in is_pos:
        if up:
            current_win += 1
            max_win = max(max_win, current_win)
            current_loss = 0
        else:
            current_loss += 1
            max_loss = max(max_loss, current_loss)
            current_win = 0

    return percent_pos, max_win, max_loss


def _var_metrics(returns: pd.Series) -> dict[str, float | None]:
    cleaned = returns.dropna()
    if len(cleaned) <= 1:
        return {
            "historical_95": None,
            "historical_99": None,
            "cvar_historical_95": None,
            "cvar_historical_99": None,
            "gaussian_95": None,
            "gaussian_99": None,
            "cornish_fisher_95": None,
            "cornish_fisher_99": None,
        }

    mu = float(cleaned.mean())
    sigma = float(cleaned.std(ddof=0))
    skew = float(cleaned.skew()) if np.isfinite(cleaned.skew()) else 0.0
    kurt = float(cleaned.kurtosis()) + 3.0
    if not np.isfinite(kurt):
        kurt = 3.0

    def _hist_var(level: float) -> float:
        q = float(cleaned.quantile(level))
        return float(-q)

    def _hist_cvar(level: float) -> float:
        q = float(cleaned.quantile(level))
        tail = cleaned[cleaned <= q]
        if tail.empty:
            return 0.0
        return float(-tail.mean())

    def _gaussian(level: float) -> float:
        z = float(norm.ppf(level))
        return float(-(mu + z * sigma))

    def _cornish_fisher(level: float) -> float:
        z = float(norm.ppf(level))
        z_cf = (
            z
            + (z**2 - 1.0) * skew / 6.0
            + (z**3 - 3.0 * z) * (kurt - 3.0) / 24.0
            - (2.0 * z**3 - 5.0 * z) * (skew**2) / 36.0
        )
        return float(-(mu + z_cf * sigma))

    return {
        "historical_95": _hist_var(0.05),
        "historical_99": _hist_var(0.01),
        "cvar_historical_95": _hist_cvar(0.05),
        "cvar_historical_99": _hist_cvar(0.01),
        "gaussian_95": _gaussian(0.05),
        "gaussian_99": _gaussian(0.01),
        "cornish_fisher_95": _cornish_fisher(0.05),
        "cornish_fisher_99": _cornish_fisher(0.01),
    }


def _horizon_returns_from_prices(prices: pd.Series) -> dict[str, float | None]:
    cleaned = prices.dropna()
    if cleaned.empty:
        return {
            "1d": None,
            "1w": None,
            "1m": None,
            "3m": None,
            "6m": None,
            "ytd": None,
            "1y": None,
            "3y": None,
            "5y": None,
        }

    def _lookback(periods: int) -> float | None:
        if len(cleaned) <= periods:
            return None
        start = float(cleaned.iloc[-(periods + 1)])
        end = float(cleaned.iloc[-1])
        if start == 0:
            return None
        return float(end / start - 1.0)

    latest_date = cleaned.index[-1]
    ytd_start = cleaned[cleaned.index.year == latest_date.year]
    ytd: float | None = None
    if len(ytd_start) > 1:
        start = float(ytd_start.iloc[0])
        end = float(ytd_start.iloc[-1])
        if start != 0:
            ytd = float(end / start - 1.0)

    return {
        "1d": _lookback(1),
        "1w": _lookback(5),
        "1m": _lookback(21),
        "3m": _lookback(63),
        "6m": _lookback(126),
        "ytd": ytd,
        "1y": _lookback(252),
        "3y": _lookback(756),
        "5y": _lookback(1260),
    }


def _capture_metrics(port_returns: pd.Series, bench_returns: pd.Series) -> dict[str, float | None]:
    df = pd.concat({"p": port_returns, "b": bench_returns}, axis=1).dropna()
    if len(df) < 10:
        return {
            "upside_capture_ratio": None,
            "downside_capture_ratio": None,
            "upside_capture_slope": None,
            "downside_capture_slope": None,
        }

    up = df[df["b"] > 0]
    down = df[df["b"] < 0]

    def _ratio(sub: pd.DataFrame) -> float | None:
        if sub.empty:
            return None
        bench_mean = float(sub["b"].mean())
        if abs(bench_mean) <= 1e-12:
            return None
        return float(sub["p"].mean() / bench_mean)

    def _slope(sub: pd.DataFrame) -> float | None:
        if len(sub) < 3:
            return None
        x = sub["b"].to_numpy(dtype=float)
        y = sub["p"].to_numpy(dtype=float)
        vx = float(np.var(x, ddof=1))
        if vx <= 0:
            return None
        return float(np.cov(y, x, ddof=1)[0, 1] / vx)

    return {
        "upside_capture_ratio": _ratio(up),
        "downside_capture_ratio": _ratio(down),
        "upside_capture_slope": _slope(up),
        "downside_capture_slope": _slope(down),
    }


def _ols_factor_exposure(
    target_returns: pd.Series,
    factor_returns: pd.DataFrame,
    periods_per_year: int,
) -> dict[str, float | None]:
    merged = pd.concat([target_returns.rename("target"), factor_returns], axis=1).dropna()
    if merged.empty:
        return {}
    if len(merged) < max(20, len(factor_returns.columns) + 5):
        return {}

    y = merged["target"].to_numpy(dtype=float)
    x = merged[factor_returns.columns].to_numpy(dtype=float)
    X = np.column_stack([np.ones(len(merged)), x])

    try:
        coeff, *_ = np.linalg.lstsq(X, y, rcond=None)
    except np.linalg.LinAlgError:
        return {}

    alpha_daily = float(coeff[0])
    out: dict[str, float | None] = {
        "alpha_daily": alpha_daily,
        "alpha_annual": float((1.0 + alpha_daily) ** periods_per_year - 1.0),
        "r2": None,
    }

    y_hat = X @ coeff
    ss_res = float(np.sum((y - y_hat) ** 2))
    ss_tot = float(np.sum((y - float(y.mean())) ** 2))
    if ss_tot > 0:
        out["r2"] = float(1.0 - ss_res / ss_tot)

    for idx, name in enumerate(factor_returns.columns, start=1):
        out[name] = float(coeff[idx])

    return out


def _single_beta(y: pd.Series, x: pd.Series) -> float | None:
    merged = pd.concat([y.rename("y"), x.rename("x")], axis=1).dropna()
    if len(merged) < 10:
        return None
    vx = float(np.var(merged["x"].to_numpy(dtype=float), ddof=1))
    if vx <= 0:
        return None
    cov = float(np.cov(merged["y"], merged["x"], ddof=1)[0, 1])
    return float(cov / vx)


def _current_rsi(prices: pd.Series, period: int = 14) -> float | None:
    cleaned = prices.dropna()
    if len(cleaned) <= period:
        return None
    delta = cleaned.diff().dropna()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.rolling(period).mean().iloc[-1]
    avg_loss = loss.rolling(period).mean().iloc[-1]
    if pd.isna(avg_gain) or pd.isna(avg_loss):
        return None
    if avg_loss == 0:
        return 100.0
    rs = float(avg_gain / avg_loss)
    return float(100.0 - 100.0 / (1.0 + rs))


def _technicals(prices: pd.Series) -> dict[str, float | None]:
    cleaned = prices.dropna()
    if cleaned.empty:
        return {
            "rsi_14": None,
            "sma_20": None,
            "sma_50": None,
            "sma_200": None,
            "ema_12": None,
            "ema_26": None,
            "macd": None,
            "macd_signal": None,
            "macd_hist": None,
        }

    ema12 = cleaned.ewm(span=12, adjust=False).mean()
    ema26 = cleaned.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    hist = macd - signal

    return {
        "rsi_14": _current_rsi(cleaned, 14),
        "sma_20": _to_float(cleaned.rolling(20).mean().iloc[-1]) if len(cleaned) >= 20 else None,
        "sma_50": _to_float(cleaned.rolling(50).mean().iloc[-1]) if len(cleaned) >= 50 else None,
        "sma_200": _to_float(cleaned.rolling(200).mean().iloc[-1]) if len(cleaned) >= 200 else None,
        "ema_12": _to_float(ema12.iloc[-1]) if len(ema12) else None,
        "ema_26": _to_float(ema26.iloc[-1]) if len(ema26) else None,
        "macd": _to_float(macd.iloc[-1]) if len(macd) else None,
        "macd_signal": _to_float(signal.iloc[-1]) if len(signal) else None,
        "macd_hist": _to_float(hist.iloc[-1]) if len(hist) else None,
    }


def _compute_metric_pack(
    *,
    returns: pd.Series,
    price_series: pd.Series,
    benchmark_returns: pd.Series,
    risk_free_rate: float,
    periods_per_year: int,
    benchmark_vol_ann: float | None,
    portfolio_value: float | None,
) -> dict[str, Any]:
    cleaned = returns.dropna()
    if len(cleaned) <= 1:
        return {
            "sharpe": None,
            "sortino": None,
            "adjusted_sharpe": None,
            "information_ratio": None,
            "beta": None,
            "historical_alpha": None,
            "returns": _horizon_returns_from_prices(price_series),
            "volatility": None,
            "skewness": None,
            "kurtosis": None,
            "capture": _capture_metrics(cleaned, benchmark_returns),
            "calmar": None,
            "omega": None,
            "m2": None,
            "pain_index": None,
            "pain_ratio": None,
            "raroc": None,
            "percent_positive_periods": None,
            "max_win_streak": 0,
            "max_loss_streak": 0,
            "drawdown": {
                "max": None,
                "current": None,
                "duration_periods": 0,
            },
            "var": _var_metrics(cleaned),
            "expected_loss": {
                "tail_cvar_95_value": None,
                "mean_negative_period_value": None,
            },
            "technicals": _technicals(price_series),
        }

    ann_return = _annualized_return(cleaned, periods_per_year=periods_per_year)
    ann_vol = _annualized_vol(cleaned, periods_per_year=periods_per_year)
    rf_per_day = float((1.0 + max(-0.999, risk_free_rate)) ** (1.0 / periods_per_year) - 1.0)

    downside = np.minimum(0.0, cleaned.to_numpy(dtype=float) - rf_per_day)
    downside_dev = float(np.sqrt(np.mean(np.square(downside))) * np.sqrt(periods_per_year))

    sharpe = None
    if ann_return is not None and ann_vol is not None and ann_vol > 0:
        sharpe = float((ann_return - risk_free_rate) / ann_vol)

    sortino = None
    if ann_return is not None and downside_dev > 0:
        sortino = float((ann_return - risk_free_rate) / downside_dev)

    skewness = _to_float(cleaned.skew())
    kurtosis = _to_float(cleaned.kurtosis() + 3.0)

    adjusted_sharpe = None
    if sharpe is not None:
        s = skewness or 0.0
        k = kurtosis or 3.0
        adjusted_sharpe = float(sharpe * (1.0 + (s / 6.0) * sharpe - ((k - 3.0) / 24.0) * sharpe**2))

    active = pd.concat([cleaned.rename("p"), benchmark_returns.rename("b")], axis=1).dropna()
    information_ratio = None
    beta = None
    historical_alpha = None
    capture = _capture_metrics(cleaned, benchmark_returns)

    if len(active) > 10:
        active_diff = active["p"] - active["b"]
        tracking_error = float(active_diff.std(ddof=1))
        if tracking_error > 0:
            information_ratio = float(active_diff.mean() / tracking_error * np.sqrt(periods_per_year))

        bench_var = float(active["b"].var(ddof=1))
        if bench_var > 0:
            beta = float(active["p"].cov(active["b"]) / bench_var)

        bench_ann = _annualized_return(active["b"], periods_per_year=periods_per_year)
        if ann_return is not None and beta is not None and bench_ann is not None:
            historical_alpha = float(ann_return - (risk_free_rate + beta * (bench_ann - risk_free_rate)))

    dd = _drawdown_series(cleaned)
    max_dd = _to_float(dd.min())
    current_dd = _to_float(dd.iloc[-1]) if len(dd) else None

    drawdown_duration = 0
    current = 0
    for value in dd:
        if value < 0:
            current += 1
            drawdown_duration = max(drawdown_duration, current)
        else:
            current = 0

    calmar = None
    if ann_return is not None and max_dd is not None and max_dd < 0:
        calmar = float(ann_return / abs(max_dd))

    gains = float((cleaned[cleaned > 0.0]).sum())
    losses = float((-cleaned[cleaned <= 0.0]).sum())
    omega = float(gains / losses) if losses > 0 else None

    m2 = None
    if sharpe is not None and benchmark_vol_ann is not None:
        m2 = float(risk_free_rate + sharpe * benchmark_vol_ann)

    pain_index = float(-dd.mean()) if len(dd) else None
    pain_ratio = None
    if pain_index is not None and pain_index > 0 and ann_return is not None:
        pain_ratio = float((ann_return - risk_free_rate) / pain_index)

    var_map = _var_metrics(cleaned)
    raroc = None
    hist_95 = var_map.get("historical_95")
    if ann_return is not None and hist_95 is not None and hist_95 > 0:
        raroc = float((ann_return - risk_free_rate) / hist_95)

    pct_pos, max_win, max_loss = _max_streaks(cleaned)

    expected_loss_tail = None
    expected_loss_mean_negative = None
    if portfolio_value is not None and portfolio_value > 0:
        cvar_95 = var_map.get("cvar_historical_95")
        if cvar_95 is not None:
            expected_loss_tail = float(cvar_95 * portfolio_value)
        negatives = cleaned[cleaned < 0]
        if not negatives.empty:
            expected_loss_mean_negative = float(-negatives.mean() * portfolio_value)

    return {
        "sharpe": sharpe,
        "sortino": sortino,
        "adjusted_sharpe": adjusted_sharpe,
        "information_ratio": information_ratio,
        "beta": beta,
        "historical_alpha": historical_alpha,
        "returns": _horizon_returns_from_prices(price_series),
        "volatility": ann_vol,
        "skewness": skewness,
        "kurtosis": kurtosis,
        "capture": capture,
        "calmar": calmar,
        "omega": omega,
        "m2": m2,
        "pain_index": pain_index,
        "pain_ratio": pain_ratio,
        "raroc": raroc,
        "percent_positive_periods": pct_pos,
        "max_win_streak": max_win,
        "max_loss_streak": max_loss,
        "drawdown": {
            "max": max_dd,
            "current": current_dd,
            "duration_periods": drawdown_duration,
        },
        "var": var_map,
        "expected_loss": {
            "tail_cvar_95_value": expected_loss_tail,
            "mean_negative_period_value": expected_loss_mean_negative,
        },
        "technicals": _technicals(price_series),
    }


def _build_factor_exposures(
    *,
    db: Session | None,
    start_date: date,
    end_date: date,
    portfolio_returns: pd.Series,
    symbol_returns: pd.DataFrame,
    interval_base: str,
    periods_per_year: int,
    warnings: list[str],
) -> dict[str, Any]:
    if db is None:
        return {
            "model": "proxy_regression",
            "proxies": {},
            "portfolio": {},
            "stocks": {},
        }

    all_symbols = sorted({symbol for arr in FACTOR_PROXY_SYMBOLS.values() for symbol in arr})
    factor_prices = get_symbols_price_frame(db, all_symbols, start_date, end_date)
    if factor_prices.empty:
        warnings.append("factors: no_proxy_price_data")
        return {
            "model": "proxy_regression",
            "proxies": {},
            "portfolio": {},
            "stocks": {},
        }

    factor_prices = _resample_frame(factor_prices, interval_base)
    factor_rets = factor_prices.pct_change().dropna(how="all").fillna(0.0)

    built: dict[str, pd.Series] = {}

    if "SPY" in factor_rets.columns:
        built["market"] = factor_rets["SPY"]
    else:
        warnings.append("factors: market_proxy_missing_SPY")

    if {"IWM", "SPY"}.issubset(set(factor_rets.columns)):
        built["size"] = factor_rets["IWM"] - factor_rets["SPY"]
    else:
        warnings.append("factors: size_proxy_missing")

    if {"IWD", "IWF"}.issubset(set(factor_rets.columns)):
        built["value"] = factor_rets["IWD"] - factor_rets["IWF"]
    else:
        warnings.append("factors: value_proxy_missing")

    if {"MTUM", "SPY"}.issubset(set(factor_rets.columns)):
        built["momentum"] = factor_rets["MTUM"] - factor_rets["SPY"]
    else:
        warnings.append("factors: momentum_proxy_missing")

    if {"SPLV", "SPHB"}.issubset(set(factor_rets.columns)):
        built["investment"] = factor_rets["SPLV"] - factor_rets["SPHB"]
    else:
        warnings.append("factors: investment_proxy_missing")

    if {"QUAL", "SPY"}.issubset(set(factor_rets.columns)):
        built["profitability"] = factor_rets["QUAL"] - factor_rets["SPY"]
    else:
        warnings.append("factors: profitability_proxy_missing")

    if not built:
        return {
            "model": "proxy_regression",
            "proxies": FACTOR_PROXY_SYMBOLS,
            "portfolio": {},
            "stocks": {},
        }

    factor_df = pd.DataFrame(built).dropna(how="all")

    portfolio_exposure = _ols_factor_exposure(portfolio_returns, factor_df, periods_per_year)
    stock_exposure: dict[str, dict[str, float | None]] = {}
    for symbol in symbol_returns.columns:
        stock_exposure[symbol] = _ols_factor_exposure(symbol_returns[symbol], factor_df, periods_per_year)

    return {
        "model": "proxy_regression",
        "proxies": FACTOR_PROXY_SYMBOLS,
        "portfolio": portfolio_exposure,
        "stocks": stock_exposure,
    }


def _build_macro_exposures(
    *,
    db: Session | None,
    start_date: date,
    end_date: date,
    portfolio_returns: pd.Series,
    symbol_returns: pd.DataFrame,
    benchmark_returns: pd.Series | None,
    interval_base: str,
    warnings: list[str],
) -> dict[str, Any]:
    if db is None:
        return {
            "model": "single_factor_beta",
            "proxies": MACRO_PROXY_SYMBOLS,
            "portfolio": {},
            "benchmark": {},
            "stocks": {},
        }

    macro_symbols = sorted(set(MACRO_PROXY_SYMBOLS.values()))
    macro_prices = get_symbols_price_frame(db, macro_symbols, start_date, end_date)
    if macro_prices.empty:
        warnings.append("macro: no_proxy_price_data")
        return {
            "model": "single_factor_beta",
            "proxies": MACRO_PROXY_SYMBOLS,
            "portfolio": {},
            "benchmark": {},
            "stocks": {},
        }

    macro_prices = _resample_frame(macro_prices, interval_base)
    macro_returns = macro_prices.pct_change().dropna(how="all").fillna(0.0)

    portfolio: dict[str, dict[str, float | None]] = {}
    benchmark: dict[str, dict[str, float | None]] = {}
    stocks: dict[str, dict[str, dict[str, float | None]]] = {
        symbol: {} for symbol in symbol_returns.columns
    }

    for macro_name, proxy_symbol in MACRO_PROXY_SYMBOLS.items():
        if proxy_symbol not in macro_returns.columns:
            warnings.append(f"macro: missing_proxy_{macro_name}")
            continue
        proxy = macro_returns[proxy_symbol]
        portfolio[macro_name] = {
            "beta": _single_beta(portfolio_returns, proxy),
            "correlation": _to_float(pd.concat([portfolio_returns, proxy], axis=1).corr().iloc[0, 1]),
        }
        if benchmark_returns is not None and not benchmark_returns.empty:
            benchmark[macro_name] = {
                "beta": _single_beta(benchmark_returns, proxy),
                "correlation": _to_float(pd.concat([benchmark_returns, proxy], axis=1).corr().iloc[0, 1]),
            }
        for symbol in symbol_returns.columns:
            symbol_ret = symbol_returns[symbol]
            stocks[symbol][macro_name] = {
                "beta": _single_beta(symbol_ret, proxy),
                "correlation": _to_float(pd.concat([symbol_ret, proxy], axis=1).corr().iloc[0, 1]),
            }

    return {
        "model": "single_factor_beta",
        "proxies": MACRO_PROXY_SYMBOLS,
        "portfolio": portfolio,
        "benchmark": benchmark,
        "stocks": stocks,
    }


def _latest_analyst_snapshot(db: Session, symbol: str) -> SecurityAnalystSnapshot | None:
    return db.scalar(
        select(SecurityAnalystSnapshot)
        .where(SecurityAnalystSnapshot.symbol == symbol)
        .order_by(desc(SecurityAnalystSnapshot.as_of_date), desc(SecurityAnalystSnapshot.fetched_at))
        .limit(1)
    )


def _latest_fundamental_snapshot(db: Session, symbol: str) -> SecurityFundamentalSnapshot | None:
    return db.scalar(
        select(SecurityFundamentalSnapshot)
        .where(SecurityFundamentalSnapshot.symbol == symbol)
        .order_by(desc(SecurityFundamentalSnapshot.as_of_date), desc(SecurityFundamentalSnapshot.fetched_at))
        .limit(1)
    )


def _extract_table(df: pd.DataFrame | None) -> dict[str, dict[str, Any]] | None:
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return None

    out: dict[str, dict[str, Any]] = {}
    for idx, row in df.head(10).iterrows():
        row_dict: dict[str, Any] = {}
        for col in row.index:
            value = row[col]
            if pd.isna(value):
                continue
            if isinstance(value, (float, int, np.floating, np.integer)):
                row_dict[str(col)] = float(value)
            else:
                row_dict[str(col)] = str(value)
        if row_dict:
            out[str(idx)] = row_dict
    return out or None


def _fetch_live_symbol_extras(symbol: str) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    out: dict[str, Any] = {}
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info or {}
    except Exception as exc:  # pragma: no cover - network/provider behavior
        warnings.append(f"{symbol}: live_info_failed:{exc.__class__.__name__}")
        return out, warnings

    out["dividend_yield"] = _to_float(info.get("dividendYield"))
    out["earnings_growth"] = _to_float(info.get("earningsGrowth"))
    if out["earnings_growth"] is None:
        out["earnings_growth"] = _to_float(info.get("earningsQuarterlyGrowth"))
    out["revenue_growth"] = _to_float(info.get("revenueGrowth"))

    out["gross_margin"] = _to_float(info.get("grossMargins"))
    out["operating_margin"] = _to_float(info.get("operatingMargins"))
    out["profit_margin"] = _to_float(info.get("profitMargins"))

    out["earnings_estimates"] = None
    out["revenue_estimates"] = None
    try:
        out["earnings_estimates"] = _extract_table(ticker.earnings_estimate)
    except Exception:  # pragma: no cover - provider variability
        out["earnings_estimates"] = None
    try:
        out["revenue_estimates"] = _extract_table(ticker.revenue_estimate)
    except Exception:  # pragma: no cover - provider variability
        out["revenue_estimates"] = None

    upgrades = 0
    downgrades = 0
    try:
        ud = ticker.upgrades_downgrades
        if isinstance(ud, pd.DataFrame) and not ud.empty:
            ud_df = ud.copy()
            if isinstance(ud_df.index, pd.DatetimeIndex):
                cutoff = pd.Timestamp.today(tz=ud_df.index.tz) - pd.Timedelta(days=180)
                ud_df = ud_df[ud_df.index >= cutoff]

            action_col = None
            for candidate in ["Action", "action"]:
                if candidate in ud_df.columns:
                    action_col = candidate
                    break

            if action_col is not None:
                actions = ud_df[action_col].astype(str).str.lower()
                upgrades = int(actions.str.contains("up|init|main|reiter", regex=True, na=False).sum())
                downgrades = int(actions.str.contains("down", regex=True, na=False).sum())
    except Exception:  # pragma: no cover - provider variability
        upgrades = 0
        downgrades = 0

    out["upgrades_6m"] = upgrades
    out["downgrades_6m"] = downgrades
    return out, warnings


def _build_stock_fundamentals(
    *,
    db: Session | None,
    symbols: list[str],
    warnings: list[str],
    include_live_extras: bool,
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    stock_payload: dict[str, dict[str, Any]] = {}
    sector_industry_map: dict[str, dict[str, Any]] = {}

    for symbol in symbols:
        analyst = _latest_analyst_snapshot(db, symbol) if db is not None else None
        fundamental = _latest_fundamental_snapshot(db, symbol) if db is not None else None

        target_return = None
        if analyst is not None and analyst.current_price and analyst.current_price > 0 and analyst.target_mean is not None:
            target_return = float(analyst.target_mean / analyst.current_price - 1.0)

        live_extras: dict[str, Any] = {}
        if include_live_extras:
            live_warn: list[str] = []
            live_extras, live_warn = _fetch_live_symbol_extras(symbol)
            warnings.extend(live_warn)

        payload = {
            "analyst_target_return": target_return,
            "analyst": {
                "current_price": (analyst.current_price if analyst is not None else None),
                "target_mean": (analyst.target_mean if analyst is not None else None),
                "target_high": (analyst.target_high if analyst is not None else None),
                "target_low": (analyst.target_low if analyst is not None else None),
                "recommendation_key": (analyst.recommendation_key if analyst is not None else None),
                "recommendation_mean": (analyst.recommendation_mean if analyst is not None else None),
                "analyst_count": (analyst.analyst_count if analyst is not None else None),
            },
            "fundamentals": {
                "trailing_eps": (fundamental.trailing_eps if fundamental is not None else None),
                "forward_eps": (fundamental.forward_eps if fundamental is not None else None),
                "pe": (fundamental.pe if fundamental is not None else None),
                "forward_pe": (fundamental.forward_pe if fundamental is not None else None),
                "pb": (fundamental.pb if fundamental is not None else None),
                "ev_ebitda": (fundamental.ev_ebitda if fundamental is not None else None),
                "market_cap": (fundamental.market_cap if fundamental is not None else None),
                "book_value_per_share": (fundamental.book_value_per_share if fundamental is not None else None),
                "sector": (fundamental.sector if fundamental is not None else None),
                "industry": (fundamental.industry if fundamental is not None else None),
            },
            "earnings_growth": live_extras.get("earnings_growth"),
            "earnings_estimates": live_extras.get("earnings_estimates"),
            "revenue_growth": live_extras.get("revenue_growth"),
            "revenue_estimates": live_extras.get("revenue_estimates"),
            "dividend_yield": live_extras.get("dividend_yield"),
            "margins": {
                "gross": live_extras.get("gross_margin"),
                "operating": live_extras.get("operating_margin"),
                "net": live_extras.get("profit_margin"),
            },
            "rating_changes": {
                "upgrades_6m": live_extras.get("upgrades_6m", 0),
                "downgrades_6m": live_extras.get("downgrades_6m", 0),
            },
        }
        stock_payload[symbol] = payload

        sector = payload["fundamentals"].get("sector") or "Unknown"
        industry = payload["fundamentals"].get("industry") or "Unknown"
        sector_industry_map[symbol] = {
            "sector": sector,
            "industry": industry,
            "pe": payload["fundamentals"].get("pe"),
            "forward_pe": payload["fundamentals"].get("forward_pe"),
            "pb": payload["fundamentals"].get("pb"),
            "ev_ebitda": payload["fundamentals"].get("ev_ebitda"),
            "gross_margin": payload["margins"].get("gross"),
            "operating_margin": payload["margins"].get("operating"),
            "net_margin": payload["margins"].get("net"),
        }

    return stock_payload, sector_industry_map


def _weighted_avg(values: list[tuple[float, float | None]]) -> float | None:
    filtered = [(w, v) for w, v in values if v is not None and np.isfinite(v)]
    if not filtered:
        return None
    total_w = float(sum(w for w, _ in filtered))
    if total_w <= 0:
        return None
    return float(sum(w * float(v) for w, v in filtered) / total_w)


def _dispersion(values: list[float | None]) -> float | None:
    arr = np.array([float(v) for v in values if v is not None and np.isfinite(v)], dtype=float)
    if len(arr) <= 1:
        return None
    return float(arr.std(ddof=1))


def _aggregate_fundamental_rollup(
    *,
    weights: dict[str, float],
    stock_fundamentals: dict[str, dict[str, Any]],
    sector_industry_map: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    metrics = {
        "dividend_yield": [],
        "earnings_growth": [],
        "revenue_growth": [],
        "pe": [],
        "forward_pe": [],
        "pb": [],
        "ev_ebitda": [],
        "gross_margin": [],
        "operating_margin": [],
        "net_margin": [],
    }

    for symbol, payload in stock_fundamentals.items():
        w = float(weights.get(symbol, 0.0))
        fundamentals = payload.get("fundamentals", {})
        margins = payload.get("margins", {})
        metrics["dividend_yield"].append((w, _to_float(payload.get("dividend_yield"))))
        metrics["earnings_growth"].append((w, _to_float(payload.get("earnings_growth"))))
        metrics["revenue_growth"].append((w, _to_float(payload.get("revenue_growth"))))
        metrics["pe"].append((w, _to_float(fundamentals.get("pe"))))
        metrics["forward_pe"].append((w, _to_float(fundamentals.get("forward_pe"))))
        metrics["pb"].append((w, _to_float(fundamentals.get("pb"))))
        metrics["ev_ebitda"].append((w, _to_float(fundamentals.get("ev_ebitda"))))
        metrics["gross_margin"].append((w, _to_float(margins.get("gross"))))
        metrics["operating_margin"].append((w, _to_float(margins.get("operating"))))
        metrics["net_margin"].append((w, _to_float(margins.get("net"))))

    weighted = {k: _weighted_avg(v) for k, v in metrics.items()}
    dispersion = {f"{k}_dispersion": _dispersion([val for _, val in metrics[k]]) for k in metrics.keys()}

    by_sector: dict[str, dict[str, Any]] = {}
    by_industry: dict[str, dict[str, Any]] = {}

    for symbol, meta in sector_industry_map.items():
        weight = float(weights.get(symbol, 0.0))
        sector = str(meta.get("sector") or "Unknown")
        industry = str(meta.get("industry") or "Unknown")

        by_sector.setdefault(
            sector,
            {
                "weight": 0.0,
                "pe": [],
                "forward_pe": [],
                "pb": [],
                "ev_ebitda": [],
                "gross_margin": [],
                "operating_margin": [],
                "net_margin": [],
            },
        )
        by_industry.setdefault(
            industry,
            {
                "weight": 0.0,
                "pe": [],
                "forward_pe": [],
                "pb": [],
                "ev_ebitda": [],
                "gross_margin": [],
                "operating_margin": [],
                "net_margin": [],
            },
        )

        for bucket in (by_sector[sector], by_industry[industry]):
            bucket["weight"] += weight
            for key in [
                "pe",
                "forward_pe",
                "pb",
                "ev_ebitda",
                "gross_margin",
                "operating_margin",
                "net_margin",
            ]:
                value = _to_float(meta.get(key))
                if value is not None:
                    bucket[key].append(value)

    def _summarize_bucket(source: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for key, payload in source.items():
            out[key] = {
                "weight": float(payload.get("weight", 0.0)),
                "avg_pe": _to_float(np.mean(payload["pe"])) if payload["pe"] else None,
                "avg_forward_pe": _to_float(np.mean(payload["forward_pe"])) if payload["forward_pe"] else None,
                "avg_pb": _to_float(np.mean(payload["pb"])) if payload["pb"] else None,
                "avg_ev_ebitda": _to_float(np.mean(payload["ev_ebitda"])) if payload["ev_ebitda"] else None,
                "avg_gross_margin": _to_float(np.mean(payload["gross_margin"])) if payload["gross_margin"] else None,
                "avg_operating_margin": _to_float(np.mean(payload["operating_margin"]))
                if payload["operating_margin"]
                else None,
                "avg_net_margin": _to_float(np.mean(payload["net_margin"])) if payload["net_margin"] else None,
            }
        return out

    return {
        "weighted_averages": weighted,
        "dispersion": dispersion,
        "sector_average_ratios": _summarize_bucket(by_sector),
        "industry_average_ratios": _summarize_bucket(by_industry),
    }


def _risk_contributions(symbol_returns: pd.DataFrame, weights: np.ndarray) -> dict[str, Any]:
    if symbol_returns.empty:
        return {
            "pct_total_risk_by_symbol": {},
            "marginal_risk_by_symbol": {},
            "component_risk_by_symbol": {},
        }

    cov = symbol_returns.cov().to_numpy(dtype=float)
    port_var = float(weights.T @ cov @ weights)
    if port_var <= 0:
        empty = {symbol: None for symbol in symbol_returns.columns}
        return {
            "pct_total_risk_by_symbol": empty,
            "marginal_risk_by_symbol": empty,
            "component_risk_by_symbol": empty,
        }

    port_vol = float(np.sqrt(port_var))
    marginal = cov @ weights / port_vol
    component = weights * marginal
    pct = component / port_vol

    return {
        "pct_total_risk_by_symbol": {
            symbol: _to_float(pct[i]) for i, symbol in enumerate(symbol_returns.columns)
        },
        "marginal_risk_by_symbol": {
            symbol: _to_float(marginal[i]) for i, symbol in enumerate(symbol_returns.columns)
        },
        "component_risk_by_symbol": {
            symbol: _to_float(component[i]) for i, symbol in enumerate(symbol_returns.columns)
        },
    }


def _pairwise_correlations(symbol_returns: pd.DataFrame) -> list[dict[str, Any]]:
    if symbol_returns.shape[1] <= 1:
        return []

    corr = symbol_returns.corr()
    pairs: list[dict[str, Any]] = []
    columns = list(corr.columns)
    for i in range(len(columns)):
        for j in range(i + 1, len(columns)):
            c = _to_float(corr.iloc[i, j])
            if c is None:
                continue
            pairs.append({
                "lhs": columns[i],
                "rhs": columns[j],
                "correlation": c,
                "abs_correlation": abs(c),
            })

    pairs.sort(key=lambda x: x["abs_correlation"], reverse=True)
    return pairs[:20]


def _resolve_window(
    *,
    as_of: date,
    preset: str,
    start_date: date | None,
    end_date: date | None,
) -> tuple[date, date, str]:
    normalized = str(preset).strip().lower()
    if start_date is not None or end_date is not None:
        if start_date is None or end_date is None:
            raise ValueError("Both custom start and end dates are required together.")
        if start_date > end_date:
            raise ValueError("Custom start date must be <= end date.")
        return start_date, end_date, "custom"

    if normalized not in WINDOW_PRESET_TO_DAYS:
        normalized = "5y"
    end = as_of
    start = end - pd.Timedelta(days=WINDOW_PRESET_TO_DAYS[normalized])
    return pd.Timestamp(start).date(), end, normalized


def _resample_prices(price_frame: pd.DataFrame, benchmark_prices: pd.Series, interval_base: str) -> tuple[pd.DataFrame, pd.Series]:
    freq_map = {
        "daily": None,
        "weekly": "W-FRI",
        "monthly": "ME",
    }
    interval = str(interval_base).strip().lower()
    resample_freq = freq_map.get(interval)
    cleaned_prices = price_frame.sort_index()
    cleaned_benchmark = benchmark_prices.sort_index()
    if resample_freq is None:
        return cleaned_prices, cleaned_benchmark
    return (
        cleaned_prices.resample(resample_freq).last(),
        cleaned_benchmark.resample(resample_freq).last(),
    )


def _resample_frame(frame: pd.DataFrame, interval_base: str) -> pd.DataFrame:
    series = pd.Series(np.arange(len(frame.index), dtype=float), index=frame.index)
    resampled, _ = _resample_prices(frame, series, interval_base)
    return resampled


def compute_extended_metrics(
    *,
    holdings: list[HoldingsPosition],
    price_frame: pd.DataFrame,
    benchmark_prices: pd.Series,
    risk_free_rate: float,
    benchmark_symbol: str,
    db: Session | None = None,
    as_of_date: date | None = None,
    include_live_extras: bool = True,
    window_preset: str = "5y",
    interval_base: str = "daily",
    custom_start_date: date | None = None,
    custom_end_date: date | None = None,
) -> ExtendedMetricResult:
    warnings: list[str] = []
    as_of = as_of_date or date.today()
    interval = str(interval_base).strip().lower()
    periods_per_year = INTERVAL_TO_TRADING_PERIODS.get(interval, TRADING_DAYS)
    requested_window = "CUSTOM" if custom_start_date is not None or custom_end_date is not None else str(window_preset).strip().upper()
    if interval not in INTERVAL_TO_TRADING_PERIODS:
        warnings.append(f"extended_metrics: unsupported_interval_{interval_base}, defaulted_to_daily")
        interval = "daily"
        periods_per_year = TRADING_DAYS

    portfolio_value = float(sum(max(0.0, float(h.market_value)) for h in holdings))

    if price_frame.empty or benchmark_prices.empty:
        warnings.append("extended_metrics: insufficient_price_data")
        return ExtendedMetricResult(
            metrics={
                "status": "no_data",
                "as_of_date": as_of.isoformat(),
                "window": requested_window,
                "benchmark_symbol": benchmark_symbol.upper(),
                "portfolio": {},
                "stocks": {},
            },
            warnings=warnings,
        )

    weights_map = {h.symbol.upper(): float(h.weight) for h in holdings}
    symbols = [symbol for symbol in price_frame.columns if symbol in weights_map]
    if not symbols:
        warnings.append("extended_metrics: no_symbol_overlap")
        return ExtendedMetricResult(
            metrics={
                "status": "no_data",
                "as_of_date": as_of.isoformat(),
                "window": requested_window,
                "benchmark_symbol": benchmark_symbol.upper(),
                "portfolio": {},
                "stocks": {},
            },
            warnings=warnings,
        )

    try:
        window_start, window_end, resolved_window = _resolve_window(
            as_of=as_of,
            preset=window_preset,
            start_date=custom_start_date,
            end_date=custom_end_date,
        )
    except ValueError as exc:
        warnings.append(f"extended_metrics: {exc}")
        window_start, window_end, resolved_window = _resolve_window(as_of=as_of, preset="5y", start_date=None, end_date=None)

    symbol_prices = price_frame[symbols].copy().sort_index()
    symbol_prices.index = pd.to_datetime(symbol_prices.index)
    window_mask = (symbol_prices.index >= pd.Timestamp(window_start)) & (symbol_prices.index <= pd.Timestamp(window_end))
    symbol_prices = symbol_prices.loc[window_mask]
    benchmark_series = pd.to_numeric(benchmark_prices, errors="coerce").dropna().sort_index()
    benchmark_series.index = pd.to_datetime(benchmark_series.index)
    benchmark_series = benchmark_series.loc[
        (benchmark_series.index >= pd.Timestamp(window_start)) & (benchmark_series.index <= pd.Timestamp(window_end))
    ]

    symbol_prices, benchmark_series = _resample_prices(symbol_prices, benchmark_series, interval)
    symbol_returns = symbol_prices.pct_change().dropna(how="all").fillna(0.0)

    if symbol_returns.empty:
        warnings.append("extended_metrics: no_returns")
        return ExtendedMetricResult(
            metrics={
                "status": "no_data",
                "as_of_date": as_of.isoformat(),
                "window": requested_window,
                "benchmark_symbol": benchmark_symbol.upper(),
                "portfolio": {},
                "stocks": {},
            },
            warnings=warnings,
        )

    w = np.array([weights_map[s] for s in symbols], dtype=float)
    if w.sum() > 0:
        w = w / w.sum()
    else:
        w = np.ones_like(w) / len(w)

    portfolio_returns = pd.Series(symbol_returns.to_numpy() @ w, index=symbol_returns.index, name="portfolio")
    benchmark_returns = benchmark_series.pct_change().dropna()

    aligned = pd.concat([portfolio_returns.rename("p"), benchmark_returns.rename("b")], axis=1).dropna()
    if len(aligned) >= 2:
        portfolio_returns = aligned["p"]
        benchmark_returns = aligned["b"]
    else:
        warnings.append("extended_metrics: benchmark_alignment_short")

    benchmark_vol_ann = _annualized_vol(benchmark_returns, periods_per_year=periods_per_year)

    portfolio_price_index = 100.0 * (1.0 + portfolio_returns.fillna(0.0)).cumprod()

    portfolio_pack = _compute_metric_pack(
        returns=portfolio_returns,
        price_series=portfolio_price_index,
        benchmark_returns=benchmark_returns,
        risk_free_rate=risk_free_rate,
        periods_per_year=periods_per_year,
        benchmark_vol_ann=benchmark_vol_ann,
        portfolio_value=portfolio_value,
    )

    risk_contrib = _risk_contributions(symbol_returns[symbols], w)

    stock_payload: dict[str, dict[str, Any]] = {}
    for symbol in symbols:
        stock_payload[symbol] = _compute_metric_pack(
            returns=symbol_returns[symbol],
            price_series=symbol_prices[symbol],
            benchmark_returns=benchmark_returns,
            risk_free_rate=risk_free_rate,
            periods_per_year=periods_per_year,
            benchmark_vol_ann=benchmark_vol_ann,
            portfolio_value=float(weights_map[symbol] * portfolio_value),
        )

    start_date = pd.Timestamp(symbol_prices.index.min()).date()
    end_date = pd.Timestamp(symbol_prices.index.max()).date()

    factor_exposures = _build_factor_exposures(
        db=db,
        start_date=start_date,
        end_date=end_date,
        portfolio_returns=portfolio_returns,
        symbol_returns=symbol_returns[symbols],
        interval_base=interval,
        periods_per_year=periods_per_year,
        warnings=warnings,
    )

    macro_exposures = _build_macro_exposures(
        db=db,
        start_date=start_date,
        end_date=end_date,
        portfolio_returns=portfolio_returns,
        symbol_returns=symbol_returns[symbols],
        benchmark_returns=benchmark_returns,
        interval_base=interval,
        warnings=warnings,
    )

    fundamentals_payload, sector_industry_map = _build_stock_fundamentals(
        db=db,
        symbols=symbols,
        warnings=warnings,
        include_live_extras=include_live_extras,
    )

    for symbol in symbols:
        stock_payload.setdefault(symbol, {})["fundamentals"] = fundamentals_payload.get(symbol, {})

    rollup = _aggregate_fundamental_rollup(
        weights={symbol: float(weights_map[symbol]) for symbol in symbols},
        stock_fundamentals=fundamentals_payload,
        sector_industry_map=sector_industry_map,
    )

    benchmark_corr = None
    if len(aligned) >= 2:
        benchmark_corr = _to_float(aligned[["p", "b"]].corr().iloc[0, 1])

    payload = {
        "status": "ok",
        "as_of_date": as_of.isoformat(),
        "window": resolved_window.upper(),
        "interval_base": interval,
        "benchmark_symbol": benchmark_symbol.upper(),
        "portfolio": {
            **portfolio_pack,
            "correlation_to_benchmark": benchmark_corr,
            "fama_french_proxy_exposures": factor_exposures.get("portfolio", {}),
            "macro_exposures": macro_exposures.get("portfolio", {}),
            "risk_contribution": risk_contrib,
            "correlations": {
                "pairwise_top": _pairwise_correlations(symbol_returns[symbols]),
            },
        },
        "stocks": stock_payload,
        "factor_model": {
            "model": factor_exposures.get("model"),
            "proxies": factor_exposures.get("proxies"),
            "stock_exposures": factor_exposures.get("stocks", {}),
        },
        "macro_model": {
            "model": macro_exposures.get("model"),
            "proxies": macro_exposures.get("proxies"),
            "benchmark_exposures": macro_exposures.get("benchmark", {}),
            "stock_exposures": macro_exposures.get("stocks", {}),
        },
        "fundamental_rollup": rollup,
        "notes": {
            "benchmark_default": "SPY unless overridden at portfolio level",
            "factor_method": "Proxy ETF regression for market, size, value, momentum, investment, profitability",
            "macro_method": "Proxy beta/correlation versus rates/oil/inflation/GDP/retail/unemployment/gov-spending market proxies",
            "disclaimer": "Metrics are analytics outputs, not investment advice.",
        },
    }

    return ExtendedMetricResult(metrics=_as_python(payload), warnings=sorted(set(warnings)))
