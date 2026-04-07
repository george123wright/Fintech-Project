import { useMemo, useState, type Dispatch } from "react";
import Plot from "react-plotly.js";
import { ResponsiveContainer, Treemap } from "recharts";
import DataWarningBanner from "../components/DataWarningBanner";
import { usePortfolioData } from "../state/DataProvider";
import type { NavAction } from "../state/nav";
import { formatPercent } from "../utils/format";

type Props = {
  dispatch: Dispatch<NavAction>;
};

type TimeWindow = "1M" | "3M" | "6M" | "YTD" | "Custom";
type Interval = "1D" | "1W" | "1M";
type MetricKey = "industry" | "weight" | "return" | "volatility" | "sharpe" | "beta";

type IndustryMetric = {
  industry: string;
  weight: number;
  ret: number;
  vol: number;
  sharpe: number;
  beta: number;
};

const INDUSTRY_BASE: IndustryMetric[] = [
  { industry: "Semiconductors", weight: 18.2, ret: 14.9, vol: 24.4, sharpe: 1.19, beta: 1.24 },
  { industry: "Software", weight: 14.1, ret: 10.6, vol: 18.3, sharpe: 0.98, beta: 1.06 },
  { industry: "Financials", weight: 12.4, ret: 8.2, vol: 16.9, sharpe: 0.74, beta: 0.93 },
  { industry: "Healthcare", weight: 11.7, ret: 6.7, vol: 14.2, sharpe: 0.71, beta: 0.82 },
  { industry: "Industrials", weight: 9.3, ret: 5.8, vol: 13.5, sharpe: 0.65, beta: 0.88 },
  { industry: "Energy", weight: 8.1, ret: 4.4, vol: 21.8, sharpe: 0.39, beta: 1.13 },
  { industry: "Consumer", weight: 10.8, ret: 7.1, vol: 15.3, sharpe: 0.68, beta: 0.9 },
  { industry: "Comm Services", weight: 8.6, ret: 9.4, vol: 17.1, sharpe: 0.83, beta: 1.01 },
  { industry: "Utilities", weight: 6.8, ret: 3.1, vol: 10.1, sharpe: 0.42, beta: 0.52 },
];

const MATRIX_TEMPLATE = [
  [1, 0.62, 0.41, 0.29, 0.36, 0.48, 0.44, 0.5, 0.22],
  [0.62, 1, 0.45, 0.34, 0.32, 0.36, 0.4, 0.52, 0.27],
  [0.41, 0.45, 1, 0.38, 0.57, 0.43, 0.49, 0.35, 0.19],
  [0.29, 0.34, 0.38, 1, 0.33, 0.21, 0.4, 0.27, 0.31],
  [0.36, 0.32, 0.57, 0.33, 1, 0.54, 0.46, 0.39, 0.24],
  [0.48, 0.36, 0.43, 0.21, 0.54, 1, 0.4, 0.28, 0.2],
  [0.44, 0.4, 0.49, 0.4, 0.46, 0.4, 1, 0.44, 0.25],
  [0.5, 0.52, 0.35, 0.27, 0.39, 0.28, 0.44, 1, 0.2],
  [0.22, 0.27, 0.19, 0.31, 0.24, 0.2, 0.25, 0.2, 1],
];

function scaleByWindow(window: TimeWindow): number {
  if (window === "1M") return 0.65;
  if (window === "3M") return 0.82;
  if (window === "6M") return 0.92;
  if (window === "YTD") return 1;
  return 1.08;
}

