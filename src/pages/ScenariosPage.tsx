import { useEffect, useMemo, useRef, useState, type Dispatch } from "react";
import DataWarningBanner from "../components/DataWarningBanner";
import SavedScenarioRuns from "../components/SavedScenarioRuns";
import ScenarioContributionsTable from "../components/ScenarioContributionsTable";
import ScenarioControlPanel from "../components/ScenarioControlPanel";
import ScenarioDistributionChart from "../components/ScenarioDistributionChart";
import ScenarioImpactCards from "../components/ScenarioImpactCards";
import ScenarioPathsChart from "../components/ScenarioPathsChart";
import ScenarioRelationshipStats from "../components/ScenarioRelationshipStats";
import ScenarioTailRiskStats from "../components/ScenarioTailRiskStats";
import { usePortfolioData } from "../state/DataProvider";
import type { NavAction } from "../state/nav";
import type { ScenarioPreviewRequest } from "../types/api";

type Props = {
  dispatch: Dispatch<NavAction>;
};

function withDefaultDraft(): ScenarioPreviewRequest {
  return {
    factor_key: "rates",
    shock_value: 25,
    shock_unit: "bps",
    horizon_days: 21,
    confidence_level: 0.95,
    n_sims: 400,
    selected_symbol: null,
    include_baseline: true,
    shrinkage_lambda: 0.2,
  };
}

