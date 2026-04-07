import { useMemo, useState } from "react";
import type { ColorScale, Data } from "plotly.js";
import Plot from "react-plotly.js";

type IndustryRow = {
  industry: string;
  ret: number;
  vol: number;
  sharpe: number;
  beta: number;
};

type MatrixMode = "covariance" | "correlation";
type SortOption = "alphabetical" | "return" | "volatility" | "sharpe" | "beta";

const DIVERGING_SCALE: ColorScale = [
  [0, "#cf6d74"],
  [0.5, "#f8f5ef"],
  [1, "#0f6b73"],
];

type Props = {
  rows: IndustryRow[];
  covarianceMatrix: Array<Array<number | null>>;
  correlationMatrix: Array<Array<number | null>>;
};

export function reorderMatrix(matrix: Array<Array<number | null>>, orderedIndices: number[]) {
  return orderedIndices.map((rowIndex) => orderedIndices.map((colIndex) => matrix[rowIndex]?.[colIndex] ?? 0));
}

export default function IndustryMatrixHeatmap({ rows, covarianceMatrix, correlationMatrix }: Props) {
  const [mode, setMode] = useState<MatrixMode>("covariance");
  const [sortOption, setSortOption] = useState<SortOption>("alphabetical");

  const orderedRows = useMemo(() => {
    const next = [...rows];
    next.sort((a, b) => {
      if (sortOption === "alphabetical") return a.industry.localeCompare(b.industry);
      if (sortOption === "return") return b.ret - a.ret;
      if (sortOption === "volatility") return b.vol - a.vol;
      if (sortOption === "sharpe") return b.sharpe - a.sharpe;
      return b.beta - a.beta;
    });
    return next;
  }, [rows, sortOption]);

  const orderedLabels = orderedRows.map((item) => item.industry);

  const orderedIndices = useMemo(() => {
    const byLabel = new Map(rows.map((row, index) => [row.industry, index]));
    return orderedLabels.map((label) => byLabel.get(label) ?? 0);
  }, [orderedLabels, rows]);

  const matrix = useMemo(() => {
    const source = mode === "correlation" ? correlationMatrix : covarianceMatrix;
    return reorderMatrix(source, orderedIndices);
  }, [correlationMatrix, covarianceMatrix, mode, orderedIndices]);

  const covarianceExtrema = useMemo(() => {
    const values = matrix.flat().filter((value): value is number => typeof value === "number" && Number.isFinite(value));
    if (values.length === 0) {
      return { min: 0, max: 0, hasSignedRange: false };
    }
    const min = Math.min(...values);
    const max = Math.max(...values);
    return { min, max, hasSignedRange: min < 0 && max > 0 };
  }, [matrix]);

  const heatmapConfig =
    mode === "correlation"
      ? {
          colorscale: DIVERGING_SCALE,
          zmin: -1,
          zmax: 1,
          zmid: 0,
        }
      : covarianceExtrema.hasSignedRange
        ? {
            colorscale: DIVERGING_SCALE,
            zmin: covarianceExtrema.min,
            zmax: covarianceExtrema.max,
            zmid: 0,
          }
        : {
            colorscale: "Viridis" as const,
            zmin: covarianceExtrema.min,
            zmax: covarianceExtrema.max,
          };

  const heatmapTrace: Data = {
    z: matrix,
    x: orderedLabels,
    y: orderedLabels,
    type: "heatmap",
    ...heatmapConfig,
  };


  return (
    <div className="overview-chart-shell">
      <div className="overview-lens-header" style={{ gap: 10, flexWrap: "wrap" }}>
        <h3 className="overview-lens-panel-title">Industry Matrix Heatmap</h3>
        <div className="market-pill-row">
          <button className={`overview-period-btn ${mode === "covariance" ? "active" : ""}`} onClick={() => setMode("covariance")}>Covariance</button>
          <button className={`overview-period-btn ${mode === "correlation" ? "active" : ""}`} onClick={() => setMode("correlation")}>Correlation</button>
        </div>
        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 8 }}>
          <label style={{ fontSize: 12, color: "#7e746d" }}>Sort</label>
          <select value={sortOption} onChange={(event) => setSortOption(event.target.value as SortOption)}>
            <option value="alphabetical">Alphabetical</option>
            <option value="return">Return</option>
            <option value="volatility">Volatility</option>
            <option value="sharpe">Sharpe</option>
            <option value="beta">Beta</option>
          </select>
        </div>
      </div>

      <Plot
        data={[heatmapTrace]}
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
  );
}