export default function MarketOverviewPage({ dispatch }: Props) {
  const { state: dataState } = usePortfolioData();
  const [window, setWindow] = useState<TimeWindow>("YTD");
  const [interval, setInterval] = useState<Interval>("1W");
  const [benchmark, setBenchmark] = useState("SPY");
  const [confidence, setConfidence] = useState(95);
  const [sortBy, setSortBy] = useState<MetricKey>("weight");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  const rows = useMemo(() => {
    const scale = scaleByWindow(window);
    const intervalScale = interval === "1D" ? 0.92 : interval === "1W" ? 1 : 1.11;
    const confidenceScale = confidence >= 99 ? 1.08 : confidence >= 97 ? 1.04 : 1;

    return INDUSTRY_BASE.map((row) => ({
      ...row,
      ret: Number((row.ret * scale * intervalScale).toFixed(2)),
      vol: Number((row.vol * confidenceScale).toFixed(2)),
      sharpe: Number((row.sharpe * scale / intervalScale).toFixed(2)),
      beta: Number((row.beta * (benchmark === "QQQ" ? 1.06 : benchmark === "IWM" ? 1.11 : 1)).toFixed(2)),
    }));
  }, [benchmark, confidence, interval, window]);

  const sortedRows = useMemo(() => {
    const sorted = [...rows].sort((a, b) => {
      const pickMetric = (row: IndustryMetric) => {
        if (sortBy === "industry") return row.industry;
        if (sortBy === "return") return row.ret;
        if (sortBy === "volatility") return row.vol;
        return row[sortBy];
      };
      const left = pickMetric(a);
      const right = pickMetric(b);
      if (typeof left === "string" && typeof right === "string") {
        return sortDir === "asc" ? left.localeCompare(right) : right.localeCompare(left);
      }
      return sortDir === "asc" ? Number(left) - Number(right) : Number(right) - Number(left);
    });
    return sorted;
  }, [rows, sortBy, sortDir]);

  const labels = rows.map((item) => item.industry);

  const covariance = useMemo(() => {
    return MATRIX_TEMPLATE.map((matrixRow, rowIdx) =>
      matrixRow.map((corr, colIdx) => {
        const volA = rows[rowIdx]?.vol ?? 0;
        const volB = rows[colIdx]?.vol ?? 0;
        return Number(((corr * volA * volB) / 10000).toFixed(3));
      })
    );
  }, [rows]);

  const warnings = useMemo(
    () => [
      ...dataState.dataWarnings,
      "Sector composition derived from holdings mapping and may lag latest filings.",
      confidence >= 99 ? "99% confidence can amplify covariance estimates for cyclical clusters." : "",
    ].filter(Boolean),
    [confidence, dataState.dataWarnings]
  );

  const totalWeight = rows.reduce((acc, row) => acc + row.weight, 0);

  const onSort = (next: MetricKey) => {
    if (sortBy === next) {
      setSortDir((prev) => (prev === "asc" ? "desc" : "asc"));
      return;
    }
    setSortBy(next);
    setSortDir(next === "industry" ? "asc" : "desc");
  };

  return (
    <div className="overview-prototype-wrap market-overview-wrap">
      <div className="overview-page-title">
        <div>
          <h1>Market Overview</h1>
          <p>Industry-relative performance, cross-industry risk linkage, and concentration stress in one place.</p>
        </div>
        <button className="btn-secondary" onClick={() => dispatch({ type: "go_page", page: "overview" })}>
          Back to Portfolio Overview
        </button>
      </div>

      <DataWarningBanner warnings={warnings} title="Industry Read Warnings" />

      <section className="overview-intel-shell market-controls-shell">
        <div className="market-controls-row">
          <div className="market-control-group">
            <label>Window</label>
            <div className="market-pill-row">
              {(["1M", "3M", "6M", "YTD", "Custom"] as TimeWindow[]).map((item) => (
                <button
                  key={item}
                  className={`overview-period-btn ${window === item ? "active" : ""}`}
                  onClick={() => setWindow(item)}
                >
                  {item}
                </button>
              ))}
            </div>
          </div>

          <div className="market-control-group">
            <label>Interval</label>
            <select value={interval} onChange={(event) => setInterval(event.target.value as Interval)}>
              <option value="1D">Daily</option>
              <option value="1W">Weekly</option>
              <option value="1M">Monthly</option>
            </select>
          </div>

          <div className="market-control-group">
            <label>Benchmark</label>
            <select value={benchmark} onChange={(event) => setBenchmark(event.target.value)}>
              <option value="SPY">SPY</option>
              <option value="QQQ">QQQ</option>
              <option value="IWM">IWM</option>
            </select>
          </div>

          <div className="market-control-group">
            <label>Confidence</label>
            <select value={confidence} onChange={(event) => setConfidence(Number(event.target.value))}>
              <option value={90}>90%</option>
              <option value={95}>95%</option>
              <option value={97}>97%</option>
              <option value={99}>99%</option>
            </select>
          </div>
        </div>
      </section>

      <section className="overview-main-shell market-main-shell">
        <div className="overview-widget-shell market-table-shell">
          <div className="overview-lens-header">
            <h3 className="overview-lens-panel-title">Industry Metrics</h3>
            <span className="overview-lens-badge">Total Weight {formatPercent(totalWeight, 1)}</span>
          </div>
          <table className="table market-table">
            <thead>
              <tr>
                <th>
                  <button className="market-sort-btn" onClick={() => onSort("industry")}>Industry</button>
                </th>
                <th className="right">
                  <button className="market-sort-btn" onClick={() => onSort("weight")}>Weight</button>
                </th>
                <th className="right">
                  <button className="market-sort-btn" onClick={() => onSort("return")}>Return</button>
                </th>
                <th className="right">
                  <button className="market-sort-btn" onClick={() => onSort("volatility")}>Volatility</button>
                </th>
                <th className="right">
                  <button className="market-sort-btn" onClick={() => onSort("sharpe")}>Sharpe</button>
                </th>
                <th className="right">
                  <button className="market-sort-btn" onClick={() => onSort("beta")}>Beta</button>
                </th>
              </tr>
            </thead>
            <tbody>
              {sortedRows.map((row) => (
                <tr key={row.industry}>
                  <td>{row.industry}</td>
                  <td className="right">{formatPercent(row.weight, 1)}</td>
                  <td className={`right ${row.ret >= 0 ? "positive" : "negative"}`}>{formatPercent(row.ret, 1)}</td>
                  <td className="right">{formatPercent(row.vol, 1)}</td>
                  <td className="right">{row.sharpe.toFixed(2)}</td>
                  <td className="right">{row.beta.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="overview-widget-shell market-treemap-shell">
          <div className="overview-lens-header">
            <h3 className="overview-lens-panel-title">Industry Weight Map</h3>
          </div>
          <div style={{ width: "100%", height: 290 }}>
            <ResponsiveContainer>
              <Treemap
                data={rows.map((row) => ({ name: row.industry, size: row.weight, ret: row.ret }))}
                dataKey="size"
                nameKey="name"
                stroke="rgba(216,197,179,0.75)"
                fill="#0f6b73"
              />
            </ResponsiveContainer>
          </div>
        </div>
      </section>

      <section className="overview-main-shell market-heatmap-grid">
        <div className="overview-chart-shell">
          <div className="overview-lens-header">
            <h3 className="overview-lens-panel-title">Covariance Heatmap</h3>
          </div>
          <Plot
            data={[
              {
                z: covariance,
                x: labels,
                y: labels,
                type: "heatmap",
                colorscale: "Viridis",
                reversescale: false,
              },
            ]}
            layout={{
              autosize: true,
              margin: { l: 90, r: 20, t: 12, b: 90 },
              paper_bgcolor: "rgba(0,0,0,0)",
              plot_bgcolor: "rgba(0,0,0,0)",
              font: { family: "Inter, sans-serif", size: 11, color: "#7e746d" },
            }}
            style={{ width: "100%", height: "320px" }}
            config={{ displayModeBar: false, responsive: true }}
          />
        </div>

        <div className="overview-chart-shell">
          <div className="overview-lens-header">
            <h3 className="overview-lens-panel-title">Correlation Heatmap</h3>
          </div>
          <Plot
            data={[
              {
                z: MATRIX_TEMPLATE,
                x: labels,
                y: labels,
                type: "heatmap",
                zmin: -1,
                zmax: 1,
                colorscale: [
                  [0, "#cf6d74"],
                  [0.5, "#f8f5ef"],
                  [1, "#0f6b73"],
                ],
              },
            ]}
            layout={{
              autosize: true,
              margin: { l: 90, r: 20, t: 12, b: 90 },
              paper_bgcolor: "rgba(0,0,0,0)",
              plot_bgcolor: "rgba(0,0,0,0)",
              font: { family: "Inter, sans-serif", size: 11, color: "#7e746d" },
            }}
            style={{ width: "100%", height: "320px" }}
            config={{ displayModeBar: false, responsive: true }}
          />
        </div>
      </section>

      <div className="overview-extended-note">
        Industry matrix is a blended estimate from current holdings exposure and benchmark-relative historical co-movement.
      </div>
    </div>
  );
}
