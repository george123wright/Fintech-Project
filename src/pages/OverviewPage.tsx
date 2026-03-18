import { useEffect, useMemo, useState, type Dispatch } from "react";
import Plot from "react-plotly.js";
import {
  Bar,
  BarChart,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { buildDonutChart, buildFrontierChart } from "../charts/builders";
import DataWarningBanner from "../components/DataWarningBanner";
import PortfolioExposureSummary from "../components/PortfolioExposureSummary";
import PortfolioNarrativePanel from "../components/PortfolioNarrativePanel";
import ValuationCompass from "../components/ValuationCompass";
import type { NavAction } from "../state/nav";
import { usePortfolioData } from "../state/DataProvider";
import type { ManualHoldingInput, NewsArticle } from "../types/api";
import { formatPercent, formatPrice } from "../utils/format";

type Props = {
  dispatch: Dispatch<NavAction>;
};

type ManualRow = {
  id: string;
  ticker: string;
  units: string;
  marketValue: string;
  currency: string;
  name: string;
  assetType: string;
  costBasis: string;
};

const COLORS = [
  "#7b6ef6",
  "#5b8ef0",
  "#3dd68c",
  "#f0b959",
  "#f05b5b",
  "#e8a838",
  "#4cb7c5",
  "#9ea7ff",
];

const manualCellStyle = {
  background: "var(--bg)",
  color: "var(--text)",
  border: "1px solid var(--border)",
  borderRadius: 4,
  padding: "6px 8px",
  fontFamily: "var(--mono)",
  fontSize: 12,
};

function MetricCard({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color?: string;
}) {
  return (
    <div className="metric-card">
      <div className="label">{label}</div>
      <div className="value" style={{ color: color ?? "var(--text)" }}>
        {value}
      </div>
    </div>
  );
}

function RiskCard({
  label,
  value,
  sub,
  color,
}: {
  label: string;
  value: string;
  sub: string;
  color: string;
}) {
  return (
    <div className="risk-card">
      <div className="label">{label}</div>
      <div className="value" style={{ color }}>
        {value}
      </div>
      <div className="sub">{sub}</div>
    </div>
  );
}

function normalizeAllocation(allocation: Record<string, number>) {
  const entries = Object.entries(allocation);
  const sum = entries.reduce((acc, [, value]) => acc + value, 0);
  if (sum <= 0) return allocation;

  const appearsDecimal = sum <= 1.25;
  if (!appearsDecimal) return allocation;

  const out: Record<string, number> = {};
  for (const [key, value] of entries) {
    out[key] = value * 100;
  }
  return out;
}

function makeManualRow(): ManualRow {
  return {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    ticker: "",
    units: "",
    marketValue: "",
    currency: "USD",
    name: "",
    assetType: "",
    costBasis: "",
  };
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (value != null && typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return null;
}

function asNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  return null;
}

function fmtPercentOrNA(value: unknown): string {
  const num = asNumber(value);
  if (num == null) return "N/A";
  return formatPercent(num * 100);
}

function fmtNumberOrNA(value: unknown, digits = 2): string {
  const num = asNumber(value);
  if (num == null) return "N/A";
  return num.toFixed(digits);
}

function formatNewsDate(value: string | null): string {
  if (!value) return "N/A";
  const parsed = new Date(value);
  if (!Number.isFinite(parsed.getTime())) return value;
  return parsed.toLocaleString();
}

export default function OverviewPage({ dispatch }: Props) {
  const {
    state: dataState,
    uploadHoldingsFile,
    submitManualEntries,
    runManualRefresh,
    recomputeValuations,
    reloadActivePortfolio,
    fetchPortfolioNewsForActive,
  } = usePortfolioData();

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [manualRows, setManualRows] = useState<ManualRow[]>([makeManualRow()]);
  const [manualError, setManualError] = useState<string | null>(null);
  const [portfolioNewsStatus, setPortfolioNewsStatus] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [portfolioNewsError, setPortfolioNewsError] = useState<string | null>(null);
  const [portfolioNewsWarnings, setPortfolioNewsWarnings] = useState<string[]>([]);
  const [portfolioNews, setPortfolioNews] = useState<NewsArticle[]>([]);

  const holdings = dataState.holdings;
  const metrics = dataState.risk?.metrics ?? dataState.overview?.metrics;
  const allocation = normalizeAllocation(dataState.overview?.allocation ?? {});
  const valuationOverview = dataState.valuationOverview ?? dataState.overview?.valuation_summary;
  const latestScenario = dataState.overview?.latest_scenario_run ?? dataState.scenarioRuns[0] ?? null;
  const exposureSummary = dataState.overview?.exposure_summary ?? null;
  const portfolioNarrative = dataState.overview?.narrative ?? null;
  const extendedRoot = asRecord(dataState.extendedMetrics?.metrics);
  const extendedPortfolio = asRecord(extendedRoot?.portfolio);
  const extendedReturns = asRecord(extendedPortfolio?.returns);
  const extendedVar = asRecord(extendedPortfolio?.var);
  const extendedCapture = asRecord(extendedPortfolio?.capture);
  const extendedNotes = asRecord(extendedRoot?.notes);
  const uploadSummary = useMemo(() => {
    if (dataState.status === "loading") return "Loading...";
    if (dataState.error) return dataState.error;
    if (dataState.lastUpload) {
      return `${dataState.lastUpload.accepted_rows} accepted / ${dataState.lastUpload.rejected_rows} rejected`;
    }
    return "Upload CSV/XLSX with ticker + units or market_value";
  }, [dataState.error, dataState.lastUpload, dataState.status]);

  const uploadReasonLines = useMemo(() => {
    const report = dataState.lastUpload;
    if (!report) return [];
    const lines: string[] = [];
    if (Array.isArray(report.errors)) {
      lines.push(...report.errors);
    }
    if (report.missing_fields.length > 0) {
      lines.push(`Missing fields: ${report.missing_fields.join(", ")}.`);
    }
    if (report.unknown_tickers.length > 0) {
      const preview = report.unknown_tickers.slice(0, 8).join(", ");
      const suffix = report.unknown_tickers.length > 8 ? "..." : "";
      lines.push(`Unknown/unpriced tickers: ${preview}${suffix}.`);
    }
    return Array.from(new Set(lines.filter((line) => line.trim().length > 0)));
  }, [dataState.lastUpload]);

  const frontier = useMemo(
    () =>
      buildFrontierChart(
        holdings.map((holding, idx) => ({
          sym: holding.symbol,
          weight: holding.weight * 100,
          color: COLORS[idx % COLORS.length],
        })),
        metrics?.ann_vol,
        metrics?.ann_return
      ),
    [holdings, metrics?.ann_return, metrics?.ann_vol]
  );

  const donut = useMemo(
    () => buildDonutChart(allocation, formatPrice(metrics?.portfolio_value ?? 0)),
    [allocation, metrics?.portfolio_value]
  );

  const riskSnapshot = [
    {
      label: "VaR 1d 95%",
      value: metrics ? metrics.var_95 * 100 : 0,
      sub: "Historical portfolio VaR",
      color: "var(--red)",
    },
    {
      label: "CVaR / ES",
      value: metrics ? metrics.cvar_95 * 100 : 0,
      sub: "Average tail-day loss",
      color: "var(--red)",
    },
    {
      label: "Sharpe",
      value: metrics?.sharpe ?? 0,
      sub: "Risk-adjusted annual return",
      color: "var(--green)",
    },
    {
      label: "Max DD",
      value: metrics ? metrics.max_drawdown * 100 : 0,
      sub: "Peak-to-trough loss",
      color: "var(--yellow)",
    },
  ];

  const pnlValue = metrics?.ann_return ?? 0;

  const updateManualCell = (
    rowId: string,
    key: Exclude<keyof ManualRow, "id">,
    value: string
  ) => {
    setManualRows((prev) =>
      prev.map((row) => (row.id === rowId ? { ...row, [key]: value } : row))
    );
  };

  const addManualRow = () => {
    setManualRows((prev) => [...prev, makeManualRow()]);
  };

  const removeManualRow = (rowId: string) => {
    setManualRows((prev) => {
      const next = prev.filter((row) => row.id !== rowId);
      return next.length > 0 ? next : [makeManualRow()];
    });
  };

  const parseOptionalNumber = (value: string): number | undefined => {
    const trimmed = value.trim();
    if (!trimmed) return undefined;
    const parsed = Number(trimmed);
    return Number.isFinite(parsed) ? parsed : Number.NaN;
  };

  const buildManualEntries = (rows: ManualRow[]): ManualHoldingInput[] => {
    const activeRows = rows.filter((row) =>
      [row.ticker, row.units, row.marketValue, row.name, row.assetType, row.costBasis]
        .join("")
        .trim()
    );

    if (activeRows.length === 0) {
      throw new Error("Manual input table is empty.");
    }

    return activeRows.map((row, idx) => {
      const ticker = row.ticker.trim().toUpperCase();
      if (!ticker) {
        throw new Error(`Row ${idx + 1}: ticker is required.`);
      }

      const units = parseOptionalNumber(row.units);
      const marketValue = parseOptionalNumber(row.marketValue);
      const costBasis = parseOptionalNumber(row.costBasis);

      if (Number.isNaN(units) || Number.isNaN(marketValue) || Number.isNaN(costBasis)) {
        throw new Error(`Row ${idx + 1}: units, market value, and cost basis must be numeric.`);
      }

      if (units == null && marketValue == null) {
        throw new Error(`Row ${idx + 1}: provide units or market value.`);
      }

      return {
        ticker,
        units,
        market_value: marketValue,
        cost_basis: costBasis,
        currency: row.currency.trim().toUpperCase() || "USD",
        name: row.name.trim() || undefined,
        asset_type: row.assetType.trim() || undefined,
      };
    });
  };

  useEffect(() => {
    if (dataState.activePortfolioId == null) {
      setPortfolioNews([]);
      setPortfolioNewsWarnings([]);
      setPortfolioNewsError(null);
      setPortfolioNewsStatus("idle");
      return;
    }
    let isMounted = true;
    setPortfolioNewsStatus("loading");
    setPortfolioNewsError(null);

    void fetchPortfolioNewsForActive({ limit: 5, perSymbol: 20 })
      .then((response) => {
        if (!isMounted) return;
        setPortfolioNews(response.articles ?? []);
        setPortfolioNewsWarnings(response.warnings ?? []);
        setPortfolioNewsStatus("ready");
      })
      .catch((error: Error) => {
        if (!isMounted) return;
        setPortfolioNews([]);
        setPortfolioNewsWarnings([]);
        setPortfolioNewsError(error.message);
        setPortfolioNewsStatus("error");
      });

    return () => {
      isMounted = false;
    };
  }, [fetchPortfolioNewsForActive, dataState.activePortfolioId, dataState.overview?.snapshot_id]);

  return (
    <>
      <div className="banner">
        <div className="banner-dot" />
        <div>
          <strong style={{ color: "var(--accent)" }}>Portfolio Intelligence</strong>
          <span> - Live analytics from uploaded holdings and cached market data. </span>
          <button className="inline-link" onClick={() => void reloadActivePortfolio()}>
            Reload snapshot
          </button>
          <span> or run a </span>
          <button className="inline-link-yellow" onClick={() => void runManualRefresh()}>
            manual refresh
          </button>
          <span> to recalculate risk metrics.</span>
        </div>
      </div>
      <DataWarningBanner warnings={dataState.dataWarnings} />

      <div className="overview-layout">
        <div className="main-col">
          <div
            className="surface"
            style={{ marginBottom: 20, padding: 14, display: "flex", gap: 10, flexWrap: "wrap" }}
          >
            <input
              type="file"
              accept=".csv,.xlsx,.xls"
              onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
            />
            <button
              className="btn-primary"
              disabled={!selectedFile || dataState.activePortfolioId == null}
              onClick={() => {
                if (selectedFile) {
                  void uploadHoldingsFile(selectedFile);
                }
              }}
            >
              Upload Holdings
            </button>
            <button
              className="btn-secondary"
              disabled={dataState.activePortfolioId == null}
              onClick={() => void runManualRefresh()}
            >
              Refresh Metrics
            </button>
            <button
              className="btn-secondary"
              disabled={dataState.activePortfolioId == null}
              onClick={() => void recomputeValuations()}
            >
              Recompute Valuations
            </button>
            <div style={{ alignSelf: "center", display: "grid", gap: 4, maxWidth: 680 }}>
              <span style={{ color: "var(--muted)", fontSize: 11 }}>{uploadSummary}</span>
              {uploadReasonLines.length > 0 ? (
                <div style={{ color: "var(--yellow)", fontSize: 11, lineHeight: 1.5 }}>
                  {uploadReasonLines.slice(0, 4).map((line) => (
                    <div key={line}>- {line}</div>
                  ))}
                </div>
              ) : null}
            </div>
          </div>

          <div className="surface" style={{ marginBottom: 22, padding: 14 }}>
            <div className="kicker" style={{ marginBottom: 8 }}>
              Manual Holdings Input
            </div>
            <div style={{ overflowX: "auto", border: "1px solid var(--border)", borderRadius: 6 }}>
              <table className="table" style={{ margin: 0, minWidth: 900 }}>
                <thead>
                  <tr>
                    <th>Ticker*</th>
                    <th>Units</th>
                    <th>Market Value</th>
                    <th>Currency</th>
                    <th>Name</th>
                    <th>Asset Type</th>
                    <th>Cost Basis</th>
                    <th className="right">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {manualRows.map((row) => (
                    <tr key={row.id}>
                      <td>
                        <input
                          value={row.ticker}
                          onChange={(event) =>
                            updateManualCell(row.id, "ticker", event.target.value.toUpperCase())
                          }
                          placeholder="NVDA"
                          style={{ width: 90, ...manualCellStyle }}
                        />
                      </td>
                      <td>
                        <input
                          value={row.units}
                          onChange={(event) => updateManualCell(row.id, "units", event.target.value)}
                          placeholder="10"
                          style={{ width: 90, ...manualCellStyle }}
                        />
                      </td>
                      <td>
                        <input
                          value={row.marketValue}
                          onChange={(event) =>
                            updateManualCell(row.id, "marketValue", event.target.value)
                          }
                          placeholder="3500"
                          style={{ width: 110, ...manualCellStyle }}
                        />
                      </td>
                      <td>
                        <input
                          value={row.currency}
                          onChange={(event) =>
                            updateManualCell(row.id, "currency", event.target.value.toUpperCase())
                          }
                          placeholder="USD"
                          style={{ width: 80, ...manualCellStyle }}
                        />
                      </td>
                      <td>
                        <input
                          value={row.name}
                          onChange={(event) => updateManualCell(row.id, "name", event.target.value)}
                          placeholder="NVIDIA"
                          style={{ width: 150, ...manualCellStyle }}
                        />
                      </td>
                      <td>
                        <input
                          value={row.assetType}
                          onChange={(event) =>
                            updateManualCell(row.id, "assetType", event.target.value)
                          }
                          placeholder="Equity"
                          style={{ width: 110, ...manualCellStyle }}
                        />
                      </td>
                      <td>
                        <input
                          value={row.costBasis}
                          onChange={(event) =>
                            updateManualCell(row.id, "costBasis", event.target.value)
                          }
                          placeholder="3200"
                          style={{ width: 110, ...manualCellStyle }}
                        />
                      </td>
                      <td className="right">
                        <button className="btn-secondary" onClick={() => removeManualRow(row.id)}>
                          Remove
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div style={{ display: "flex", gap: 10, marginTop: 10, alignItems: "center" }}>
              <button className="btn-secondary" onClick={addManualRow}>
                Add Row
              </button>
              <button
                className="btn-secondary"
                disabled={dataState.activePortfolioId == null || dataState.status === "loading"}
                onClick={() => {
                  try {
                    const rows = buildManualEntries(manualRows);
                    setManualError(null);
                    void submitManualEntries(rows);
                  } catch (error) {
                    setManualError((error as Error).message);
                  }
                }}
              >
                Submit Manual Holdings
              </button>
              <button
                className="btn-secondary"
                onClick={() => {
                  setManualRows([makeManualRow()]);
                  setManualError(null);
                }}
              >
                Clear
              </button>
              <span style={{ color: manualError ? "var(--red)" : "var(--muted)", fontSize: 11 }}>
                {manualError ??
                  "Fill ticker + units or market value in each row, then submit."}
              </span>
            </div>
          </div>

          <div className="metrics-row">
            <div>
              <div className="value-big">{formatPrice(metrics?.portfolio_value ?? 0)}</div>
              <div
                className="value-sub"
                style={{ color: pnlValue >= 0 ? "var(--green)" : "var(--red)" }}
              >
                {formatPercent(pnlValue * 100)} annualized return
              </div>
            </div>
            <div className="metric-grid">
              <MetricCard
                label="Sharpe"
                value={(metrics?.sharpe ?? 0).toFixed(2)}
                color="var(--green)"
              />
              <MetricCard
                label="VaR 95%"
                value={formatPercent((metrics?.var_95 ?? 0) * 100)}
                color="var(--yellow)"
              />
              <MetricCard
                label="CVaR"
                value={formatPercent((metrics?.cvar_95 ?? 0) * 100)}
                color="var(--red)"
              />
              <MetricCard label="Beta" value={(metrics?.beta ?? 0).toFixed(2)} />
            </div>
          </div>

          <PortfolioNarrativePanel narrative={portfolioNarrative} />
          <PortfolioExposureSummary summary={exposureSummary} />

          <div className="kicker">Efficient Frontier - Portfolio Position</div>
          <div className="surface" style={{ marginBottom: 24 }}>
            <Plot
              data={frontier.data}
              layout={frontier.layout}
              config={{ displayModeBar: false, responsive: true }}
              style={{ width: "100%", height: 260 }}
              useResizeHandler
            />
          </div>

          <div className="kicker">Holdings</div>
          <table className="table">
            <thead>
              <tr>
                <th>Asset</th>
                <th className="right">Weight</th>
                <th className="right">Market Value</th>
                <th className="right">Units</th>
                <th className="right">Currency</th>
                <th className="right" />
              </tr>
            </thead>
            <tbody>
              {holdings.map((holding, idx) => (
                <tr
                  key={holding.symbol}
                  className="clickable"
                  onClick={() => dispatch({ type: "open_stock", sym: holding.symbol })}
                >
                  <td>
                    <div>
                      <span
                        className="ticker-color-dot"
                        style={{ backgroundColor: COLORS[idx % COLORS.length] }}
                      />
                      <span style={{ fontWeight: 600 }}>{holding.symbol}</span>
                    </div>
                    <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 2 }}>
                      {holding.name ?? "No name"}
                    </div>
                  </td>
                  <td className="right">{(holding.weight * 100).toFixed(1)}%</td>
                  <td className="right">{formatPrice(holding.market_value)}</td>
                  <td className="right">{holding.units?.toFixed(2) ?? "-"}</td>
                  <td className="right">{holding.currency}</td>
                  <td className="right" style={{ color: "var(--muted)" }}>
                    {"->"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <div className="kicker" style={{ marginTop: 24 }}>
            Portfolio News
          </div>
          <div className="surface" style={{ padding: 14, marginBottom: 20 }}>
            <div className="row-between" style={{ marginBottom: 10 }}>
              <div style={{ color: "var(--muted)", fontSize: 12 }}>
                Last 5 articles across all current holdings.
              </div>
              <button
                className="inline-link"
                onClick={() => dispatch({ type: "go_page", page: "portfolio_news" })}
              >
                See all articles
              </button>
            </div>

            <DataWarningBanner warnings={portfolioNewsWarnings} title="Portfolio News Warnings" />

            {portfolioNewsStatus === "loading" && (
              <div style={{ color: "var(--muted)", fontSize: 12 }}>Loading portfolio news...</div>
            )}
            {portfolioNewsStatus === "error" && (
              <div style={{ color: "var(--red)", fontSize: 12 }}>
                {portfolioNewsError ?? "Failed to load portfolio news."}
              </div>
            )}
            {portfolioNewsStatus !== "loading" && portfolioNewsStatus !== "error" && (
              <>
                {portfolioNews.length ? (
                  <div style={{ display: "grid", gap: 10 }}>
                    {portfolioNews.map((article) => (
                      <article key={article.id} className="surface-soft" style={{ padding: 10 }}>
                        <div className="row-between" style={{ alignItems: "flex-start", gap: 12 }}>
                          <div style={{ minWidth: 0, flex: 1 }}>
                            <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 6 }}>
                              {article.url ? (
                                <a
                                  href={article.url}
                                  target="_blank"
                                  rel="noreferrer"
                                  style={{ color: "var(--text)", textDecoration: "underline" }}
                                >
                                  {article.title}
                                </a>
                              ) : (
                                article.title
                              )}
                            </div>
                            <div style={{ color: "var(--muted)", fontSize: 11, marginBottom: 6 }}>
                              {article.provider ?? "Unknown source"} | {formatNewsDate(article.pub_date)}
                            </div>
                            <div style={{ fontSize: 12, lineHeight: 1.6, marginBottom: 8 }}>
                              {article.summary ?? "No summary available."}
                            </div>
                            {(article.symbols ?? []).length > 0 && (
                              <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                                {article.symbols.map((symbol) => (
                                  <span
                                    key={`${article.id}-${symbol}`}
                                    style={{
                                      border: "1px solid var(--border)",
                                      borderRadius: 999,
                                      padding: "2px 8px",
                                      fontSize: 10,
                                      color: "var(--muted)",
                                    }}
                                  >
                                    {symbol}
                                  </span>
                                ))}
                              </div>
                            )}
                          </div>
                          {article.thumbnail_url ? (
                            <img
                              src={article.thumbnail_url}
                              alt={article.title}
                              style={{
                                width: 120,
                                height: 80,
                                objectFit: "cover",
                                borderRadius: 8,
                                border: "1px solid var(--border)",
                                flexShrink: 0,
                              }}
                            />
                          ) : null}
                        </div>
                      </article>
                    ))}
                  </div>
                ) : (
                  <div style={{ color: "var(--muted)", fontSize: 12 }}>
                    No portfolio news articles available yet.
                  </div>
                )}
              </>
            )}
          </div>

          <div className="kicker" style={{ marginTop: 24 }}>
            Extended Historical Metrics
          </div>
          <div className="surface" style={{ padding: 14, marginBottom: 20 }}>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(4, minmax(120px, 1fr))",
                gap: 10,
                marginBottom: 14,
              }}
            >
              <MetricCard
                label="Adjusted Sharpe"
                value={fmtNumberOrNA(extendedPortfolio?.adjusted_sharpe)}
                color="var(--green)"
              />
              <MetricCard
                label="Info Ratio"
                value={fmtNumberOrNA(extendedPortfolio?.information_ratio)}
                color="var(--accent)"
              />
              <MetricCard
                label="Calmar"
                value={fmtNumberOrNA(extendedPortfolio?.calmar)}
                color="var(--yellow)"
              />
              <MetricCard
                label="Omega"
                value={fmtNumberOrNA(extendedPortfolio?.omega)}
                color="var(--green)"
              />
              <MetricCard
                label="M2"
                value={fmtPercentOrNA(extendedPortfolio?.m2)}
                color="var(--accent)"
              />
              <MetricCard
                label="RAROC"
                value={fmtNumberOrNA(extendedPortfolio?.raroc)}
                color="var(--yellow)"
              />
              <MetricCard
                label="Skewness"
                value={fmtNumberOrNA(extendedPortfolio?.skewness)}
              />
              <MetricCard
                label="Kurtosis"
                value={fmtNumberOrNA(extendedPortfolio?.kurtosis)}
              />
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
              <div className="surface-soft" style={{ padding: 10 }}>
                <div className="kicker" style={{ marginBottom: 8 }}>
                  Return Ladder
                </div>
                <div style={{ fontSize: 12, lineHeight: 1.8 }}>
                  1D {fmtPercentOrNA(extendedReturns?.["1d"])} | 1W{" "}
                  {fmtPercentOrNA(extendedReturns?.["1w"])} | 1M{" "}
                  {fmtPercentOrNA(extendedReturns?.["1m"])} | 3M{" "}
                  {fmtPercentOrNA(extendedReturns?.["3m"])}
                </div>
                <div style={{ fontSize: 12, lineHeight: 1.8 }}>
                  6M {fmtPercentOrNA(extendedReturns?.["6m"])} | YTD{" "}
                  {fmtPercentOrNA(extendedReturns?.["ytd"])} | 1Y{" "}
                  {fmtPercentOrNA(extendedReturns?.["1y"])} | 3Y{" "}
                  {fmtPercentOrNA(extendedReturns?.["3y"])} | 5Y{" "}
                  {fmtPercentOrNA(extendedReturns?.["5y"])}
                </div>
              </div>

              <div className="surface-soft" style={{ padding: 10 }}>
                <div className="kicker" style={{ marginBottom: 8 }}>
                  Multi-Type VaR + Capture
                </div>
                <div style={{ fontSize: 12, lineHeight: 1.8 }}>
                  Hist VaR95 {fmtPercentOrNA(extendedVar?.historical_95)} | Hist VaR99{" "}
                  {fmtPercentOrNA(extendedVar?.historical_99)}
                </div>
                <div style={{ fontSize: 12, lineHeight: 1.8 }}>
                  Gauss VaR95 {fmtPercentOrNA(extendedVar?.gaussian_95)} | CF VaR95{" "}
                  {fmtPercentOrNA(extendedVar?.cornish_fisher_95)}
                </div>
                <div style={{ fontSize: 12, lineHeight: 1.8 }}>
                  Upside Capture {fmtNumberOrNA(extendedCapture?.upside_capture_ratio)} | Downside
                  Capture {fmtNumberOrNA(extendedCapture?.downside_capture_ratio)}
                </div>
              </div>
            </div>
            <div style={{ color: "var(--muted)", fontSize: 11, marginTop: 10 }}>
              {String(
                extendedNotes?.factor_method ??
                  "Factor and macro exposures are computed via proxy regressions."
              )}
            </div>
          </div>
        </div>

        <aside className="side-col">
          <div className="kicker">Allocation Breakdown</div>
          <Plot
            data={donut.data}
            layout={donut.layout}
            config={{ displayModeBar: false, responsive: true }}
            style={{ width: "100%", height: 220 }}
            useResizeHandler
          />

          <div style={{ marginBottom: 24 }}>
            {Object.entries(allocation).map(([label, pct], idx) => (
              <div className="allocation-row" key={label}>
                <span>
                  <span
                    className="alloc-color-dot"
                    style={{ backgroundColor: COLORS[idx % COLORS.length] }}
                  />
                  <span style={{ color: "var(--muted)" }}>{label}</span>
                </span>
                <strong>{pct.toFixed(1)}%</strong>
              </div>
            ))}
          </div>

          <hr style={{ borderColor: "var(--border)", margin: "4px 0 20px" }} />

          <div className="kicker">Risk Snapshot</div>
          <div className="risk-grid" style={{ marginBottom: 16 }}>
            {riskSnapshot.map((item) => (
              <RiskCard
                key={item.label}
                label={item.label}
                value={
                  item.label === "Sharpe"
                    ? item.value.toFixed(2)
                    : `${item.value >= 0 ? "+" : ""}${item.value.toFixed(2)}%`
                }
                sub={item.sub}
                color={item.color}
              />
            ))}
          </div>

          <div className="surface-soft" style={{ padding: 12, marginBottom: 24 }}>
            <div className="kicker" style={{ marginBottom: 6 }}>
              Risk Regime Intensity
            </div>
            <ResponsiveContainer width="100%" height={170}>
              <BarChart
                data={riskSnapshot}
                layout="vertical"
                margin={{ left: 10, right: 10, top: 8, bottom: 8 }}
              >
                <XAxis type="number" hide domain={[0, 15]} />
                <YAxis
                  dataKey="label"
                  type="category"
                  width={80}
                  tick={{ fill: "#6b6b8a", fontSize: 9 }}
                />
                <Tooltip
                  contentStyle={{
                    background: "#111118",
                    border: "1px solid #1e1e2e",
                    color: "#e8e8f0",
                  }}
                />
                <Bar
                  dataKey={(entry: { value: number }) => Math.abs(entry.value)}
                  barSize={9}
                  radius={[0, 4, 4, 0]}
                >
                  {riskSnapshot.map((item) => (
                    <Cell key={item.label} fill={item.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          <hr style={{ borderColor: "var(--border)", margin: "4px 0 20px" }} />

          <div className="kicker">Valuation Summary</div>
          <div className="surface-soft" style={{ padding: 14, marginBottom: 24 }}>
            <ValuationCompass
              weightedAnalystUpside={valuationOverview?.weighted_analyst_upside}
              weightedDcfUpside={valuationOverview?.weighted_dcf_upside}
              weightedRiUpside={valuationOverview?.weighted_ri_upside}
              weightedDdmUpside={valuationOverview?.weighted_ddm_upside}
              weightedRelativeUpside={valuationOverview?.weighted_relative_upside}
              coverageRatio={valuationOverview?.coverage_ratio}
              overvaluedWeight={valuationOverview?.overvalued_weight}
              undervaluedWeight={valuationOverview?.undervalued_weight}
            />
            {valuationOverview?.warnings?.length ? (
              <div style={{ marginTop: 10, display: "flex", gap: 6, flexWrap: "wrap" }}>
                {valuationOverview.warnings.map((warning) => (
                  <span className="pill" key={warning}>
                    {warning}
                  </span>
                ))}
              </div>
            ) : null}
          </div>

          <hr style={{ borderColor: "var(--border)", margin: "4px 0 20px" }} />

          <div className="kicker">Latest Scenario</div>
          <div className="surface-soft" style={{ padding: 14, marginBottom: 24 }}>
            {latestScenario ? (
              <>
                <div className="row-between" style={{ marginBottom: 8 }}>
                  <span style={{ fontSize: 12 }}>
                    {latestScenario.factor_key} {latestScenario.shock_value >= 0 ? "+" : ""}
                    {latestScenario.shock_value} {latestScenario.shock_unit}
                  </span>
                  <span style={{ color: "var(--muted)", fontSize: 10 }}>
                    {new Date(latestScenario.started_at).toLocaleString()}
                  </span>
                </div>
                <div style={{ fontSize: 11, color: "var(--muted)", marginBottom: 8 }}>
                  Status: {latestScenario.status} | Horizon: {latestScenario.horizon_days}d
                </div>
              </>
            ) : (
              <div style={{ fontSize: 11, color: "var(--muted)", marginBottom: 8 }}>
                No saved scenario run yet.
              </div>
            )}
            <button className="inline-link" onClick={() => dispatch({ type: "go_page", page: "scenarios" })}>
              Open Scenario Lab
            </button>
          </div>

          <hr style={{ borderColor: "var(--border)", margin: "4px 0 20px" }} />

          <div className="kicker">Refresh Status</div>
          <div className="surface-soft" style={{ padding: 14 }}>
            <div className="row-between" style={{ marginBottom: 8 }}>
              <span style={{ color: "var(--yellow)", fontSize: 11, fontWeight: 600 }}>
                Last refresh
              </span>
              <span style={{ color: "var(--muted)", fontSize: 10, opacity: 0.8 }}>
                {dataState.overview?.last_refresh?.finished_at ?? "Never"}
              </span>
            </div>
            <div style={{ fontSize: 11, lineHeight: 1.6, marginBottom: 10 }}>
              Status: {dataState.overview?.last_refresh?.status ?? "not run"}
            </div>
            <button className="inline-link" onClick={() => void runManualRefresh()}>
              Run manual refresh
            </button>
          </div>
        </aside>
      </div>
    </>
  );
}
