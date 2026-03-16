from __future__ import annotations

import json
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import (
    SecurityValuationResult,
    ValuationDcfDetail,
    ValuationDdmDetail,
    ValuationRiDetail,
    ValuationRun,
)
from app.schemas.valuation import (
    AnalystCoverageDetail,
    AnalystDetailResponse,
    AnalystLatestResponse,
    FinancialRatioMetricOut,
    InstitutionalHolderOut,
    AnalystPriceTargetSnapshot,
    AnalystTargetScenario,
    PortfolioValuationOverviewResponse,
    RecommendationBucket,
    SecurityDcfDetailResponse,
    SecurityDdmDetailResponse,
    SecurityRiDetailResponse,
    SecurityFinancialRatiosResponse,
    SecurityFinancialStatementsResponse,
    SecurityOverviewResponse,
    SecurityValuationOut,
    ShareholderBreakdownItem,
    RiDetailScenarioOut,
    DdmDetailScenarioOut,
    ValuationAssumptionsIn,
    DcfDetailScenarioOut,
    ValuationRecomputeResponse,
    ValuationRunOut,
)
from app.schemas.analytics import NewsArticleOut, SecurityNewsResponse
from app.services.portfolio import get_portfolio_or_404
from app.services.providers import (
    fetch_analyst_detail,
    fetch_financial_ratios,
    fetch_financial_statements,
    fetch_security_news,
    fetch_security_snapshot,
    fetch_stock_overview,
)
from app.services.valuation import (
    latest_analyst_snapshot,
    latest_portfolio_valuation_snapshot,
    latest_security_valuation_result,
    latest_valuation_run,
    parse_portfolio_valuation_summary,
    parse_security_valuation_result,
    run_portfolio_valuation,
)
from app.services.valuation.analyst import compute_analyst_upside
from app.services.valuation.orchestrator import _upsert_analyst_snapshot, _upsert_fundamental_snapshot

router = APIRouter(tags=["valuations"])


def _json_loads(value: str | None, fallback: Any) -> Any:
    if value is None or value == "":
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def _overview_payload(
    db: Session,
    portfolio_id: int,
) -> PortfolioValuationOverviewResponse:
    snapshot = latest_portfolio_valuation_snapshot(db, portfolio_id)
    run = latest_valuation_run(db, portfolio_id)
    if snapshot is None:
        return PortfolioValuationOverviewResponse(
            portfolio_id=portfolio_id,
            snapshot_id=None,
            as_of_date=None,
            status="no_data",
            weighted_analyst_upside=None,
            weighted_dcf_upside=None,
            weighted_ri_upside=None,
            weighted_ddm_upside=None,
            weighted_relative_upside=None,
            weighted_composite_upside=None,
            coverage_ratio=0.0,
            overvalued_weight=0.0,
            undervalued_weight=0.0,
            summary={},
            run=(ValuationRunOut.model_validate(run) if run else None),
            results=[],
            warnings=["valuation: no_snapshot"],
        )

    parsed = parse_portfolio_valuation_summary(snapshot)

    latest_run = run
    if latest_run is None or latest_run.id != snapshot.run_id:
        latest_run = db.get(ValuationRun, snapshot.run_id)

    result_rows = list(
        db.scalars(
            select(SecurityValuationResult)
            .where(SecurityValuationResult.run_id == snapshot.run_id)
            .order_by(SecurityValuationResult.symbol.asc())
        )
    )
    results = [SecurityValuationOut(**parse_security_valuation_result(row)) for row in result_rows]

    warnings: list[str] = []
    status = "ok"
    if parsed["coverage_ratio"] <= 0:
        status = "partial"
        warnings.append("valuation: no_term_coverage")
    elif parsed["coverage_ratio"] < 0.6:
        status = "partial"
        warnings.append("valuation: low_coverage")

    return PortfolioValuationOverviewResponse(
        portfolio_id=portfolio_id,
        snapshot_id=parsed["snapshot_id"],
        as_of_date=parsed["as_of_date"],
        status=status,
        weighted_analyst_upside=parsed["weighted_analyst_upside"],
        weighted_dcf_upside=parsed["weighted_dcf_upside"],
        weighted_ri_upside=parsed["weighted_ri_upside"],
        weighted_ddm_upside=parsed["weighted_ddm_upside"],
        weighted_relative_upside=parsed["weighted_relative_upside"],
        weighted_composite_upside=parsed["weighted_composite_upside"],
        coverage_ratio=parsed["coverage_ratio"],
        overvalued_weight=parsed["overvalued_weight"],
        undervalued_weight=parsed["undervalued_weight"],
        summary=parsed["summary"],
        run=(ValuationRunOut.model_validate(latest_run) if latest_run is not None else None),
        results=results,
        warnings=warnings,
    )


