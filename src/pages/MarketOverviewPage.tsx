import { useEffect, useMemo, useState, type Dispatch } from "react";
import { ResponsiveContainer, Treemap } from "recharts";
import DataWarningBanner from "../components/DataWarningBanner";
import { getIndustryOverview } from "../api/client";
import IndustryMatrixHeatmap from "../components/IndustryMatrixHeatmap";
import { usePortfolioData } from "../state/DataProvider";
import type {
  IndustryAnalyticsInterval,
  IndustryAnalyticsSortBy,
  IndustryAnalyticsWindow,
  IndustryMetricRow,
  IndustryOverviewResponse,
} from "../types/api";
import type { NavAction } from "../state/nav";
import { formatPercent } from "../utils/format";

type Props = {
  dispatch: Dispatch<NavAction>;
};

type SortDirection = "asc" | "desc";
type MetricKey =
  | "industry"
  | "weight"
  | "window_return"
  | "volatility_annualized"
  | "sharpe"
  | "beta"
  | "skewness"
  | "kurtosis"
  | "var_95"
  | "cvar_95"
  | "sortino"
  | "upside_capture"
  | "downside_capture";

function asFinite(value: number | null | undefined): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function fmtNum(value: number | null | undefined, digits = 2): string {
  const safe = asFinite(value);
  return safe == null ? "N/A" : safe.toFixed(digits);
}

function metricKeyToApiSort(metric: MetricKey): IndustryAnalyticsSortBy {
  if (metric === "industry") return "alphabetical";
  if (metric === "volatility_annualized") return "vol";
  if (metric === "sharpe") return "sharpe";
  return "return";
}

