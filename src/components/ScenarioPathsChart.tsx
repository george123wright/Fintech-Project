import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { ScenarioPath } from "../types/api";

type Props = {
  paths: ScenarioPath[];
  title: string;
};

function groupToRows(paths: ScenarioPath[]) {
  const byStep = new Map<number, Record<string, number | string>>();
  for (const path of paths) {
    for (const point of path.points) {
      const row = byStep.get(point.step) ?? { step: point.step, label: point.label };
      row[path.path_id] = point.cumulative_return_pct;
      byStep.set(point.step, row);
    }
  }
  return [...byStep.values()].sort((a, b) => Number(a.step) - Number(b.step));
}

export default function ScenarioPathsChart({ paths, title }: Props) {
  if (!paths.length) {
    return (
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="kicker">{title}</div>
        <div style={{ color: "var(--muted)", fontSize: 12 }}>No simulation paths available.</div>
      </div>
    );
  }

  const rows = groupToRows(paths);

  return (
    <div className="card" style={{ marginBottom: 16 }}>
      <div className="kicker">{title}</div>
      <div style={{ width: "100%", height: 280 }}>
        <ResponsiveContainer>
          <LineChart data={rows} margin={{ top: 10, right: 16, left: 0, bottom: 8 }}>
            <CartesianGrid stroke="var(--border)" strokeDasharray="4 4" />
            <XAxis dataKey="label" tick={{ fill: "var(--muted)", fontSize: 11 }} />
            <YAxis tick={{ fill: "var(--muted)", fontSize: 11 }} />
            <Tooltip
              formatter={(value: number) => `${Number(value).toFixed(2)}%`}
              contentStyle={{
                background: "rgba(13,18,29,0.95)",
                border: "1px solid var(--border)",
                borderRadius: 8,
              }}
            />
            {paths.map((path) => (
              <Line
                key={path.path_id}
                type="monotone"
                dataKey={path.path_id}
                dot={false}
                stroke="rgba(111,124,255,0.28)"
                strokeWidth={1}
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
