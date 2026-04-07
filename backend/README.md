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
# then edit backend/.env and set:
# OPENROUTER_API_KEY=sk-or-v1-...
```

The backend auto-loads `backend/.env` on startup via `python-dotenv`.

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

## Environment variables

### Core
- `DATABASE_URL` (default: `sqlite:///./quick_balance.db`)
- `DEFAULT_BENCHMARK` (default: `SPY`)
- `DEFAULT_BASE_CCY` (default: `USD`)
- `NIGHTLY_REFRESH_CRON` (default: `10 2 * * *`)
- `RISK_FREE_RATE` (default: `0.02`)
- `FRED_API_KEY` (optional)
- `FRED_BASE_URL` (default: `https://api.stlouisfed.org/fred`)
- `FRED_TIMEOUT_SEC` (default: `12`)
- `FRONTEND_DIST_DIR` (default: `<repo>/dist`)

### OpenRouter (chat)
- `APP_ENV` or `ENV` (default: `dev`)
- `OPENROUTER_API_KEY` (**required for chat usage in all environments**)
- `OPENROUTER_BASE_URL` (default: `https://openrouter.ai/api/v1`)
- `OPENROUTER_MODEL` (default: `openrouter/free`)
- `OPENROUTER_TIMEOUT_SEC` (optional)
- `OPENROUTER_MAX_TOKENS` (optional)

> Validation behavior: the app still boots without `OPENROUTER_API_KEY`, but chat requests fail with a clear config error until the key is configured.
