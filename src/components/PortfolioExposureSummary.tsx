import type { ExposureBucket, ExposureSummary } from "../types/api";
import { formatPrice } from "../utils/format";

type Props = {
  summary: ExposureSummary | null | undefined;
};

function ExposureList({
  title,
  buckets,
  barColor,
}: {
  title: string;
  buckets: ExposureBucket[];
  barColor: string;
}) {
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
                <strong style={{ fontSize: 12 }}>{bucket.weight_pct.toFixed(1)}%</strong>
              </div>
              <div
                style={{
                  height: 7,
                  width: "100%",
                  background: "rgba(255,255,255,0.06)",
                  borderRadius: 999,
                  overflow: "hidden",
                }}
              >
                <div
                  style={{
                    width: `${Math.max(4, Math.min(100, bucket.weight_pct))}%`,
                    height: "100%",
                    background: barColor,
                    borderRadius: 999,
                  }}
                />
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

  return (
    <div style={{ marginBottom: 24 }}>
      <div className="kicker" style={{ marginBottom: 10 }}>
        What you actually own
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1.15fr 0.85fr", gap: 14, marginBottom: 14 }}>
        <div className="surface" style={{ padding: 14 }}>
          <div className="row-between" style={{ marginBottom: 10, alignItems: "flex-start" }}>
            <div>
              <div style={{ fontSize: 15, fontWeight: 700 }}>Top holdings concentration</div>
              <div style={{ color: "var(--muted)", fontSize: 11, marginTop: 4 }}>
                Sector coverage: {summary.coverage.sector_weight_covered_pct.toFixed(1)}% of portfolio weight
              </div>
            </div>
            <span className="pill">{summary.coverage.holding_count} holdings</span>
          </div>
          <div style={{ overflowX: "auto" }}>
            <table className="table" style={{ margin: 0 }}>
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th>Sector</th>
                  <th className="right">Weight</th>
                  <th className="right">Market Value</th>
                </tr>
              </thead>
              <tbody>
                {summary.top_holdings.map((holding) => (
                  <tr key={holding.symbol}>
                    <td>
                      <div style={{ fontWeight: 700 }}>{holding.symbol}</div>
                      <div style={{ fontSize: 10, color: "var(--muted)" }}>{holding.name ?? "No name"}</div>
                    </td>
                    <td>{holding.sector ?? "Unknown sector"}</td>
                    <td className="right">{holding.weight_pct.toFixed(1)}%</td>
                    <td className="right">{formatPrice(holding.market_value)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="surface" style={{ padding: 14 }}>
          <div className="kicker" style={{ marginBottom: 8 }}>
            Concentration signals
          </div>
          <div style={{ display: "grid", gap: 10 }}>
            {summary.concentration_flags.length ? (
              summary.concentration_flags.map((flag, idx) => (
                <div
                  key={`${flag.title}-${idx}`}
                  style={{
                    border: "1px solid var(--border)",
                    borderRadius: 12,
                    padding: 10,
                    background: "rgba(255,255,255,0.02)",
                  }}
                >
                  <div className="row-between" style={{ marginBottom: 6 }}>
                    <strong style={{ fontSize: 12 }}>{flag.title}</strong>
                    <span className="pill" style={{ textTransform: "capitalize" }}>
                      {flag.level}
                    </span>
                  </div>
                  <div style={{ color: "var(--muted)", fontSize: 11, lineHeight: 1.55 }}>{flag.detail}</div>
                </div>
              ))
            ) : (
              <div style={{ fontSize: 12, color: "var(--muted)" }}>
                No concentration flags have triggered for the latest snapshot.
              </div>
            )}
          </div>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 12 }}>
        <ExposureList title="Sector Exposure" buckets={summary.sector} barColor="var(--accent)" />
        <ExposureList title="Currency Exposure" buckets={summary.currency} barColor="var(--yellow)" />
        <ExposureList title="Asset Mix" buckets={summary.asset_type} barColor="var(--green)" />
      </div>
    </div>
  );
}
