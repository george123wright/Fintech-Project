import { useEffect, useState } from "react";
import type { Dispatch } from "react";
import { getGuidedMacroWorkflow } from "../api/client";
import { usePortfolioData } from "../state/DataProvider";
import type { NavAction } from "../state/nav";
import type { GuidedMacroWorkflowResponse, ScenarioTemplate } from "../types/api";

type Props = {
  dispatch: Dispatch<NavAction>;
};

export default function MacroPage({ dispatch }: Props) {
  const { state, previewScenarioForActive } = usePortfolioData();
  const [workflow, setWorkflow] = useState<GuidedMacroWorkflowResponse | null>(null);
  const [selected, setSelected] = useState<ScenarioTemplate | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    async function load() {
      if (state.activePortfolioId == null) return;
      const payload = await getGuidedMacroWorkflow(state.activePortfolioId);
      setWorkflow(payload);
      setSelected(payload.templates[0] ?? null);
    }
    void load();
  }, [state.activePortfolioId]);

  async function loadPreset(template: ScenarioTemplate) {
    setSelected(template);
    setLoading(true);
    try {
      await previewScenarioForActive({
        factor_key: template.factor_key,
        shock_value: template.shock_value,
        shock_unit: template.shock_unit,
        horizon_days: template.horizon_days,
        confidence_level: template.confidence_level,
        n_sims: template.n_sims,
        selected_symbol: state.holdings[0]?.symbol ?? null,
        include_baseline: true,
        shrinkage_lambda: 0.2,
      });
      dispatch({ type: "go_page", page: "scenarios" });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page-wrap" style={{ maxWidth: 1080, margin: "0 auto" }}>
      <div className="card" style={{ padding: 26, marginBottom: 18 }}>
        <div className="kicker">Guided macro workflow</div>
        <h1 style={{ marginTop: 0, fontFamily: "var(--sans)", letterSpacing: "-0.03em" }}>{workflow?.title ?? "Macro workflow"}</h1>
        <p style={{ color: "var(--muted)", lineHeight: 1.7 }}>{workflow?.description ?? "Loading workflow…"}</p>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, minmax(0, 1fr))", gap: 12, marginTop: 18 }}>
          {(workflow?.steps ?? []).map((step, idx) => (
            <div key={step.step_key} className="surface-soft" style={{ padding: 12 }}>
              <div className="kicker">Step {idx + 1}</div>
              <div style={{ fontWeight: 700, marginBottom: 6 }}>{step.title}</div>
              <div style={{ color: "var(--muted)", fontSize: 12, lineHeight: 1.6 }}>{step.detail}</div>
            </div>
          ))}
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1.2fr 0.8fr", gap: 16 }}>
        <div className="card">
          <div className="kicker">Scenario templates</div>
          <div style={{ display: "grid", gap: 10 }}>
            {(workflow?.templates ?? []).map((template) => (
              <button
                key={template.key}
                type="button"
                className="btn-secondary"
                onClick={() => void loadPreset(template)}
                style={{ textAlign: "left", padding: 14, opacity: loading ? 0.7 : 1 }}
              >
                <div className="row-between">
                  <strong>{template.display_name}</strong>
                  <span className="pill">{template.objective}</span>
                </div>
                <div style={{ color: "var(--muted)", fontSize: 12, marginTop: 6 }}>{template.narrative}</div>
                <div style={{ color: "var(--muted)", fontSize: 11, marginTop: 6 }}>
                  {template.factor_key} · {template.shock_value} {template.shock_unit} · {template.horizon_days}d
                </div>
              </button>
            ))}
          </div>
        </div>

        <div className="card">
          <div className="kicker">Selected workflow</div>
          {selected ? (
            <>
              <h3 style={{ marginTop: 6 }}>{selected.display_name}</h3>
              <p style={{ color: "var(--muted)", lineHeight: 1.7 }}>{selected.narrative}</p>
              <div style={{ display: "grid", gap: 8, marginTop: 12 }}>
                <div className="surface-soft" style={{ padding: 10 }}>Factor: {selected.factor_key}</div>
                <div className="surface-soft" style={{ padding: 10 }}>Shock: {selected.shock_value} {selected.shock_unit}</div>
                <div className="surface-soft" style={{ padding: 10 }}>Horizon: {selected.horizon_days} trading days</div>
                <div className="surface-soft" style={{ padding: 10 }}>Simulations: {selected.n_sims.toLocaleString()}</div>
              </div>
              <button className="btn-primary" style={{ marginTop: 14 }} onClick={() => void loadPreset(selected)} disabled={loading}>
                {loading ? "Loading preset…" : "Open in Scenario Lab"}
              </button>
            </>
          ) : (
            <div style={{ color: "var(--muted)" }}>No workflow available yet.</div>
          )}
        </div>
      </div>
    </div>
  );
}
