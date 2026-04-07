from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
import pandas as pd
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.config import settings
from app.models import HoldingsPosition, PositionRiskContribution
from app.schemas.analytics import (
    AnalystRevisionRowOut,
    CorporateActionRowOut,
    ExposureSummaryOut,
    ExtendedAnalyticsResponse,
    ExtendedMetricSnapshotOut,
    IndustryAnalyticsDateMode,
    IndustryAnalyticsInterval,
    IndustryAnalyticsParams,
    IndustryAnalyticsSortBy,
    IndustryAnalyticsSortOrder,
    IndustryAnalyticsWindow,
    IndustryMatrixOut,
    IndustryMetricRowOut,
    IndustryOverviewResponse,
    MacroForecastResponse,
    MacroForecastTableOut,
    InsiderTransactionRowOut,
    MarketEventOut,
    NewsArticleOut,
    PricePoint,
    PortfolioNarrativeOut,
    PortfolioNewsResponse,
    PricesResponse,
    RefreshJobOut,
    RefreshResponse,
    RiskAnalyticsResponse,
    RiskContributionOut,
    RiskMetricOut,
    SecurityEventsResponse,
    SymbolPriceSeries,
)
from app.schemas.portfolios import (
    HoldingPositionOut,
    HoldingsLatestResponse,
    ManualHoldingsRequest,
    OverviewResponse,
    PortfolioCreate,
    PortfolioRead,
    UploadValidationReport,
)
from app.schemas.scenarios import ScenarioRunListItem
from app.schemas.valuation import PortfolioValuationOverviewResponse, ValuationRunOut
from app.services.ingestion import ingest_holdings_upload, ingest_manual_holdings
from app.services.exposures import exposure_snapshot_payload, latest_exposure_snapshot
from app.services.industry_analytics import (
    aggregate_industry_panel,
    build_industry_return_matrices,
    compute_industry_return_metrics,
    fetch_industry_price_panel,
    fetch_sector_price_panel,
    map_tickers_to_display_industries,
    resolve_industry_ticker_map,
)
from app.services.industry_map import INDUSTRY_MAP, slug_to_display
from app.services.insights import load_latest_fundamentals
from app.services.narratives import narrative_payload, latest_narrative_snapshot
from app.services.portfolio import (
    create_portfolio,
    ensure_default_portfolio,
    get_portfolio_or_404,
    latest_extended_metrics_for_snapshot,
    latest_metrics_for_snapshot,
    latest_refresh_job,
    latest_scenario_run,
    latest_snapshot,
    list_portfolios,
)
from app.services.pricing import RANGE_TO_DAYS, get_symbols_price_frame
from app.services.providers import fetch_portfolio_news, fetch_security_events
from app.services.refresh import RefreshBusyError, run_refresh_for_portfolio
from app.services.trading_economics import load_forecasts
from app.services.valuation import (
    latest_portfolio_valuation_snapshot,
    latest_valuation_run,
    parse_portfolio_valuation_summary,
)

from app.db import get_db

router = APIRouter(prefix="/portfolios", tags=["portfolios"])


def _industry_analytics_params(
    window: IndustryAnalyticsWindow = Query("1Y"),
    date_mode: IndustryAnalyticsDateMode = Query("preset"),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    interval: IndustryAnalyticsInterval = Query("daily"),
    benchmark: str | None = Query(None),
    sort_by: IndustryAnalyticsSortBy = Query("return"),
    sort_order: IndustryAnalyticsSortOrder = Query("desc"),
) -> IndustryAnalyticsParams:
    if not isinstance(start_date, date):
        start_date = None
    if not isinstance(end_date, date):
        end_date = None

    return IndustryAnalyticsParams(
        window=window,
        date_mode=date_mode,
        start_date=start_date,
        end_date=end_date,
        interval=interval,
        benchmark=(benchmark.upper().strip() if benchmark else None),
        sort_by=sort_by,
        sort_order=sort_order,
    )


