# Quick Balance: Detailed Next-Step Implementation Plan

## Review scope and assumptions

I reviewed:
- the repository structure and current frontend/backend implementation;
- the repository-root project documents `Fintech Project Plan.docx` and `Portfolio Code Plan.docx`;
- the current API, data model, analytics, scenario, and valuation code paths.

> Note: the IDE-provided absolute paths under `/Users/georgewright/...` were not available in this environment, so I used the repository copies of those same documents.

## 1. Current-state assessment

The project already has a strong Phase 1/Phase 1.5 base:
- portfolio creation and holdings ingestion exist for CSV/XLSX/manual entry;
- refresh orchestration computes core risk metrics, extended metrics, scenario cache refreshes, and valuations;
- the frontend already surfaces Overview, Scenario Lab, Stock Detail, Macro preset, Portfolio News, and valuation views;
- the backend already has route groups for portfolios, valuations, and scenarios;
- scenario analytics and valuation engines are materially more advanced than a pure prototype.

However, the product plan documents call for a more explicit “diagnose → explain → stress → value” workflow than the current application fully delivers. The biggest gap is not raw analytics anymore; it is productizing those analytics into a coherent user journey with a richer exposure model, plain-English explanation, better persistence, and clearer portfolio-level insight surfaces.

## 2. Priority order for the next implementation cycle

The next cycle should be delivered in this order:

1. **Portfolio exposure + overlap foundation**
2. **Explanation / narrative engine for portfolio diagnosis**
3. **Scenario productization with event-aware presets and saved comparisons**
4. **Valuation workflow completion and assumption management**
5. **Reporting layer and portfolio review outputs**
6. **Data quality, async jobs, and operational hardening**

This order is deliberate:
- the project plan’s core promise is understanding hidden exposures and false diversification;
- the existing code already computes risk/scenario/valuation outputs, so the highest-leverage next step is making those outputs more explainable and portfolio-usable;
- a richer exposure layer will also materially improve scenario narratives, stock pages, and future reporting.

---

## 3. Detailed implementation plan

## Workstream A — Build a real exposure + overlap engine

### Goal
Deliver the “Diagnose: what you actually own” pillar properly by adding look-through exposures, overlap detection, concentration diagnostics, and portfolio decomposition that can be shown across Overview, Stock, and Reports.

### Why this is next
The current model stores holdings, prices, metrics, valuation snapshots, and scenario runs, but it does **not** yet persist a dedicated exposure snapshot or ETF constituent look-through layer. That makes the app analytically useful but still short of the product vision in the project documents.

### Exact implementation

#### A1. Add new persistence models
Create new SQLAlchemy models in `backend/app/models/entities.py` for:
- `SecurityMasterSnapshot`
  - symbol, name, asset_type, sector, industry, country, currency, market_cap_bucket, beta, provider metadata;
- `EtfConstituentSnapshot`
  - parent_symbol, constituent_symbol, constituent_name, weight, sector, country, as_of_date, source;
- `PortfolioExposureSnapshot`
  - snapshot_id, as_of_date, methodology_version, summary_json, warnings_json;
- `PortfolioExposureBreakdown`
  - exposure_snapshot_id, dimension (`sector`, `country`, `currency`, `asset_type`, `factor`, `market_cap_bucket`), bucket, direct_weight, lookthrough_weight;
- `PortfolioOverlapPair`
  - exposure_snapshot_id, left_symbol, right_symbol, overlap_weight, overlap_pct_of_pair, overlap_type;
- `PortfolioConcentrationSignal`
  - exposure_snapshot_id, signal_key, signal_value, severity, summary.

#### A2. Build provider interfaces first
Extend the provider layer under `backend/app/services/providers/` with small interface-style functions/classes rather than hard-coding logic into the routes.

Implementation steps:
- add a `security_master` provider module for metadata hydration;
- add an ETF constituents provider module that initially uses Yahoo-compatible holdings data where possible and gracefully degrades when unavailable;
- standardize provider responses into typed dictionaries or Pydantic schemas before persistence.

This should be structured so that later swapping Yahoo for another provider does not require changes to API routes or exposure calculations.

#### A3. Create `backend/app/services/exposures.py`
Implement a dedicated service module with functions like:
- `build_security_master_snapshot(...)`
- `load_or_refresh_security_master(...)`
- `expand_lookthrough_holdings(...)`
- `compute_exposure_breakdowns(...)`
- `compute_overlap_matrix(...)`
- `compute_concentration_signals(...)`
- `persist_portfolio_exposure_snapshot(...)`

