from __future__ import annotations

from app.api.v1.routes import portfolios
from app.db import SessionLocal
from app.services.portfolio import ensure_default_portfolio


def test_prices_route_returns_partial_when_provider_fails(monkeypatch) -> None:
    with SessionLocal() as db:
        portfolio = ensure_default_portfolio(db)

        def _raise(*_args, **_kwargs):
            raise RuntimeError("provider down")

        monkeypatch.setattr(portfolios, "get_symbols_price_frame", _raise)
        response = portfolios.prices_route(
            portfolio_id=portfolio.id,
            symbols="NVDA",
            range="1M",
            db=db,
        )
        assert response.status == "partial"
        assert "E_PRICE_FETCH_FAILED" in response.warnings
        assert response.series == []