def _safe_json_loads(value: str | None, fallback: object) -> object:
    if value is None or value == "":
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def _valuation_overview_for_portfolio(
    db: Session,
    portfolio_id: int,
) -> PortfolioValuationOverviewResponse | None:
    snapshot = latest_portfolio_valuation_snapshot(db, portfolio_id)
    if snapshot is None:
        return None

    run = latest_valuation_run(db, portfolio_id)
    parsed = parse_portfolio_valuation_summary(snapshot)
    return PortfolioValuationOverviewResponse(
        portfolio_id=portfolio_id,
        snapshot_id=parsed["snapshot_id"],
        as_of_date=parsed["as_of_date"],
        status="ok",
        weighted_analyst_upside=parsed["weighted_analyst_upside"],
        weighted_dcf_upside=parsed["weighted_dcf_upside"],
        weighted_ri_upside=parsed["weighted_ri_upside"],
        weighted_relative_upside=parsed["weighted_relative_upside"],
        weighted_composite_upside=parsed["weighted_composite_upside"],
        coverage_ratio=parsed["coverage_ratio"],
        overvalued_weight=parsed["overvalued_weight"],
        undervalued_weight=parsed["undervalued_weight"],
        summary=parsed["summary"],
        run=(ValuationRunOut.model_validate(run) if run is not None else None),
        results=[],
        warnings=[],
    )


@router.post("", response_model=PortfolioRead)
def create_portfolio_route(payload: PortfolioCreate, db: Session = Depends(get_db)) -> PortfolioRead:
    portfolio = create_portfolio(
        db,
        name=payload.name,
        base_currency=payload.base_currency,
        benchmark_symbol=payload.benchmark_symbol,
    )
    return portfolio


@router.get("", response_model=list[PortfolioRead])
def list_portfolios_route(db: Session = Depends(get_db)) -> list[PortfolioRead]:
    ensure_default_portfolio(db)
    return list_portfolios(db)


