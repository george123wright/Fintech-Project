# Quick Balance (Phase 1)

Frontend and backend implementation for live holdings ingestion, market data refresh, and core risk metrics.

## Install

If npm cache ownership was previously broken, first fix it:

```bash
sudo chown -R "$(id -u):$(id -g)" ~/.npm
npm cache verify
```

Then install and run:

```bash
npm install
npm run dev:api
npm run dev
```

Open:

- Frontend: `http://localhost:5173`
- Backend API: `http://127.0.0.1:8000/api/v1`
- Health: `http://127.0.0.1:8000/healthz`

## Backend setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

## No-Terminal Startup (macOS launchd)

This project includes scripts to run as a single local process (FastAPI serving both API and built frontend) and auto-start at login.

1. Build frontend once:

```bash
cd /Users/georgewright/Trinity/fintech
npm run build
```

2. Install launch agent:

```bash
/Users/georgewright/Trinity/fintech/scripts/local/install_launchagent.sh
```

3. Open app directly:

- `http://127.0.0.1:8000`

4. Remove auto-start later (optional):

```bash
/Users/georgewright/Trinity/fintech/scripts/local/uninstall_launchagent.sh
```

5. After code changes, rebuild + restart background app:

```bash
/Users/georgewright/Trinity/fintech/scripts/local/rebuild_and_restart.sh
```

## What is included

- Central reducer-based nav state (`src/state/nav.ts`) similar to Dash `dcc.Store`
- Split page modules (`src/pages/*`)
- Dark Lens shell and theme tokens (`src/styles/lens.css`)
- FastAPI backend (`backend/app/*`) with SQLite models, upload ingestion, pricing cache, and risk metrics
- REST endpoints for portfolio CRUD, upload, refresh, overview, risk analytics, and price ranges
- Frontend data provider (`src/state/DataProvider.tsx`) and API client (`src/api/client.ts`)
- Plotly + Recharts visualizations powered by API data in Overview/Chart/Stock pages
