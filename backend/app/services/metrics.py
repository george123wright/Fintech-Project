from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from app.models import HoldingsPosition


@dataclass
class Contribution:
    symbol: str
    marginal_risk: float
    component_risk: float
    pct_total_risk: float


@dataclass
class MetricResult:
    portfolio_value: float
    ann_return: float
    ann_vol: float
    sharpe: float
    sortino: float
    max_drawdown: float
    var_95: float
    cvar_95: float
    beta: float
    top3_weight_share: float
    hhi: float
    contributions: list[Contribution]


def _safe_float(value: float | np.floating | None) -> float:
    if value is None or not np.isfinite(value):
        return 0.0
    return float(value)


def compute_metrics(
    *,
    holdings: list[HoldingsPosition],
    price_frame: pd.DataFrame,
    benchmark_prices: pd.Series,
    risk_free_rate: float,
) -> MetricResult:
    portfolio_value = float(sum(max(0.0, p.market_value) for p in holdings))
    if portfolio_value <= 0:
        portfolio_value = float(sum(p.market_value for p in holdings if p.market_value is not None))

    if price_frame.empty or benchmark_prices.empty:
        return MetricResult(
            portfolio_value=max(portfolio_value, 0.0),
            ann_return=0.0,
            ann_vol=0.0,
            sharpe=0.0,
            sortino=0.0,
            max_drawdown=0.0,
            var_95=0.0,
            cvar_95=0.0,
            beta=0.0,
            top3_weight_share=0.0,
            hhi=0.0,
            contributions=[],
        )

    weights_map = {p.symbol.upper(): float(p.weight) for p in holdings}
    present_symbols = [s for s in price_frame.columns if s in weights_map]
    if not present_symbols:
        return MetricResult(
            portfolio_value=max(portfolio_value, 0.0),
            ann_return=0.0,
            ann_vol=0.0,
            sharpe=0.0,
            sortino=0.0,
            max_drawdown=0.0,
            var_95=0.0,
            cvar_95=0.0,
            beta=0.0,
            top3_weight_share=0.0,
            hhi=0.0,
            contributions=[],
        )

    symbol_returns = price_frame[present_symbols].pct_change().dropna(how="all").fillna(0.0)
    if symbol_returns.empty:
        return MetricResult(
            portfolio_value=max(portfolio_value, 0.0),
            ann_return=0.0,
            ann_vol=0.0,
            sharpe=0.0,
            sortino=0.0,
            max_drawdown=0.0,
            var_95=0.0,
            cvar_95=0.0,
            beta=0.0,
            top3_weight_share=0.0,
            hhi=0.0,
            contributions=[],
        )

    w = np.array([weights_map[s] for s in present_symbols], dtype=float)
    if w.sum() <= 0:
        w = np.ones_like(w) / len(w)
    else:
        w = w / w.sum()

    portfolio_returns = symbol_returns.to_numpy() @ w
    portfolio_sr = pd.Series(portfolio_returns, index=symbol_returns.index).dropna()

    bench_returns = pd.to_numeric(benchmark_prices, errors="coerce").pct_change().dropna()
    common_idx = portfolio_sr.index.intersection(bench_returns.index)
    portfolio_sr = portfolio_sr.loc[common_idx]
    bench_returns = bench_returns.loc[common_idx]

    if len(portfolio_sr) < 2:
        return MetricResult(
            portfolio_value=max(portfolio_value, 0.0),
            ann_return=0.0,
            ann_vol=0.0,
            sharpe=0.0,
            sortino=0.0,
            max_drawdown=0.0,
            var_95=0.0,
            cvar_95=0.0,
            beta=0.0,
            top3_weight_share=float(np.sort(w)[-3:].sum()) if w.size else 0.0,
            hhi=float(np.sum(np.square(w))) if w.size else 0.0,
            contributions=[],
        )

    n = len(portfolio_sr)
    total_return = float((1.0 + portfolio_sr).prod() - 1.0)
    ann_return = float((1.0 + total_return) ** (252.0 / n) - 1.0)

    daily_vol = float(portfolio_sr.std(ddof=1))
    ann_vol = float(daily_vol * np.sqrt(252.0)) if daily_vol > 0 else 0.0

    downside = portfolio_sr[portfolio_sr < 0]
    downside_vol = float(downside.std(ddof=1)) if len(downside) > 1 else 0.0
    downside_ann = downside_vol * np.sqrt(252.0)

    sharpe = (ann_return - risk_free_rate) / ann_vol if ann_vol > 0 else 0.0
    sortino = (ann_return - risk_free_rate) / downside_ann if downside_ann > 0 else 0.0

    cumulative = (1.0 + portfolio_sr).cumprod()
    running_max = cumulative.cummax()
    drawdown = cumulative / running_max - 1.0
    max_drawdown = float(drawdown.min()) if not drawdown.empty else 0.0

    var_95 = float(np.quantile(portfolio_sr, 0.05))
    cvar_95 = float(portfolio_sr[portfolio_sr <= var_95].mean())

    bench_var = float(bench_returns.var(ddof=1))
    beta = float(portfolio_sr.cov(bench_returns) / bench_var) if bench_var > 0 else 0.0

    cov = symbol_returns[present_symbols].cov().to_numpy()
    port_vol_daily = float(np.sqrt(max(0.0, float(w.T @ cov @ w))))
    contributions: list[Contribution] = []
    if port_vol_daily > 0:
        marginal = cov @ w / port_vol_daily
        component = w * marginal
        pct = component / port_vol_daily
        for i, symbol in enumerate(present_symbols):
            contributions.append(
                Contribution(
                    symbol=symbol,
                    marginal_risk=_safe_float(marginal[i]),
                    component_risk=_safe_float(component[i]),
                    pct_total_risk=_safe_float(pct[i]),
                )
            )

    weights_full = np.array([max(0.0, float(p.weight)) for p in holdings], dtype=float)
    if weights_full.sum() > 0:
        weights_full = weights_full / weights_full.sum()
        top3_weight_share = float(np.sort(weights_full)[-3:].sum())
        hhi = float(np.sum(np.square(weights_full)))
    else:
        top3_weight_share = 0.0
        hhi = 0.0

    return MetricResult(
        portfolio_value=max(portfolio_value, 0.0),
        ann_return=_safe_float(ann_return),
        ann_vol=_safe_float(ann_vol),
        sharpe=_safe_float(sharpe),
        sortino=_safe_float(sortino),
        max_drawdown=_safe_float(max_drawdown),
        var_95=_safe_float(var_95),
        cvar_95=_safe_float(cvar_95),
        beta=_safe_float(beta),
        top3_weight_share=_safe_float(top3_weight_share),
        hhi=_safe_float(hhi),
        contributions=contributions,
    )