@router.get(
    "/portfolios/{portfolio_id}/valuations/overview",
    response_model=PortfolioValuationOverviewResponse,
)
def portfolio_valuation_overview_route(
    portfolio_id: int,
    db: Session = Depends(get_db),
) -> PortfolioValuationOverviewResponse:
    portfolio = get_portfolio_or_404(db, portfolio_id)
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    return _overview_payload(db, portfolio_id)


@router.post(
    "/portfolios/{portfolio_id}/valuations/recompute",
    response_model=ValuationRecomputeResponse,
)
def portfolio_valuation_recompute_route(
    portfolio_id: int,
    payload: ValuationAssumptionsIn,
    db: Session = Depends(get_db),
) -> ValuationRecomputeResponse:
    portfolio = get_portfolio_or_404(db, portfolio_id)
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    try:
        outcome = run_portfolio_valuation(
            db,
            portfolio_id=portfolio_id,
            trigger_type="manual_recompute",
            assumptions_override=payload.model_dump(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    db.refresh(outcome.run)
    overview = _overview_payload(db, portfolio_id)
    return ValuationRecomputeResponse(
        run=ValuationRunOut.model_validate(outcome.run),
        overview=overview,
    )


@router.get("/securities/{symbol}/analyst/latest", response_model=AnalystLatestResponse)
def analyst_latest_route(symbol: str, db: Session = Depends(get_db)) -> AnalystLatestResponse:
    symbol = symbol.upper()
    snap = latest_analyst_snapshot(db, symbol)
    warnings: list[str] = []
    if snap is None or snap.as_of_date < date.today():
        try:
            payload = fetch_security_snapshot(symbol, date.today())
            snap = _upsert_analyst_snapshot(db, symbol=symbol, as_of_date=date.today(), payload=payload)
            _upsert_fundamental_snapshot(db, symbol=symbol, as_of_date=date.today(), payload=payload)
            db.commit()
        except Exception as exc:
            warnings.append(f"provider_error:{exc.__class__.__name__}")
            db.rollback()
            snap = latest_analyst_snapshot(db, symbol)

    if snap is None:
        return AnalystLatestResponse(
            symbol=symbol,
            as_of_date=None,
            current_price=None,
            target_mean=None,
            target_high=None,
            target_low=None,
            analyst_count=None,
            recommendation_key=None,
            recommendation_mean=None,
            analyst_upside=None,
            status="no_data",
            warnings=["analyst: no_snapshot", *warnings],
        )

    analyst_upside, status_base, compute_warn = compute_analyst_upside(
        current_price=snap.current_price,
        target_mean=snap.target_mean,
    )
    warnings.extend(compute_warn)
    status = "ok" if status_base == "full" else "partial"

    return AnalystLatestResponse(
        symbol=symbol,
        as_of_date=snap.as_of_date,
        current_price=snap.current_price,
        target_mean=snap.target_mean,
        target_high=snap.target_high,
        target_low=snap.target_low,
        analyst_count=snap.analyst_count,
        recommendation_key=snap.recommendation_key,
        recommendation_mean=snap.recommendation_mean,
        analyst_upside=analyst_upside,
        status=status,
        warnings=sorted(set(warnings)),
    )


@router.get("/securities/{symbol}/overview", response_model=SecurityOverviewResponse)
def security_overview_route(symbol: str) -> SecurityOverviewResponse:
    symbol = symbol.upper()
    try:
        payload = fetch_stock_overview(symbol=symbol, max_holders=80)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Security overview fetch failed: {exc.__class__.__name__}") from exc

    return SecurityOverviewResponse(
        symbol=payload.symbol,
        status=payload.status,
        warnings=payload.warnings,
        name=payload.name,
        description=payload.description,
        industry=payload.industry,
        sector=payload.sector,
        country=payload.country,
        full_address=payload.full_address,
        website=payload.website,
        market_cap=payload.market_cap,
        current_price=payload.current_price,
        daily_return=payload.daily_return,
        ytd_return=payload.ytd_return,
        one_year_return=payload.one_year_return,
        beta=payload.beta,
        pe=payload.pe,
        dividend_yield=payload.dividend_yield,
        shareholder_breakdown=[
            ShareholderBreakdownItem(
                label=row.label,
                value=row.value,
                display_value=row.display_value,
            )
            for row in payload.shareholder_breakdown
        ],
        institutional_holders=[
            InstitutionalHolderOut(
                date_reported=row.date_reported,
                holder=row.holder,
                pct_held=row.pct_held,
                shares=row.shares,
                value=row.value,
                pct_change=row.pct_change,
            )
            for row in payload.institutional_holders
        ],
    )


@router.get("/securities/{symbol}/financial-ratios", response_model=SecurityFinancialRatiosResponse)
def security_financial_ratios_route(symbol: str) -> SecurityFinancialRatiosResponse:
    symbol = symbol.upper()
    try:
        payload = fetch_financial_ratios(symbol=symbol)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Security financial ratios fetch failed: {exc.__class__.__name__}") from exc

    return SecurityFinancialRatiosResponse(
        symbol=payload.symbol,
        status=payload.status,
        warnings=payload.warnings,
        annual=[
            FinancialRatioMetricOut(
                key=item.key,
                label=item.label,
                category=item.category,
                unit=item.unit,
                value=item.value,
                source=item.source,
                description=item.description,
            )
            for item in payload.annual
        ],
        quarterly=[
            FinancialRatioMetricOut(
                key=item.key,
                label=item.label,
                category=item.category,
                unit=item.unit,
                value=item.value,
                source=item.source,
                description=item.description,
            )
            for item in payload.quarterly
        ],
    )


@router.get("/securities/{symbol}/financials", response_model=SecurityFinancialStatementsResponse)
def security_financials_route(symbol: str) -> SecurityFinancialStatementsResponse:
    symbol = symbol.upper()
    try:
        payload = fetch_financial_statements(symbol=symbol, max_rows=260)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Security financials fetch failed: {exc.__class__.__name__}") from exc

    return SecurityFinancialStatementsResponse(
        symbol=payload.symbol,
        status=payload.status,
        warnings=payload.warnings,
        income_statement_annual=payload.income_statement_annual,
        income_statement_quarterly=payload.income_statement_quarterly,
        balance_sheet_annual=payload.balance_sheet_annual,
        balance_sheet_quarterly=payload.balance_sheet_quarterly,
        cashflow_annual=payload.cashflow_annual,
        cashflow_quarterly=payload.cashflow_quarterly,
    )


@router.get("/securities/{symbol}/analyst/detail", response_model=AnalystDetailResponse)
def analyst_detail_route(symbol: str) -> AnalystDetailResponse:
    symbol = symbol.upper()
    try:
        payload = fetch_analyst_detail(symbol=symbol, max_rows=300)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Analyst detail fetch failed: {exc.__class__.__name__}") from exc

    return AnalystDetailResponse(
        symbol=payload.symbol,
        status=payload.status,
        warnings=payload.warnings,
        snapshot=AnalystPriceTargetSnapshot(
            as_of_date=payload.snapshot.get("as_of_date"),
            current=payload.snapshot.get("current"),
            high=payload.snapshot.get("high"),
            low=payload.snapshot.get("low"),
            mean=payload.snapshot.get("mean"),
            median=payload.snapshot.get("median"),
        ),
        coverage=AnalystCoverageDetail(
            analyst_count=payload.coverage.get("analyst_count"),
            recommendation_key=payload.coverage.get("recommendation_key"),
            recommendation_mean=payload.coverage.get("recommendation_mean"),
        ),
        target_scenarios=[
            AnalystTargetScenario(
                label=row.get("label", ""),
                target=row.get("target"),
                return_pct=row.get("return_pct"),
            )
            for row in payload.target_scenarios
        ],
        current_recommendations=[
            RecommendationBucket(
                label=row.get("label", ""),
                count=int(row.get("count", 0) or 0),
            )
            for row in payload.current_recommendations
        ],
        recommendations_history=payload.recommendations_history,
        recommendations_table=payload.recommendations_table,
        eps_trend=payload.eps_trend,
        eps_revisions=payload.eps_revisions,
        earnings_estimate=payload.earnings_estimate,
        revenue_estimate=payload.revenue_estimate,
        growth_estimates=payload.growth_estimates,
    )


@router.get("/securities/{symbol}/news", response_model=SecurityNewsResponse)
def security_news_route(
    symbol: str,
    limit: int = Query(40, ge=1, le=300),
) -> SecurityNewsResponse:
    symbol = symbol.upper()
    try:
        payload = fetch_security_news(symbol=symbol, max_rows=limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Security news fetch failed: {exc.__class__.__name__}") from exc

    return SecurityNewsResponse(
        symbol=symbol,
        status=payload.status,
        warnings=payload.warnings,
        articles=[
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
        ],
    )


@router.get("/securities/{symbol}/valuation/latest", response_model=SecurityValuationOut)
def security_valuation_latest_route(
    symbol: str,
    portfolio_id: int = Query(...),
    db: Session = Depends(get_db),
) -> SecurityValuationOut:
    portfolio = get_portfolio_or_404(db, portfolio_id)
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    row = latest_security_valuation_result(
        db,
        portfolio_id=portfolio_id,
        symbol=symbol.upper(),
    )
    if row is None:
        raise HTTPException(status_code=404, detail="No valuation found for symbol in this portfolio")
    return SecurityValuationOut(**parse_security_valuation_result(row))


@router.get("/securities/{symbol}/valuation/dcf-detail", response_model=SecurityDcfDetailResponse)
def security_valuation_dcf_detail_route(
    symbol: str,
    portfolio_id: int = Query(...),
    db: Session = Depends(get_db),
) -> SecurityDcfDetailResponse:
    clean_symbol = symbol.upper()
    portfolio = get_portfolio_or_404(db, portfolio_id)
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    valuation_row = latest_security_valuation_result(
        db,
        portfolio_id=portfolio_id,
        symbol=clean_symbol,
    )
    if valuation_row is None:
        raise HTTPException(status_code=404, detail="No valuation found for symbol in this portfolio")

    detail_rows = list(
        db.scalars(
            select(ValuationDcfDetail)
            .where(ValuationDcfDetail.run_id == valuation_row.run_id)
            .where(ValuationDcfDetail.symbol == clean_symbol)
            .order_by(ValuationDcfDetail.id.asc())
        )
    )

    scenario_sort = {"base": 0, "bull": 1, "bear": 2}
    parsed_scenarios: list[DcfDetailScenarioOut] = []
    warnings: list[str] = []
    for row in sorted(detail_rows, key=lambda item: scenario_sort.get(item.scenario_key, 99)):
        row_warnings = _json_loads(row.warnings_json, [])
        if isinstance(row_warnings, list):
            warnings.extend([str(warn) for warn in row_warnings])
        parsed_scenarios.append(
            DcfDetailScenarioOut(
                scenario_key=row.scenario_key,
                assumptions=_json_loads(row.assumptions_json, {}),
                forecast=_json_loads(row.forecast_json, []),
                diagnostics=_json_loads(row.diagnostics_json, {}),
                warnings=[str(warn) for warn in row_warnings] if isinstance(row_warnings, list) else [],
            )
        )

    valuation_payload = parse_security_valuation_result(valuation_row)
    inputs = valuation_payload.get("inputs")
    if not isinstance(inputs, dict):
        inputs = {}
    run_assumptions = _json_loads(valuation_row.run.assumptions_json, {}) if valuation_row.run is not None else {}
    if not isinstance(run_assumptions, dict):
        run_assumptions = {}
    dcf_assumptions = run_assumptions.get("dcf")
    if not isinstance(dcf_assumptions, dict):
        dcf_assumptions = {}

    warnings.extend([str(warn) for warn in valuation_payload.get("warnings", [])])
    status = "ok"
    if not parsed_scenarios:
        status = "no_data"
        warnings.append("dcf:detail_unavailable")
    elif warnings:
        status = "partial"

    return SecurityDcfDetailResponse(
        portfolio_id=portfolio_id,
        symbol=clean_symbol,
        as_of_date=valuation_row.as_of_date,
        status=status,
        model_version=inputs.get("dcf_model_version"),
        quality_score=inputs.get("dcf_quality_score"),
        anchor_mode=dcf_assumptions.get("anchor_mode"),
        anchor_diagnostics_summary=inputs.get("dcf_anchor_diagnostics_summary") or {},
        tv_breakdown_summary=inputs.get("dcf_tv_breakdown_summary") or {},
        assumptions_used=inputs.get("dcf_assumptions_used") or {},
        scenarios=parsed_scenarios,
        warnings=sorted(set(warnings)),
    )


@router.get("/securities/{symbol}/valuation/ri-detail", response_model=SecurityRiDetailResponse)
def security_valuation_ri_detail_route(
    symbol: str,
    portfolio_id: int = Query(...),
    db: Session = Depends(get_db),
) -> SecurityRiDetailResponse:
    clean_symbol = symbol.upper()
    portfolio = get_portfolio_or_404(db, portfolio_id)
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    valuation_row = latest_security_valuation_result(
        db,
        portfolio_id=portfolio_id,
        symbol=clean_symbol,
    )
    if valuation_row is None:
        raise HTTPException(status_code=404, detail="No valuation found for symbol in this portfolio")

    detail_rows = list(
        db.scalars(
            select(ValuationRiDetail)
            .where(ValuationRiDetail.run_id == valuation_row.run_id)
            .where(ValuationRiDetail.symbol == clean_symbol)
            .order_by(ValuationRiDetail.id.asc())
        )
    )

    scenario_sort = {"base": 0, "bull": 1, "bear": 2}
    parsed_scenarios: list[RiDetailScenarioOut] = []
    warnings: list[str] = []
    for row in sorted(detail_rows, key=lambda item: scenario_sort.get(item.scenario_key, 99)):
        row_warnings = _json_loads(row.warnings_json, [])
        if isinstance(row_warnings, list):
            warnings.extend([str(warn) for warn in row_warnings])
        parsed_scenarios.append(
            RiDetailScenarioOut(
                scenario_key=row.scenario_key,
                assumptions=_json_loads(row.assumptions_json, {}),
                forecast=_json_loads(row.forecast_json, []),
                diagnostics=_json_loads(row.diagnostics_json, {}),
                warnings=[str(warn) for warn in row_warnings] if isinstance(row_warnings, list) else [],
            )
        )

    valuation_payload = parse_security_valuation_result(valuation_row)
    inputs = valuation_payload.get("inputs")
    if not isinstance(inputs, dict):
        inputs = {}
    run_assumptions = _json_loads(valuation_row.run.assumptions_json, {}) if valuation_row.run is not None else {}
    if not isinstance(run_assumptions, dict):
        run_assumptions = {}
    ri_assumptions = run_assumptions.get("ri")
    if not isinstance(ri_assumptions, dict):
        ri_assumptions = {}

    warnings.extend([str(warn) for warn in valuation_payload.get("warnings", [])])
    status = "ok"
    if not parsed_scenarios:
        status = "no_data"
        warnings.append("ri:detail_unavailable")
    elif warnings:
        status = "partial"

    return SecurityRiDetailResponse(
        portfolio_id=portfolio_id,
        symbol=clean_symbol,
        as_of_date=valuation_row.as_of_date,
        status=status,
        model_version=inputs.get("ri_model_version"),
        quality_score=inputs.get("ri_quality_score"),
        anchor_mode=ri_assumptions.get("anchor_mode"),
        anchor_diagnostics_summary=inputs.get("ri_anchor_diagnostics_summary") or {},
        terminal_summary=inputs.get("ri_terminal_summary") or {},
        assumptions_used=inputs.get("ri_assumptions_used") or {},
        scenarios=parsed_scenarios,
        warnings=sorted(set(warnings)),
    )


@router.get("/securities/{symbol}/valuation/ddm-detail", response_model=SecurityDdmDetailResponse)
def security_valuation_ddm_detail_route(
    symbol: str,
    portfolio_id: int = Query(...),
    db: Session = Depends(get_db),
) -> SecurityDdmDetailResponse:
    clean_symbol = symbol.upper()
    portfolio = get_portfolio_or_404(db, portfolio_id)
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    valuation_row = latest_security_valuation_result(
        db,
        portfolio_id=portfolio_id,
        symbol=clean_symbol,
    )
    if valuation_row is None:
        raise HTTPException(status_code=404, detail="No valuation found for symbol in this portfolio")

    detail_rows = list(
        db.scalars(
            select(ValuationDdmDetail)
            .where(ValuationDdmDetail.run_id == valuation_row.run_id)
            .where(ValuationDdmDetail.symbol == clean_symbol)
            .order_by(ValuationDdmDetail.id.asc())
        )
    )

    scenario_sort = {"base": 0, "bull": 1, "bear": 2}
    parsed_scenarios: list[DdmDetailScenarioOut] = []
    warnings: list[str] = []
    for row in sorted(detail_rows, key=lambda item: scenario_sort.get(item.scenario_key, 99)):
        row_warnings = _json_loads(row.warnings_json, [])
        if isinstance(row_warnings, list):
            warnings.extend([str(warn) for warn in row_warnings])
        parsed_scenarios.append(
            DdmDetailScenarioOut(
                scenario_key=row.scenario_key,
                assumptions=_json_loads(row.assumptions_json, {}),
                forecast=_json_loads(row.forecast_json, []),
                diagnostics=_json_loads(row.diagnostics_json, {}),
                warnings=[str(warn) for warn in row_warnings] if isinstance(row_warnings, list) else [],
            )
        )

    valuation_payload = parse_security_valuation_result(valuation_row)
    inputs = valuation_payload.get("inputs")
    if not isinstance(inputs, dict):
        inputs = {}
    run_assumptions = _json_loads(valuation_row.run.assumptions_json, {}) if valuation_row.run is not None else {}
    if not isinstance(run_assumptions, dict):
        run_assumptions = {}
    ddm_assumptions = run_assumptions.get("ddm")
    if not isinstance(ddm_assumptions, dict):
        ddm_assumptions = {}

    warnings.extend([str(warn) for warn in valuation_payload.get("warnings", [])])
    status = "ok"
    if not parsed_scenarios:
        status = "no_data"
        warnings.append("ddm:detail_unavailable")
    elif warnings:
        status = "partial"

    return SecurityDdmDetailResponse(
        portfolio_id=portfolio_id,
        symbol=clean_symbol,
        as_of_date=valuation_row.as_of_date,
        status=status,
        model_version=inputs.get("ddm_model_version"),
        quality_score=inputs.get("ddm_quality_score"),
        anchor_mode=ddm_assumptions.get("anchor_mode"),
        coverage_mode=inputs.get("ddm_coverage_mode"),
        anchor_diagnostics_summary=inputs.get("ddm_anchor_diagnostics_summary") or {},
        terminal_summary=inputs.get("ddm_terminal_summary") or {},
        assumptions_used=inputs.get("ddm_assumptions_used") or {},
        scenarios=parsed_scenarios,
        warnings=sorted(set(warnings)),
    )


@router.post("/securities/{symbol}/valuation/recompute", response_model=SecurityValuationOut)
def security_valuation_recompute_route(
    symbol: str,
    portfolio_id: int = Query(...),
    payload: ValuationAssumptionsIn | None = None,
    db: Session = Depends(get_db),
) -> SecurityValuationOut:
    portfolio = get_portfolio_or_404(db, portfolio_id)
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    assumptions: dict[str, Any] | None = payload.model_dump() if payload is not None else None
    try:
        run_portfolio_valuation(
            db,
            portfolio_id=portfolio_id,
            trigger_type="symbol_recompute",
            assumptions_override=assumptions,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()

    row = latest_security_valuation_result(
        db,
        portfolio_id=portfolio_id,
        symbol=symbol.upper(),
    )
    if row is None:
        raise HTTPException(status_code=404, detail="No valuation found for symbol in this portfolio")
    return SecurityValuationOut(**parse_security_valuation_result(row))