export default function ScenariosPage({ dispatch }: Props) {
  const {
    state,
    previewScenarioForActive,
    runScenarioForActive,
    loadScenarioRunDetailForActive,
    listScenarioRunsForActive,
  } = usePortfolioData();

  const factors = state.scenarioMetadata?.factors ?? [];
  const scenarioSymbols = useMemo(() => {
    const seen = new Set<string>();
    const symbols: string[] = [];
    for (const holding of state.holdings) {
      const symbol = String(holding.symbol ?? "").trim().toUpperCase();
      if (!symbol || seen.has(symbol)) continue;
      seen.add(symbol);
      symbols.push(symbol);
    }
    return symbols;
  }, [state.holdings]);
  const [draft, setDraft] = useState<ScenarioPreviewRequest>(withDefaultDraft());
  const [isWorking, setIsWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const requestSeqRef = useRef(0);

  useEffect(() => {
    if (!factors.length) return;
    if (factors.some((factor) => factor.key === draft.factor_key)) return;

    const first = factors[0];
    setDraft((prev) => ({
      ...prev,
      factor_key: first.key,
      shock_unit: first.unit,
      shock_value: first.default_value,
    }));
  }, [draft.factor_key, factors]);

  useEffect(() => {
    if (!scenarioSymbols.length) return;
    if (draft.selected_symbol && scenarioSymbols.includes(draft.selected_symbol)) return;
    setDraft((prev) => ({
      ...prev,
      selected_symbol: scenarioSymbols[0],
    }));
  }, [draft.selected_symbol, scenarioSymbols]);

  useEffect(() => {
    if (!state.scenarioMetadata?.factors?.length) return;
    const seq = ++requestSeqRef.current;
    let cancelled = false;
    const timeout = window.setTimeout(async () => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      setError(null);
      setIsWorking(true);
      try {
        await previewScenarioForActive(
          { ...draft, n_sims: Math.min(400, draft.n_sims) },
          { signal: controller.signal }
        );
      } catch (err) {
        if ((err as Error).name === "AbortError") {
          return;
        }
        if (!cancelled) {
          setError("Scenario preview failed. Refresh data and try again.");
        }
      } finally {
        if (!cancelled && seq === requestSeqRef.current) {
          setIsWorking(false);
        }
      }
    }, 650);

    return () => {
      cancelled = true;
      window.clearTimeout(timeout);
      abortRef.current?.abort();
    };
  }, [draft, previewScenarioForActive, state.scenarioMetadata?.factors]);

  const preview = state.scenarioPreview;

  const combinedWarnings = useMemo(() => {
    return [...(state.dataWarnings ?? []), ...(preview?.warnings ?? [])];
  }, [preview?.warnings, state.dataWarnings]);

  async function handlePreview() {
    abortRef.current?.abort();
    setError(null);
    setIsWorking(true);
    try {
      await previewScenarioForActive(draft);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setIsWorking(false);
    }
  }

  async function handleRun() {
    abortRef.current?.abort();
    setError(null);
    setIsWorking(true);
    try {
      await runScenarioForActive(draft);
      await listScenarioRunsForActive(120);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setIsWorking(false);
    }
  }

  async function openRun(runId: number) {
    abortRef.current?.abort();
    setError(null);
    setIsWorking(true);
    try {
      await loadScenarioRunDetailForActive(runId);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setIsWorking(false);
    }
  }

  const selectedSymbol = String(preview?.inputs?.selected_symbol ?? "");
  const portfolioStats = preview?.relationship_stats?.portfolio;
  const selectedStats = selectedSymbol ? preview?.relationship_stats?.[selectedSymbol] : null;
  const portfolioSimStats = preview?.simulation_stats?.portfolio;
  const selectedSimStats = selectedSymbol ? preview?.simulation_stats?.[selectedSymbol] : null;
  const portfolioPaths = (preview?.simulation_paths ?? []).filter((path) => path.series_key === "portfolio");
  const selectedPaths = (preview?.simulation_paths ?? []).filter((path) => path.series_key === selectedSymbol);

  return (
    <div className="page-wrap">
      <div className="page-intro" style={{ marginBottom: 18 }}>
        <h1>Scenario Lab</h1>
        <p>
          Run single-factor macro shocks with deterministic betas plus Monte Carlo uncertainty. Use sliders to stress
          portfolio and ticker outcomes.
        </p>
      </div>

      {combinedWarnings.length ? <DataWarningBanner warnings={combinedWarnings} /> : null}
      {error ? <DataWarningBanner warnings={[error]} /> : null}

      <ScenarioControlPanel
        factors={factors}
        symbols={scenarioSymbols}
        value={draft}
        loading={isWorking}
        onChange={setDraft}
        onPreview={handlePreview}
        onRun={handleRun}
      />

      {preview ? (
        <>
          <ScenarioImpactCards portfolio={preview.portfolio_impact} selected={preview.selected_stock_impact} />

          <div className="grid-2" style={{ marginBottom: 16 }}>
            <ScenarioTailRiskStats
              title="Portfolio Tail Risk (Scenario)"
              stats={portfolioSimStats}
              currentValue={preview.portfolio_impact.current_value}
            />
            <ScenarioTailRiskStats
              title={`${selectedSymbol || "Selected"} Tail Risk (Scenario)`}
              stats={selectedSimStats}
              currentValue={preview.selected_stock_impact?.current_value}
            />
          </div>

          <div className="grid-2" style={{ marginBottom: 16 }}>
            <ScenarioRelationshipStats title="Portfolio Relationship Stats" stats={portfolioStats} />
            <ScenarioRelationshipStats
              title={`${selectedSymbol || "Selected"} Relationship Stats`}
              stats={selectedStats}
            />
          </div>

          <ScenarioDistributionChart bins={preview.distribution_bins} />
          <ScenarioPathsChart paths={portfolioPaths} title="Portfolio Simulation Paths" />
          <ScenarioPathsChart paths={selectedPaths} title={`${selectedSymbol || "Selected"} Simulation Paths`} />
          <ScenarioContributionsTable rows={preview.contributions} />

          {preview.narrative?.length ? (
            <div className="card" style={{ marginBottom: 16 }}>
              <div className="kicker">Scenario Narrative</div>
              <div style={{ display: "grid", gap: 8 }}>
                {preview.narrative.map((line, idx) => (
                  <div key={idx} style={{ color: "var(--muted)", fontSize: 12, lineHeight: 1.65 }}>
                    {line}
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </>
      ) : null}

      <div className="grid-2" style={{ alignItems: "start" }}>
        <SavedScenarioRuns runs={state.scenarioRuns} onOpen={openRun} />
        <div className="card">
          <div className="kicker">Quick Presets</div>
          <div style={{ display: "grid", gap: 8 }}>
            <button
              type="button"
              className="btn-secondary"
              onClick={() => setDraft((prev) => ({ ...prev, factor_key: "rates", shock_unit: "bps", shock_value: 25 }))}
            >
              Rates +25 bps
            </button>
            <button
              type="button"
              className="btn-secondary"
              onClick={() => setDraft((prev) => ({ ...prev, factor_key: "inflation", shock_unit: "%", shock_value: 0.5 }))}
            >
              Inflation +0.5%
            </button>
            <button
              type="button"
              className="btn-secondary"
              onClick={() => setDraft((prev) => ({ ...prev, factor_key: "vix", shock_unit: "%", shock_value: 12 }))}
            >
              Volatility +12%
            </button>
            <button
              type="button"
              className="btn-primary"
              onClick={() => dispatch({ type: "go_page", page: "overview" })}
            >
              Back to Overview
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
