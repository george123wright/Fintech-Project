import type { ScenarioFactorMeta, ScenarioPreviewRequest } from "../types/api";

type Props = {
  factors: ScenarioFactorMeta[];
  symbols: string[];
  value: ScenarioPreviewRequest;
  loading: boolean;
  onChange: (next: ScenarioPreviewRequest) => void;
  onPreview: () => void;
  onRun: () => void;
};

const HORIZONS: Array<{ label: string; days: number }> = [
  { label: "1D", days: 1 },
  { label: "1W", days: 5 },
  { label: "1M", days: 21 },
  { label: "3M", days: 63 },
  { label: "6M", days: 126 },
  { label: "1Y", days: 252 },
];

export default function ScenarioControlPanel({
  factors,
  symbols,
  value,
  loading,
  onChange,
  onPreview,
  onRun,
}: Props) {
  const selected = factors.find((factor) => factor.key === value.factor_key) ?? factors[0];

  function updateFactor(factorKey: string) {
    const factor = factors.find((item) => item.key === factorKey);
    if (!factor) return;
    onChange({
      ...value,
      factor_key: factor.key,
      shock_unit: factor.unit,
      shock_value: factor.default_value,
    });
  }

  function unitSuffix(unit: string): string {
    if (unit === "bps") return "bps";
    if (unit === "pp") return "pp";
    return "%";
  }

  return (
    <div className="card" style={{ marginBottom: 16 }}>
      <div className="kicker">Scenario Controls</div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
          gap: 12,
        }}
      >
        <label className="custom-range-field" style={{ textTransform: "none", fontSize: 11 }}>
          Factor
          <select
            value={value.factor_key}
            onChange={(event) => updateFactor(event.target.value)}
            style={{
              border: "1px solid var(--border-soft)",
              background: "rgba(255,255,255,0.02)",
              color: "var(--text)",
              borderRadius: 8,
              padding: "8px 10px",
            }}
          >
            {factors.map((factor) => (
              <option key={factor.key} value={factor.key}>
                {factor.label}
              </option>
            ))}
          </select>
        </label>

        <label className="custom-range-field" style={{ textTransform: "none", fontSize: 11 }}>
          Shock ({unitSuffix(selected?.unit ?? value.shock_unit)})
          <input
            type="number"
            step={selected?.step ?? 0.1}
            min={selected?.min_value}
            max={selected?.max_value}
            value={value.shock_value}
            onChange={(event) => {
              const num = Number(event.target.value);
              onChange({ ...value, shock_value: Number.isFinite(num) ? num : value.shock_value });
            }}
          />
        </label>

        <label className="custom-range-field" style={{ textTransform: "none", fontSize: 11 }}>
          Sims
          <input
            type="number"
            min={100}
            max={5000}
            step={100}
            value={value.n_sims}
            onChange={(event) => {
              const num = Number(event.target.value);
              onChange({ ...value, n_sims: Number.isFinite(num) ? Math.round(num) : value.n_sims });
            }}
          />
        </label>

        <label className="custom-range-field" style={{ textTransform: "none", fontSize: 11 }}>
          Ticker Focus
          <select
            value={value.selected_symbol ?? "AUTO"}
            onChange={(event) =>
              onChange({
                ...value,
                selected_symbol: event.target.value === "AUTO" ? null : event.target.value,
              })
            }
            style={{
              border: "1px solid var(--border-soft)",
              background: "rgba(255,255,255,0.02)",
              color: "var(--text)",
              borderRadius: 8,
              padding: "8px 10px",
            }}
          >
            <option value="AUTO">Auto (top holding)</option>
            {symbols.map((symbol) => (
              <option key={symbol} value={symbol}>
                {symbol}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div style={{ marginTop: 12, marginBottom: 8 }}>
        <div style={{ color: "var(--muted)", fontSize: 11, marginBottom: 8 }}>Shock Slider</div>
        <input
          type="range"
          min={selected?.min_value ?? -10}
          max={selected?.max_value ?? 10}
          step={selected?.step ?? 0.1}
          value={value.shock_value}
          onChange={(event) => {
            const num = Number(event.target.value);
            onChange({ ...value, shock_value: Number.isFinite(num) ? num : value.shock_value });
          }}
          style={{ width: "100%" }}
        />
      </div>

      <div className="row-between" style={{ marginTop: 10, alignItems: "flex-end" }}>
        <div>
          <div className="kicker" style={{ marginBottom: 8 }}>
            Horizon
          </div>
          <div className="range-row" style={{ marginBottom: 0 }}>
            {HORIZONS.map((horizon) => (
              <button
                key={horizon.label}
                className={`range-btn ${value.horizon_days === horizon.days ? "active" : ""}`}
                onClick={() => onChange({ ...value, horizon_days: horizon.days })}
                type="button"
              >
                {horizon.label}
              </button>
            ))}
          </div>
        </div>

        <div className="row-between" style={{ gap: 8 }}>
          <button className="btn-secondary" type="button" disabled={loading} onClick={onPreview}>
            Preview
          </button>
          <button className="btn-primary" type="button" disabled={loading} onClick={onRun}>
            Save Run
          </button>
        </div>
      </div>

      {selected ? (
        <div style={{ marginTop: 10, color: "var(--muted)", fontSize: 11, lineHeight: 1.6 }}>{selected.description}</div>
      ) : null}
    </div>
  );
}
