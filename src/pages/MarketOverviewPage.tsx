import { useEffect, useMemo, useState, type Dispatch } from "react";
import { ResponsiveContainer, Treemap } from "recharts";
import DataWarningBanner from "../components/DataWarningBanner";
import { getIndustryOverview, getMacroForecasts, getSectorOverview } from "../api/client";
import IndustryMatrixHeatmap from "../components/IndustryMatrixHeatmap";
import { usePortfolioData } from "../state/DataProvider";
import type {
  IndustryAnalyticsDateMode,
  IndustryAnalyticsInterval,
  IndustryAnalyticsSortBy,
  IndustryAnalyticsWindow,
  IndustryMetricRow,
  IndustryOverviewResponse,
  MacroForecastResponse,
} from "../types/api";
import type { NavAction } from "../state/nav";
import { formatPercent } from "../utils/format";

type Props = {
  dispatch: Dispatch<NavAction>;
};

type SortDirection = "asc" | "desc";
type MarketSection = "macro" | "industry" | "sector";
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
  | "upside_capture"
  | "tracking_error"
  | "information_ratio";

type ColumnPreset = "core" | "risk" | "relative" | "all";
type MarketColumn = {
  key: MetricKey;
  label: string;
  align?: "left" | "right";
  formatter?: (row: IndustryMetricRow) => string;
};

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

const PRESET_LABELS: Record<ColumnPreset, string> = {
  core: "Core",
  risk: "Risk",
  relative: "Relative",
  all: "All",
};

const COLUMN_PRESETS: ColumnPreset[] = ["core", "risk", "relative", "all"];

const CORE_COLUMNS: MarketColumn[] = [
  { key: "industry", label: "Industry" },
  { key: "weight", label: "Weight", align: "right", formatter: (row) => formatPercent(row.weight * 100, 1) },
  {
    key: "window_return",
    label: "Return",
    align: "right",
    formatter: (row) => (row.window_return == null ? "N/A" : formatPercent(row.window_return * 100, 1)),
  },
  {
    key: "volatility_annualized",
    label: "Volatility",
    align: "right",
    formatter: (row) => (row.volatility_annualized == null ? "N/A" : formatPercent(row.volatility_annualized * 100, 1)),
  },
  { key: "sharpe", label: "Sharpe", align: "right", formatter: (row) => fmtNum(row.sharpe) },
  { key: "beta", label: "Beta", align: "right", formatter: (row) => fmtNum(row.beta) },
];

const RISK_COLUMNS: MarketColumn[] = [
  { key: "skewness", label: "Skew", align: "right", formatter: (row) => fmtNum(row.skewness) },
  { key: "kurtosis", label: "Kurt", align: "right", formatter: (row) => fmtNum(row.kurtosis) },
  {
    key: "var_95",
    label: "VaR 95%",
    align: "right",
    formatter: (row) => (row.var_95 == null ? "N/A" : formatPercent(row.var_95 * 100, 1)),
  },
  {
    key: "cvar_95",
    label: "ES 95%",
    align: "right",
    formatter: (row) => (row.cvar_95 == null ? "N/A" : formatPercent(row.cvar_95 * 100, 1)),
  },
];

const RELATIVE_COLUMNS: MarketColumn[] = [
  { key: "upside_capture", label: "Capture", align: "right", formatter: (row) => fmtNum(row.upside_capture) },
  { key: "tracking_error", label: "Tracking Err", align: "right", formatter: (row) => fmtNum(row.tracking_error) },
  { key: "information_ratio", label: "Info Ratio", align: "right", formatter: (row) => fmtNum(row.information_ratio) },
];

export function getVisibleMarketColumns(preset: ColumnPreset): MarketColumn[] {
  if (preset === "core") return CORE_COLUMNS;
  if (preset === "risk") return [...CORE_COLUMNS, ...RISK_COLUMNS];
  if (preset === "relative") return [...CORE_COLUMNS, ...RELATIVE_COLUMNS];
  return [...CORE_COLUMNS, ...RISK_COLUMNS, ...RELATIVE_COLUMNS];
}

