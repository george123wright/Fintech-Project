import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { ScenarioDistributionBin } from "../types/api";

type Props = {
  bins: ScenarioDistributionBin[];
};

export default function ScenarioDistributionChart({ bins }: Props) {
  return (
    <div className="card" style={{ marginBottom: 16 }}>
      <div className="kicker">Simulated Distribution (Portfolio Return)</div>
      <div style={{ width: "100%", height: 260 }}>
        <ResponsiveContainer>
          <BarChart
            data={bins.map((item) => ({
              x: Number(((item.bin_start + item.bin_end) / 2).toFixed(2)),
              density: item.density,
              count: item.count,
            }))}
            margin={{ top: 10, right: 10, bottom: 20, left: 0 }}
          >
            <CartesianGrid stroke="var(--border)" strokeDasharray="4 4" />
            <XAxis dataKey="x" tick={{ fill: "var(--muted)", fontSize: 11 }} />
            <YAxis tick={{ fill: "var(--muted)", fontSize: 11 }} />
            <Tooltip
              contentStyle={{
                background: "rgba(13,18,29,0.95)",
                border: "1px solid var(--border)",
                borderRadius: 8,
              }}
            />
            <Bar dataKey="density" fill="var(--accent)" radius={[2, 2, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
