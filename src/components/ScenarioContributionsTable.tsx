import type { ScenarioContribution } from "../types/api";
import { formatPercent } from "../utils/format";

type Props = {
  rows: ScenarioContribution[];
};

export default function ScenarioContributionsTable({ rows }: Props) {
  return (
    <div className="card" style={{ marginBottom: 16 }}>
      <div className="kicker">Contribution Attribution (Shock-only)</div>
      <div style={{ overflowX: "auto" }}>
        <table className="table">
          <thead>
            <tr>
              <th>Symbol</th>
              <th className="right">Weight</th>
              <th className="right">Beta</th>
              <th className="right">Contribution</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.symbol}>
                <td>{row.symbol}</td>
                <td className="right">{formatPercent(row.weight * 100)}</td>
                <td className="right">{row.beta == null ? "N/A" : row.beta.toFixed(3)}</td>
                <td className="right" style={{ color: (row.contribution_pct ?? 0) >= 0 ? "var(--green)" : "var(--red)" }}>
                  {row.contribution_pct == null ? "N/A" : formatPercent(row.contribution_pct)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
