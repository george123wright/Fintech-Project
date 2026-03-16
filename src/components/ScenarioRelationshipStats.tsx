import type { ScenarioRelationshipStats } from "../types/api";

type Props = {
  title: string;
  stats: ScenarioRelationshipStats | null | undefined;
};

function fmt(value: number | null | undefined, digits = 3): string {
  if (value == null || Number.isNaN(value)) return "N/A";
  return value.toFixed(digits);
}

export default function ScenarioRelationshipStats({ title, stats }: Props) {
  if (!stats) {
    return (
      <div className="card">
        <div className="kicker">{title}</div>
        <div style={{ color: "var(--muted)", fontSize: 12 }}>No relationship stats available.</div>
      </div>
    );
  }

  return (
    <div className="card">
      <div className="kicker">{title}</div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
        <div className="row-between" style={{ fontSize: 12 }}><span>Alpha</span><span>{fmt(stats.alpha)}</span></div>
        <div className="row-between" style={{ fontSize: 12 }}><span>Beta</span><span>{fmt(stats.beta)}</span></div>
        <div className="row-between" style={{ fontSize: 12 }}><span>Beta SE</span><span>{fmt(stats.beta_std_error)}</span></div>
        <div className="row-between" style={{ fontSize: 12 }}><span>p-value</span><span>{fmt(stats.beta_p_value)}</span></div>
        <div className="row-between" style={{ fontSize: 12 }}><span>R2</span><span>{fmt(stats.r2)}</span></div>
        <div className="row-between" style={{ fontSize: 12 }}><span>Adj R2</span><span>{fmt(stats.adj_r2)}</span></div>
        <div className="row-between" style={{ fontSize: 12 }}><span>N Obs</span><span>{stats.n_obs}</span></div>
        <div className="row-between" style={{ fontSize: 12 }}><span>Corr</span><span>{fmt(stats.correlation)}</span></div>
        <div className="row-between" style={{ fontSize: 12 }}><span>Shock Z</span><span>{fmt(stats.shock_z_score)}</span></div>
        <div className="row-between" style={{ fontSize: 12 }}><span>Shock Percentile</span><span>{fmt(stats.shock_percentile)}</span></div>
      </div>
      {stats.flags.length ? (
        <div style={{ marginTop: 10, display: "flex", flexWrap: "wrap", gap: 6 }}>
          {stats.flags.map((flag) => (
            <span key={flag} className="pill" style={{ color: "var(--yellow)", borderColor: "rgba(240,190,107,0.45)" }}>
              {flag}
            </span>
          ))}
        </div>
      ) : null}
    </div>
  );
}
