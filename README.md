# Quick Balance (Phase 1)

Frontend and backend implementation for live holdings ingestion, market data refresh, and core risk metrics.

## Run this repository via GitHub (without local setup)

### Option 1: GitHub Codespaces (fastest)

1. Open the repository page on GitHub.
2. Click **Code** → **Codespaces** → **Create codespace on main**.
3. In the **first Codespace terminal**, run exactly:

```bash
npm install
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd ..
npm run dev:api
```

4. In a **second Codespace terminal**, run:

```bash
npm run dev -- --host 0.0.0.0 --port 5173
```

Important:
- Do **not** type the word `bash` before commands.
- If you see `The default interactive shell is now zsh...`, that is a macOS informational message, not an error.

Use the **Ports** tab in Codespaces to open:
- Frontend port `5173`
- Backend port `8000`

### Option 2: GitHub + Cloud deploy (shareable URL)

For a fully online version (no dev terminal running), deploy:
- **Frontend (Vite/React)** to Vercel or Netlify
- **Backend (FastAPI)** to Render/Railway/Fly.io

Typical flow:
1. Push your repo to GitHub.
2. Create backend service from `backend/` and set start command:
   - `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
3. Create frontend service and set build command:
   - `npm ci && npm run build`
4. Set the frontend environment variable for API base URL to your deployed backend URL.

### Personal-use recommendation (GitHub)

Yes — for personal use, the simplest choices are:

1. **Use GitHub Codespaces** (already documented above): quick, no local install, good for occasional use.
2. **Use GitHub + cloud deploy** for a permanent URL:
   - Frontend: Vercel/Netlify
   - Backend API: Render/Railway/Fly.io

Note: **GitHub Pages alone is not enough** for this project because it only hosts static files and cannot run the FastAPI backend.

## Local install (optional)

If npm cache ownership was previously broken, first fix it:

```bash
sudo chown -R "$(id -u):$(id -g)" ~/.npm
npm cache verify
```

Then run backend + frontend in two terminals.

### Terminal 1 (backend)

```bash
npm install
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd ..
npm run dev:api
```

### Terminal 2 (frontend)

```bash
npm run dev
```

Notes:
- Do **not** include a leading `bash` line as a command.
- On macOS, `The default interactive shell is now zsh` is informational and can be ignored.

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
- Light, high-readability theme tokens (`src/styles/lens.css`)
- FastAPI backend (`backend/app/*`) with SQLite models, upload ingestion, pricing cache, and risk metrics
- REST endpoints for portfolio CRUD, upload, refresh, overview, risk analytics, and price ranges
- Frontend data provider (`src/state/DataProvider.tsx`) and API client (`src/api/client.ts`)
- Plotly + Recharts visualizations powered by API data in Overview/Chart/Stock pages