Computation rules:
- if a holding is a stock, use direct weight;
- if a holding is an ETF/fund and constituents are available, calculate look-through exposure by multiplying holding weight × constituent weight;
- aggregate exposures for sector, industry, geography, currency, market-cap bucket, and simple factor proxies;
- compute overlap by measuring shared constituent exposure across ETFs/funds and direct holdings;
- generate concentration flags such as:
  - top-3 look-through weight concentration;
  - top sector > threshold;
  - top country > threshold;
  - repeated mega-cap overlap across multiple funds;
  - single-currency dominance.

#### A4. Hook exposures into refresh orchestration
Extend `backend/app/services/refresh.py` so a normal portfolio refresh does the following sequence:
1. load latest holdings snapshot;
2. fetch/update price history;
3. compute base risk metrics;
4. compute valuation snapshot;
5. compute extended metrics;
6. **compute and persist exposure snapshot**;
7. refresh scenario macro cache.

If exposure generation partially fails, do **not** fail the entire refresh. Instead:
- store warnings on the exposure snapshot;
- append warnings into the refresh job error/warning string;
- return a usable partial response to the frontend.

#### A5. Add new exposure APIs
Add endpoints under `backend/app/api/v1/routes/portfolios.py` or a new `exposures.py` route module:
- `GET /portfolios/{portfolio_id}/exposures/overview`
- `GET /portfolios/{portfolio_id}/exposures/breakdown?dimension=sector`
- `GET /portfolios/{portfolio_id}/exposures/overlap`
- `GET /portfolios/{portfolio_id}/exposures/concentration`

Keep the REST shape simple and aligned with the existing API style.

#### A6. Frontend implementation
Add new UI sections/components:
- `src/components/ExposureBreakdownCard.tsx`
- `src/components/OverlapTable.tsx`
- `src/components/ConcentrationSignals.tsx`
- optional `src/components/LookthroughHoldingsTable.tsx`

Integrate them into:
- `src/pages/OverviewPage.tsx` as a new “What you actually own” section;
- `src/pages/StockPage.tsx` for portfolio-relative exposure context;
- `src/pages/ReportsPage.tsx` for report-ready exposure summaries.

### Acceptance criteria
- user can see direct vs look-through exposure by sector/country/currency;
- user can see which ETFs/direct names overlap most;
- app surfaces at least 3 concentration warnings in plain product language;
- refresh completes even if constituent coverage is incomplete.

---

## Workstream B — Add a rule-based explanation engine

### Goal
Turn raw metrics into the project’s promised plain-English “Explain: what drove return and risk” layer.

### Why this matters now
The project plan repeatedly emphasizes explanation over raw dashboards. The backend already computes enough inputs to support a deterministic explanation layer without needing an LLM.

### Exact implementation

#### B1. Add a dedicated explanation service
Create `backend/app/services/explanations.py` with functions such as:
- `rank_portfolio_insights(...)`
- `build_risk_narrative(...)`
- `build_return_driver_narrative(...)`
- `build_change_since_last_snapshot_narrative(...)`
- `build_evidence_chips(...)`
- `build_watchouts(...)`

Use a rule-based pipeline:
1. ingest holdings, metrics, exposure snapshot, overlap signals, scenario sensitivities, valuation summary;
2. score possible insights by magnitude, novelty, and user relevance;
3. emit structured narrative output.

#### B2. Add explicit narrative schema
Add response schemas in `backend/app/schemas/analytics.py` for:
- `PortfolioNarrativeResponse`
- `NarrativeCardOut`
- `EvidenceChipOut`
- `WatchoutOut`
- `ChangeSummaryOut`

These should be **structured**, not a single free-text blob.

#### B3. Persist or derive?
Recommended approach for the next cycle:
- **derive on refresh and persist** a compact JSON summary onto a new table `PortfolioNarrativeSnapshot`.

Reason:
- consistent UX;
- easier report generation;
- easier diffing between snapshots;
- avoids expensive recomputation on every frontend page load.

#### B4. Narrative logic rules
Implement a first deterministic rule library such as:
- if top-3 holdings contribute > X% of total risk → emit “portfolio is concentrated” narrative;
- if look-through sector > threshold → emit “sector crowding” narrative;
- if overlap matrix shows same names repeated across multiple ETFs → emit “false diversification” narrative;
- if rates factor beta or scenario sensitivity is large → emit “rates-sensitive portfolio” narrative;
- if benchmark-relative beta or drawdown worsened since prior snapshot → emit “risk has increased since last refresh” narrative;
- if valuation coverage is low → emit “valuation insight is partial” warning;
- if data/provider coverage is partial → emit evidence-quality caveat.