export default function MarketOverviewPage({ dispatch }: Props) {
  const { state: dataState } = usePortfolioData();
  const [window, setWindow] = useState<IndustryAnalyticsWindow>("1Y");
  const [interval, setInterval] = useState<IndustryAnalyticsInterval>("weekly");
  const [benchmark, setBenchmark] = useState("SPY");
  const [sortBy, setSortBy] = useState<MetricKey>("weight");
  const [sortDir, setSortDir] = useState<SortDirection>("desc");
  const [showAdvanced, setShowAdvanced] = useState(true);
  const [payload, setPayload] = useState<IndustryOverviewResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const portfolioId = dataState.activePortfolioId;
    if (portfolioId == null) {
      setPayload(null);
      return;
    }

    setLoading(true);
    setError(null);
    getIndustryOverview(portfolioId, {
      window,
      interval,
      benchmark,
      sortBy: metricKeyToApiSort(sortBy),
      sortOrder: sortDir,
    })
      .then((response) => {
        if (!cancelled) {
          setPayload(response);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setPayload(null);
          setError((err as Error).message || "Failed to load industry analytics");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [benchmark, dataState.activePortfolioId, interval, sortBy, sortDir, window]);

  const rows = useMemo(() => {
    const base = payload?.rows ?? [];
    return sortIndustryRows(base, sortBy, sortDir);
  }, [payload?.rows, sortBy, sortDir]);

  const warnings = useMemo(
    () => [
      ...dataState.dataWarnings,
      ...(error ? [error] : []),
      ...(payload == null ? [] : [`Showing ${rows.length} industries from current portfolio holdings universe.`]),
    ],
    [dataState.dataWarnings, error, payload, rows.length]
  );

  const totalWeight = rows.reduce((acc, row) => acc + (asFinite(row.weight) ?? 0), 0);

  const matrixRows = useMemo(
    () =>
      rows.map((row) => ({
        industry: row.industry,
        ret: asFinite(row.window_return) ?? 0,
        vol: asFinite(row.volatility_annualized) ?? 0,
        sharpe: asFinite(row.sharpe) ?? 0,
        beta: asFinite(row.beta) ?? 0,
      })),
    [rows]
  );

  const onSort = (next: MetricKey) => {
    const nextState = getNextSortState(sortBy, sortDir, next);
    setSortBy(nextState.sortBy);
    setSortDir(nextState.sortDir);
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
              {(["1M", "3M", "6M", "1Y", "5Y"] as IndustryAnalyticsWindow[]).map((item) => (
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
            <select value={interval} onChange={(event) => setInterval(event.target.value as IndustryAnalyticsInterval)}>
              <option value="daily">Daily</option>
              <option value="weekly">Weekly</option>
              <option value="monthly">Monthly</option>
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
            <label>Columns</label>
            <button className="btn-secondary" onClick={() => setShowAdvanced((prev) => !prev)}>
              {showAdvanced ? "Hide advanced" : "Show advanced"}
            </button>
          </div>
        </div>
      </section>

      <section className="overview-main-shell market-main-shell">
        <div className="overview-widget-shell market-table-shell">
          <div className="overview-lens-header">
            <h3 className="overview-lens-panel-title">Industry Metrics</h3>
            <span className="overview-lens-badge">Total Weight {formatPercent(totalWeight * 100, 1)}</span>
          </div>
          <table className="table market-table">
            <thead>
              <tr>
                <th><button className="market-sort-btn" onClick={() => onSort("industry")}>Industry</button></th>
                <th className="right"><button className="market-sort-btn" onClick={() => onSort("weight")}>Weight</button></th>
                <th className="right"><button className="market-sort-btn" onClick={() => onSort("window_return")}>Return</button></th>
                <th className="right"><button className="market-sort-btn" onClick={() => onSort("volatility_annualized")}>Volatility</button></th>
                <th className="right"><button className="market-sort-btn" onClick={() => onSort("sharpe")}>Sharpe</button></th>
                <th className="right"><button className="market-sort-btn" onClick={() => onSort("beta")}>Beta</button></th>
                {showAdvanced ? (
                  <>
                    <th className="right"><button className="market-sort-btn" onClick={() => onSort("sortino")}>Sortino</button></th>
                    <th className="right"><button className="market-sort-btn" onClick={() => onSort("skewness")}>Skew</button></th>
                    <th className="right"><button className="market-sort-btn" onClick={() => onSort("kurtosis")}>Kurt</button></th>
                    <th className="right"><button className="market-sort-btn" onClick={() => onSort("var_95")}>VaR 95%</button></th>
                    <th className="right"><button className="market-sort-btn" onClick={() => onSort("cvar_95")}>ES 95%</button></th>
                    <th className="right"><button className="market-sort-btn" onClick={() => onSort("upside_capture")}>Upside Cap</button></th>
                    <th className="right"><button className="market-sort-btn" onClick={() => onSort("downside_capture")}>Downside Cap</button></th>
                  </>
                ) : null}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.industry}>
                  <td>{row.industry}</td>
                  <td className="right">{formatPercent(row.weight * 100, 1)}</td>
                  <td className={`right ${(row.window_return ?? 0) >= 0 ? "positive" : "negative"}`}>
                    {row.window_return == null ? "N/A" : formatPercent(row.window_return * 100, 1)}
                  </td>
                  <td className="right">{row.volatility_annualized == null ? "N/A" : formatPercent(row.volatility_annualized * 100, 1)}</td>
                  <td className="right">{fmtNum(row.sharpe)}</td>
                  <td className="right">{fmtNum(row.beta)}</td>
                  {showAdvanced ? (
                    <>
                      <td className="right">{fmtNum(row.sortino)}</td>
                      <td className="right">{fmtNum(row.skewness)}</td>
                      <td className="right">{fmtNum(row.kurtosis)}</td>
                      <td className="right">{row.var_95 == null ? "N/A" : formatPercent(row.var_95 * 100, 1)}</td>
                      <td className="right">{row.cvar_95 == null ? "N/A" : formatPercent(row.cvar_95 * 100, 1)}</td>
                      <td className="right">{fmtNum(row.upside_capture)}</td>
                      <td className="right">{fmtNum(row.downside_capture)}</td>
                    </>
                  ) : null}
                </tr>
              ))}
              {!loading && rows.length === 0 ? (
                <tr>
                  <td colSpan={showAdvanced ? 13 : 6}>No industry analytics rows available for this portfolio/window.</td>
                </tr>
              ) : null}
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
                data={rows.map((row) => ({ name: row.industry, size: row.weight, ret: row.window_return ?? 0 }))}
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
        <IndustryMatrixHeatmap
          rows={matrixRows}
          covarianceMatrix={payload?.covariance_matrix.values ?? []}
          correlationMatrix={payload?.correlation_matrix.values ?? []}
        />
      </section>

      <div className="overview-extended-note">
        Industry matrix is derived from live portfolio holdings industry exposures for the selected interval/window.
      </div>
    </div>
  );
}

export function sortIndustryRows(rows: IndustryMetricRow[], sortBy: MetricKey, sortDir: SortDirection): IndustryMetricRow[] {
  return [...rows].sort((a, b) => {
    const pickMetric = (row: IndustryMetricRow): string | number => {
      if (sortBy === "industry") return row.industry;
      const value = row[sortBy];
      return typeof value === "number" ? value : Number.NEGATIVE_INFINITY;
    };
    const left = pickMetric(a);
    const right = pickMetric(b);
    if (typeof left === "string" && typeof right === "string") {
      return sortDir === "asc" ? left.localeCompare(right) : right.localeCompare(left);
    }
    return sortDir === "asc" ? Number(left) - Number(right) : Number(right) - Number(left);
  });
}

export function getNextSortState(currentBy: MetricKey, currentDir: SortDirection, nextBy: MetricKey) {
  if (currentBy === nextBy) {
    return { sortBy: currentBy, sortDir: (currentDir === "asc" ? "desc" : "asc") as SortDirection };
  }
  return { sortBy: nextBy, sortDir: (nextBy === "industry" ? "asc" : "desc") as SortDirection };
}
