import { usePortfolioData } from "../state/DataProvider";
import type { Dispatch } from "react";
import type { NavAction } from "../state/nav";

type Props = {
  dispatch: Dispatch<NavAction>;
};

export default function MacroPage({ dispatch }: Props) {
  const { previewScenarioForActive } = usePortfolioData();

  async function loadFomcPreset() {
    try {
      await previewScenarioForActive({
        factor_key: "rates",
        shock_value: 25,
        shock_unit: "bps",
        horizon_days: 21,
        confidence_level: 0.95,
        n_sims: 1000,
        selected_symbol: null,
        include_baseline: true,
        shrinkage_lambda: 0.2,
      });
    } catch {
      // Ignore and still route to Scenario Lab.
    }
    dispatch({ type: "go_page", page: "scenarios" });
  }

  return (
    <div className="page-wrap" style={{ maxWidth: 980, margin: "0 auto" }}>
      <div className="card" style={{ padding: 26 }}>
        <div className="kicker">Macro Event Preset</div>
        <h1 style={{ marginTop: 0, fontFamily: "var(--sans)", letterSpacing: "-0.03em" }}>FOMC Scenario Loader</h1>
        <p style={{ color: "var(--muted)", lineHeight: 1.7 }}>
          This page now loads a Scenario Lab preset instead of static text. Use it to jump directly into a rates shock
          simulation for the portfolio.
        </p>
        <div className="row-between" style={{ marginTop: 14 }}>
          <button className="btn-secondary" onClick={() => dispatch({ type: "go_page", page: "overview" })}>
            Back
          </button>
          <button className="btn-primary" onClick={loadFomcPreset}>
            Open Scenario Lab (+25 bps)
          </button>
        </div>
      </div>
    </div>
  );
}