@router.post("/{portfolio_id}/holdings/upload", response_model=UploadValidationReport)
def upload_holdings_route(
    portfolio_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> UploadValidationReport:
    portfolio = get_portfolio_or_404(db, portfolio_id)
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    result = ingest_holdings_upload(db, portfolio_id=portfolio_id, upload=file)
    return UploadValidationReport(
        upload_id=result.upload_id,
        status=result.status,
        accepted_rows=result.accepted_rows,
        rejected_rows=result.rejected_rows,
        unknown_tickers=result.unknown_tickers,
        missing_fields=result.missing_fields,
        errors=result.errors,
        snapshot_id=result.snapshot_id,
        as_of_date=result.as_of_date,
    )


@router.post("/{portfolio_id}/holdings/manual", response_model=UploadValidationReport)
def manual_holdings_route(
    portfolio_id: int,
    payload: ManualHoldingsRequest,
    db: Session = Depends(get_db),
) -> UploadValidationReport:
    portfolio = get_portfolio_or_404(db, portfolio_id)
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    result = ingest_manual_holdings(
        db,
        portfolio_id=portfolio_id,
        holdings=[item.model_dump() for item in payload.holdings],
    )
    return UploadValidationReport(
        upload_id=result.upload_id,
        status=result.status,
        accepted_rows=result.accepted_rows,
        rejected_rows=result.rejected_rows,
        unknown_tickers=result.unknown_tickers,
        missing_fields=result.missing_fields,
        errors=result.errors,
        snapshot_id=result.snapshot_id,
        as_of_date=result.as_of_date,
    )


@router.get("/{portfolio_id}/holdings/latest", response_model=HoldingsLatestResponse)
def latest_holdings_route(portfolio_id: int, db: Session = Depends(get_db)) -> HoldingsLatestResponse:
    portfolio = get_portfolio_or_404(db, portfolio_id)
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    snapshot = latest_snapshot(db, portfolio_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="No holdings snapshot found")

    positions = list(
        db.scalars(
            select(HoldingsPosition)
            .where(HoldingsPosition.snapshot_id == snapshot.id)
            .order_by(HoldingsPosition.weight.desc())
        )
    )

    return HoldingsLatestResponse(
        portfolio_id=portfolio_id,
        snapshot_id=snapshot.id,
        as_of_date=snapshot.as_of_date,
        positions=[HoldingPositionOut.model_validate(position) for position in positions],
    )


@router.post("/{portfolio_id}/refresh", response_model=RefreshResponse)
def refresh_portfolio_route(portfolio_id: int, db: Session = Depends(get_db)) -> RefreshResponse:
    portfolio = get_portfolio_or_404(db, portfolio_id)
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    try:
        outcome = run_refresh_for_portfolio(db, portfolio_id, trigger_type="manual")
    except RefreshBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except OperationalError as exc:
        detail = str(getattr(exc, "orig", exc))
        if "database is locked" in detail.lower():
            raise HTTPException(
                status_code=503,
                detail="Database is busy (SQLite lock). Another refresh or valuation is still running. Retry shortly.",
            ) from exc
        raise
    metric = (
        RiskMetricOut.model_validate(outcome.metric_snapshot)
        if outcome.metric_snapshot is not None
        else None
    )
    return RefreshResponse(job=outcome.job, metrics=metric)


@router.get("/{portfolio_id}/overview", response_model=OverviewResponse)
def overview_route(portfolio_id: int, db: Session = Depends(get_db)) -> OverviewResponse:
    portfolio = get_portfolio_or_404(db, portfolio_id)
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    snapshot = latest_snapshot(db, portfolio_id)

    if snapshot is None:
        return OverviewResponse(
            portfolio=PortfolioRead.model_validate(portfolio),
            snapshot_id=None,
            as_of_date=None,
            holdings_count=0,
            top_holdings=[],
            allocation={},
            metrics=None,
            last_refresh=None,
            exposure_summary=None,
            narrative=None,
            valuation_summary=None,
            latest_scenario_run=None,
        )

    positions = list(
        db.scalars(
            select(HoldingsPosition)
            .where(HoldingsPosition.snapshot_id == snapshot.id)
            .order_by(HoldingsPosition.weight.desc())
        )
    )

    allocation: dict[str, float] = {}
    for pos in positions:
        key = pos.asset_type or "Unclassified"
        allocation[key] = allocation.get(key, 0.0) + float(pos.weight)

    metric = latest_metrics_for_snapshot(db, snapshot.id)
    metric_payload = RiskMetricOut.model_validate(metric) if metric else None
    exposure_summary = ExposureSummaryOut.model_validate(exposure_snapshot_payload(latest_exposure_snapshot(db, portfolio_id, snapshot.id)) or {
        "coverage": {"holding_count": len(positions), "lookthrough_positions": 0, "constituent_positions": 0, "covered_weight": 0.0, "covered_weight_pct": 0.0},
        "breakdowns": {},
        "top_lookthrough_holdings": [],
        "overlap_pairs": [],
        "concentration_signals": [],
        "warnings": ["exposure_snapshot_missing"],
    })

    last_job = latest_refresh_job(db, portfolio_id)
    last_refresh_payload = None if last_job is None else RefreshJobOut.model_validate(last_job)
    valuation_summary = _valuation_overview_for_portfolio(db, portfolio_id)
    latest_scenario = latest_scenario_run(db, portfolio_id)
    narrative = PortfolioNarrativeOut.model_validate(narrative_payload(latest_narrative_snapshot(db, portfolio_id, snapshot_id=snapshot.id)) or {
        "status": "partial",
        "cards": [],
        "watchouts": [{"level": "medium", "title": "Narrative not ready", "detail": "Run refresh to generate the deterministic portfolio narrative."}],
        "change_summary": {"headline": "No narrative snapshot available."},
        "evidence_chips": [],
        "warnings": ["narrative_snapshot_missing"],
    })

    return OverviewResponse(
        portfolio=PortfolioRead.model_validate(portfolio),
        snapshot_id=snapshot.id,
        as_of_date=snapshot.as_of_date,
        holdings_count=len(positions),
        top_holdings=[HoldingPositionOut.model_validate(p) for p in positions[:6]],
        allocation=allocation,
        metrics=metric_payload,
        last_refresh=last_refresh_payload,
        exposure_summary=exposure_summary,
        narrative=narrative,
        valuation_summary=valuation_summary,
        latest_scenario_run=(
            ScenarioRunListItem(
                id=latest_scenario.id,
                status=latest_scenario.status,
                factor_key=latest_scenario.factor_key,
                shock_value=latest_scenario.shock_value,
                shock_unit=latest_scenario.shock_unit,
                horizon_days=latest_scenario.horizon_days,
                confidence_level=latest_scenario.confidence_level,
                n_sims=latest_scenario.n_sims,
                selected_symbol=latest_scenario.selected_symbol,
                started_at=latest_scenario.started_at,
                finished_at=latest_scenario.finished_at,
                error=latest_scenario.error,
            )
            if latest_scenario is not None
            else None
        ),
    )


@router.get("/{portfolio_id}/exposures/overview", response_model=ExposureSummaryOut)
def portfolio_exposure_overview_route(portfolio_id: int, db: Session = Depends(get_db)) -> ExposureSummaryOut:
    portfolio = get_portfolio_or_404(db, portfolio_id)
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    snapshot = latest_snapshot(db, portfolio_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="No holdings snapshot found")
    payload = exposure_snapshot_payload(latest_exposure_snapshot(db, portfolio_id, snapshot.id))
    if payload is None:
        raise HTTPException(status_code=404, detail="No exposure snapshot found. Run refresh first.")
    return ExposureSummaryOut.model_validate(payload)


@router.get("/{portfolio_id}/narrative", response_model=PortfolioNarrativeOut)
def portfolio_narrative_route(portfolio_id: int, db: Session = Depends(get_db)) -> PortfolioNarrativeOut:
    portfolio = get_portfolio_or_404(db, portfolio_id)
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    snapshot = latest_snapshot(db, portfolio_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="No holdings snapshot found")
    payload = narrative_payload(latest_narrative_snapshot(db, portfolio_id, snapshot_id=snapshot.id))
    if payload is None:
        raise HTTPException(status_code=404, detail="No narrative snapshot found. Run refresh first.")
    return PortfolioNarrativeOut.model_validate(payload)


@router.get("/{portfolio_id}/analytics/risk", response_model=RiskAnalyticsResponse)
def risk_analytics_route(portfolio_id: int, db: Session = Depends(get_db)) -> RiskAnalyticsResponse:
    portfolio = get_portfolio_or_404(db, portfolio_id)
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    snapshot = latest_snapshot(db, portfolio_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="No holdings snapshot found")

    metric = latest_metrics_for_snapshot(db, snapshot.id)
    if metric is None:
        raise HTTPException(status_code=404, detail="No metrics found. Run refresh first.")

    contributions = list(
        db.scalars(
            select(PositionRiskContribution)
            .where(PositionRiskContribution.snapshot_id == snapshot.id)
            .order_by(PositionRiskContribution.pct_total_risk.desc())
        )
    )

    return RiskAnalyticsResponse(
        portfolio_id=portfolio_id,
        snapshot_id=snapshot.id,
        metrics=RiskMetricOut.model_validate(metric),
        contributions=[RiskContributionOut.model_validate(c) for c in contributions],
    )


@router.get("/{portfolio_id}/analytics/extended", response_model=ExtendedAnalyticsResponse)
def extended_analytics_route(portfolio_id: int, db: Session = Depends(get_db)) -> ExtendedAnalyticsResponse:
    portfolio = get_portfolio_or_404(db, portfolio_id)
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    snapshot = latest_snapshot(db, portfolio_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="No holdings snapshot found")

    ext = latest_extended_metrics_for_snapshot(db, snapshot.id)
    if ext is None:
        raise HTTPException(status_code=404, detail="No extended metrics found. Run refresh first.")

    metrics_json = _safe_json_loads(ext.metrics_json, {})
    warnings_json = _safe_json_loads(ext.warnings_json, [])
    if not isinstance(metrics_json, dict):
        metrics_json = {}
    if not isinstance(warnings_json, list):
        warnings_json = []

    return ExtendedAnalyticsResponse(
        portfolio_id=portfolio_id,
        snapshot_id=snapshot.id,
        extended=ExtendedMetricSnapshotOut(
            as_of_date=ext.as_of_date,
            window=ext.window,
            benchmark_symbol=ext.benchmark_symbol,
            metrics=metrics_json,
            warnings=[str(w) for w in warnings_json],
        ),
    )


@router.get("/{portfolio_id}/analytics/industry", response_model=IndustryOverviewResponse)
def industry_analytics_route(
    portfolio_id: int,
    params: Annotated[IndustryAnalyticsParams, Depends(_industry_analytics_params)],
    scope: Literal["holdings", "industry_map", "sector_map"] = Query("industry_map"),
    db: Session = Depends(get_db),
) -> IndustryOverviewResponse:
    portfolio = get_portfolio_or_404(db, portfolio_id)
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    snapshot = latest_snapshot(db, portfolio_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="No holdings snapshot found")

    positions = list(
        db.scalars(
            select(HoldingsPosition)
            .where(HoldingsPosition.snapshot_id == snapshot.id)
            .order_by(HoldingsPosition.weight.desc())
        )
    )
    if not positions:
        raise HTTPException(status_code=404, detail="No holdings positions found")

    industry_window_days = {
        "1D": 1,
        "1W": 7,
        "1M": 31,
        "3M": 92,
        "1Y": 366,
        "3Y": 366 * 3,
        "5Y": 366 * 5,
        "10Y": 366 * 10,
    }
    if params.date_mode == "custom" and params.start_date is not None and params.end_date is not None:
        start_date = params.start_date
        end_date = params.end_date
    else:
        window_days = industry_window_days.get(params.window, 366)
        end_date = date.today()
        start_date = end_date - timedelta(days=max(window_days * 2, 31))

    symbol_weights = {str(p.symbol).upper(): float(p.weight) for p in positions if p.symbol}
    returns_panel = pd.DataFrame(dtype=float)
    industry_weights: dict[str, float] = {}
    resolved_ticker_count = 0
    unresolved_slugs: list[str] = []
    mapped_industry_count = 0
    if scope == "industry_map":
        slugs = [entry.slug for entry in INDUSTRY_MAP]
        ticker_to_slug = resolve_industry_ticker_map(slugs)
        resolved_ticker_count = len(ticker_to_slug)
        unresolved_slugs = [slug for slug in slugs if slug not in set(ticker_to_slug.values())]
        mapped_prices = fetch_industry_price_panel(
            tickers=list(ticker_to_slug.keys()),
            start=start_date,
            end=end_date,
        )
        if params.interval == "weekly":
            mapped_prices = mapped_prices.resample("W-FRI").last().dropna(how="all")
        elif params.interval == "monthly":
            mapped_prices = mapped_prices.resample("ME").last().dropna(how="all")
        display_prices = map_tickers_to_display_industries(
            mapped_prices,
            ticker_to_slug=ticker_to_slug,
            slug_to_display=slug_to_display(),
        )
        normalized_display_prices = display_prices.copy()
        normalized_display_prices.index = pd.to_datetime(normalized_display_prices.index)
        normalized_display_prices = normalized_display_prices.sort_index()
        normalized_display_prices = normalized_display_prices.apply(pd.to_numeric, errors="coerce").ffill()
        returns_panel = normalized_display_prices.pct_change(fill_method=None)
        returns_panel = returns_panel.T.groupby(level=0).mean().T
        returns_panel = returns_panel.dropna(axis=0, how="all").dropna(axis=1, how="all")
        if returns_panel.empty:
            raise HTTPException(status_code=404, detail="Unable to compute industry return panel")
        mapped_industry_count = len(list(returns_panel.columns))
    elif scope == "sector_map":
        sector_prices = fetch_sector_price_panel(
            start=start_date,
            end=end_date,
        )
        if params.interval == "weekly":
            sector_prices = sector_prices.resample("W-FRI").last().dropna(how="all")
        elif params.interval == "monthly":
            sector_prices = sector_prices.resample("ME").last().dropna(how="all")
        sector_prices = sector_prices.sort_index().apply(pd.to_numeric, errors="coerce").ffill()
        returns_panel = sector_prices.pct_change(fill_method=None)
        returns_panel = returns_panel.T.groupby(level=0).mean().T
        returns_panel = returns_panel.dropna(axis=0, how="all").dropna(axis=1, how="all")
        if returns_panel.empty:
            raise HTTPException(status_code=404, detail="Unable to compute sector return panel")
        mapped_industry_count = len(list(returns_panel.columns))
        resolved_ticker_count = len(list(sector_prices.columns))
    else:
        symbols = list(symbol_weights.keys())
        prices = get_symbols_price_frame(db, symbols, start_date, end_date)
        if prices.empty:
            raise HTTPException(status_code=404, detail="No price history found for portfolio symbols")

        if params.interval == "weekly":
            prices = prices.resample("W-FRI").last().dropna(how="all")
        elif params.interval == "monthly":
            prices = prices.resample("ME").last().dropna(how="all")

        fundamentals = load_latest_fundamentals(db, symbols)
        ticker_to_industry = {
            symbol: str((getattr(fundamentals.get(symbol), "industry", None) or "Unknown industry")).strip() or "Unknown industry"
            for symbol in symbols
        }
        for symbol, weight in symbol_weights.items():
            industry = ticker_to_industry.get(symbol, "Unknown industry")
            industry_weights[industry] = industry_weights.get(industry, 0.0) + float(weight)

        returns_panel, _aggregation_meta = aggregate_industry_panel(
            prices,
            ticker_to_industry=ticker_to_industry,
            method="cap_weight_returns",
            market_caps=symbol_weights,
        )
        if returns_panel.empty:
            raise HTTPException(status_code=404, detail="Unable to compute industry return panel")
        mapped_industry_count = len(list(returns_panel.columns))
        resolved_ticker_count = len(symbols)

    periods_per_year = 252 if params.interval == "daily" else (52 if params.interval == "weekly" else 12)

    benchmark_symbol = (params.benchmark or portfolio.benchmark_symbol or "SPY").upper()
    benchmark_returns = None
    bench_frame = get_symbols_price_frame(db, [benchmark_symbol], start_date, end_date)
    if not bench_frame.empty:
        bench_series = bench_frame[benchmark_symbol] if benchmark_symbol in bench_frame.columns else bench_frame.iloc[:, 0]
        if params.interval == "weekly":
            bench_series = bench_series.resample("W-FRI").last()
        elif params.interval == "monthly":
            bench_series = bench_series.resample("ME").last()
        benchmark_returns = bench_series.pct_change(fill_method=None).dropna()

    metrics = compute_industry_return_metrics(
        returns_panel=returns_panel,
        benchmark_returns=benchmark_returns,
        risk_free_rate=settings.risk_free_rate,
        periods_per_year=periods_per_year,
    )
    matrices = build_industry_return_matrices(
        returns_panel=returns_panel,
        sort_by=params.sort_by,
        risk_free_rate=settings.risk_free_rate,
        periods_per_year=periods_per_year,
    )

    def _sort_value(item: IndustryMetricRowOut) -> float | str:
        if params.sort_by == "alphabetical":
            return item.industry.lower()
        if params.sort_by == "vol":
            return item.volatility_annualized if item.volatility_annualized is not None else float("-inf")
        if params.sort_by == "sharpe":
            return item.sharpe if item.sharpe is not None else float("-inf")
        return item.window_return if item.window_return is not None else float("-inf")

    rows = [
        IndustryMetricRowOut(
            industry=industry,
            weight=float(industry_weights.get(industry, 0.0)),
            window_return=payload.get("window_return"),
            annualized_return=payload.get("annualized_return"),
            volatility_periodic=payload.get("volatility_periodic"),
            volatility_annualized=payload.get("volatility_annualized"),
            skewness=payload.get("skewness"),
            kurtosis=payload.get("kurtosis"),
            var_95=payload.get("var_95"),
            cvar_95=payload.get("cvar_95"),
            sharpe=payload.get("sharpe"),
            sortino=payload.get("sortino"),
            upside_capture=payload.get("upside_capture"),
            downside_capture=payload.get("downside_capture"),
            beta=payload.get("beta"),
            tracking_error=payload.get("tracking_error"),
            information_ratio=payload.get("information_ratio"),
            max_drawdown=payload.get("max_drawdown"),
            hit_rate=payload.get("hit_rate"),
        )
        for industry, payload in metrics.items()
    ]
    rows.sort(key=_sort_value, reverse=(params.sort_order == "desc" and params.sort_by != "alphabetical"))
    if params.sort_by == "alphabetical" and params.sort_order == "desc":
        rows.reverse()

    def _maybe_reverse_matrix(matrix: dict[str, object]) -> IndustryMatrixOut:
        labels = [str(label) for label in matrix.get("labels", [])]
        values = matrix.get("values", [])
        sort_context = dict(matrix.get("sort_context", {}))
        direction = str(sort_context.get("direction", "desc"))
        expected = "asc" if params.sort_order == "asc" else "desc"
        if labels and direction != expected:
            labels = list(reversed(labels))
            values = [list(reversed(row)) for row in list(reversed(values))]
            sort_context["direction"] = expected
            metric_values = sort_context.get("metric_values")
            if isinstance(metric_values, dict):
                sort_context["metric_values"] = {label: metric_values.get(label) for label in labels}
        return IndustryMatrixOut(labels=labels, values=values, sort_context=sort_context)

    return IndustryOverviewResponse(
        portfolio_id=portfolio_id,
        snapshot_id=snapshot.id,
        as_of_date=snapshot.as_of_date,
        scope=scope,
        mapped_industry_count=mapped_industry_count,
        resolved_ticker_count=resolved_ticker_count,
        unresolved_slugs=unresolved_slugs,
        window=params.window,
        date_mode=params.date_mode,
        start_date=start_date,
        end_date=end_date,
        interval=params.interval,
        benchmark=benchmark_symbol,
        sort_by=params.sort_by,
        sort_order=params.sort_order,
        rows=rows,
        covariance_matrix=_maybe_reverse_matrix(matrices.get("covariance_matrix", {})),
        correlation_matrix=_maybe_reverse_matrix(matrices.get("correlation_matrix", {})),
    )


@router.get("/{portfolio_id}/analytics/macro-forecasts", response_model=MacroForecastResponse)
def macro_forecasts_route(portfolio_id: int, db: Session = Depends(get_db)) -> MacroForecastResponse:
    portfolio = get_portfolio_or_404(db, portfolio_id)
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    try:
        table_map = load_forecasts()
    except Exception as exc:
        return MacroForecastResponse(
            status="partial",
            tables=[],
            warnings=[f"Unable to load TradingEconomics forecasts: {exc}"],
        )

    tables = [
        MacroForecastTableOut(key=key, columns=payload["columns"], rows=payload["rows"])
        for key, payload in table_map.items()
    ]
    return MacroForecastResponse(tables=tables)


@router.get("/{portfolio_id}/prices", response_model=PricesResponse)
def prices_route(
    portfolio_id: int,
    symbols: str = Query(..., description="Comma-separated symbols"),
    range: Literal["1M", "3M", "6M", "1Y", "5Y", "CUSTOM"] = Query("1M"),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    db: Session = Depends(get_db),
) -> PricesResponse:
    portfolio = get_portfolio_or_404(db, portfolio_id)
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    # Support direct function invocation in tests where FastAPI Query defaults can leak through.
    if not isinstance(start_date, date):
        start_date = None
    if not isinstance(end_date, date):
        end_date = None

    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    if not symbol_list:
        raise HTTPException(status_code=400, detail="At least one symbol is required")

    if (start_date is None) != (end_date is None):
        raise HTTPException(
            status_code=400,
            detail="Both start_date and end_date are required together.",
        )

    if range == "CUSTOM" and (start_date is None or end_date is None):
        raise HTTPException(
            status_code=400,
            detail="CUSTOM range requires start_date and end_date.",
        )

    if start_date is not None and end_date is not None:
        if start_date > end_date:
            raise HTTPException(status_code=400, detail="start_date must be <= end_date.")
        effective_start = start_date
        effective_end = end_date
        response_range = "CUSTOM"
    else:
        days = RANGE_TO_DAYS.get(range, 31)
        effective_end = date.today()
        effective_start = effective_end - timedelta(days=max(days * 2, 31))
        response_range = range

    warnings: list[str] = []
    try:
        frame = get_symbols_price_frame(db, symbol_list, effective_start, effective_end)
    except Exception as exc:
        warnings.append("E_PRICE_FETCH_FAILED")
        warnings.append(f"provider_error:{exc.__class__.__name__}")
        return PricesResponse(
            portfolio_id=portfolio_id,
            range=response_range,
            status="partial",
            warnings=warnings,
            missing_symbols=symbol_list,
            series=[],
        )

    if frame.empty:
        warnings.append("E_NO_PRICE_DATA")
        return PricesResponse(
            portfolio_id=portfolio_id,
            range=response_range,
            status="no_data",
            warnings=warnings,
            missing_symbols=symbol_list,
            series=[],
        )

    if response_range == "CUSTOM":
        cutoff_ts = pd.Timestamp(effective_start)
    else:
        days = RANGE_TO_DAYS.get(range, 31)
        cutoff_ts = pd.Timestamp(effective_end - timedelta(days=days + 2))
    end_ts = pd.Timestamp(effective_end)
    frame = frame.loc[(frame.index >= cutoff_ts) & (frame.index <= end_ts)]

    series: list[SymbolPriceSeries] = []
    missing_symbols: list[str] = []
    for symbol in symbol_list:
        if symbol not in frame.columns:
            missing_symbols.append(symbol)
            continue
        points = [
            PricePoint(date=idx.date(), close=float(value))
            for idx, value in frame[symbol].dropna().items()
        ]
        if points:
            series.append(SymbolPriceSeries(symbol=symbol, points=points))
        else:
            missing_symbols.append(symbol)

    status = "ok"
    if missing_symbols:
        status = "partial"
        warnings.append("E_SYMBOL_DATA_MISSING")
    if not series:
        status = "no_data"
        warnings.append("E_NO_RANGE_DATA")

    return PricesResponse(
        portfolio_id=portfolio_id,
        range=response_range,
        status=status,
        warnings=warnings,
        missing_symbols=missing_symbols,
        series=series,
    )


@router.get("/{portfolio_id}/securities/{symbol}/events", response_model=SecurityEventsResponse)
def security_events_route(
    portfolio_id: int,
    symbol: str,
    range: Literal["1M", "3M", "6M", "1Y", "5Y", "CUSTOM"] = Query("1M"),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    db: Session = Depends(get_db),
) -> SecurityEventsResponse:
    portfolio = get_portfolio_or_404(db, portfolio_id)
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    if not isinstance(start_date, date):
        start_date = None
    if not isinstance(end_date, date):
        end_date = None

    if (start_date is None) != (end_date is None):
        raise HTTPException(
            status_code=400,
            detail="Both start_date and end_date are required together.",
        )

    if range == "CUSTOM" and (start_date is None or end_date is None):
        raise HTTPException(
            status_code=400,
            detail="CUSTOM range requires start_date and end_date.",
        )

    if start_date is not None and end_date is not None:
        if start_date > end_date:
            raise HTTPException(status_code=400, detail="start_date must be <= end_date.")
        effective_start = start_date
        effective_end = end_date
        response_range = "CUSTOM"
    else:
        days = RANGE_TO_DAYS.get(range, 31)
        effective_end = date.today()
        effective_start = effective_end - timedelta(days=days)
        response_range = range

    warnings: list[str] = []
    try:
        payload = fetch_security_events(
            symbol=symbol.upper(),
            start_date=effective_start,
            end_date=effective_end,
            max_rows=300,
        )
        warnings.extend(payload.warnings)
    except Exception as exc:  # pragma: no cover - provider variability
        warnings.append("E_EVENT_FETCH_FAILED")
        warnings.append(f"provider_error:{exc.__class__.__name__}")
        return SecurityEventsResponse(
            symbol=symbol.upper(),
            range=response_range,
            status="partial",
            warnings=warnings,
            events=[],
            corporate_actions=[],
            insider_transactions=[],
            analyst_revisions=[],
        )

    return SecurityEventsResponse(
        symbol=payload.symbol,
        range=response_range,
        status=payload.status,
        warnings=sorted(set(warnings)),
        events=[
            MarketEventOut(
                id=item.id,
                date=item.date,
                event_type=item.event_type,
                title=item.title,
                summary=item.summary,
                detail=item.detail,
                link_target=item.link_target,
            )
            for item in payload.events
        ],
        corporate_actions=[
            CorporateActionRowOut(
                date=item.date,
                action_type=item.action_type,
                value=item.value,
                description=item.description,
            )
            for item in payload.corporate_actions
        ],
        insider_transactions=[
            InsiderTransactionRowOut(
                date=item.date,
                insider=item.insider,
                position=item.position,
                transaction=item.transaction,
                shares=item.shares,
                value=item.value,
                ownership=item.ownership,
                text=item.text,
            )
            for item in payload.insider_transactions
        ],
        analyst_revisions=[
            AnalystRevisionRowOut(
                date=item.date,
                firm=item.firm,
                action=item.action,
                to_grade=item.to_grade,
                from_grade=item.from_grade,
                current_price_target=item.current_price_target,
                prior_price_target=item.prior_price_target,
                price_target_action=item.price_target_action,
            )
            for item in payload.analyst_revisions
        ],
    )


@router.get("/{portfolio_id}/news", response_model=PortfolioNewsResponse)
def portfolio_news_route(
    portfolio_id: int,
    limit: int = Query(120, ge=1, le=500),
    per_symbol: int = Query(30, ge=1, le=150),
    db: Session = Depends(get_db),
) -> PortfolioNewsResponse:
    portfolio = get_portfolio_or_404(db, portfolio_id)
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    snapshot = latest_snapshot(db, portfolio_id)
    if snapshot is None:
        return PortfolioNewsResponse(
            portfolio_id=portfolio_id,
            status="no_data",
            warnings=["portfolio_news:no_snapshot"],
            count=0,
            articles=[],
        )

    positions = list(
        db.scalars(
            select(HoldingsPosition)
            .where(HoldingsPosition.snapshot_id == snapshot.id)
            .order_by(HoldingsPosition.weight.desc())
        )
    )
    symbols = [position.symbol.upper() for position in positions]
    if not symbols:
        return PortfolioNewsResponse(
            portfolio_id=portfolio_id,
            status="no_data",
            warnings=["portfolio_news:no_symbols"],
            count=0,
            articles=[],
        )

    try:
        payload = fetch_portfolio_news(
            symbols=symbols,
            max_per_symbol=per_symbol,
            max_rows=limit,
        )
    except Exception as exc:  # pragma: no cover - provider variability
        return PortfolioNewsResponse(
            portfolio_id=portfolio_id,
            status="partial",
            warnings=["E_PORTFOLIO_NEWS_FETCH_FAILED", f"provider_error:{exc.__class__.__name__}"],
            count=0,
            articles=[],
        )

    articles = [
        NewsArticleOut(
            id=article.id,
            title=article.title,
            summary=article.summary,
            pub_date=article.pub_date,
            provider=article.provider,
            url=article.url,
            thumbnail_url=article.thumbnail_url,
            content_type=article.content_type,
            symbols=article.symbols,
        )
        for article in payload.articles
    ]

    return PortfolioNewsResponse(
        portfolio_id=portfolio_id,
        status=payload.status,
        warnings=payload.warnings,
        count=len(articles),
        articles=articles,
    )
