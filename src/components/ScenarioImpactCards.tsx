import type { ScenarioImpact } from "../types/api";
import { formatPercent, formatPrice } from "../utils/format";

type Props = {
  portfolio: ScenarioImpact;
  selected: ScenarioImpact | null;
};

function ImpactCard({ title, impact }: { title: string; impact: ScenarioImpact }) {
  return (
    <div className="card">
      <div className="kicker">{title}</div>
      <div style={{ fontFamily: "var(--sans)", fontSize: 28, fontWeight: 700, marginBottom: 8 }}>
        {formatPercent(impact.shock_only_return_pct ?? 0)}
      </div>
      <div style={{ display: "grid", gap: 8 }}>
        <div className="row-between" style={{ fontSize: 12 }}>
          <span style={{ color: "var(--muted)" }}>Expected Return</span>
          <span>{impact.expected_return_pct == null ? "N/A" : formatPercent(impact.expected_return_pct)}</span>
        </div>
        <div className="row-between" style={{ fontSize: 12 }}>
          <span style={{ color: "var(--muted)" }}>Shock-only Return</span>
          <span>{impact.shock_only_return_pct == null ? "N/A" : formatPercent(impact.shock_only_return_pct)}</span>
        </div>
        <div className="row-between" style={{ fontSize: 12 }}>
          <span style={{ color: "var(--muted)" }}>Expected Value</span>
          <span>{impact.expected_value == null ? "N/A" : formatPrice(impact.expected_value)}</span>
        </div>
        <div className="row-between" style={{ fontSize: 12 }}>
          <span style={{ color: "var(--muted)" }}>Confidence Band</span>
          <span>
            {impact.quantile_low_pct == null || impact.quantile_high_pct == null
              ? "N/A"
              : `${formatPercent(impact.quantile_low_pct)} to ${formatPercent(impact.quantile_high_pct)}`}
          </span>
        </div>
      </div>
    </div>
  );
}

export default function ScenarioImpactCards({ portfolio, selected }: Props) {
  return (
    <div className="grid-2" style={{ marginBottom: 16 }}>
      <ImpactCard title="Portfolio Impact" impact={portfolio} />
      <ImpactCard title={`${selected?.symbol ?? "Selected"} Impact`} impact={selected ?? portfolio} />
    </div>
  );
}
