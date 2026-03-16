import type { ScenarioRunListItem } from "../types/api";

type Props = {
  runs: ScenarioRunListItem[];
  onOpen: (runId: number) => void;
};

export default function SavedScenarioRuns({ runs, onOpen }: Props) {
  return (
    <div className="card">
      <div className="kicker">Saved Scenario Runs</div>
      {!runs.length ? (
        <div style={{ color: "var(--muted)", fontSize: 12 }}>No saved runs yet.</div>
      ) : (
        <div style={{ display: "grid", gap: 8 }}>
          {runs.slice(0, 12).map((run) => (
            <button
              key={run.id}
              type="button"
              onClick={() => onOpen(run.id)}
              className="btn-secondary"
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                textTransform: "none",
                letterSpacing: 0,
                fontSize: 12,
              }}
            >
              <span>
                {run.factor_key} {run.shock_value > 0 ? "+" : ""}{run.shock_value} {run.shock_unit}
              </span>
              <span style={{ color: "var(--muted)", fontSize: 11 }}>{new Date(run.started_at).toLocaleString()}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
