# Quick Balance Backend (Phase 1)

FastAPI + SQLite backend for live holdings ingestion, refresh jobs, risk metrics, and price APIs.
Now includes a Scenario Engine with mixed-source macro factors (Yahoo + FRED) and Monte Carlo diagnostics.

## Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Run

```bash
uvicorn app.main:app --reload --port 8000
```

- Full app URL (backend + served frontend when `dist/` exists): `http://127.0.0.1:8000`
- API base: `http://127.0.0.1:8000/api/v1`
- Health check: `http://127.0.0.1:8000/healthz`

## Main endpoints

- `POST /api/v1/portfolios`
- `GET /api/v1/portfolios`
- `POST /api/v1/portfolios/{portfolio_id}/holdings/upload`
- `POST /api/v1/portfolios/{portfolio_id}/holdings/manual`
- `GET /api/v1/portfolios/{portfolio_id}/holdings/latest`
- `POST /api/v1/portfolios/{portfolio_id}/refresh`
- `GET /api/v1/portfolios/{portfolio_id}/overview`
- `GET /api/v1/portfolios/{portfolio_id}/analytics/risk`
- `GET /api/v1/portfolios/{portfolio_id}/prices?symbols=NVDA,MSFT&range=1M`
- `GET /api/v1/portfolios/{portfolio_id}/scenarios/metadata`
- `POST /api/v1/portfolios/{portfolio_id}/scenarios/preview`
- `POST /api/v1/portfolios/{portfolio_id}/scenarios/run`
- `GET /api/v1/portfolios/{portfolio_id}/scenarios`
- `GET /api/v1/portfolios/{portfolio_id}/scenarios/{run_id}`
- `GET /api/v1/securities/{symbol}/scenario-sensitivity?portfolio_id={id}&factor=rates`
