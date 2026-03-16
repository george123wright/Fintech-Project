from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.scenarios import (
    ScenarioMetadataResponse,
    ScenarioPreviewRequest,
    ScenarioResultResponse,
    ScenarioRunListResponse,
)
from app.services.portfolio import get_portfolio_or_404
from app.services.scenarios import (
    FACTOR_SPECS,
    get_scenario_run_detail,
    list_scenario_runs,
    run_scenario_preview,
    scenario_metadata,
    scenario_sensitivity,
)

router = APIRouter(tags=["scenarios"])


@router.get(
    "/portfolios/{portfolio_id}/scenarios/metadata",
    response_model=ScenarioMetadataResponse,
)
def scenario_metadata_route(portfolio_id: int, db: Session = Depends(get_db)) -> ScenarioMetadataResponse:
    portfolio = get_portfolio_or_404(db, portfolio_id)
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    return scenario_metadata(portfolio_id)


@router.post(
    "/portfolios/{portfolio_id}/scenarios/preview",
    response_model=ScenarioResultResponse,
)
def scenario_preview_route(
    portfolio_id: int,
    payload: ScenarioPreviewRequest,
    db: Session = Depends(get_db),
) -> ScenarioResultResponse:
    portfolio = get_portfolio_or_404(db, portfolio_id)
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    try:
        out = run_scenario_preview(db, portfolio_id=portfolio_id, payload=payload, persist=False)
        return out
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OperationalError as exc:
        db.rollback()
        return ScenarioResultResponse(
            status="partial",
            warnings=[
                "E_DB_SCHEMA_MISMATCH",
                "Database schema is out of date for scenarios. Restart backend after backup DB migration/reset.",
            ],
            model_version="scenario_v1",
            inputs=payload.model_dump(),
            assumptions={},
            portfolio_impact={"symbol": "portfolio"},
            selected_stock_impact=None,
            contributions=[],
            distribution_bins=[],
            simulation_paths=[],
            relationship_stats={},
            simulation_stats={},
            narrative=["Scenario preview blocked by database schema mismatch."],
            run_id=None,
            created_at=None,
        )
    except Exception as exc:
        db.rollback()
        return ScenarioResultResponse(
            status="partial",
            warnings=["E_SCENARIO_PREVIEW_FAILED", f"provider_error:{exc.__class__.__name__}"],
            model_version="scenario_v1",
            inputs=payload.model_dump(),
            assumptions={},
            portfolio_impact={"symbol": "portfolio"},
            selected_stock_impact=None,
            contributions=[],
            distribution_bins=[],
            simulation_paths=[],
            relationship_stats={},
            simulation_stats={},
            narrative=["Preview failed due to recoverable data issue. Run refresh and try again."],
            run_id=None,
            created_at=None,
        )


@router.post(
    "/portfolios/{portfolio_id}/scenarios/run",
    response_model=ScenarioResultResponse,
)
def scenario_run_route(
    portfolio_id: int,
    payload: ScenarioPreviewRequest,
    db: Session = Depends(get_db),
) -> ScenarioResultResponse:
    portfolio = get_portfolio_or_404(db, portfolio_id)
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    try:
        out = run_scenario_preview(db, portfolio_id=portfolio_id, payload=payload, persist=True)
        db.commit()
        return out
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Scenario run failed: {exc.__class__.__name__}") from exc


@router.get(
    "/portfolios/{portfolio_id}/scenarios",
    response_model=ScenarioRunListResponse,
)
def scenario_runs_route(
    portfolio_id: int,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> ScenarioRunListResponse:
    portfolio = get_portfolio_or_404(db, portfolio_id)
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    return list_scenario_runs(db, portfolio_id=portfolio_id, limit=limit)


@router.get(
    "/portfolios/{portfolio_id}/scenarios/{run_id}",
    response_model=ScenarioResultResponse,
)
def scenario_run_detail_route(
    portfolio_id: int,
    run_id: int,
    db: Session = Depends(get_db),
) -> ScenarioResultResponse:
    portfolio = get_portfolio_or_404(db, portfolio_id)
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    payload = get_scenario_run_detail(db, portfolio_id=portfolio_id, run_id=run_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Scenario run not found")
    return payload


@router.get("/securities/{symbol}/scenario-sensitivity")
def scenario_sensitivity_route(
    symbol: str,
    portfolio_id: int = Query(...),
    factor: str = Query("rates"),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    portfolio = get_portfolio_or_404(db, portfolio_id)
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    factor_key = factor.strip().lower()
    if factor_key not in FACTOR_SPECS:
        raise HTTPException(status_code=400, detail=f"Unknown factor '{factor}'")

    try:
        return scenario_sensitivity(
            db,
            portfolio_id=portfolio_id,
            symbol=symbol.upper(),
            factor_key=factor_key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