export default function MarketOverviewPage({ dispatch }: Props) {
  const { state: dataState } = usePortfolioData();
  const [section, setSection] = useState<MarketSection>("industry");
  const [window, setWindow] = useState<IndustryAnalyticsWindow>("1Y");
  const [dateMode, setDateMode] = useState<IndustryAnalyticsDateMode>("preset");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [interval, setInterval] = useState<IndustryAnalyticsInterval>("weekly");
  const [benchmark, setBenchmark] = useState("SPY");
  const [sortBy, setSortBy] = useState<MetricKey>("weight");
  const [sortDir, setSortDir] = useState<SortDirection>("desc");
  const [columnPreset, setColumnPreset] = useState<ColumnPreset>("all");
  const [payload, setPayload] = useState<IndustryOverviewResponse | null>(null);
  const [macroPayload, setMacroPayload] = useState<MacroForecastResponse | null>(null);
  const [activeMacroTable, setActiveMacroTable] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [macroLoading, setMacroLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [macroError, setMacroError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const portfolioId = dataState.activePortfolioId;
    if (portfolioId == null) {
      setPayload(null);
      return;
    }
    if (dateMode === "custom" && (!startDate || !endDate)) {
      setLoading(false);
      setPayload(null);
      setError("Custom mode requires both a start and end date.");
      return;
    }

    setLoading(true);
    setError(null);
    if (section === "macro") {
      setLoading(false);
      return;
    }

    const load = section === "sector" ? getSectorOverview : getIndustryOverview;
    load(portfolioId, {
      window,
      dateMode,
      startDate: dateMode === "custom" ? startDate : undefined,
      endDate: dateMode === "custom" ? endDate : undefined,
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
          setError((err as Error).message || `Failed to load ${section} analytics`);
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
  }, [benchmark, dataState.activePortfolioId, dateMode, endDate, interval, section, sortBy, sortDir, startDate, window]);

  useEffect(() => {
    if (section !== "macro") return;
    const portfolioId = dataState.activePortfolioId;
    if (portfolioId == null) {
      setMacroPayload(null);
      return;
    }

    let cancelled = false;
    setMacroLoading(true);
    setMacroError(null);
    getMacroForecasts(portfolioId)
      .then((response) => {
        if (!cancelled) {
          setMacroPayload(response);
          if (!activeMacroTable && response.tables.length > 0) {
            setActiveMacroTable(response.tables[0].key);
          }
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setMacroPayload(null);
          setMacroError((err as Error).message || "Failed to load macro forecasts");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setMacroLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [activeMacroTable, dataState.activePortfolioId, section]);

  const rows = useMemo(() => {
    const base = payload?.rows ?? [];
    return sortIndustryRows(base, sortBy, sortDir);
  }, [payload?.rows, sortBy, sortDir]);

  const warnings = useMemo(
    () => [
      ...dataState.dataWarnings,
      ...(error ? [error] : []),
      ...(payload == null ? [] : [`Showing ${rows.length} ${section === "sector" ? "sectors" : "industries"} from current market universe.`]),
    ],
    [dataState.dataWarnings, error, payload, rows.length, section]
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

  const visibleColumns = useMemo(() => getVisibleMarketColumns(columnPreset), [columnPreset]);
  const isCoreOnly = columnPreset === "core";
  const selectedPresetLabel = PRESET_LABELS[columnPreset];
  const selectedMacroTable = useMemo(
    () => macroPayload?.tables.find((table) => table.key === activeMacroTable) ?? macroPayload?.tables[0] ?? null,
    [activeMacroTable, macroPayload?.tables]
  );

  return (
    <div className="overview-prototype-wrap market-overview-wrap">
      <div className="overview-page-title">
        <div>
          <h1>Market Overview</h1>
          <p>
            {section === "industry"
              ? "Industry-relative performance, cross-industry risk linkage, and concentration stress in one place."
              : section === "sector"
                ? "Sector-relative performance, cross-sector risk linkage, and concentration stress in one place."
              : "TradingEconomics macro forecasts grouped by table."}
          </p>
        </div>
        <button className="btn-secondary" onClick={() => dispatch({ type: "go_page", page: "overview" })}>
          Back to Portfolio Overview
        </button>
      </div>

      <section className="overview-intel-shell market-section-shell">
        <div className="market-subsection-tabs" role="tablist" aria-label="Market subsections">
          <button
            className={`market-subsection-tab ${section === "macro" ? "active" : ""}`}
            onClick={() => setSection("macro")}
            role="tab"
            aria-selected={section === "macro"}
          >
            Macro
          </button>
          <button
            className={`market-subsection-tab ${section === "sector" ? "active" : ""}`}
            onClick={() => setSection("sector")}
            role="tab"
            aria-selected={section === "sector"}
          >
            Sector
          </button>
          <button
            className={`market-subsection-tab ${section === "industry" ? "active" : ""}`}
            onClick={() => setSection("industry")}
            role="tab"
            aria-selected={section === "industry"}
          >
            Industry
          </button>
        </div>
      </section>

      {section === "industry" || section === "sector" ? (
        <DataWarningBanner warnings={warnings} title={`${section === "sector" ? "Sector" : "Industry"} Read Warnings`} />
      ) : null}
      {section === "macro" && (macroError || (macroPayload?.warnings ?? []).length > 0) ? (
        <DataWarningBanner
          warnings={[...(macroError ? [macroError] : []), ...(macroPayload?.warnings ?? [])]}
          title="Macro Read Warnings"
        />
      ) : null}

      {section === "industry" || section === "sector" ? (
        <>
          <section className="overview-intel-shell market-controls-shell">
            <div className="market-controls-row">
              <div className="market-control-group">
                <label>Window</label>
                <div className="market-pill-row">
                  {(["1D", "1W", "1M", "3M", "1Y", "3Y", "5Y", "10Y"] as IndustryAnalyticsWindow[]).map((item) => (
                    <button
                      key={item}
                      className={`overview-period-btn ${window === item ? "active" : ""}`}
                      onClick={() => {
                        setWindow(item);
                        setDateMode("preset");
                      }}
                    >
                      {item}
                    </button>
                  ))}
                </div>
                <div style={{ marginTop: 10 }}>
                  <button
                    className={`overview-period-btn ${dateMode === "custom" ? "active" : ""}`}
                    onClick={() => setDateMode("custom")}
                  >
                    Custom
                  </button>
                </div>
                {dateMode === "custom" ? (
                  <div className="market-pill-row" style={{ marginTop: 8 }}>
                    <input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} />
                    <input type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} />
                  </div>
                ) : null}
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
                <div className="market-pill-row">
                  {COLUMN_PRESETS.map((preset) => (
                    <button
                      key={preset}
                      className={`overview-period-btn ${columnPreset === preset ? "active" : ""}`}
                      onClick={() => setColumnPreset(preset)}
                    >
                      {PRESET_LABELS[preset]}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </section>

          <section className="overview-main-shell market-main-shell">
            <div className="overview-widget-shell market-table-shell">
              <div className="overview-lens-header">
                <h3 className="overview-lens-panel-title">{section === "sector" ? "Sector" : "Industry"} Metrics</h3>
                <span className="overview-lens-badge">Total Weight {formatPercent(totalWeight * 100, 1)}</span>
                <span className="overview-lens-badge">Columns: {selectedPresetLabel} ({visibleColumns.length})</span>
              </div>
              <div className="market-table-scroll">
                <table className="table market-table">
                  <thead>
                    <tr>
                      {visibleColumns.map((column) => (
                        <th key={column.key} className={column.align === "right" ? "right" : undefined}>
                          <button className="market-sort-btn" onClick={() => onSort(column.key)}>
                            {section === "sector" && column.key === "industry" ? "Sector" : column.label}
                          </button>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row) => (
                      <tr key={row.industry}>
                        {visibleColumns.map((column) => (
                          <td
                            key={`${row.industry}-${column.key}`}
                            className={
                              column.key === "window_return"
                                ? `right ${(row.window_return ?? 0) >= 0 ? "positive" : "negative"}`
                                : column.align === "right"
                                  ? "right"
                                  : undefined
                            }
                          >
                            {column.formatter ? column.formatter(row) : row.industry}
                          </td>
                        ))}
                      </tr>
                    ))}
                    {!loading && rows.length === 0 ? (
                      <tr>
                        <td colSpan={visibleColumns.length}>
                          No {section === "sector" ? "sector" : "industry"} analytics rows available for this portfolio/window.
                        </td>
                      </tr>
                    ) : null}
                  </tbody>
                </table>
              </div>
              {isCoreOnly ? (
                <p className="market-core-note">
                  Core view is enabled. Switch to Risk, Relative, or All to reveal tail risk and benchmark-relative columns.
                </p>
              ) : null}
            </div>

            <div className="overview-widget-shell market-treemap-shell">
              <div className="overview-lens-header">
                <h3 className="overview-lens-panel-title">{section === "sector" ? "Sector" : "Industry"} Weight Map</h3>
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
            {section === "sector"
              ? "Sector matrix is derived from Yahoo Finance sector index history for the selected interval/window."
              : "Industry matrix is derived from live portfolio holdings industry exposures for the selected interval/window."}
          </div>
        </>
      ) : (
        <section className="overview-main-shell market-main-shell">
          <div className="overview-widget-shell market-table-shell">
            <div className="overview-lens-header">
              <h3 className="overview-lens-panel-title">TradingEconomics Forecast Tables</h3>
            </div>
            <div className="market-pill-row" style={{ marginBottom: 12 }}>
              {(macroPayload?.tables ?? []).map((table) => (
                <button
                  key={table.key}
                  className={`overview-period-btn ${selectedMacroTable?.key === table.key ? "active" : ""}`}
                  onClick={() => setActiveMacroTable(table.key)}
                >
                  {table.key.replaceAll("_", " ")}
                </button>
              ))}
            </div>
            {selectedMacroTable ? (
              <div className="market-table-scroll">
                <table className="table market-table">
                  <thead>
                    <tr>
                      {selectedMacroTable.columns.map((column) => (
                        <th key={`${selectedMacroTable.key}-${column}`}>{column}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {selectedMacroTable.rows.map((row, index) => (
                      <tr key={`${selectedMacroTable.key}-${index}`}>
                        {selectedMacroTable.columns.map((column) => (
                          <td key={`${selectedMacroTable.key}-${index}-${column}`}>{row[column] || "—"}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div style={{ color: "var(--muted)" }}>
                {macroLoading ? "Loading TradingEconomics tables..." : "No macro forecast tables available."}
              </div>
            )}
          </div>
        </section>
      )}
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
