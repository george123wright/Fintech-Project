import type { ExposureBucket, ExposureSummary } from "../types/api";

type Props = {
  summary: ExposureSummary | null | undefined;
};

function ExposureList({ title, buckets, barColor }: { title: string; buckets: ExposureBucket[]; barColor: string }) {
  return (
    <div className="surface-soft" style={{ padding: 12 }}>
      <div className="kicker" style={{ marginBottom: 10 }}>
        {title}
      </div>
      <div style={{ display: "grid", gap: 10 }}>
        {buckets.length ? (
          buckets.map((bucket) => (
            <div key={`${title}-${bucket.label}`} style={{ display: "grid", gap: 5 }}>
              <div className="row-between" style={{ gap: 10 }}>
                <span style={{ fontSize: 12 }}>{bucket.label}</span>
                <strong style={{ fontSize: 12 }}>{bucket.lookthrough_weight_pct.toFixed(1)}%</strong>
              </div>
              <div style={{ display: "grid", gap: 4 }}>
                <div style={{ height: 7, width: "100%", background: "rgba(255,255,255,0.06)", borderRadius: 999, overflow: "hidden" }}>
                  <div style={{ width: `${Math.max(4, Math.min(100, bucket.lookthrough_weight_pct))}%`, height: "100%", background: barColor, borderRadius: 999 }} />
                </div>
                <div style={{ fontSize: 10, color: "var(--muted)" }}>
                  Direct {bucket.direct_weight_pct.toFixed(1)}% · Look-through {bucket.lookthrough_weight_pct.toFixed(1)}%
                </div>
              </div>
            </div>
          ))
        ) : (
          <div style={{ fontSize: 12, color: "var(--muted)" }}>No exposure buckets available yet.</div>
        )}
      </div>
    </div>
  );
}

export default function PortfolioExposureSummary({ summary }: Props) {
  if (!summary) return null;

  const sector = summary.breakdowns.sector ?? [];
  const currency = summary.breakdowns.currency ?? [];
  const assetType = summary.breakdowns.asset_type ?? [];

  return (
    <div style={{ marginBottom: 24 }}>
      <div className="kicker" style={{ marginBottom: 10 }}>
        What you actually own
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1.1fr 0.9fr", gap: 14, marginBottom: 14 }}>
        <div className="surface" style={{ padding: 14 }}>
          <div className="row-between" style={{ marginBottom: 10, alignItems: "flex-start" }}>
            <div>
              <div style={{ fontSize: 15, fontWeight: 700 }}>Look-through concentration</div>
              <div style={{ color: "var(--muted)", fontSize: 11, marginTop: 4 }}>
                Coverage {summary.coverage.covered_weight_pct.toFixed(1)}% across {summary.coverage.holding_count} holdings
              </div>
            </div>
            <span className="pill">{summary.coverage.constituent_positions} funds expanded</span>
          </div>
          <div style={{ overflowX: "auto" }}>
            <table className="table" style={{ margin: 0 }}>
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th className="right">Look-through weight</th>
                </tr>
              </thead>
              <tbody>
                {summary.top_lookthrough_holdings.map((holding) => (
                  <tr key={holding.symbol}>
                    <td>
                      <div style={{ fontWeight: 700 }}>{holding.symbol}</div>
                    </td>
                    <td className="right">{holding.weight_pct.toFixed(1)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div style={{ marginTop: 12 }}>
            <div className="kicker" style={{ marginBottom: 6 }}>Highest overlap pairs</div>
            <div style={{ display: "grid", gap: 8 }}>
              {summary.overlap_pairs.length ? summary.overlap_pairs.map((pair) => (
                <div key={`${pair.left_symbol}-${pair.right_symbol}`} className="surface-soft" style={{ padding: 10 }}>
                  <div className="row-between" style={{ fontSize: 12 }}>
                    <strong>{pair.left_symbol} / {pair.right_symbol}</strong>
                    <span>{(pair.overlap_weight * 100).toFixed(1)}%</span>
                  </div>
                  <div style={{ fontSize: 10, color: "var(--muted)", marginTop: 4 }}>
                    {pair.overlap_type} overlap · {(pair.overlap_pct_of_pair * 100).toFixed(1)}% of pair weight
                  </div>
                </div>
              )) : <div style={{ fontSize: 12, color: "var(--muted)" }}>No material overlap pairs detected.</div>}
            </div>
          </div>
        </div>

        <div className="surface" style={{ padding: 14 }}>
          <div className="kicker" style={{ marginBottom: 8 }}>
            Concentration signals
          </div>
          <div style={{ display: "grid", gap: 10 }}>
            {summary.concentration_signals.length ? (
              summary.concentration_signals.map((flag, idx) => (
                <div key={`${flag.signal_key}-${idx}`} style={{ border: "1px solid var(--border)", borderRadius: 12, padding: 10, background: "rgba(255,255,255,0.02)" }}>
                  <div className="row-between" style={{ marginBottom: 6 }}>
                    <strong style={{ fontSize: 12 }}>{flag.signal_key.replace(/_/g, " ")}</strong>
                    <span className="pill" style={{ textTransform: "capitalize" }}>{flag.severity}</span>
                  </div>
                  <div style={{ color: "var(--muted)", fontSize: 11, lineHeight: 1.55 }}>{flag.summary}</div>
                </div>
              ))
            ) : (
              <div style={{ fontSize: 12, color: "var(--muted)" }}>No concentration flags have triggered for the latest snapshot.</div>
            )}
          </div>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 12 }}>
        <ExposureList title="Sector Exposure" buckets={sector} barColor="var(--accent)" />
        <ExposureList title="Currency Exposure" buckets={currency} barColor="var(--yellow)" />
        <ExposureList title="Asset Mix" buckets={assetType} barColor="var(--green)" />
      </div>
    </div>
  );
}