#### B5. Add endpoint and wire it into state
Add endpoint:
- `GET /portfolios/{portfolio_id}/narrative`

Then extend:
- `src/api/client.ts`
- `src/types/api.ts`
- `src/state/data.ts`
- `src/state/DataProvider.tsx`

to fetch/store the narrative payload with the portfolio overview load.

#### B6. Frontend surfacing
Add components such as:
- `src/components/PortfolioNarrativeCards.tsx`
- `src/components/EvidenceChips.tsx`
- `src/components/WhatChangedCard.tsx`

Place them near the top of `src/pages/OverviewPage.tsx` so the app answers “What matters right now?” before deep charts.

### Acceptance criteria
- overview page opens with 3–5 ranked insight cards;
- each insight is backed by machine-readable evidence chips;
- narrative language is deterministic, specific, and not generic;
- snapshot-to-snapshot “what changed since last month/refresh” is visible when prior data exists.

---

## Workstream C — Productize the scenario engine into a real macro workflow

### Goal
Upgrade the existing Scenario Lab from a strong calculator into the “Stress: what happens if macro conditions shift?” pillar from the product plan.

### Current status
The scenario engine is already quite substantial: it has factor specs, macro series transforms, preview/run modes, Monte Carlo paths, relationship stats, saved runs, and sensitivity endpoints.

### Exact implementation

#### C1. Add named scenario templates
Create a template registry module, for example `backend/app/services/scenarios/templates.py`, with templates such as:
- Rates +25 bps
- Rates +100 bps
- Inflation surprise
- GDP slowdown / recession-lite
- Retail spending drawdown
- Oil spike
- VIX spike
- USD strength / FX shock (if FX factor is added in this cycle)

Each template should store:
- display name;
- factor key;
- default shock magnitude;
- recommended horizon;
- narrative framing;
- applicable portfolio tags (optional later extension).

Expose them via:
- `GET /portfolios/{portfolio_id}/scenarios/templates`

#### C2. Add event-aware presets
Create a lightweight event calendar ingestion layer that initially supports:
- FOMC / central bank events;
- CPI release dates;
- earnings dates for portfolio holdings;
- dividend dates / stock splits where already available.

Implementation approach for next cycle:
- use provider-layer fetchers already exposed for security events;
- create a simple `PortfolioEventSnapshot` table that stores upcoming events by portfolio;
- add a summarizer that links upcoming macro events to the most relevant scenario template.

Then expose:
- `GET /portfolios/{portfolio_id}/events/upcoming`
- `GET /portfolios/{portfolio_id}/macro/next-risk`

#### C3. Add scenario comparison support
Currently the app supports saved runs. The next step is side-by-side comparison.

Implementation steps:
- add frontend selection state for 2 saved scenario runs;
- create comparison cards for delta in expected portfolio impact, top contributors, left-tail loss, and selected symbol effect;
- optional backend helper endpoint:
  - `GET /portfolios/{portfolio_id}/scenarios/compare?left_run_id=...&right_run_id=...`

#### C4. Improve narrative output for scenarios
Extend the scenario engine output to include:
- exposure-linked explanation;
- confidence caveat when sample size is small;
- “why these holdings drive the result” summary;
- a user-facing distinction between deterministic beta shock and Monte Carlo uncertainty band.

This should be implemented in the backend so the frontend remains simple.

#### C5. Macro page redesign
Replace the current single-button macro preset in `src/pages/MacroPage.tsx` with:
- an “Upcoming macro risk” hero card;
- a list of event-linked presets;
- event date, expected relevance, impacted holdings, and one-click run actions;
- links into detailed Scenario Lab runs.

### Acceptance criteria
- users can launch scenario templates directly from a curated list;
- the macro page surfaces upcoming events instead of static text;
- users can compare saved runs side-by-side;
- scenario narratives explain both impact and confidence.

---

## Workstream D — Complete the valuation workflow and user assumption management

### Goal
Strengthen the “Value” pillar so valuation is editable, transparent, portfolio-level, and reportable.

### Current status
The backend valuation stack is already advanced: analyst, DCF, RI, DDM, relative valuation, market-rate injection, and portfolio aggregation are all present. The main missing piece is turning these capabilities into a user-controlled workflow.

### Exact implementation

