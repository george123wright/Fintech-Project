from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
import pandas as pd
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.models import HoldingsPosition, PositionRiskContribution
from app.schemas.analytics import (
    AnalystRevisionRowOut,
    CorporateActionRowOut,
    ExposureSummaryOut,
    ExtendedAnalyticsResponse,
    ExtendedMetricSnapshotOut,
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
from app.services.insights import (
    build_portfolio_exposure_summary,
    build_portfolio_narrative,
    load_latest_fundamentals,
)
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
from app.services.refresh import run_refresh_for_portfolio
from app.services.valuation import (
    latest_portfolio_valuation_snapshot,
    latest_valuation_run,
    parse_portfolio_valuation_summary,
)

from app.db import get_db

router = APIRouter(prefix="/portfolios", tags=["portfolios"])


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
    fundamentals_by_symbol = load_latest_fundamentals(db, [position.symbol for position in positions])
    exposure_summary_raw = build_portfolio_exposure_summary(
        positions,
        fundamentals_by_symbol=fundamentals_by_symbol,
        metrics=metric,
    )
    exposure_summary = ExposureSummaryOut.model_validate(exposure_summary_raw)

    last_job = latest_refresh_job(db, portfolio_id)
    last_refresh_payload = None if last_job is None else RefreshJobOut.model_validate(last_job)
    valuation_summary = _valuation_overview_for_portfolio(db, portfolio_id)
    latest_scenario = latest_scenario_run(db, portfolio_id)
    narrative = PortfolioNarrativeOut.model_validate(
        build_portfolio_narrative(
            positions=positions,
            exposure_summary=exposure_summary_raw,
            metrics=metric,
            valuation_summary=valuation_summary,
            latest_scenario=latest_scenario,
        )
    )

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
