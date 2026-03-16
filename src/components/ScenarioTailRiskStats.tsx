import type { ScenarioSimulationStats } from "../types/api";
import { formatPrice } from "../utils/format";

type Props = {
  title: string;
  stats: ScenarioSimulationStats | null | undefined;
  currentValue: number | null | undefined;
};

function fmtPct(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "N/A";
  return `${value.toFixed(2)}%`;
}

function fmtValue(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "N/A";
  return formatPrice(value);
}

function tailLossValue(currentValue: number | null | undefined, tailPct: number | null | undefined): number | null {
  if (currentValue == null || tailPct == null || Number.isNaN(currentValue) || Number.isNaN(tailPct)) {
    return null;
  }
  return (currentValue * tailPct) / 100.0;
}

export default function ScenarioTailRiskStats({ title, stats, currentValue }: Props) {
  if (!stats) {
    return (
      <div className="card">
        <div className="kicker">{title}</div>
        <div style={{ color: "var(--muted)", fontSize: 12 }}>No simulation stats available.</div>
      </div>
    );
  }

  const var95 = stats.var_95_pct;
  const cvar95 = stats.cvar_95_pct;
  const var99 = stats.var_99_pct;
  const cvar99 = stats.cvar_99_pct;

  return (
    <div className="card">
      <div className="kicker">{title}</div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
        <div className="row-between" style={{ fontSize: 12 }}>
          <span>VaR 95%</span>
          <span style={{ color: "var(--yellow)" }}>{fmtPct(var95)}</span>
        </div>
        <div className="row-between" style={{ fontSize: 12 }}>
          <span>CVaR / ES 95%</span>
          <span style={{ color: "var(--red)" }}>{fmtPct(cvar95)}</span>
        </div>
        <div className="row-between" style={{ fontSize: 12 }}>
          <span>VaR 99%</span>
          <span style={{ color: "var(--yellow)" }}>{fmtPct(var99)}</span>
        </div>
        <div className="row-between" style={{ fontSize: 12 }}>
          <span>CVaR / ES 99%</span>
          <span style={{ color: "var(--red)" }}>{fmtPct(cvar99)}</span>
        </div>
        <div className="row-between" style={{ fontSize: 12 }}>
          <span>Tail Loss 95% (Value)</span>
          <span>{fmtValue(tailLossValue(currentValue, cvar95))}</span>
        </div>
        <div className="row-between" style={{ fontSize: 12 }}>
          <span>Tail Loss 99% (Value)</span>
          <span>{fmtValue(tailLossValue(currentValue, cvar99))}</span>
        </div>
        <div className="row-between" style={{ fontSize: 12 }}>
          <span>Sim Mean</span>
          <span>{fmtPct(stats.mean_pct)}</span>
        </div>
        <div className="row-between" style={{ fontSize: 12 }}>
          <span>Sim Std Dev</span>
          <span>{fmtPct(stats.std_pct)}</span>
        </div>
      </div>
    </div>
  );
}