#### D1. Persist user-editable valuation assumptions
Add a table such as `PortfolioValuationAssumptionSet` with:
- portfolio_id;
- name;
- assumptions_json;
- is_default;
- created_at / updated_at.

This allows named assumption profiles like:
- Base;
- Conservative;
- Optimistic.

#### D2. Extend valuation APIs
Add endpoints:
- `GET /portfolios/{portfolio_id}/valuations/assumptions`
- `POST /portfolios/{portfolio_id}/valuations/assumptions`
- `PATCH /portfolios/{portfolio_id}/valuations/assumptions/{id}`
- `POST /portfolios/{portfolio_id}/valuations/recompute-from-profile/{id}`

#### D3. Improve portfolio valuation explanation
Extend valuation overview output to include user-readable summaries such as:
- portfolio appears mildly overvalued / fairly valued / undervalued;
- X% of weight has usable valuation coverage;
- largest upside/downside contributors;
- model disagreement summary (e.g. analyst vs DCF vs RI divergence).

#### D4. Stock page valuation transparency
Enhance `src/pages/StockPage.tsx` with:
- scenario tabs that clearly compare analyst / DCF / RI / DDM / relative valuation;
- diagnostics badges for model quality and data coverage;
- assumption editors that call the recompute endpoint.

#### D5. Portfolio-level valuation drilldown
Add a dedicated section or page showing:
- weighted portfolio upside by model;
- holdings sorted by valuation disagreement;
- holdings with no coverage / weak coverage;
- best/worst composite upside contributors;
- editable assumptions panel.

### Acceptance criteria
- users can save and reload assumption profiles;
- valuation recompute can be triggered from saved profiles;
- portfolio-level valuation summary clearly communicates coverage and disagreement;
- stock pages show why a valuation result should or should not be trusted.

---

## Workstream E — Build actual reports, not placeholders

### Goal
Turn the current mock reports page into a tangible deliverable aligned with the project’s “client-ready communication” and portfolio review narrative.

### Exact implementation

#### E1. Replace mock cards with report generators
The reports page should generate at least 3 concrete report types:
1. Portfolio Diagnosis Report
2. Scenario Stress Report
3. Valuation Review Report

#### E2. Backend report payload assembly
Create `backend/app/services/reporting.py` with report builders that combine:
- latest holdings snapshot;
- exposure snapshot;
- narrative snapshot;
- latest scenario run / selected scenarios;
- valuation overview.

Expose endpoints like:
- `GET /portfolios/{portfolio_id}/reports/diagnosis`
- `GET /portfolios/{portfolio_id}/reports/scenario`
- `GET /portfolios/{portfolio_id}/reports/valuation`

#### E3. Frontend implementation
Update `src/pages/ReportsPage.tsx` to show:
- download-ready sections;
- print-friendly layout;
- the top insight summary, key charts, and evidence tables;
- future-ready export buttons (initially stub PDF export if needed, but structure the page properly).

A pragmatic v1 is HTML print-first, then add PDF export later.

### Acceptance criteria
- reports page shows real report content sourced from live backend data;
- reports can be printed cleanly from the browser;
- report payloads are deterministic and reusable.

---

## Workstream F — Harden ingestion, jobs, and data quality

### Goal
Move from a single-process prototype toward the modular-monolith architecture described in the code plan, without over-engineering the student project.

### Exact implementation

#### F1. Improve ingestion normalization
Extend `backend/app/services/ingestion.py` to support:
- stronger ticker/identifier normalization;
- explicit duplicate-handling rules by account/source;
- clearer currency handling and currency mismatch warnings;
- better asset-type inference using metadata lookups;
- ingestion audit trail fields for row-level rejection reasons.

#### F2. Add migration support
The app currently relies on `Base.metadata.create_all(...)`, which is acceptable early on but will become risky as tables multiply.

Next step:
- introduce Alembic;
- generate an initial migration matching current schema;
- add follow-up migrations for the new exposure/narrative/reporting tables.

#### F3. Add lightweight async job support
Do **not** split into microservices yet. Instead:
- keep FastAPI as the main app;
- add a small background worker path for long-running refreshes/recomputes;
- if time permits, use Redis + Dramatiq/Celery;
- if not, keep synchronous execution but create a job abstraction now so later migration is simple.

The key implementation point is the contract:
- create job records;
- expose job status endpoints;
- allow the frontend to poll long-running tasks cleanly.

#### F4. Add data quality status surfaces
Every major backend response should consistently expose:
- `status`;
- `warnings`;
- `coverage_ratio` where applicable.

Then add a frontend status system that distinguishes:
- full insight;
- partial insight;
- no data.

### Acceptance criteria
- schema changes are managed with migrations;
- refresh/valuation/scenario jobs have a consistent job-status pattern;
- users can see when analytics are partial because of provider/data gaps.

---

## Workstream G — Testing and quality gates

### Goal
Match the growing sophistication of the backend with stable automated coverage.

### Exact implementation

#### G1. Backend tests
Expand `backend/tests/` with dedicated tests for:
- exposure breakdown aggregation;
- ETF look-through and overlap calculations;
- explanation ranking logic;
- scenario template registry;
- valuation assumption profile persistence;
- report payload assembly.

Use deterministic fixtures and small synthetic portfolios for these tests.

#### G2. Frontend tests
If you do not want to add a heavy test stack immediately, at minimum add:
- lightweight component tests for narrative cards and exposure tables;
- integration tests for the overview page loading state and scenario comparison flow.

#### G3. CI pipeline
Add GitHub Actions for:
- frontend install + build;
- backend dependency install + pytest;
- optional type-check step.

### Acceptance criteria
- key analytical modules are covered by deterministic unit tests;
- frontend builds in CI;
- core “overview → refresh → scenario → valuation” workflows are regression-resistant.

---

## 4. Suggested implementation sequence by sprint

## Sprint 1 — Exposure foundation
Deliver:
- exposure DB tables;
- provider normalization for metadata/ETF constituents;
- exposure snapshot generation in refresh flow;
- exposure APIs;
- first Overview exposure cards.

## Sprint 2 — Narrative layer
Deliver:
- narrative snapshot table/service;
- ranked overview insight cards;
- evidence chips;
- “what changed since last refresh” output.

## Sprint 3 — Scenario workflow
Deliver:
- scenario templates;
- macro/event snapshots;
- redesigned Macro page;
- saved run comparison.

## Sprint 4 — Valuation UX
Deliver:
- saved assumption profiles;
- valuation profile APIs;
- richer stock-page valuation controls;
- portfolio valuation drilldown.

## Sprint 5 — Reports + hardening
Deliver:
- real reports page;
- migration support;
- better job abstraction;
- CI/test expansion.

---

## 5. Concrete file-level change map

If I were implementing this next cycle, I would expect the following file groups to change first:

### Backend
- `backend/app/models/entities.py`
- `backend/app/api/v1/router.py`
- `backend/app/api/v1/routes/portfolios.py`
- new route modules such as:
  - `backend/app/api/v1/routes/exposures.py`
  - `backend/app/api/v1/routes/narrative.py`
  - `backend/app/api/v1/routes/reports.py`
- existing/new service modules:
  - `backend/app/services/refresh.py`
  - `backend/app/services/ingestion.py`
  - `backend/app/services/exposures.py`
  - `backend/app/services/explanations.py`
  - `backend/app/services/reporting.py`
  - `backend/app/services/scenarios/templates.py`
- schemas:
  - `backend/app/schemas/analytics.py`
  - `backend/app/schemas/portfolios.py`
  - new `backend/app/schemas/exposures.py`
  - new `backend/app/schemas/reports.py`
- tests:
  - new backend tests for exposures, narratives, reports.

### Frontend
- `src/api/client.ts`
- `src/types/api.ts`
- `src/state/data.ts`
- `src/state/DataProvider.tsx`
- `src/pages/OverviewPage.tsx`
- `src/pages/MacroPage.tsx`
- `src/pages/ReportsPage.tsx`
- `src/pages/StockPage.tsx`
- new components for exposures, narratives, scenario comparisons, and reporting.

---

## 6. What should *not* be done yet

To keep the project focused, I would **not** do these in the next cycle:
- do not split into separate microservices;
- do not add LLM-generated explanations yet;
- do not add full broker integrations before the diagnosis/explanation flow is excellent;
- do not add broad recommendation/rebalancing advice language until guardrails are explicit;
- do not overinvest in auth/billing before the core investor insight loop is polished.

---

## 7. Recommended definition of success for the next release

The next release should be considered successful if a new user can:
1. upload holdings;
2. refresh the portfolio;
3. immediately see hidden concentration and overlap;
4. read 3–5 plain-English explanation cards about current risk and recent change;
5. run a macro scenario from either Scenario Lab or the Macro page;
6. understand whether valuation insight is broad, partial, or low-confidence;
7. generate a real portfolio review report.

That would make the product much more tightly aligned with both planning documents and would turn the current codebase from a strong analytics prototype into a more coherent “portfolio intelligence” application.
