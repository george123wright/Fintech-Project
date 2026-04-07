import { useEffect, useMemo, useRef, useState, type Dispatch } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Legend,
  Pie,
  PieChart,
  ReferenceDot,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import DataWarningBanner from "../components/DataWarningBanner";
import InsightBox from "../components/InsightBox";
import ValuationCompass from "../components/ValuationCompass";
import { getSecurityDcfDetail, getSecurityDdmDetail, getSecurityRiDetail } from "../api/client";
import type {
  AnalystDetailResponse,
  AnalystRevisionRow,
  AnalystTableCell,
  AnalystTableRow,
  CorporateActionRow,
  FinancialRatioMetric,
  FinancialStatementRow,
  InsiderTransactionRow,
  NewsArticle,
  PricePoint,
  SecurityFinancialRatiosResponse,
  SecurityFinancialStatementsResponse,
  SecurityDcfDetailResponse,
  SecurityDdmDetailResponse,
  SecurityRiDetailResponse,
  SecurityOverviewResponse,
  ValuationAssumptions,
} from "../types/api";
import type { NavAction, NavState, StockTabKey } from "../state/nav";
import { usePortfolioData } from "../state/DataProvider";
import { formatPercent, formatPrice } from "../utils/format";

type Props = {
  state: NavState;
  dispatch: Dispatch<NavAction>;
};

type ExposureDatum = {
  metric: string;
  stock: number;
  portfolio: number;
  benchmark?: number;
};

type AnalystProjectionPoint = {
  timestamp: number;
  date: string;
  price: number | null;
  targetHigh: number | null;
  targetMean: number | null;
  targetMedian: number | null;
  targetLow: number | null;
};

type ShareholderPieDatum = {
  name: string;
  value: number;
  color: string;
};

type FinancialPeriod = "annual" | "quarterly";
type FinancialView = "level" | "growth";
type FinancialTab = "income" | "balance" | "cashflow";

function Row({
  label,
  value,
  sub,
  valueColor,
}: {
  label: string;
  value: string;
  sub?: string;
  valueColor?: string;
}) {
  return (
    <div
      className="row-between"
      style={{
        padding: "10px 0",
        borderBottom: "1px solid var(--border)",
        alignItems: "flex-start",
      }}
    >
      <span style={{ color: "var(--muted)", fontSize: 12 }}>{label}</span>
      <div style={{ textAlign: "right" }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: valueColor ?? "var(--text)" }}>{value}</div>
        {sub ? <div style={{ fontSize: 10, color: "var(--muted)" }}>{sub}</div> : null}
      </div>
    </div>
  );
}

function formatMaybePct(value: number | null | undefined): string {
  if (value == null) return "N/A";
  return formatPercent(value * 100);
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

function fmtNumber(value: unknown, digits = 2): string {
  const num = asNumber(value);
  if (num == null) return "N/A";
  return num.toFixed(digits);
}

function fmtPct(value: unknown): string {
  const num = asNumber(value);
  if (num == null) return "N/A";
  return formatPercent(num * 100);
}

function toTitleCase(value: string): string {
  return value
    .toLowerCase()
    .split(" ")
    .filter((part) => part.length > 0)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function formatRatingLabel(value: string | null | undefined): string {
  if (value == null) return "N/A";
  const cleaned = value.trim();
  if (!cleaned) return "N/A";
  if (/^n\/?a$/i.test(cleaned)) return "N/A";
  return toTitleCase(cleaned);
}

function ratingTone(value: string | null | undefined): "positive" | "negative" | "neutral" | "unknown" {
  if (value == null) return "unknown";
  const normalized = value.toLowerCase();
  const positive = [
    "buy",
    "strong buy",
    "outperform",
    "overweight",
    "accumulate",
    "add",
    "overperform",
  ];
  const negative = [
    "sell",
    "strong sell",
    "underperform",
    "underweight",
    "reduce",
    "trim",
  ];
  const neutral = ["hold", "neutral", "market perform", "equal weight", "peer perform"];
  if (positive.some((token) => normalized.includes(token))) return "positive";
  if (negative.some((token) => normalized.includes(token))) return "negative";
  if (neutral.some((token) => normalized.includes(token))) return "neutral";
  return "unknown";
}

function formatRevisionAction(value: string | null | undefined): string {
  if (value == null) return "N/A";
  const normalized = value.trim().toLowerCase();
  if (!normalized) return "N/A";
  if (normalized === "up") return "Upgrade";
  if (normalized === "down") return "Downgrade";
  if (normalized === "init") return "Initiated";
  if (normalized === "reit") return "Reiterated";
  return toTitleCase(normalized);
}

function RatingBadge({ value }: { value: string | null | undefined }) {
  const label = formatRatingLabel(value);
  const tone = ratingTone(value);
  return <span className={`rating-badge ${tone}`}>{label}</span>;
}

function formatTableCell(value: AnalystTableCell): string {
  if (value == null) return "N/A";
  if (typeof value === "number") {
    return Number.isInteger(value) ? String(value) : value.toFixed(2);
  }
  if (typeof value === "boolean") {
    return value ? "True" : "False";
  }
  return String(value);
}

function DynamicTable({
  rows,
  maxRows = 120,
}: {
  rows: AnalystTableRow[];
  maxRows?: number;
}) {
  const columns = rows.length ? Object.keys(rows[0]) : [];
  if (!rows.length || !columns.length) {
    return <div style={{ color: "var(--muted)", fontSize: 12 }}>No rows available.</div>;
  }

  return (
    <div style={{ overflowX: "auto" }}>
      <table className="table">
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column}>{column}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.slice(0, maxRows).map((row, rowIndex) => (
            <tr key={rowIndex}>
              {columns.map((column) => (
                <td key={`${rowIndex}-${column}`}>{formatTableCell(row[column])}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function isLabelColumn(key: string): boolean {
  const normalized = key.toLowerCase();
  return (
    normalized.includes("period") ||
    normalized.includes("date") ||
    normalized.includes("firm") ||
    normalized.includes("action")
  );
}

function formatMillionsValue(value: number): string {
  return `${(value / 1_000_000).toLocaleString(undefined, {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })}`;
}

function formatPercentValue(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function formatMarketCap(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "N/A";
  const abs = Math.abs(value);
  if (abs >= 1_000_000_000_000) return `$${(value / 1_000_000_000_000).toFixed(2)}T`;
  if (abs >= 1_000_000_000) return `$${(value / 1_000_000_000).toFixed(2)}B`;
  if (abs >= 1_000_000) return `$${(value / 1_000_000).toFixed(2)}M`;
  return `$${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

function formatCount(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "N/A";
  return Math.round(value).toLocaleString();
}

function formatShareholderValue(label: string, value: number | null, displayValue: string | null): string {
  if (displayValue != null && displayValue.trim()) return displayValue;
  if (value == null || !Number.isFinite(value)) return "N/A";
  const normalized = label.toLowerCase();
  if (normalized.includes("percent")) {
    return `${(value * 100).toFixed(2)}%`;
  }
  if (normalized.includes("count")) {
    return formatCount(value);
  }
  return value.toLocaleString(undefined, { maximumFractionDigits: 4 });
}

function metricColor(value: number | null | undefined): string | undefined {
  if (value == null || !Number.isFinite(value)) return undefined;
  if (value > 0) return "var(--green)";
  if (value < 0) return "var(--red)";
  return "var(--muted)";
}

function toNumeric(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function isMonetaryMetric(metric: string): boolean {
  const normalized = metric.toLowerCase();
  const nonMonetaryTokens = [
    "eps",
    "per share",
    "shares",
    "share issued",
    "share number",
    "ratio",
    "margin",
    "yield",
    "rate",
    "tax rate",
    "count",
    "days",
  ];
  return !nonMonetaryTokens.some((token) => normalized.includes(token));
}

function formatStatementLevelValue(metric: string, value: unknown): string {
  const numeric = toNumeric(value);
  if (numeric == null) return "N/A";
  if (isMonetaryMetric(metric)) {
    return `${(numeric / 1_000_000).toLocaleString(undefined, {
      minimumFractionDigits: 1,
      maximumFractionDigits: 1,
    })}m`;
  }
  if (Math.abs(numeric) >= 1_000_000_000) {
    return numeric.toLocaleString(undefined, { maximumFractionDigits: 0 });
  }
  if (Math.abs(numeric) >= 1_000) {
    return numeric.toLocaleString(undefined, { maximumFractionDigits: 2 });
  }
  return Number.isInteger(numeric) ? `${numeric}` : numeric.toFixed(4);
}

function computeGrowthRows(rows: FinancialStatementRow[], valueColumns: string[]): FinancialStatementRow[] {
  if (!rows.length) return [];

  return rows.map((row) => {
    const metric = typeof row.Metric === "string" ? row.Metric : "Metric";
    const out: FinancialStatementRow = { Metric: metric };
    for (let idx = 0; idx < valueColumns.length; idx += 1) {
      const currentCol = valueColumns[idx];
      const priorCol = valueColumns[idx + 1];
      if (priorCol == null) {
        out[currentCol] = null;
        continue;
      }
      const currentVal = toNumeric(row[currentCol]);
      const priorVal = toNumeric(row[priorCol]);
      if (currentVal == null || priorVal == null || priorVal === 0) {
        out[currentCol] = null;
        continue;
      }
      out[currentCol] = currentVal / priorVal - 1;
    }
    return out;
  });
}

function formatFinancialCell(metric: string, value: unknown, view: FinancialView): string {
  if (view === "growth") {
    const growth = toNumeric(value);
    if (growth == null) return "N/A";
    return formatPercent(growth * 100, 1);
  }
  return formatStatementLevelValue(metric, value);
}

function financialCellColor(value: unknown, view: FinancialView): string | undefined {
  if (view !== "growth") return undefined;
  const growth = toNumeric(value);
  if (growth == null) return "var(--muted)";
  return growth >= 0 ? "var(--green)" : "var(--red)";
}

function formatRatioMetricValue(metric: FinancialRatioMetric): string {
  const value = metric.value;
  if (value == null || !Number.isFinite(value)) return "N/A";
  if (metric.unit === "pct") {
    return formatPercent(value * 100, 2);
  }
  if (metric.unit === "x") {
    return `${value.toFixed(2)}x`;
  }
  if (metric.unit === "days") {
    return `${value.toFixed(1)}d`;
  }
  if (Math.abs(value) >= 1_000) {
    return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
  }
  return value.toFixed(4);
}

function ratioMetricColor(metric: FinancialRatioMetric): string | undefined {
  if (metric.value == null || !Number.isFinite(metric.value)) return "var(--muted)";
  const growthLikeCategories = new Set(["Profitability", "Returns", "Growth", "Cash Flow Quality"]);
  if (!growthLikeCategories.has(metric.category)) {
    return undefined;
  }
  if (metric.value > 0) return "var(--green)";
  if (metric.value < 0) return "var(--red)";
  return "var(--muted)";
}

function matchesCommonStatementMetric(metricRaw: string): boolean {
  const metric = metricRaw.toLowerCase();
  const keywordGroups: string[][] = [
    ["revenue"],
    ["ebit"],
    ["net income"],
    ["operating cash flow", "cash flow from continuing operating activities", "cashflow from operating activities"],
    ["free cash flow"],
    ["debt", "borrowings"],
    ["cash and cash equivalents", "cash cash equivalents and short term investments", "cash and short term investments"],
  ];
  return keywordGroups.some((group) => group.some((keyword) => metric.includes(keyword)));
}

function csvEscape(value: string): string {
  if (value.includes(",") || value.includes("\"") || value.includes("\n")) {
    return `"${value.replace(/"/g, "\"\"")}"`;
  }
  return value;
}

function transformGrowthEstimateRows(rows: AnalystTableRow[]): AnalystTableRow[] {
  return rows.map((row) => {
    const next: AnalystTableRow = {};
    for (const [key, rawValue] of Object.entries(row)) {
      const num = asNumber(rawValue);
      next[key] = num != null && !isLabelColumn(key) ? formatPercentValue(num) : rawValue;
    }
    return next;
  });
}

function transformRevenueEstimateRows(rows: AnalystTableRow[]): AnalystTableRow[] {
  return rows.map((row) => {
    const next: AnalystTableRow = {};
    for (const [key, rawValue] of Object.entries(row)) {
      const num = asNumber(rawValue);
      const normalized = key.toLowerCase();
      if (num == null) {
        next[key] = rawValue;
      } else if (normalized.includes("analyst")) {
        next[key] = Math.round(num);
      } else if (normalized.includes("growth")) {
        next[key] = formatPercentValue(num);
      } else if (!isLabelColumn(key)) {
        next[key] = formatMillionsValue(num);
      } else {
        next[key] = rawValue;
      }
    }
    return next;
  });
}

function addMonthsIso(baseIso: string, months: number): string {
  const date = new Date(baseIso);
  if (!Number.isFinite(date.getTime())) {
    const fallback = new Date();
    fallback.setMonth(fallback.getMonth() + months);
    return fallback.toISOString();
  }
  date.setMonth(date.getMonth() + months);
  return date.toISOString();
}

function formatAxisDate(iso: string): string {
  const date = new Date(iso);
  if (!Number.isFinite(date.getTime())) return iso;
  return date.toLocaleDateString(undefined, { month: "short", year: "numeric" });
}

function formatNewsDate(value: string | null): string {
  if (!value) return "N/A";
  const parsed = new Date(value);
  if (!Number.isFinite(parsed.getTime())) return value;
  return parsed.toLocaleString();
}

function toTimestamp(value: string): number {
  const parsed = new Date(value).getTime();
  return Number.isFinite(parsed) ? parsed : Date.now();
}

function sortPricePoints(points: PricePoint[]): PricePoint[] {
  return [...points].sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());
}

function computeProjectionYDomain(
  rows: AnalystProjectionPoint[]
): [number, number] | null {
  const values: number[] = [];
  for (const row of rows) {
    for (const field of ["price", "targetHigh", "targetMean", "targetMedian", "targetLow"] as const) {
      const value = row[field];
      if (typeof value === "number" && Number.isFinite(value)) {
        values.push(value);
      }
    }
  }
  if (!values.length) return null;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const spread = Math.max(max - min, 1);
  const pad = spread * 0.14;
  return [Math.max(0, min - pad), max + pad];
}

function ExposureDivergingChart({
  title,
  data,
  stockLabel,
  idPrefix,
  benchmarkLabel,
}: {
  title: string;
  data: ExposureDatum[];
  stockLabel: string;
  idPrefix: string;
  benchmarkLabel?: string;
}) {
  if (!data.length) {
    return (
      <div className="card exposure-chart-panel">
        <div className="kicker" style={{ marginBottom: 10 }}>
          {title}
        </div>
        <div style={{ color: "var(--muted)", fontSize: 12 }}>
          No exposure data available yet. Run a refresh after prices load.
        </div>
      </div>
    );
  }

  const hasBenchmark = data.some((item) => typeof item.benchmark === "number" && Number.isFinite(item.benchmark));
  const maxAbs = data.reduce((acc, item) => {
    const benchmarkAbs =
      typeof item.benchmark === "number" && Number.isFinite(item.benchmark) ? Math.abs(item.benchmark) : 0;
    return Math.max(acc, Math.abs(item.stock), Math.abs(item.portfolio), benchmarkAbs);
  }, 0);
  const domainMax = Math.max(0.2, Math.ceil(maxAbs * 120) / 100);

  return (
    <div className="card exposure-chart-panel">
      <div className="kicker" style={{ marginBottom: 8 }}>
        {title}
      </div>
      <div className="exposure-chart-subtitle">
        {hasBenchmark
          ? `Centered at 0, comparing stock vs portfolio vs ${benchmarkLabel ?? "SPY"} betas`
          : "Centered at 0, comparing stock vs portfolio betas"}
      </div>
      <div className="exposure-chart-frame">
        <ResponsiveContainer width="100%" height={Math.max(250, data.length * 46)}>
          <BarChart
            data={data}
            layout="vertical"
            margin={{ top: 14, right: 20, bottom: 14, left: 10 }}
            barCategoryGap="28%"
          >
            <defs>
              <linearGradient id={`${idPrefix}-stock-gradient`} x1="0" y1="0" x2="1" y2="0">
                <stop offset="0%" stopColor="#6f7cff" stopOpacity={0.92} />
                <stop offset="100%" stopColor="#3cb8ff" stopOpacity={0.95} />
              </linearGradient>
              <linearGradient id={`${idPrefix}-portfolio-gradient`} x1="0" y1="0" x2="1" y2="0">
                <stop offset="0%" stopColor="#3ad1a1" stopOpacity={0.9} />
                <stop offset="100%" stopColor="#7fe3c3" stopOpacity={0.92} />
              </linearGradient>
              <linearGradient id={`${idPrefix}-benchmark-gradient`} x1="0" y1="0" x2="1" y2="0">
                <stop offset="0%" stopColor="#f0be6b" stopOpacity={0.92} />
                <stop offset="100%" stopColor="#ffd992" stopOpacity={0.95} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="rgba(151,161,189,0.18)" strokeDasharray="3 4" horizontal={false} />
            <XAxis
              type="number"
              domain={[-domainMax, domainMax]}
              tick={{ fill: "#97a1bd", fontSize: 10 }}
              tickFormatter={(value) => value.toFixed(1)}
            />
            <YAxis
              dataKey="metric"
              type="category"
              width={118}
              tick={{ fill: "#d9def2", fontSize: 11 }}
            />
            <Tooltip
              cursor={{ fill: "rgba(111,124,255,0.08)" }}
              contentStyle={{
                background: "#11131d",
                border: "1px solid #2f3750",
                borderRadius: 10,
                color: "#eceef9",
              }}
              formatter={(value: number, name: string) => [value.toFixed(2), name]}
            />
            <Legend
              verticalAlign="top"
              align="right"
              iconType="circle"
              wrapperStyle={{ fontSize: 11, color: "#97a1bd", top: -2 }}
            />
            <ReferenceLine x={0} stroke="rgba(240,190,107,0.9)" strokeWidth={2} />
            <Bar
              dataKey="portfolio"
              name="Portfolio"
              fill={`url(#${idPrefix}-portfolio-gradient)`}
              radius={[4, 4, 4, 4]}
            />
            {hasBenchmark && (
              <Bar
                dataKey="benchmark"
                name={benchmarkLabel ?? "SPY"}
                fill={`url(#${idPrefix}-benchmark-gradient)`}
                radius={[4, 4, 4, 4]}
              />
            )}
            <Bar
              dataKey="stock"
              name={stockLabel}
              fill={`url(#${idPrefix}-stock-gradient)`}
              radius={[4, 4, 4, 4]}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export default function StockPage({ state, dispatch }: Props) {
  const [tab, setTab] = useState<StockTabKey>(state.stockTab ?? "overview");
  const {
    state: dataState,
    loadSymbolInsight,
    recomputeValuations,
    runManualRefresh,
    fetchAnalystDetail,
    fetchPricesForActive,
    fetchSecurityNews,
    fetchSecurityEventsForActive,
    fetchSecurityOverview,
    fetchSecurityFinancials,
    fetchSecurityRatios,
  } = usePortfolioData();
  const [eventsStatus, setEventsStatus] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [eventsError, setEventsError] = useState<string | null>(null);
  const [eventsWarnings, setEventsWarnings] = useState<string[]>([]);
  const [analystDetail, setAnalystDetail] = useState<AnalystDetailResponse | null>(null);
  const [analystDetailError, setAnalystDetailError] = useState<string | null>(null);
  const [corporateActions, setCorporateActions] = useState<CorporateActionRow[]>([]);
  const [insiderTransactions, setInsiderTransactions] = useState<InsiderTransactionRow[]>([]);
  const [analystRevisions, setAnalystRevisions] = useState<AnalystRevisionRow[]>([]);
  const [securityNews, setSecurityNews] = useState<NewsArticle[]>([]);
  const [securityNewsStatus, setSecurityNewsStatus] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [securityNewsWarnings, setSecurityNewsWarnings] = useState<string[]>([]);
  const [securityNewsError, setSecurityNewsError] = useState<string | null>(null);
  const [stockOverview, setStockOverview] = useState<SecurityOverviewResponse | null>(null);
  const [stockOverviewStatus, setStockOverviewStatus] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [stockOverviewWarnings, setStockOverviewWarnings] = useState<string[]>([]);
  const [stockOverviewError, setStockOverviewError] = useState<string | null>(null);
  const [financials, setFinancials] = useState<SecurityFinancialStatementsResponse | null>(null);
  const [financialsSymbol, setFinancialsSymbol] = useState<string | null>(null);
  const [financialsStatus, setFinancialsStatus] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [financialsWarnings, setFinancialsWarnings] = useState<string[]>([]);
  const [financialsError, setFinancialsError] = useState<string | null>(null);
  const [ratios, setRatios] = useState<SecurityFinancialRatiosResponse | null>(null);
  const [ratiosSymbol, setRatiosSymbol] = useState<string | null>(null);
  const [ratiosStatus, setRatiosStatus] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [ratiosWarnings, setRatiosWarnings] = useState<string[]>([]);
  const [ratiosError, setRatiosError] = useState<string | null>(null);
  const [financialPeriod, setFinancialPeriod] = useState<FinancialPeriod>("annual");
  const [financialView, setFinancialView] = useState<FinancialView>("level");
  const [financialSearch, setFinancialSearch] = useState<string>("");
  const [financialCommonOnly, setFinancialCommonOnly] = useState<boolean>(false);
  const [ratioSearch, setRatioSearch] = useState<string>("");
  const [showFullAddress, setShowFullAddress] = useState<boolean>(false);
  const [analystPriceSeries, setAnalystPriceSeries] = useState<PricePoint[]>([]);
  const [analystPriceError, setAnalystPriceError] = useState<string | null>(null);
  const [analystPriceWarnings, setAnalystPriceWarnings] = useState<string[]>([]);
  const [showRevenue, setShowRevenue] = useState<boolean>(false);
  const [showEarnings, setShowEarnings] = useState<boolean>(false);
  const [showDcfDetail, setShowDcfDetail] = useState<boolean>(false);
  const [dcfDetail, setDcfDetail] = useState<SecurityDcfDetailResponse | null>(null);
  const [dcfDetailStatus, setDcfDetailStatus] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [dcfDetailError, setDcfDetailError] = useState<string | null>(null);
  const [showRiDetail, setShowRiDetail] = useState<boolean>(false);
  const [riDetail, setRiDetail] = useState<SecurityRiDetailResponse | null>(null);
  const [riDetailStatus, setRiDetailStatus] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [riDetailError, setRiDetailError] = useState<string | null>(null);
  const [showDdmDetail, setShowDdmDetail] = useState<boolean>(false);
  const [ddmDetail, setDdmDetail] = useState<SecurityDdmDetailResponse | null>(null);
  const [ddmDetailStatus, setDdmDetailStatus] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [ddmDetailError, setDdmDetailError] = useState<string | null>(null);
  const [terminalClipBuffer, setTerminalClipBuffer] = useState<number>(0.02);
  const corporateActionsRef = useRef<HTMLDivElement | null>(null);
  const insiderTransactionsRef = useRef<HTMLDivElement | null>(null);
  const analystRevisionsRef = useRef<HTMLDivElement | null>(null);

  const holdings = dataState.holdings;
  const fallbackSymbol = holdings[0]?.symbol ?? "N/A";
  const sym = state.sym ?? fallbackSymbol;

  const selected = useMemo(
    () => holdings.find((holding) => holding.symbol === sym),
    [holdings, sym]
  );
  const stockDisplayName =
    stockOverview?.name ??
    selected?.name ??
    selected?.symbol ??
    sym;
  const shareholderPieData = useMemo<ShareholderPieDatum[]>(() => {
    if (!stockOverview?.shareholder_breakdown?.length) return [];

    const normalizePercent = (value: number | null): number | null => {
      if (value == null || !Number.isFinite(value)) return null;
      if (value > 1) return value / 100;
      if (value < 0) return null;
      return value;
    };

    let insiders: number | null = null;
    let institutions: number | null = null;

    for (const row of stockOverview.shareholder_breakdown) {
      const normalizedLabel = row.label.toLowerCase().replace(/[^a-z]/g, "");
      const value = normalizePercent(row.value);
      if (value == null) continue;

      if (normalizedLabel.includes("institutionsfloatpercentheld")) {
        continue;
      }

      if (normalizedLabel.includes("insiderspercentheld")) {
        insiders = value;
        continue;
      }

      if (normalizedLabel.includes("institutionspercentheld")) {
        institutions = value;
      }
    }

    const insidersPct = Math.max(0, Math.min(1, insiders ?? 0));
    const institutionsPct = Math.max(0, Math.min(1, institutions ?? 0));
    const accounted = Math.max(0, Math.min(1, insidersPct + institutionsPct));
    const otherPct = Math.max(0, 1 - accounted);

    if (accounted <= 0 && otherPct <= 0) return [];

    return [
      { name: "Insiders", value: insidersPct * 100, color: "#6f7cff" },
      { name: "Institutions", value: institutionsPct * 100, color: "#3ad1a1" },
      { name: "Other", value: otherPct * 100, color: "#f0be6b" },
    ];
  }, [stockOverview?.shareholder_breakdown]);
  const activeFinancialTab: FinancialTab | null =
    tab === "income" || tab === "balance" || tab === "cashflow" ? tab : null;
  const baseFinancialRows = useMemo<FinancialStatementRow[]>(() => {
    if (!financials || activeFinancialTab == null) return [];
    if (activeFinancialTab === "income") {
      return financialPeriod === "annual"
        ? financials.income_statement_annual
        : financials.income_statement_quarterly;
    }
    if (activeFinancialTab === "balance") {
      return financialPeriod === "annual"
        ? financials.balance_sheet_annual
        : financials.balance_sheet_quarterly;
    }
    return financialPeriod === "annual"
      ? financials.cashflow_annual
      : financials.cashflow_quarterly;
  }, [activeFinancialTab, financialPeriod, financials]);
  const financialValueColumns = useMemo<string[]>(() => {
    if (!baseFinancialRows.length) return [];
    return Object.keys(baseFinancialRows[0]).filter((key) => key !== "Metric");
  }, [baseFinancialRows]);
  const financialRows = useMemo<FinancialStatementRow[]>(() => {
    if (financialView === "level") return baseFinancialRows;
    return computeGrowthRows(baseFinancialRows, financialValueColumns);
  }, [baseFinancialRows, financialValueColumns, financialView]);
  const filteredFinancialRows = useMemo<FinancialStatementRow[]>(() => {
    let rows = financialRows;
    if (financialCommonOnly) {
      rows = rows.filter((row) => {
        const metric = typeof row.Metric === "string" ? row.Metric : "";
        return matchesCommonStatementMetric(metric);
      });
    }
    const query = financialSearch.trim().toLowerCase();
    if (!query) return rows;
    return rows.filter((row) => {
      const metric = typeof row.Metric === "string" ? row.Metric.toLowerCase() : "";
      return metric.includes(query);
    });
  }, [financialCommonOnly, financialRows, financialSearch]);
  const activeRatioMetrics = useMemo<FinancialRatioMetric[]>(() => {
    if (!ratios) return [];
    return financialPeriod === "annual" ? ratios.annual : ratios.quarterly;
  }, [financialPeriod, ratios]);
  const filteredRatioMetrics = useMemo<FinancialRatioMetric[]>(() => {
    const query = ratioSearch.trim().toLowerCase();
    if (!query) return activeRatioMetrics;
    return activeRatioMetrics.filter((metric) => {
      return (
        metric.label.toLowerCase().includes(query) ||
        metric.category.toLowerCase().includes(query) ||
        metric.key.toLowerCase().includes(query) ||
        metric.description.toLowerCase().includes(query)
      );
    });
  }, [activeRatioMetrics, ratioSearch]);
  const groupedRatioMetrics = useMemo<Array<{ category: string; metrics: FinancialRatioMetric[] }>>(() => {
    const byCategory = new Map<string, FinancialRatioMetric[]>();
    for (const metric of filteredRatioMetrics) {
      const existing = byCategory.get(metric.category) ?? [];
      existing.push(metric);
      byCategory.set(metric.category, existing);
    }
    return Array.from(byCategory.entries())
      .map(([category, metrics]) => ({
        category,
        metrics: [...metrics].sort((left, right) => left.label.localeCompare(right.label)),
      }))
      .sort((left, right) => left.category.localeCompare(right.category));
  }, [filteredRatioMetrics]);
  const highlightedRatios = useMemo<FinancialRatioMetric[]>(() => {
    const preferredKeys = [
      "trailing_pe",
      "price_to_sales",
      "price_to_book",
      "roe",
      "roa",
      "roic",
      "net_margin",
      "fcf_margin",
      "current_ratio",
      "debt_to_equity",
      "fcf_yield",
      "revenue_growth_yoy",
    ];
    const metricByKey = new Map(activeRatioMetrics.map((metric) => [metric.key, metric]));
    const picked: FinancialRatioMetric[] = [];
    for (const key of preferredKeys) {
      const metric = metricByKey.get(key);
      if (metric) {
        picked.push(metric);
      }
    }
    if (picked.length >= 8) return picked.slice(0, 8);
    const fallback = activeRatioMetrics
      .filter((metric) => metric.value != null && Number.isFinite(metric.value))
      .slice(0, 8 - picked.length);
    return [...picked, ...fallback].slice(0, 8);
  }, [activeRatioMetrics]);
  const downloadCurrentFinancialCsv = () => {
    if (!activeFinancialTab || !selected?.symbol || !financialValueColumns.length || !filteredFinancialRows.length) {
      return;
    }
    const header = ["Metric", ...financialValueColumns];
    const lines = [header.map(csvEscape).join(",")];

    for (const row of filteredFinancialRows) {
      const metric = typeof row.Metric === "string" ? row.Metric : "Metric";
      const cells = [metric];
      for (const column of financialValueColumns) {
        cells.push(formatFinancialCell(metric, row[column], financialView));
      }
      lines.push(cells.map(csvEscape).join(","));
    }

    const csv = lines.join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    const statement = activeFinancialTab === "income"
      ? "income_statement"
      : activeFinancialTab === "balance"
        ? "balance_sheet"
        : "cashflow";
    a.href = url;
    a.download = `${selected.symbol}_${statement}_${financialPeriod}_${financialView}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  useEffect(() => {
    setTab(state.stockTab ?? "overview");
  }, [state.stockTab]);

  useEffect(() => {
    if (selected?.symbol) {
      void loadSymbolInsight(selected.symbol);
    }
  }, [loadSymbolInsight, selected?.symbol]);

  useEffect(() => {
    setShowDcfDetail(false);
    setDcfDetail(null);
    setDcfDetailStatus("idle");
    setDcfDetailError(null);
    setShowRiDetail(false);
    setRiDetail(null);
    setRiDetailStatus("idle");
    setRiDetailError(null);
    setShowDdmDetail(false);
    setDdmDetail(null);
    setDdmDetailStatus("idle");
    setDdmDetailError(null);
  }, [selected?.symbol, dataState.activePortfolioId]);

  useEffect(() => {
    if (tab !== "valuation") return;
    if (!showDcfDetail) return;
    if (!selected?.symbol) return;
    if (dataState.activePortfolioId == null) return;

    let isMounted = true;
    setDcfDetailStatus("loading");
    setDcfDetailError(null);

    void getSecurityDcfDetail(dataState.activePortfolioId, selected.symbol)
      .then((payload) => {
        if (!isMounted) return;
        setDcfDetail(payload);
        setDcfDetailStatus("ready");
      })
      .catch((error: Error) => {
        if (!isMounted) return;
        setDcfDetail(null);
        setDcfDetailError(error.message);
        setDcfDetailStatus("error");
      });

    return () => {
      isMounted = false;
    };
  }, [dataState.activePortfolioId, selected?.symbol, showDcfDetail, tab]);

  useEffect(() => {
    if (tab !== "valuation") return;
    if (!showRiDetail) return;
    if (!selected?.symbol) return;
    if (dataState.activePortfolioId == null) return;

    let isMounted = true;
    setRiDetailStatus("loading");
    setRiDetailError(null);

    void getSecurityRiDetail(dataState.activePortfolioId, selected.symbol)
      .then((payload) => {
        if (!isMounted) return;
        setRiDetail(payload);
        setRiDetailStatus("ready");
      })
      .catch((error: Error) => {
        if (!isMounted) return;
        setRiDetail(null);
        setRiDetailError(error.message);
        setRiDetailStatus("error");
      });

    return () => {
      isMounted = false;
    };
  }, [dataState.activePortfolioId, selected?.symbol, showRiDetail, tab]);

  useEffect(() => {
    if (tab !== "valuation") return;
    if (!showDdmDetail) return;
    if (!selected?.symbol) return;
    if (dataState.activePortfolioId == null) return;

    let isMounted = true;
    setDdmDetailStatus("loading");
    setDdmDetailError(null);

    void getSecurityDdmDetail(dataState.activePortfolioId, selected.symbol)
      .then((payload) => {
        if (!isMounted) return;
        setDdmDetail(payload);
        setDdmDetailStatus("ready");
      })
      .catch((error: Error) => {
        if (!isMounted) return;
        setDdmDetail(null);
        setDdmDetailError(error.message);
        setDdmDetailStatus("error");
      });

    return () => {
      isMounted = false;
    };
  }, [dataState.activePortfolioId, selected?.symbol, showDdmDetail, tab]);

  useEffect(() => {
    if (!selected?.symbol) return;
    let isMounted = true;
    setStockOverviewStatus("loading");
    setStockOverviewError(null);
    setShowFullAddress(false);

    void fetchSecurityOverview(selected.symbol)
      .then((payload) => {
        if (!isMounted) return;
        setStockOverview(payload);
        setStockOverviewWarnings(payload.warnings ?? []);
        setStockOverviewStatus("ready");
      })
      .catch((error: Error) => {
        if (!isMounted) return;
        setStockOverview(null);
        setStockOverviewWarnings([]);
        setStockOverviewError(error.message);
        setStockOverviewStatus("error");
      });

    return () => {
      isMounted = false;
    };
  }, [fetchSecurityOverview, selected?.symbol]);

  useEffect(() => {
    if (!selected?.symbol) return;
    if (!(tab === "income" || tab === "balance" || tab === "cashflow")) return;
    if (financials != null && financialsSymbol === selected.symbol) {
      setFinancialsStatus("ready");
      return;
    }
    let isMounted = true;
    setFinancialsStatus("loading");
    setFinancialsError(null);

    void fetchSecurityFinancials(selected.symbol)
      .then((payload) => {
        if (!isMounted) return;
        setFinancials(payload);
        setFinancialsSymbol(selected.symbol);
        setFinancialsWarnings(payload.warnings ?? []);
        setFinancialsStatus("ready");
      })
      .catch((error: Error) => {
        if (!isMounted) return;
        setFinancials(null);
        setFinancialsSymbol(null);
        setFinancialsWarnings([]);
        setFinancialsError(error.message);
        setFinancialsStatus("error");
      });

    return () => {
      isMounted = false;
    };
  }, [fetchSecurityFinancials, financials, financialsSymbol, selected?.symbol, tab]);

  useEffect(() => {
    if (!selected?.symbol) return;
    if (tab !== "ratios") return;
    if (ratios != null && ratiosSymbol === selected.symbol) {
      setRatiosStatus("ready");
      return;
    }
    let isMounted = true;
    setRatiosStatus("loading");
    setRatiosError(null);

    void fetchSecurityRatios(selected.symbol)
      .then((payload) => {
        if (!isMounted) return;
        setRatios(payload);
        setRatiosSymbol(selected.symbol);
        setRatiosWarnings(payload.warnings ?? []);
        setRatiosStatus("ready");
      })
      .catch((error: Error) => {
        if (!isMounted) return;
        setRatios(null);
        setRatiosSymbol(null);
        setRatiosWarnings([]);
        setRatiosError(error.message);
        setRatiosStatus("error");
      });

    return () => {
      isMounted = false;
    };
  }, [fetchSecurityRatios, ratios, ratiosSymbol, selected?.symbol, tab]);

  useEffect(() => {
    if (!selected?.symbol) return;
    let isMounted = true;
    setAnalystDetailError(null);

    void fetchAnalystDetail(selected.symbol)
      .then((payload) => {
        if (!isMounted) return;
        setAnalystDetail(payload);
      })
      .catch((error: Error) => {
        if (!isMounted) return;
        setAnalystDetail(null);
        setAnalystDetailError(error.message);
      });

    return () => {
      isMounted = false;
    };
  }, [fetchAnalystDetail, selected?.symbol]);

  useEffect(() => {
    if (!selected?.symbol) return;
    if (tab !== "news") return;
    let isMounted = true;
    setSecurityNewsStatus("loading");
    setSecurityNewsError(null);

    void fetchSecurityNews(selected.symbol, 120)
      .then((response) => {
        if (!isMounted) return;
        setSecurityNews(response.articles ?? []);
        setSecurityNewsWarnings(response.warnings ?? []);
        setSecurityNewsStatus("ready");
      })
      .catch((error: Error) => {
        if (!isMounted) return;
        setSecurityNews([]);
        setSecurityNewsWarnings([]);
        setSecurityNewsError(error.message);
        setSecurityNewsStatus("error");
      });

    return () => {
      isMounted = false;
    };
  }, [fetchSecurityNews, selected?.symbol, tab]);

  useEffect(() => {
    if (!selected?.symbol) return;
    if (tab !== "analyst") return;
    let isMounted = true;
    setAnalystPriceError(null);

    void fetchPricesForActive([selected.symbol], "1Y")
      .then((response) => {
        if (!isMounted) return;
        const series = response.series.find((item) => item.symbol === selected.symbol);
        setAnalystPriceSeries(series?.points ?? []);
        setAnalystPriceWarnings(response.warnings ?? []);
      })
      .catch((error: Error) => {
        if (!isMounted) return;
        setAnalystPriceSeries([]);
        setAnalystPriceWarnings([]);
        setAnalystPriceError(error.message);
      });

    return () => {
      isMounted = false;
    };
  }, [fetchPricesForActive, selected?.symbol, tab]);

  useEffect(() => {
    if (!selected?.symbol) return;
    let isMounted = true;
    setEventsStatus("loading");
    setEventsError(null);

    void fetchSecurityEventsForActive(selected.symbol, "5Y")
      .then((response) => {
        if (!isMounted) return;
        setCorporateActions(response.corporate_actions);
        setInsiderTransactions(response.insider_transactions);
        setAnalystRevisions(response.analyst_revisions);
        setEventsWarnings(response.warnings ?? []);
        setEventsStatus("ready");
      })
      .catch((error: Error) => {
        if (!isMounted) return;
        setEventsStatus("error");
        setEventsError(error.message);
        setCorporateActions([]);
        setInsiderTransactions([]);
        setAnalystRevisions([]);
      });

    return () => {
      isMounted = false;
    };
  }, [fetchSecurityEventsForActive, selected?.symbol]);

  useEffect(() => {
    if (state.stockSection == null) return;

    const requiredTab: StockTabKey =
      state.stockSection === "analyst_revisions"
        ? "analyst"
        : state.stockSection === "insider_transactions"
          ? "insider"
          : "corporate";

    if (tab !== requiredTab) return;

    const targetRef =
      state.stockSection === "analyst_revisions"
        ? analystRevisionsRef
        : state.stockSection === "insider_transactions"
          ? insiderTransactionsRef
          : corporateActionsRef;

    targetRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    dispatch({ type: "set_stock_section", section: null });
  }, [dispatch, state.stockSection, tab]);

  const analyst = dataState.analystBySymbol[sym] ?? undefined;
  const valuationFromMap = dataState.valuationBySymbol[sym] ?? undefined;
  const valuationFromOverview =
    dataState.valuationOverview?.results.find((result) => result.symbol === sym) ?? undefined;
  const valuation = valuationFromMap ?? valuationFromOverview;
  const valuationInputs = asRecord(valuation?.inputs);
  const dcfModelVersion =
    valuationInputs && typeof valuationInputs.dcf_model_version === "string"
      ? valuationInputs.dcf_model_version
      : null;
  const dcfQualityScore = asNumber(valuationInputs?.dcf_quality_score);
  const dcfAnchorSummary = asRecord(valuationInputs?.dcf_anchor_diagnostics_summary);
  const dcfTvSummary = asRecord(valuationInputs?.dcf_tv_breakdown_summary);
  const dcfAssumptionsUsed = asRecord(valuationInputs?.dcf_assumptions_used);
  const riModelVersion =
    valuationInputs && typeof valuationInputs.ri_model_version === "string"
      ? valuationInputs.ri_model_version
      : null;
  const riQualityScore = asNumber(valuationInputs?.ri_quality_score);
  const riAnchorSummary = asRecord(valuationInputs?.ri_anchor_diagnostics_summary);
  const riTerminalSummary = asRecord(valuationInputs?.ri_terminal_summary);
  const riAssumptionsUsed = asRecord(valuationInputs?.ri_assumptions_used);
  const ddmModelVersion =
    valuationInputs && typeof valuationInputs.ddm_model_version === "string"
      ? valuationInputs.ddm_model_version
      : null;
  const ddmQualityScore = asNumber(valuationInputs?.ddm_quality_score);
  const ddmAnchorSummary = asRecord(valuationInputs?.ddm_anchor_diagnostics_summary);
  const ddmTerminalSummary = asRecord(valuationInputs?.ddm_terminal_summary);
  const ddmAssumptionsUsed = asRecord(valuationInputs?.ddm_assumptions_used);
  const ddmCoverageMode =
    valuationInputs && typeof valuationInputs.ddm_coverage_mode === "string"
      ? valuationInputs.ddm_coverage_mode
      : null;

  useEffect(() => {
    const assumptions = asRecord(valuationInputs?.assumptions);
    const dcfAssumptions = asRecord(assumptions?.dcf);
    const fromInputs = asNumber(dcfAssumptions?.terminal_clip_buffer);
    const fromUsed = asNumber(dcfAssumptionsUsed?.terminal_clip_buffer);
    const next = fromInputs ?? fromUsed ?? 0.02;
    setTerminalClipBuffer(Math.min(0.1, Math.max(0, next)));
  }, [dcfAssumptionsUsed?.terminal_clip_buffer, selected?.symbol, valuationInputs?.assumptions]);

  const riskMetrics = dataState.risk?.metrics;
  const contribution = dataState.risk?.contributions.find((c) => c.symbol === sym);
  const extendedRoot = asRecord(dataState.extendedMetrics?.metrics);
  const extendedPortfolio = asRecord(extendedRoot?.portfolio);
  const extendedStocks = asRecord(extendedRoot?.stocks);
  const extendedStock = asRecord(extendedStocks?.[sym]);
  const extendedStockVar = asRecord(extendedStock?.var);
  const extendedStockCapture = asRecord(extendedStock?.capture);
  const extendedStockDrawdown = asRecord(extendedStock?.drawdown);
  const extendedStockTechnicals = asRecord(extendedStock?.technicals);
  const extendedStockFundamentals = asRecord(extendedStock?.fundamentals);
  const extendedFundamentalCore = asRecord(extendedStockFundamentals?.fundamentals);
  const extendedMargins = asRecord(extendedStockFundamentals?.margins);
  const extendedRatings = asRecord(extendedStockFundamentals?.rating_changes);
  const extendedFactorModel = asRecord(extendedRoot?.factor_model);
  const extendedMacroModel = asRecord(extendedRoot?.macro_model);
  const extendedFactorStocks = asRecord(extendedFactorModel?.stock_exposures);
  const extendedMacroStocks = asRecord(extendedMacroModel?.stock_exposures);
  const extendedMacroBenchmark = asRecord(extendedMacroModel?.benchmark_exposures);
  const stockFactorExposure = asRecord(extendedFactorStocks?.[sym]);
  const stockMacroExposure = asRecord(extendedMacroStocks?.[sym]);
  const earningsEstimates = asRecord(extendedStockFundamentals?.earnings_estimates);
  const revenueEstimates = asRecord(extendedStockFundamentals?.revenue_estimates);

  const factorExposureSeries = useMemo<ExposureDatum[]>(() => {
    const portfolioFactor = asRecord(extendedPortfolio?.fama_french_proxy_exposures);
    const defs: Array<{ key: string; label: string }> = [
      { key: "market", label: "Market" },
      { key: "size", label: "Size" },
      { key: "value", label: "Value" },
      { key: "momentum", label: "Momentum" },
      { key: "investment", label: "Investment" },
      { key: "profitability", label: "Profitability" },
    ];

    return defs
      .map((item) => {
        const stock = asNumber(stockFactorExposure?.[item.key]);
        const portfolio = asNumber(portfolioFactor?.[item.key]);
        return {
          metric: item.label,
          stock: stock ?? 0,
          portfolio: portfolio ?? 0,
          has: stock != null || portfolio != null,
        };
      })
      .filter((item) => item.has)
      .map(({ has: _has, ...rest }) => rest);
  }, [extendedPortfolio?.fama_french_proxy_exposures, stockFactorExposure]);

  const macroExposureSeries = useMemo<ExposureDatum[]>(() => {
    const portfolioMacro = asRecord(extendedPortfolio?.macro_exposures);
    const defs: Array<{ key: string; label: string }> = [
      { key: "rates", label: "Rates" },
      { key: "oil_prices", label: "Oil" },
      { key: "inflation", label: "Inflation" },
      { key: "gdp", label: "GDP" },
      { key: "retail_spending", label: "Retail" },
      { key: "unemployment", label: "Unemployment" },
      { key: "government_spending", label: "Gov Spend" },
      { key: "market", label: "Market" },
    ];

    return defs
      .map((item) => {
        const stock = asNumber(asRecord(stockMacroExposure?.[item.key])?.beta);
        const portfolio = asNumber(asRecord(portfolioMacro?.[item.key])?.beta);
        const benchmark = asNumber(asRecord(extendedMacroBenchmark?.[item.key])?.beta);
        return {
          metric: item.label,
          stock: stock ?? 0,
          portfolio: portfolio ?? 0,
          benchmark: benchmark ?? undefined,
          has: stock != null || portfolio != null || benchmark != null,
        };
      })
      .filter((item) => item.has)
      .map(({ has: _has, ...rest }) => rest);
  }, [extendedPortfolio?.macro_exposures, extendedMacroBenchmark, stockMacroExposure]);

  const factorBars = (dataState.risk?.contributions ?? []).slice(0, 8).map((item) => ({
    name: item.symbol,
    value: item.pct_total_risk,
    color: item.pct_total_risk >= 0 ? "#7b6ef6" : "#f05b5b",
  }));

  const analystSnapshot = analystDetail?.snapshot;
  const analystCoverage = analystDetail?.coverage;
  const analystTargetChart = useMemo(() => {
    return (analystDetail?.target_scenarios ?? [])
      .filter((item) => item.return_pct != null)
      .map((item) => ({
        label: item.label,
        returnPct: (item.return_pct ?? 0) * 100,
      }));
  }, [analystDetail?.target_scenarios]);
  const analystTargetProjectionData = useMemo(() => {
    const sortedPrices = sortPricePoints(analystPriceSeries).filter((point) => Number.isFinite(point.close));
    const sourceCurrent = sortedPrices.length
      ? sortedPrices[sortedPrices.length - 1].close
      : analystSnapshot?.current ?? analyst?.current_price ?? null;
    const sourceDate = sortedPrices.length
      ? sortedPrices[sortedPrices.length - 1].date
      : new Date().toISOString();
    const projectionDate = addMonthsIso(sourceDate, 12);

    const baseRows: AnalystProjectionPoint[] = sortedPrices.map((point) => ({
      timestamp: toTimestamp(point.date),
      date: point.date,
      price: point.close,
      targetHigh: null,
      targetMean: null,
      targetMedian: null,
      targetLow: null,
    }));

    if (sourceCurrent == null) return baseRows;

    if (baseRows.length === 0) {
      baseRows.push({
        timestamp: toTimestamp(sourceDate),
        date: sourceDate,
        price: sourceCurrent,
        targetHigh: sourceCurrent,
        targetMean: sourceCurrent,
        targetMedian: sourceCurrent,
        targetLow: sourceCurrent,
      });
    } else {
      const lastIdx = baseRows.length - 1;
      baseRows[lastIdx] = {
        ...baseRows[lastIdx],
        targetHigh: sourceCurrent,
        targetMean: sourceCurrent,
        targetMedian: sourceCurrent,
        targetLow: sourceCurrent,
      };
    }

    baseRows.push({
      timestamp: toTimestamp(projectionDate),
      date: projectionDate,
      price: null,
      targetHigh: analystSnapshot?.high ?? null,
      targetMean: analystSnapshot?.mean ?? null,
      targetMedian: analystSnapshot?.median ?? null,
      targetLow: analystSnapshot?.low ?? null,
    });

    return baseRows.sort((left, right) => left.timestamp - right.timestamp);
  }, [
    analyst?.current_price,
    analystPriceSeries,
    analystSnapshot?.current,
    analystSnapshot?.high,
    analystSnapshot?.low,
    analystSnapshot?.mean,
    analystSnapshot?.median,
  ]);
  const analystRecommendationChart = useMemo(() => {
    return (analystDetail?.current_recommendations ?? []).map((item) => ({
      label: item.label,
      count: item.count,
      color:
        ratingTone(item.label) === "positive"
          ? "#3ad1a1"
          : ratingTone(item.label) === "negative"
            ? "#f07575"
            : ratingTone(item.label) === "neutral"
              ? "#f0be6b"
              : "#6f7cff",
    }));
  }, [analystDetail?.current_recommendations]);
  const analystWarnings = useMemo(() => {
    const merged = [
      ...(analyst?.warnings ?? []),
      ...(analystDetail?.warnings ?? []),
      ...analystPriceWarnings,
      ...(analystDetailError ? [`analyst_detail_error:${analystDetailError}`] : []),
      ...(analystPriceError ? [`analyst_price_error:${analystPriceError}`] : []),
    ];
    return Array.from(new Set(merged));
  }, [analyst?.warnings, analystDetail?.warnings, analystDetailError, analystPriceError, analystPriceWarnings]);
  const growthEstimateRows = useMemo(
    () => transformGrowthEstimateRows(analystDetail?.growth_estimates ?? []),
    [analystDetail?.growth_estimates]
  );
  const revenueEstimateRows = useMemo(
    () => transformRevenueEstimateRows(analystDetail?.revenue_estimate ?? []),
    [analystDetail?.revenue_estimate]
  );
  const projectionYDomain = useMemo(
    () => computeProjectionYDomain(analystTargetProjectionData),
    [analystTargetProjectionData]
  );
  const projectionEndPoint = useMemo(() => {
    if (!analystTargetProjectionData.length) return null;
    return analystTargetProjectionData[analystTargetProjectionData.length - 1];
  }, [analystTargetProjectionData]);
  const projectionTargetCallouts = useMemo(() => {
    if (!projectionEndPoint) return [];
    const defs = [
      { key: "targetHigh", label: "High", color: "#3ad1a1" },
      { key: "targetMean", label: "Mean", color: "#97a1bd" },
      { key: "targetMedian", label: "Median", color: "#5b8ef0" },
      { key: "targetLow", label: "Low", color: "#f07575" },
    ] as const;
    const out: Array<{ key: string; label: string; color: string; value: number }> = [];
    for (const item of defs) {
      const value = projectionEndPoint[item.key];
      if (typeof value === "number" && Number.isFinite(value)) {
        out.push({ key: item.key, label: item.label, color: item.color, value });
      }
    }
    return out;
  }, [projectionEndPoint]);
  const dcfBaseScenario = useMemo(() => {
    if (!dcfDetail?.scenarios?.length) return null;
    return dcfDetail.scenarios.find((item) => item.scenario_key === "base") ?? dcfDetail.scenarios[0];
  }, [dcfDetail]);
  const riBaseScenario = useMemo(() => {
    if (!riDetail?.scenarios?.length) return null;
    return riDetail.scenarios.find((item) => item.scenario_key === "base") ?? riDetail.scenarios[0];
  }, [riDetail]);
  const ddmBaseScenario = useMemo(() => {
    if (!ddmDetail?.scenarios?.length) return null;
    return ddmDetail.scenarios.find((item) => item.scenario_key === "base") ?? ddmDetail.scenarios[0];
  }, [ddmDetail]);
  const valuationAssumptionsForRecompute = useMemo<ValuationAssumptions>(
    () => ({
      dcf: {
        terminal_growth: 0.025,
        steady_state_growth: 0.025,
        explicit_years: 7,
        rf: 0.02,
        erp: 0.05,
        anchor_mode: "revenue_only",
        tv_method: "blended",
        tv_blend_weight: 0.65,
        reinvestment_blend_weight: 0.5,
        fallback_rev_spread: 0.1,
        fallback_eps_spread: 0.15,
        terminal_clip_buffer: terminalClipBuffer,
        quality_penalty_enabled: true,
      },
      ri: {
        explicit_years: 7,
        anchor_mode: "revenue_eps_consistency",
        terminal_method: "blended",
        terminal_blend_weight: 0.65,
        steady_state_growth: 0.025,
        long_run_roe: 0.12,
        long_run_payout: 0.35,
        payout_smoothing_weight: 0.6,
        fade_years_post_horizon: 8,
        fallback_rev_spread: 0.1,
        fallback_eps_spread: 0.15,
        terminal_clip_buffer: terminalClipBuffer,
        quality_penalty_enabled: true,
        cost_of_equity: null,
      },
      ddm: {
        explicit_years: 7,
        anchor_mode: "eps_payout_linked",
        coverage_mode: "hybrid_eps_payout",
        terminal_method: "two_stage_gordon",
        steady_state_growth: 0.025,
        long_run_payout: 0.35,
        payout_smoothing_weight: 0.6,
        initiation_payout_floor: 0.08,
        payout_cap: 0.9,
        fallback_eps_spread: 0.15,
        fallback_payout_spread: 0.1,
        terminal_clip_buffer: terminalClipBuffer,
        quality_penalty_enabled: true,
        cost_of_equity: null,
      },
      relative: { peer_set: "sector", multiples: ["forward_pe", "pb", "ev_ebitda"], cap_upside: 0.6 },
    }),
    [terminalClipBuffer]
  );

  if (!selected) {
    return (
      <div className="page-wrap" style={{ maxWidth: 920, margin: "0 auto" }}>
        <button className="back-btn" onClick={() => dispatch({ type: "go_page", page: "overview" })}>
          {"<- Back to Overview"}
        </button>
        <div className="card" style={{ marginTop: 24 }}>
          <h3>No holding selected</h3>
          <p>Upload holdings and pick a row from the overview table to open stock detail.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="page-wrap" style={{ maxWidth: 1100, margin: "0 auto" }}>
      <button className="back-btn" onClick={() => dispatch({ type: "go_page", page: "overview" })}>
        {"<- Back to Overview"}
      </button>

      <div
        className="row-between"
        style={{
          alignItems: "flex-start",
          marginTop: 24,
          marginBottom: 24,
          paddingBottom: 24,
          borderBottom: "1px solid var(--border)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <div
            style={{
              width: 44,
              height: 44,
              borderRadius: 10,
              background: "linear-gradient(135deg, #7b6ef6, #5b8ef0)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontFamily: "var(--sans)",
              fontWeight: 800,
              fontSize: 16,
            }}
          >
            {selected.symbol.slice(0, 2)}
          </div>
          <div>
            <div
              style={{
                fontFamily: "var(--sans)",
                fontSize: 24,
                fontWeight: 700,
                letterSpacing: "-0.03em",
              }}
            >
              {selected.symbol}
            </div>
            <div style={{ color: "var(--muted)", fontSize: 12, marginTop: 2 }}>
              {selected.name ?? "No company name available"}
            </div>
          </div>
        </div>

        <div style={{ textAlign: "right" }}>
          <div
            style={{
              fontFamily: "var(--sans)",
              fontSize: 28,
              fontWeight: 700,
              letterSpacing: "-0.03em",
            }}
          >
            {formatPrice(selected.market_value)}
          </div>
          <div style={{ marginTop: 4, color: "var(--muted)", fontSize: 13 }}>
            Weight {(selected.weight * 100).toFixed(2)}%
          </div>
        </div>
      </div>

      <div className="stock-tabs">
        {(["overview", "income", "balance", "cashflow", "ratios", "analyst", "risk", "exposure", "valuation", "corporate", "insider", "news"] as StockTabKey[]).map((candidate) => (
          <button
            key={candidate}
            className={`stock-tab ${tab === candidate ? "active" : ""}`}
            onClick={() => setTab(candidate)}
          >
            {candidate === "overview"
              ? `${stockDisplayName} Overview`
              : candidate === "income"
                ? "Income Statement"
                : candidate === "balance"
                  ? "Balance Sheet"
                  : candidate === "cashflow"
                    ? "Cash Flows"
                    : candidate === "ratios"
                      ? "Ratios & Metrics"
              : candidate === "analyst"
              ? "Analyst View"
              : candidate === "risk"
                ? "Risk"
                : candidate === "exposure"
                ? "Exposure"
                : candidate === "valuation"
                  ? "Valuation"
                  : candidate === "corporate"
                    ? "Corporate Actions"
                    : candidate === "insider"
                      ? "Insider Transactions"
                      : "News"}
          </button>
        ))}
      </div>

      {tab === "overview" && (
        <>
          <DataWarningBanner warnings={stockOverviewWarnings} title="Overview Feed Warnings" />
          {stockOverviewStatus === "loading" && (
            <div className="card" style={{ marginBottom: 14 }}>
              Loading stock overview...
            </div>
          )}
          {stockOverviewStatus === "error" && (
            <div className="card" style={{ marginBottom: 14, color: "var(--red)" }}>
              {stockOverviewError ?? "Failed to load stock overview."}
            </div>
          )}
          {stockOverviewStatus === "ready" && stockOverview == null && (
            <div className="card" style={{ marginBottom: 14, color: "var(--muted)" }}>
              No overview data available yet for this symbol.
            </div>
          )}
          {stockOverview && (
            <>
              <div className="grid-2" style={{ marginBottom: 14 }}>
                <div className="card">
                  <div className="kicker" style={{ marginBottom: 12 }}>
                    {stockDisplayName} Overview
                  </div>
                  <p style={{ marginBottom: 14 }}>
                    {stockOverview.description ?? "No company summary available from Yahoo Finance."}
                  </p>
                  <Row label="Industry" value={stockOverview.industry ?? "N/A"} />
                  <Row label="Sector" value={stockOverview.sector ?? "N/A"} />
                  <div
                    className="row-between"
                    style={{
                      padding: "10px 0",
                      borderBottom: "1px solid var(--border)",
                      alignItems: "flex-start",
                    }}
                  >
                    <span style={{ color: "var(--muted)", fontSize: 12 }}>Country</span>
                    <div style={{ textAlign: "right" }}>
                      <div style={{ fontSize: 13, fontWeight: 600 }}>{stockOverview.country ?? "N/A"}</div>
                      {stockOverview.full_address ? (
                        <button
                          className="inline-link"
                          style={{ fontSize: 10, marginTop: 4 }}
                          onClick={() => setShowFullAddress((prev) => !prev)}
                        >
                          {showFullAddress ? "Hide full address" : "See full address"}
                        </button>
                      ) : null}
                    </div>
                  </div>
                  {showFullAddress && stockOverview.full_address ? (
                    <div
                      style={{
                        marginTop: 8,
                        fontSize: 11,
                        lineHeight: 1.6,
                        color: "var(--muted)",
                        paddingBottom: 10,
                        borderBottom: "1px solid var(--border)",
                      }}
                    >
                      {stockOverview.full_address}
                    </div>
                  ) : null}
                  <div
                    className="row-between"
                    style={{
                      padding: "10px 0",
                      borderBottom: "1px solid var(--border)",
                      alignItems: "flex-start",
                    }}
                  >
                    <span style={{ color: "var(--muted)", fontSize: 12 }}>Website</span>
                    <div style={{ textAlign: "right" }}>
                      {stockOverview.website ? (
                        <a
                          href={stockOverview.website}
                          target="_blank"
                          rel="noreferrer"
                          style={{ color: "var(--accent)", fontSize: 12, textDecoration: "underline" }}
                        >
                          {stockOverview.website}
                        </a>
                      ) : (
                        <span style={{ fontSize: 13, fontWeight: 600 }}>N/A</span>
                      )}
                    </div>
                  </div>
                </div>

                <div className="card">
                  <div className="kicker" style={{ marginBottom: 12 }}>
                    Key Stats
                  </div>
                  <Row label="Market Cap" value={formatMarketCap(stockOverview.market_cap)} />
                  <Row
                    label="Current Price"
                    value={stockOverview.current_price != null ? formatPrice(stockOverview.current_price) : "N/A"}
                  />
                  <Row
                    label="Daily Return"
                    value={formatMaybePct(stockOverview.daily_return)}
                    valueColor={metricColor(stockOverview.daily_return)}
                  />
                  <Row
                    label="YTD Return"
                    value={formatMaybePct(stockOverview.ytd_return)}
                    valueColor={metricColor(stockOverview.ytd_return)}
                  />
                  <Row
                    label="1Y Return"
                    value={formatMaybePct(stockOverview.one_year_return)}
                    valueColor={metricColor(stockOverview.one_year_return)}
                  />
                  <Row
                    label="Beta"
                    value={stockOverview.beta != null ? stockOverview.beta.toFixed(2) : "N/A"}
                  />
                  <Row
                    label="P/E (TTM)"
                    value={stockOverview.pe != null ? stockOverview.pe.toFixed(2) : "N/A"}
                  />
                  <Row
                    label="Dividend Yield"
                    value={stockOverview.dividend_yield != null ? formatPercentValue(stockOverview.dividend_yield) : "N/A"}
                  />
                </div>
              </div>

              <div className="grid-2">
                <div className="card">
                  <div className="kicker" style={{ marginBottom: 12 }}>
                    Shareholder Breakdown
                  </div>
                  {stockOverview.shareholder_breakdown.length ? (
                    <>
                      <table className="table">
                        <thead>
                          <tr>
                            <th>Metric</th>
                            <th className="right">Value</th>
                          </tr>
                        </thead>
                        <tbody>
                          {stockOverview.shareholder_breakdown.map((row, index) => (
                            <tr key={`${row.label}-${index}`}>
                              <td>{row.label}</td>
                              <td className="right">{formatShareholderValue(row.label, row.value, row.display_value)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>

                      {shareholderPieData.length ? (
                        <div style={{ marginTop: 16 }}>
                          <div style={{ color: "var(--muted)", fontSize: 10, letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 8 }}>
                            Ownership Mix (%, excludes Institutions Float % Held)
                          </div>
                          <div
                            style={{
                              border: "1px solid var(--border)",
                              borderRadius: 10,
                              padding: "8px 10px 2px",
                              background: "linear-gradient(150deg, rgba(12,16,25,0.95), rgba(9,13,21,0.96))",
                            }}
                          >
                            <ResponsiveContainer width="100%" height={250}>
                              <PieChart>
                                <Pie
                                  data={shareholderPieData}
                                  dataKey="value"
                                  nameKey="name"
                                  cx="50%"
                                  cy="50%"
                                  innerRadius={62}
                                  outerRadius={88}
                                  paddingAngle={2}
                                  stroke="rgba(255,255,255,0.08)"
                                  strokeWidth={1}
                                  label={({ name, value }) => `${name} ${Number(value).toFixed(1)}%`}
                                  labelLine={false}
                                >
                                  {shareholderPieData.map((entry) => (
                                    <Cell key={`shareholder-pie-${entry.name}`} fill={entry.color} />
                                  ))}
                                </Pie>
                                <Tooltip
                                  formatter={(value: number) => `${value.toFixed(2)}%`}
                                  contentStyle={{
                                    background: "#11131d",
                                    border: "1px solid #2f3750",
                                    borderRadius: 10,
                                    color: "#eceef9",
                                  }}
                                />
                                <Legend
                                  iconType="circle"
                                  formatter={(value) => {
                                    const item = shareholderPieData.find((datum) => datum.name === value);
                                    return `${value} (${item ? item.value.toFixed(1) : "0.0"}%)`;
                                  }}
                                  wrapperStyle={{ fontSize: 11, color: "#97a1bd" }}
                                />
                              </PieChart>
                            </ResponsiveContainer>
                          </div>
                        </div>
                      ) : null}
                    </>
                  ) : (
                    <div style={{ color: "var(--muted)", fontSize: 12 }}>
                      No shareholder breakdown data available.
                    </div>
                  )}
                </div>

                <div className="card">
                  <div className="kicker" style={{ marginBottom: 12 }}>
                    Institutional Holders
                  </div>
                  {stockOverview.institutional_holders.length ? (
                    <div style={{ maxHeight: 380, overflow: "auto" }}>
                      <table className="table">
                        <thead>
                          <tr>
                            <th>Date</th>
                            <th>Holder</th>
                            <th className="right">% Held</th>
                            <th className="right">Shares</th>
                            <th className="right">Value</th>
                            <th className="right">% Change</th>
                          </tr>
                        </thead>
                        <tbody>
                          {stockOverview.institutional_holders.slice(0, 120).map((row, index) => (
                            <tr key={`${row.holder}-${row.date_reported ?? "none"}-${index}`}>
                              <td>{row.date_reported ?? "N/A"}</td>
                              <td>{row.holder}</td>
                              <td className="right">{row.pct_held != null ? formatPercentValue(row.pct_held) : "N/A"}</td>
                              <td className="right">{formatCount(row.shares)}</td>
                              <td className="right">{formatMarketCap(row.value)}</td>
                              <td className="right">{row.pct_change != null ? formatPercentValue(row.pct_change) : "N/A"}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div style={{ color: "var(--muted)", fontSize: 12 }}>
                      No institutional holder rows available.
                    </div>
                  )}
                </div>
              </div>
            </>
          )}
        </>
      )}

      {(tab === "income" || tab === "balance" || tab === "cashflow") && (
        <>
          <DataWarningBanner warnings={financialsWarnings} title="Financial Statement Warnings" />
          <div className="card">
            <div className="row-between" style={{ alignItems: "flex-start", marginBottom: 14, gap: 16, flexWrap: "wrap" }}>
              <div>
                <div className="kicker" style={{ marginBottom: 8 }}>
                  {tab === "income"
                    ? "Income Statement"
                    : tab === "balance"
                      ? "Balance Sheet"
                      : "Cash Flow Statement"}
                </div>
                <div style={{ color: "var(--muted)", fontSize: 12 }}>
                  {financialView === "level"
                    ? "Level view. Monetary items shown in USD millions where relevant."
                    : "Growth view. Period-over-period change for each line item."}
                </div>
              </div>
              <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                <div style={{ display: "flex", gap: 6 }}>
                  {(["annual", "quarterly"] as FinancialPeriod[]).map((candidate) => (
                    <button
                      key={candidate}
                      className={`range-btn ${financialPeriod === candidate ? "active" : ""}`}
                      onClick={() => setFinancialPeriod(candidate)}
                    >
                      {candidate === "annual" ? "Annual" : "Quarterly"}
                    </button>
                  ))}
                </div>
                <div style={{ display: "flex", gap: 6 }}>
                  {(["level", "growth"] as FinancialView[]).map((candidate) => (
                    <button
                      key={candidate}
                      className={`range-btn ${financialView === candidate ? "active" : ""}`}
                      onClick={() => setFinancialView(candidate)}
                    >
                      {candidate === "level" ? "Level" : "Growth"}
                    </button>
                  ))}
                </div>
                <button
                  className={`range-btn ${financialCommonOnly ? "active" : ""}`}
                  onClick={() => setFinancialCommonOnly((prev) => !prev)}
                >
                  Common Rows
                </button>
                <button
                  className="range-btn"
                  onClick={downloadCurrentFinancialCsv}
                  disabled={!filteredFinancialRows.length}
                  style={{ opacity: filteredFinancialRows.length ? 1 : 0.5, cursor: filteredFinancialRows.length ? "pointer" : "not-allowed" }}
                >
                  Download CSV
                </button>
              </div>
            </div>

            <div className="row-between" style={{ marginBottom: 12, alignItems: "center", gap: 12, flexWrap: "wrap" }}>
              <input
                type="text"
                value={financialSearch}
                onChange={(event) => setFinancialSearch(event.target.value)}
                placeholder="Search statement rows (e.g. revenue, ebit, cash)"
                style={{
                  minWidth: 280,
                  flex: "1 1 360px",
                  border: "1px solid var(--border-soft)",
                  background: "rgba(255,255,255,0.03)",
                  color: "var(--text)",
                  borderRadius: 8,
                  padding: "8px 10px",
                  fontSize: 12,
                }}
              />
              <div style={{ color: "var(--muted)", fontSize: 11 }}>
                Showing {filteredFinancialRows.length} of {financialRows.length} rows
              </div>
            </div>

            {financialsStatus === "loading" && (
              <div style={{ color: "var(--muted)", fontSize: 12 }}>Loading financial statements...</div>
            )}
            {financialsStatus === "error" && (
              <div style={{ color: "var(--red)", fontSize: 12 }}>
                {financialsError ?? "Failed to load financial statements."}
              </div>
            )}
            {financialsStatus === "ready" && !financialRows.length && (
              <div style={{ color: "var(--muted)", fontSize: 12 }}>
                No statement rows available for this selection.
              </div>
            )}
            {financialsStatus === "ready" && financialRows.length > 0 && filteredFinancialRows.length === 0 && (
              <div style={{ color: "var(--muted)", fontSize: 12 }}>
                No rows match the current search/filter.
              </div>
            )}

            {filteredFinancialRows.length ? (
              <div style={{ overflowX: "auto", maxHeight: 620 }}>
                <table className="table">
                  <thead>
                    <tr>
                      <th>Metric</th>
                      {financialValueColumns.map((column) => (
                        <th key={column} className="right">
                          {column}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {filteredFinancialRows.slice(0, 240).map((row, rowIdx) => {
                      const metric = typeof row.Metric === "string" ? row.Metric : "Metric";
                      return (
                        <tr key={`${metric}-${rowIdx}`}>
                          <td>{metric}</td>
                          {financialValueColumns.map((column) => {
                            const value = row[column];
                            return (
                              <td
                                key={`${metric}-${column}`}
                                className="right"
                                style={{ color: financialCellColor(value, financialView) }}
                              >
                                {formatFinancialCell(metric, value, financialView)}
                              </td>
                            );
                          })}
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ) : null}
          </div>
        </>
      )}

      {tab === "ratios" && (
        <>
          <DataWarningBanner warnings={ratiosWarnings} title="Financial Ratio Warnings" />
          <div className="card" style={{ marginBottom: 14 }}>
            <div className="row-between" style={{ alignItems: "flex-start", marginBottom: 14, gap: 16, flexWrap: "wrap" }}>
              <div>
                <div className="kicker" style={{ marginBottom: 8 }}>
                  Ratios & Metrics
                </div>
                <div style={{ color: "var(--muted)", fontSize: 12 }}>
                  Computed from income statement, balance sheet, cash flow, and market fields.
                </div>
              </div>
              <div style={{ display: "flex", gap: 6 }}>
                {(["annual", "quarterly"] as FinancialPeriod[]).map((candidate) => (
                  <button
                    key={candidate}
                    className={`range-btn ${financialPeriod === candidate ? "active" : ""}`}
                    onClick={() => setFinancialPeriod(candidate)}
                  >
                    {candidate === "annual" ? "Annual" : "Quarterly"}
                  </button>
                ))}
              </div>
            </div>

            <div className="row-between" style={{ marginBottom: 12, alignItems: "center", gap: 12, flexWrap: "wrap" }}>
              <input
                type="text"
                value={ratioSearch}
                onChange={(event) => setRatioSearch(event.target.value)}
                placeholder="Search ratios (e.g. margin, yield, leverage, growth)"
                style={{
                  minWidth: 280,
                  flex: "1 1 360px",
                  border: "1px solid var(--border-soft)",
                  background: "rgba(255,255,255,0.03)",
                  color: "var(--text)",
                  borderRadius: 8,
                  padding: "8px 10px",
                  fontSize: 12,
                }}
              />
              <div style={{ color: "var(--muted)", fontSize: 11 }}>
                Showing {filteredRatioMetrics.length} of {activeRatioMetrics.length} metrics
              </div>
            </div>

            {ratiosStatus === "loading" && (
              <div style={{ color: "var(--muted)", fontSize: 12 }}>Loading financial ratios...</div>
            )}
            {ratiosStatus === "error" && (
              <div style={{ color: "var(--red)", fontSize: 12 }}>
                {ratiosError ?? "Failed to load financial ratios."}
              </div>
            )}
            {ratiosStatus === "ready" && !activeRatioMetrics.length && (
              <div style={{ color: "var(--muted)", fontSize: 12 }}>
                No ratio data available for this symbol yet.
              </div>
            )}
            {ratiosStatus === "ready" && activeRatioMetrics.length > 0 && !filteredRatioMetrics.length && (
              <div style={{ color: "var(--muted)", fontSize: 12 }}>
                No ratios match the current search.
              </div>
            )}

            {highlightedRatios.length > 0 && (
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))",
                  gap: 10,
                  marginTop: 10,
                }}
              >
                {highlightedRatios.map((metric) => (
                  <div key={`highlight-${metric.key}`} className="surface-soft" style={{ padding: 12 }}>
                    <div style={{ color: "var(--muted)", fontSize: 10, letterSpacing: "0.06em", textTransform: "uppercase", marginBottom: 8 }}>
                      {metric.label}
                    </div>
                    <div style={{ fontFamily: "var(--sans)", fontWeight: 700, fontSize: 22, color: ratioMetricColor(metric) }}>
                      {formatRatioMetricValue(metric)}
                    </div>
                    <div style={{ marginTop: 6, fontSize: 11, color: "var(--muted)" }}>{metric.category}</div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {groupedRatioMetrics.length > 0 && (
            <div className="grid-2">
              {groupedRatioMetrics.map((group) => (
                <div key={group.category} className="card">
                  <div className="kicker" style={{ marginBottom: 12 }}>
                    {group.category}
                  </div>
                  <div style={{ overflowX: "auto" }}>
                    <table className="table">
                      <thead>
                        <tr>
                          <th>Metric</th>
                          <th className="right">Value</th>
                          <th>Definition</th>
                        </tr>
                      </thead>
                      <tbody>
                        {group.metrics.map((metric) => (
                          <tr key={`${group.category}-${metric.key}`}>
                            <td>
                              <div>{metric.label}</div>
                              <div style={{ color: "var(--muted)", fontSize: 10, marginTop: 4 }}>
                                Source: {metric.source}
                              </div>
                            </td>
                            <td className="right" style={{ color: ratioMetricColor(metric) }}>
                              {formatRatioMetricValue(metric)}
                            </td>
                            <td style={{ color: "var(--muted)", fontSize: 11 }}>{metric.description}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {tab === "analyst" && (
        <>
          <DataWarningBanner warnings={analystWarnings} title="Analyst Feed Warnings" />
          <div className="grid-2">
            <div className="card">
              <div className="kicker" style={{ marginBottom: 12 }}>
                Analyst Snapshot
              </div>
              <Row
                label="Feed Status"
                value={analystDetail?.status ?? analyst?.status ?? "no_data"}
                valueColor={(analystDetail?.status ?? analyst?.status) === "ok" ? "var(--green)" : "var(--yellow)"}
              />
              <Row
                label="Current Price"
                value={
                  analystSnapshot?.current != null
                    ? formatPrice(analystSnapshot.current)
                    : analyst?.current_price != null
                      ? formatPrice(analyst.current_price)
                      : "N/A"
                }
              />
              <Row
                label="Target Mean"
                value={
                  analystSnapshot?.mean != null
                    ? formatPrice(analystSnapshot.mean)
                    : analyst?.target_mean != null
                      ? formatPrice(analyst.target_mean)
                      : "N/A"
                }
                valueColor="var(--accent)"
              />
              <Row
                label="Target Median"
                value={analystSnapshot?.median != null ? formatPrice(analystSnapshot.median) : "N/A"}
              />
              <Row
                label="Target High / Low"
                value={`${analystSnapshot?.high != null ? formatPrice(analystSnapshot.high) : "N/A"} / ${
                  analystSnapshot?.low != null ? formatPrice(analystSnapshot.low) : "N/A"
                }`}
              />
              <Row
                label="Analyst Upside"
                value={formatMaybePct(analyst?.analyst_upside)}
                valueColor={
                  (analyst?.analyst_upside ?? 0) > 0
                    ? "var(--green)"
                    : (analyst?.analyst_upside ?? 0) < 0
                      ? "var(--red)"
                      : "var(--muted)"
                }
              />
            </div>

            <div className="card">
              <div className="kicker" style={{ marginBottom: 12 }}>
                Coverage Detail
              </div>
              <Row
                label="Recommendation"
                value={formatRatingLabel(analystCoverage?.recommendation_key ?? analyst?.recommendation_key)}
              />
              <Row
                label="Recommendation Mean"
                value={
                  analystCoverage?.recommendation_mean != null
                    ? analystCoverage.recommendation_mean.toFixed(2)
                    : analyst?.recommendation_mean != null
                      ? analyst.recommendation_mean.toFixed(2)
                      : "N/A"
                }
              />
              <Row
                label="Analyst Count"
                value={
                  analystCoverage?.analyst_count != null
                    ? String(analystCoverage.analyst_count)
                    : analyst?.analyst_count != null
                      ? String(analyst.analyst_count)
                      : "N/A"
                }
              />
              <Row
                label="As Of"
                value={analystSnapshot?.as_of_date ?? analyst?.as_of_date ?? "N/A"}
              />
            </div>
          </div>

          <div
            className="card"
            style={{
              marginTop: 14,
              maxWidth: 1080,
              marginLeft: "auto",
              marginRight: "auto",
            }}
          >
            <div className="kicker" style={{ marginBottom: 12, textAlign: "center" }}>
              Analyst Target Projection
            </div>
            <div style={{ color: "var(--muted)", fontSize: 11, marginBottom: 12, textAlign: "center" }}>
              1Y realized price path with 12M high/mean/median/low target trajectories starting today.
            </div>
            {analystTargetProjectionData.length >= 2 ? (
              <ResponsiveContainer width="100%" height={470}>
                <LineChart data={analystTargetProjectionData} margin={{ top: 6, right: 110, bottom: 6, left: 4 }}>
                  <CartesianGrid stroke="rgba(151,161,189,0.18)" strokeDasharray="3 4" />
                  <XAxis
                    dataKey="timestamp"
                    type="number"
                    scale="time"
                    domain={["dataMin", "dataMax"]}
                    tick={{ fill: "#97a1bd", fontSize: 11 }}
                    minTickGap={38}
                    tickFormatter={(value: number) => formatAxisDate(new Date(value).toISOString())}
                  />
                  <YAxis
                    domain={projectionYDomain ?? ["auto", "auto"]}
                    tick={{ fill: "#97a1bd", fontSize: 11 }}
                    tickFormatter={(value: number) => `$${Math.round(value)}`}
                  />
                  <Tooltip
                    labelFormatter={(value) =>
                      typeof value === "number"
                        ? formatAxisDate(new Date(value).toISOString())
                        : String(value)
                    }
                    formatter={(value, name) => {
                      const num =
                        typeof value === "number"
                          ? value
                          : typeof value === "string"
                            ? Number(value)
                            : NaN;
                      if (!Number.isFinite(num)) return "N/A";
                      const displayName = name === "Price (1Y)" ? "Price on day" : String(name);
                      return [formatPrice(num), displayName];
                    }}
                    contentStyle={{
                      background: "#11131d",
                      border: "1px solid #2f3750",
                      borderRadius: 10,
                      color: "#eceef9",
                    }}
                  />
                  <Legend />
                  <Line
                    type="monotone"
                    dataKey="price"
                    name="Price (1Y)"
                    stroke="#6f7cff"
                    strokeWidth={2.5}
                    dot={false}
                    connectNulls
                  />
                  <Line
                    type="linear"
                    dataKey="targetHigh"
                    name="High Target"
                    stroke="#3ad1a1"
                    strokeWidth={2.2}
                    strokeDasharray="6 5"
                    dot={{ r: 2.2 }}
                    connectNulls
                  />
                  <Line
                    type="linear"
                    dataKey="targetMean"
                    name="Mean Target"
                    stroke="#97a1bd"
                    strokeWidth={2.2}
                    strokeDasharray="6 5"
                    dot={{ r: 2.2 }}
                    connectNulls
                  />
                  <Line
                    type="linear"
                    dataKey="targetMedian"
                    name="Median Target"
                    stroke="#5b8ef0"
                    strokeWidth={2.2}
                    strokeDasharray="6 5"
                    dot={{ r: 2.2 }}
                    connectNulls
                  />
                  <Line
                    type="linear"
                    dataKey="targetLow"
                    name="Low Target"
                    stroke="#f07575"
                    strokeWidth={2.2}
                    strokeDasharray="6 5"
                    dot={{ r: 2.2 }}
                    connectNulls
                  />
                  {projectionEndPoint &&
                    projectionTargetCallouts.map((item) => (
                      <ReferenceDot
                        key={item.key}
                        x={projectionEndPoint.timestamp}
                        y={item.value}
                        r={4.5}
                        fill={item.color}
                        stroke="#0f1322"
                        strokeWidth={1.2}
                        ifOverflow="extendDomain"
                        label={{
                          value: `${item.label} ${formatPrice(item.value)}`,
                          fill: item.color,
                          position: "insideRight",
                          fontSize: 11,
                          fontWeight: 600,
                        }}
                      />
                    ))}
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div style={{ color: "var(--muted)", fontSize: 12 }}>
                Not enough price/target data to draw the projection chart yet.
              </div>
            )}
          </div>

          <div className="grid-2" style={{ marginTop: 14 }}>
            <div className="card">
              <div className="kicker" style={{ marginBottom: 10 }}>
                Potential Returns (By Target)
              </div>
              {analystTargetChart.length ? (
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={analystTargetChart} margin={{ top: 6, right: 12, bottom: 6, left: 0 }}>
                    <CartesianGrid stroke="rgba(151,161,189,0.18)" strokeDasharray="3 4" />
                    <XAxis dataKey="label" tick={{ fill: "#97a1bd", fontSize: 10 }} />
                    <YAxis
                      tick={{ fill: "#97a1bd", fontSize: 10 }}
                      tickFormatter={(value: number) => `${value.toFixed(0)}%`}
                    />
                    <Tooltip
                      formatter={(value: number) => `${value.toFixed(2)}%`}
                      contentStyle={{
                        background: "#11131d",
                        border: "1px solid #2f3750",
                        borderRadius: 10,
                        color: "#eceef9",
                      }}
                    />
                    <Bar dataKey="returnPct" radius={[4, 4, 0, 0]}>
                      {analystTargetChart.map((item) => (
                        <Cell
                          key={item.label}
                          fill={item.returnPct >= 0 ? "rgba(58,209,161,0.9)" : "rgba(240,117,117,0.9)"}
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div style={{ color: "var(--muted)", fontSize: 12 }}>
                  Potential-return scenarios are unavailable for this symbol.
                </div>
              )}
            </div>

            <div className="card">
              <div className="row-between" style={{ marginBottom: 10 }}>
                <div className="kicker" style={{ marginBottom: 0 }}>
                  Current Recommendations
                </div>
                <button
                  className="inline-link"
                  onClick={() => dispatch({ type: "open_analyst_history", sym: selected.symbol })}
                >
                  see more
                </button>
              </div>
              {analystRecommendationChart.length ? (
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={analystRecommendationChart} margin={{ top: 6, right: 12, bottom: 6, left: 0 }}>
                    <CartesianGrid stroke="rgba(151,161,189,0.18)" strokeDasharray="3 4" />
                    <XAxis dataKey="label" tick={{ fill: "#97a1bd", fontSize: 10 }} />
                    <YAxis tick={{ fill: "#97a1bd", fontSize: 10 }} />
                    <Tooltip
                      contentStyle={{
                        background: "#11131d",
                        border: "1px solid #2f3750",
                        borderRadius: 10,
                        color: "#eceef9",
                      }}
                    />
                    <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                      {analystRecommendationChart.map((item) => (
                        <Cell key={item.label} fill={item.color} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div style={{ color: "var(--muted)", fontSize: 12 }}>
                  Current recommendation counts are unavailable.
                </div>
              )}
            </div>
          </div>

          <div className="grid-2" style={{ marginTop: 14 }}>
            <div className="card">
              <button className="btn-secondary" onClick={() => setShowRevenue((prev) => !prev)}>
                {showRevenue ? "Hide Revenue" : "Revenue"}
              </button>
              {showRevenue && (
                <div style={{ marginTop: 12 }}>
                  <div className="kicker" style={{ marginBottom: 8 }}>
                    Revenue Estimate (USD millions)
                  </div>
                  <div style={{ color: "var(--muted)", fontSize: 11, marginBottom: 8 }}>
                    Monetary columns are displayed in USD millions.
                  </div>
                  <DynamicTable rows={revenueEstimateRows} />
                  {(analystDetail?.growth_estimates ?? []).length > 0 && (
                    <>
                      <div className="kicker" style={{ marginTop: 14, marginBottom: 8 }}>
                        Growth Estimates (%)
                      </div>
                      <DynamicTable rows={growthEstimateRows} />
                    </>
                  )}
                </div>
              )}
            </div>

            <div className="card">
              <button className="btn-secondary" onClick={() => setShowEarnings((prev) => !prev)}>
                {showEarnings ? "Hide Earnings" : "Earnings"}
              </button>
              {showEarnings && (
                <div style={{ marginTop: 12 }}>
                  <div className="kicker" style={{ marginBottom: 8 }}>
                    Earnings Estimate
                  </div>
                  <DynamicTable rows={analystDetail?.earnings_estimate ?? []} />
                  <div className="kicker" style={{ marginTop: 14, marginBottom: 8 }}>
                    EPS Trend
                  </div>
                  <DynamicTable rows={analystDetail?.eps_trend ?? []} />
                  <div className="kicker" style={{ marginTop: 14, marginBottom: 8 }}>
                    EPS Revisions
                  </div>
                  <DynamicTable rows={analystDetail?.eps_revisions ?? []} />
                </div>
              )}
            </div>
          </div>

          <DataWarningBanner warnings={eventsWarnings} title="Analyst Revision Feed Warnings" />
          {eventsStatus === "loading" && (
            <div className="card" style={{ marginTop: 14 }}>
              Loading analyst revisions...
            </div>
          )}
          {eventsStatus === "error" && (
            <div className="card" style={{ marginTop: 14, color: "var(--red)" }}>
              {eventsError ?? "Failed to load analyst revisions."}
            </div>
          )}
          <div className="card" ref={analystRevisionsRef} style={{ marginTop: 14 }}>
            <div className="kicker" style={{ marginBottom: 12 }}>
              Analyst Revisions
            </div>
            {analystRevisions.length ? (
              <table className="table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Firm</th>
                    <th>Action</th>
                    <th>To / From</th>
                    <th className="right">PT (Current / Prior)</th>
                  </tr>
                </thead>
                <tbody>
                  {analystRevisions.slice(0, 120).map((row, index) => (
                    <tr key={`${row.date}-${index}`}>
                      <td>{new Date(row.date).toLocaleDateString()}</td>
                      <td>{row.firm ?? "N/A"}</td>
                      <td>{formatRevisionAction(row.action)}</td>
                      <td>
                        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                          <RatingBadge value={row.to_grade} />
                          <span style={{ color: "var(--muted)", fontSize: 11 }}>/</span>
                          <RatingBadge value={row.from_grade} />
                        </div>
                      </td>
                      <td className="right">
                        {row.current_price_target != null || row.prior_price_target != null
                          ? `${row.current_price_target?.toFixed(2) ?? "N/A"} / ${row.prior_price_target?.toFixed(2) ?? "N/A"}`
                          : "N/A"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div style={{ color: "var(--muted)", fontSize: 12 }}>
                No analyst revision rows available yet for this symbol.
              </div>
            )}
          </div>
          <div style={{ marginTop: 14 }}>
            <InsightBox text="Analyst consensus now comes from the live Yahoo-backed snapshot cache and is refreshed on manual/nightly runs." />
          </div>
        </>
      )}

      {tab === "risk" && (
        <>
          <div className="grid-3">
            <div className="card" style={{ padding: 16 }}>
              <div className="kicker" style={{ marginBottom: 8 }}>
                Position Risk Share
              </div>
              <div
                style={{
                  fontFamily: "var(--sans)",
                  fontSize: 28,
                  fontWeight: 700,
                  color: "var(--red)",
                  marginBottom: 4,
                }}
              >
                {contribution ? formatPercent(contribution.pct_total_risk * 100) : "N/A"}
              </div>
              <div style={{ color: "var(--muted)", fontSize: 11 }}>
                {contribution
                  ? "Percentage contribution to total portfolio volatility."
                  : "Insufficient covariance history. Run refresh after uploading holdings."}
              </div>
            </div>

            <div className="card" style={{ padding: 16 }}>
              <div className="kicker" style={{ marginBottom: 8 }}>
                Portfolio VaR 95%
              </div>
              <div
                style={{
                  fontFamily: "var(--sans)",
                  fontSize: 28,
                  fontWeight: 700,
                  color: "var(--yellow)",
                  marginBottom: 4,
                }}
              >
                {riskMetrics ? formatPercent(riskMetrics.var_95 * 100) : "N/A"}
              </div>
              <div style={{ color: "var(--muted)", fontSize: 11 }}>
                {riskMetrics ? "Historical one-day VaR." : "No risk snapshot yet."}
              </div>
            </div>

            <div className="card" style={{ padding: 16 }}>
              <div className="kicker" style={{ marginBottom: 8 }}>
                Portfolio Beta
              </div>
              <div
                style={{
                  fontFamily: "var(--sans)",
                  fontSize: 28,
                  fontWeight: 700,
                  color: "var(--green)",
                  marginBottom: 4,
                }}
              >
                {riskMetrics ? riskMetrics.beta.toFixed(2) : "N/A"}
              </div>
              <div style={{ color: "var(--muted)", fontSize: 11 }}>
                Versus {dataState.overview?.portfolio.benchmark_symbol ?? "SPY"}.
              </div>
            </div>
          </div>

          <div className="card" style={{ marginTop: 14 }}>
            <div className="kicker" style={{ marginBottom: 12 }}>
              Extended Risk + Performance Metrics
            </div>
            <div className="grid-3">
              <Row label="Adjusted Sharpe" value={fmtNumber(extendedStock?.adjusted_sharpe)} />
              <Row label="Information Ratio" value={fmtNumber(extendedStock?.information_ratio)} />
              <Row label="Sortino" value={fmtNumber(extendedStock?.sortino)} />
              <Row label="Calmar" value={fmtNumber(extendedStock?.calmar)} />
              <Row label="Omega" value={fmtNumber(extendedStock?.omega)} />
              <Row label="RAROC" value={fmtNumber(extendedStock?.raroc)} />
              <Row label="Skewness" value={fmtNumber(extendedStock?.skewness)} />
              <Row label="Kurtosis" value={fmtNumber(extendedStock?.kurtosis)} />
              <Row label="% Positive Periods" value={fmtPct(extendedStock?.percent_positive_periods)} />
            </div>
            <div style={{ marginTop: 10, fontSize: 12, color: "var(--muted)", lineHeight: 1.8 }}>
              Hist VaR95 {fmtPct(extendedStockVar?.historical_95)} | Hist CVaR95{" "}
              {fmtPct(extendedStockVar?.cvar_historical_95)} | Max DD{" "}
              {fmtPct(extendedStockDrawdown?.max)}
            </div>
            <div style={{ marginTop: 6, fontSize: 12, color: "var(--muted)", lineHeight: 1.8 }}>
              Upside Capture {fmtNumber(extendedStockCapture?.upside_capture_ratio)} | Downside Capture{" "}
              {fmtNumber(extendedStockCapture?.downside_capture_ratio)} | Alpha{" "}
              {fmtPct(extendedStock?.historical_alpha)}
            </div>
          </div>

          <div className="card" style={{ marginTop: 14 }}>
            <div className="kicker" style={{ marginBottom: 10 }}>
              Risk Contribution Leaderboard
            </div>
            {factorBars.length ? (
              <ResponsiveContainer width="100%" height={240}>
                <BarChart data={factorBars} layout="vertical" margin={{ top: 6, right: 16, bottom: 6, left: 16 }}>
                  <XAxis type="number" tick={{ fill: "#6b6b8a", fontSize: 10 }} />
                  <YAxis dataKey="name" type="category" width={90} tick={{ fill: "#e8e8f0", fontSize: 11 }} />
                  <Tooltip
                    cursor={{ fill: "rgba(123,110,246,0.08)" }}
                    contentStyle={{ background: "#111118", border: "1px solid #1e1e2e" }}
                    formatter={(value: number) => [`${(value * 100).toFixed(2)}%`, "Risk share"]}
                  />
                  <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                    {factorBars.map((item) => (
                      <Cell key={item.name} fill={item.color} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div style={{ color: "var(--muted)", fontSize: 12 }}>
                No contribution series yet. Use refresh once price history is cached.
              </div>
            )}
          </div>
        </>
      )}

      {tab === "exposure" && (
        <>
          <div className="grid-2">
            <div className="card">
              <div className="kicker" style={{ marginBottom: 12 }}>
                Position Exposure
              </div>
              <Row label="Asset Type" value={selected.asset_type ?? "Unclassified"} />
              <Row label="Currency" value={selected.currency} />
              <Row label="Portfolio Weight" value={`${(selected.weight * 100).toFixed(2)}%`} />
              <Row label="Sector" value={(extendedFundamentalCore?.sector as string | undefined) ?? "N/A"} />
              <Row
                label="Industry"
                value={(extendedFundamentalCore?.industry as string | undefined) ?? "N/A"}
              />
              <Row
                label="Top-3 concentration"
                value={riskMetrics ? `${(riskMetrics.top3_weight_share * 100).toFixed(2)}%` : "N/A"}
              />
              <Row label="HHI" value={riskMetrics ? riskMetrics.hhi.toFixed(4) : "N/A"} />
            </div>
            <ExposureDivergingChart
              title="Factor Exposures (Stock vs Portfolio)"
              data={factorExposureSeries}
              stockLabel={selected.symbol}
              idPrefix="factor-exp"
            />
          </div>
          <div style={{ marginTop: 14 }}>
            <ExposureDivergingChart
              title="Macro Proxy Exposures (Stock vs Portfolio vs Benchmark)"
              data={macroExposureSeries}
              stockLabel={selected.symbol}
              idPrefix="macro-exp"
              benchmarkLabel={dataState.overview?.portfolio.benchmark_symbol ?? "SPY"}
            />
          </div>
          <div style={{ marginTop: 14 }}>
            <InsightBox text="Each bar is centered on 0 so positive and negative regime sensitivity is immediately visible for both this stock and the overall portfolio." />
          </div>
        </>
      )}

      {tab === "valuation" && (
        <>
          <DataWarningBanner warnings={valuation?.warnings ?? []} title="Valuation Warnings" />
          <div className="grid-2">
            <div className="card">
              <div className="kicker" style={{ marginBottom: 12 }}>
                Model Outputs
              </div>
              <Row
                label="Model status"
                value={valuation?.model_status ?? "no_data"}
                valueColor={valuation?.model_status === "full" ? "var(--green)" : "var(--yellow)"}
              />
              <Row
                label="Analyst Upside"
                value={formatMaybePct(valuation?.analyst_upside)}
              />
              <Row
                label="Relative Fair Value"
                value={valuation?.relative_fair_value != null ? formatPrice(valuation.relative_fair_value) : "N/A"}
              />
              <Row
                label="Relative Upside"
                value={formatMaybePct(valuation?.relative_upside)}
              />
              <Row
                label="Analyst Target Return"
                value={fmtPct(extendedStockFundamentals?.analyst_target_return)}
              />
              <Row
                label="Earnings Growth"
                value={fmtPct(extendedStockFundamentals?.earnings_growth)}
              />
              <Row
                label="Revenue Growth"
                value={fmtPct(extendedStockFundamentals?.revenue_growth)}
              />
              <Row
                label="Dividend Yield"
                value={fmtPct(extendedStockFundamentals?.dividend_yield)}
              />
              <Row
                label="Earnings Estimates"
                value={earningsEstimates ? `${Object.keys(earningsEstimates).length} rows` : "N/A"}
              />
              <Row
                label="Revenue Estimates"
                value={revenueEstimates ? `${Object.keys(revenueEstimates).length} rows` : "N/A"}
              />
              <Row
                label="Upgrades/Downgrades (6m)"
                value={`${fmtNumber(extendedRatings?.upgrades_6m, 0)} / ${fmtNumber(
                  extendedRatings?.downgrades_6m,
                  0
                )}`}
              />
              <Row
                label="Margins (G/O/N)"
                value={`${fmtPct(extendedMargins?.gross)} / ${fmtPct(
                  extendedMargins?.operating
                )} / ${fmtPct(extendedMargins?.net)}`}
              />
              <Row
                label="Confidence Range"
                value={
                  valuation?.confidence_low != null && valuation?.confidence_high != null
                    ? `${formatPrice(valuation.confidence_low)} - ${formatPrice(valuation.confidence_high)}`
                    : "N/A"
                }
              />
              <Row
                label="RSI / MACD"
                value={`${fmtNumber(extendedStockTechnicals?.rsi_14)} / ${fmtNumber(
                  extendedStockTechnicals?.macd
                )}`}
              />
            </div>

            <div className="card">
              <div className="kicker" style={{ marginBottom: 12 }}>
                Portfolio Valuation Context
              </div>
              <ValuationCompass
                weightedAnalystUpside={dataState.valuationOverview?.weighted_analyst_upside}
                weightedDcfUpside={dataState.valuationOverview?.weighted_dcf_upside}
                weightedRiUpside={dataState.valuationOverview?.weighted_ri_upside}
                weightedDdmUpside={dataState.valuationOverview?.weighted_ddm_upside}
                weightedRelativeUpside={dataState.valuationOverview?.weighted_relative_upside}
                coverageRatio={dataState.valuationOverview?.coverage_ratio}
                overvaluedWeight={dataState.valuationOverview?.overvalued_weight}
                undervaluedWeight={dataState.valuationOverview?.undervalued_weight}
              />
              <div style={{ marginTop: 12, marginBottom: 8 }}>
                <div className="kicker" style={{ marginBottom: 6 }}>
                  Terminal Growth Safety Buffer (x): {terminalClipBuffer.toFixed(3)}
                </div>
                <input
                  type="range"
                  min={0}
                  max={0.1}
                  step={0.001}
                  value={terminalClipBuffer}
                  onChange={(event) => {
                    const parsed = Number(event.target.value);
                    if (Number.isFinite(parsed)) {
                      setTerminalClipBuffer(Math.min(0.1, Math.max(0, parsed)));
                    }
                  }}
                  style={{ width: "100%" }}
                />
                <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 6, lineHeight: 1.45 }}>
                  Terminal growth is estimated from analyst and historical growth signals, then clipped for
                  conservatism. DCF enforces <code>g {"<="} WACC - x</code>; RI and DDM enforce{" "}
                  <code>g {"<="} Cost of Equity - x</code>. Higher <code>x</code> means a more conservative
                  terminal assumption.
                </div>
              </div>
              <div style={{ marginTop: 12, display: "flex", gap: 8, flexWrap: "wrap" }}>
                <button
                  className="btn-secondary"
                  onClick={() => void recomputeValuations(valuationAssumptionsForRecompute)}
                >
                  Recompute Portfolio Valuation
                </button>
                <button className="btn-secondary" onClick={() => void runManualRefresh()}>
                  Refresh Risk + Prices
                </button>
              </div>
            </div>
          </div>

          <div className="card" style={{ marginTop: 14 }}>
            <div className="kicker" style={{ marginBottom: 12 }}>
              DCF Diagnostics
            </div>
            <Row label="Model Version" value={dcfModelVersion ?? "N/A"} />
            <Row
              label="Quality Score"
              value={dcfQualityScore != null ? `${dcfQualityScore.toFixed(1)} / 100` : "N/A"}
              valueColor={dcfQualityScore != null && dcfQualityScore >= 70 ? "var(--green)" : "var(--yellow)"}
            />
            <Row label="Anchor Mode" value={dcfDetail?.anchor_mode ?? "revenue_only"} />
            <Row
              label="Revenue Fit (FY0 / FY1)"
              value={`${fmtPct(dcfAnchorSummary?.rev_fit_t1)} / ${fmtPct(dcfAnchorSummary?.rev_fit_t2)}`}
            />
            <Row
              label="EPS Fit (FY0 / FY1)"
              value={`${fmtPct(dcfAnchorSummary?.eps_fit_t1)} / ${fmtPct(dcfAnchorSummary?.eps_fit_t2)}`}
            />
            <Row
              label="TV Blend (Gordon Weight)"
              value={fmtPct(dcfTvSummary?.tv_blend_weight)}
            />
            <Row
              label="Terminal PV Share"
              value={fmtPct(dcfTvSummary?.base_tv_pv_share)}
              valueColor={
                (asNumber(dcfTvSummary?.base_tv_pv_share) ?? 0) > 0.85 ? "var(--yellow)" : "var(--muted)"
              }
            />
            <Row
              label="WACC / Terminal Growth"
              value={`${fmtPct(dcfAssumptionsUsed?.wacc)} / ${fmtPct(dcfAssumptionsUsed?.terminal_growth)}`}
            />
            <div style={{ marginTop: 12, display: "flex", gap: 8, flexWrap: "wrap" }}>
              <button className="btn-secondary" onClick={() => setShowDcfDetail((prev) => !prev)}>
                {showDcfDetail ? "Hide DCF Detail" : "See DCF Detail"}
              </button>
            </div>

            {showDcfDetail && (
              <div style={{ marginTop: 12 }}>
                <DataWarningBanner warnings={dcfDetail?.warnings ?? []} title="DCF Detail Warnings" />
                {dcfDetailStatus === "loading" && (
                  <div style={{ color: "var(--muted)", fontSize: 12 }}>Loading DCF detail...</div>
                )}
                {dcfDetailStatus === "error" && (
                  <div style={{ color: "var(--red)", fontSize: 12 }}>
                    {dcfDetailError ?? "Failed to load DCF detail."}
                  </div>
                )}
                {dcfDetailStatus === "ready" && dcfDetail != null && (
                  <>
                    <div style={{ overflowX: "auto", marginBottom: 10 }}>
                      <table className="table">
                        <thead>
                          <tr>
                            <th>Scenario</th>
                            <th className="right">Fair Value</th>
                            <th className="right">Upside</th>
                            <th className="right">WACC</th>
                            <th className="right">Terminal g</th>
                            <th className="right">TV PV Share</th>
                          </tr>
                        </thead>
                        <tbody>
                          {dcfDetail.scenarios.map((scenario) => {
                            const diag = asRecord(scenario.diagnostics);
                            return (
                              <tr key={scenario.scenario_key}>
                                <td style={{ textTransform: "capitalize" }}>{scenario.scenario_key}</td>
                                <td className="right">
                                  {asNumber(diag?.fair_value) != null ? formatPrice(asNumber(diag?.fair_value) ?? 0) : "N/A"}
                                </td>
                                <td className="right">{fmtPct(diag?.upside)}</td>
                                <td className="right">{fmtPct(diag?.wacc)}</td>
                                <td className="right">{fmtPct(diag?.terminal_growth)}</td>
                                <td className="right">{fmtPct(diag?.tv_pv_share)}</td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>

                    {dcfBaseScenario?.forecast?.length ? (
                      <div style={{ overflowX: "auto" }}>
                        <div className="kicker" style={{ marginBottom: 8 }}>
                          Base Scenario Forecast
                        </div>
                        <table className="table">
                          <thead>
                            <tr>
                              <th>Year</th>
                              <th className="right">Revenue</th>
                              <th className="right">EBIT Margin</th>
                              <th className="right">NOPAT</th>
                              <th className="right">FCFF</th>
                              <th className="right">EPS Model / Anchor</th>
                            </tr>
                          </thead>
                          <tbody>
                            {dcfBaseScenario.forecast.slice(0, 10).map((row, idx) => {
                              const item = asRecord(row);
                              const metric = `Y${String(asNumber(item?.year) ?? idx + 1)}`;
                              const epsModel = asNumber(item?.eps_model);
                              const epsAnchor = asNumber(item?.eps_anchor);
                              return (
                                <tr key={`${metric}-${idx}`}>
                                  <td>{metric}</td>
                                  <td className="right">
                                    {asNumber(item?.revenue) != null ? formatPrice(asNumber(item?.revenue) ?? 0) : "N/A"}
                                  </td>
                                  <td className="right">{fmtPct(item?.ebit_margin)}</td>
                                  <td className="right">
                                    {asNumber(item?.nopat) != null ? formatPrice(asNumber(item?.nopat) ?? 0) : "N/A"}
                                  </td>
                                  <td className="right">
                                    {asNumber(item?.fcff) != null ? formatPrice(asNumber(item?.fcff) ?? 0) : "N/A"}
                                  </td>
                                  <td className="right">
                                    {epsModel != null ? epsModel.toFixed(2) : "N/A"}
                                    {" / "}
                                    {epsAnchor != null ? epsAnchor.toFixed(2) : "N/A"}
                                  </td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <div style={{ color: "var(--muted)", fontSize: 12 }}>No DCF forecast rows available.</div>
                    )}
                  </>
                )}
              </div>
            )}
          </div>

          <div className="card" style={{ marginTop: 14 }}>
            <div className="kicker" style={{ marginBottom: 12 }}>
              RI Diagnostics
            </div>
            <Row label="Model Version" value={riModelVersion ?? "N/A"} />
            <Row
              label="Quality Score"
              value={riQualityScore != null ? `${riQualityScore.toFixed(1)} / 100` : "N/A"}
              valueColor={riQualityScore != null && riQualityScore >= 70 ? "var(--green)" : "var(--yellow)"}
            />
            <Row label="Anchor Mode" value={riDetail?.anchor_mode ?? "revenue_eps_consistency"} />
            <Row
              label="Revenue Fit (FY0 / FY1)"
              value={`${fmtPct(riAnchorSummary?.rev_fit_t1)} / ${fmtPct(riAnchorSummary?.rev_fit_t2)}`}
            />
            <Row
              label="EPS Fit (FY0 / FY1)"
              value={`${fmtPct(riAnchorSummary?.eps_fit_t1)} / ${fmtPct(riAnchorSummary?.eps_fit_t2)}`}
            />
            <Row
              label="Terminal Blend (Gordon Weight)"
              value={fmtPct(riTerminalSummary?.terminal_blend_weight)}
            />
            <Row
              label="Terminal PV Share"
              value={fmtPct(riTerminalSummary?.base_tv_pv_share)}
              valueColor={
                (asNumber(riTerminalSummary?.base_tv_pv_share) ?? 0) > 0.85 ? "var(--yellow)" : "var(--muted)"
              }
            />
            <Row
              label="Cost of Equity / Terminal Growth"
              value={`${fmtPct(riAssumptionsUsed?.cost_of_equity)} / ${fmtPct(riAssumptionsUsed?.terminal_growth)}`}
            />

            <div style={{ marginTop: 12, display: "flex", gap: 8, flexWrap: "wrap" }}>
              <button className="btn-secondary" onClick={() => setShowRiDetail((prev) => !prev)}>
                {showRiDetail ? "Hide RI Detail" : "See RI Detail"}
              </button>
            </div>

            {showRiDetail && (
              <div style={{ marginTop: 12 }}>
                <DataWarningBanner warnings={riDetail?.warnings ?? []} title="RI Detail Warnings" />
                {riDetailStatus === "loading" && (
                  <div style={{ color: "var(--muted)", fontSize: 12 }}>Loading RI detail...</div>
                )}
                {riDetailStatus === "error" && (
                  <div style={{ color: "var(--red)", fontSize: 12 }}>
                    {riDetailError ?? "Failed to load RI detail."}
                  </div>
                )}
                {riDetailStatus === "ready" && riDetail != null && (
                  <>
                    <div style={{ overflowX: "auto", marginBottom: 10 }}>
                      <table className="table">
                        <thead>
                          <tr>
                            <th>Scenario</th>
                            <th className="right">Fair Value</th>
                            <th className="right">Upside</th>
                            <th className="right">Cost of Equity</th>
                            <th className="right">Terminal g</th>
                            <th className="right">TV PV Share</th>
                          </tr>
                        </thead>
                        <tbody>
                          {riDetail.scenarios.map((scenario) => {
                            const diag = asRecord(scenario.diagnostics);
                            return (
                              <tr key={scenario.scenario_key}>
                                <td style={{ textTransform: "capitalize" }}>{scenario.scenario_key}</td>
                                <td className="right">
                                  {asNumber(diag?.fair_value) != null ? formatPrice(asNumber(diag?.fair_value) ?? 0) : "N/A"}
                                </td>
                                <td className="right">{fmtPct(diag?.upside)}</td>
                                <td className="right">{fmtPct(diag?.cost_of_equity)}</td>
                                <td className="right">{fmtPct(diag?.terminal_growth)}</td>
                                <td className="right">{fmtPct(diag?.tv_pv_share)}</td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>

                    {riBaseScenario?.forecast?.length ? (
                      <div style={{ overflowX: "auto" }}>
                        <div className="kicker" style={{ marginBottom: 8 }}>
                          Base Scenario Forecast
                        </div>
                        <table className="table">
                          <thead>
                            <tr>
                              <th>Year</th>
                              <th className="right">Revenue</th>
                              <th className="right">Net Income</th>
                              <th className="right">Payout</th>
                              <th className="right">Book Value</th>
                              <th className="right">Residual Income</th>
                              <th className="right">ROE</th>
                            </tr>
                          </thead>
                          <tbody>
                            {riBaseScenario.forecast.slice(0, 12).map((row, idx) => {
                              const item = asRecord(row);
                              const metric = `Y${String(asNumber(item?.year) ?? idx + 1)}`;
                              return (
                                <tr key={`${metric}-${idx}`}>
                                  <td>{metric}</td>
                                  <td className="right">
                                    {asNumber(item?.revenue) != null ? formatPrice(asNumber(item?.revenue) ?? 0) : "N/A"}
                                  </td>
                                  <td className="right">
                                    {asNumber(item?.net_income) != null ? formatPrice(asNumber(item?.net_income) ?? 0) : "N/A"}
                                  </td>
                                  <td className="right">{fmtPct(item?.payout)}</td>
                                  <td className="right">
                                    {asNumber(item?.book_value) != null ? formatPrice(asNumber(item?.book_value) ?? 0) : "N/A"}
                                  </td>
                                  <td className="right">
                                    {asNumber(item?.residual_income) != null
                                      ? formatPrice(asNumber(item?.residual_income) ?? 0)
                                      : "N/A"}
                                  </td>
                                  <td className="right">{fmtPct(item?.roe_model)}</td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <div style={{ color: "var(--muted)", fontSize: 12 }}>No RI forecast rows available.</div>
                    )}
                  </>
                )}
              </div>
            )}
          </div>

          <div className="card" style={{ marginTop: 14 }}>
            <div className="kicker" style={{ marginBottom: 12 }}>
              DDM Diagnostics
            </div>
            <Row label="Model Version" value={ddmModelVersion ?? "N/A"} />
            <Row
              label="Quality Score"
              value={ddmQualityScore != null ? `${ddmQualityScore.toFixed(1)} / 100` : "N/A"}
              valueColor={ddmQualityScore != null && ddmQualityScore >= 70 ? "var(--green)" : "var(--yellow)"}
            />
            <Row label="Anchor Mode" value={ddmDetail?.anchor_mode ?? "eps_payout_linked"} />
            <Row label="Coverage Mode" value={ddmDetail?.coverage_mode ?? ddmCoverageMode ?? "hybrid_eps_payout"} />
            <Row
              label="EPS Fit (FY0 / FY1)"
              value={`${fmtPct(ddmAnchorSummary?.eps_fit_t1)} / ${fmtPct(ddmAnchorSummary?.eps_fit_t2)}`}
            />
            <Row
              label="Payout Violations / Margin Outliers"
              value={`${fmtNumber(ddmAnchorSummary?.payout_violations, 0)} / ${fmtNumber(
                ddmAnchorSummary?.margin_outliers,
                0
              )}`}
            />
            <Row
              label="Terminal PV Share"
              value={fmtPct(ddmTerminalSummary?.base_tv_pv_share)}
              valueColor={
                (asNumber(ddmTerminalSummary?.base_tv_pv_share) ?? 0) > 0.85 ? "var(--yellow)" : "var(--muted)"
              }
            />
            <Row
              label="Cost of Equity / Terminal Growth"
              value={`${fmtPct(ddmAssumptionsUsed?.cost_of_equity)} / ${fmtPct(ddmAssumptionsUsed?.terminal_growth)}`}
            />
            <div style={{ marginTop: 12, display: "flex", gap: 8, flexWrap: "wrap" }}>
              <button className="btn-secondary" onClick={() => setShowDdmDetail((prev) => !prev)}>
                {showDdmDetail ? "Hide DDM Detail" : "See DDM Detail"}
              </button>
            </div>

            {showDdmDetail && (
              <div style={{ marginTop: 12 }}>
                <DataWarningBanner warnings={ddmDetail?.warnings ?? []} title="DDM Detail Warnings" />
                {ddmDetailStatus === "loading" && (
                  <div style={{ color: "var(--muted)", fontSize: 12 }}>Loading DDM detail...</div>
                )}
                {ddmDetailStatus === "error" && (
                  <div style={{ color: "var(--red)", fontSize: 12 }}>
                    {ddmDetailError ?? "Failed to load DDM detail."}
                  </div>
                )}
                {ddmDetailStatus === "ready" && ddmDetail != null && (
                  <>
                    <div style={{ overflowX: "auto", marginBottom: 10 }}>
                      <table className="table">
                        <thead>
                          <tr>
                            <th>Scenario</th>
                            <th className="right">Fair Value</th>
                            <th className="right">Upside</th>
                            <th className="right">Cost of Equity</th>
                            <th className="right">Terminal g</th>
                            <th className="right">TV PV Share</th>
                          </tr>
                        </thead>
                        <tbody>
                          {ddmDetail.scenarios.map((scenario) => {
                            const diag = asRecord(scenario.diagnostics);
                            return (
                              <tr key={scenario.scenario_key}>
                                <td style={{ textTransform: "capitalize" }}>{scenario.scenario_key}</td>
                                <td className="right">
                                  {asNumber(diag?.fair_value) != null ? formatPrice(asNumber(diag?.fair_value) ?? 0) : "N/A"}
                                </td>
                                <td className="right">{fmtPct(diag?.upside)}</td>
                                <td className="right">{fmtPct(diag?.cost_of_equity)}</td>
                                <td className="right">{fmtPct(diag?.terminal_growth)}</td>
                                <td className="right">{fmtPct(diag?.tv_pv_share)}</td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>

                    {ddmBaseScenario?.forecast?.length ? (
                      <div style={{ overflowX: "auto" }}>
                        <div className="kicker" style={{ marginBottom: 8 }}>
                          Base Scenario Forecast
                        </div>
                        <table className="table">
                          <thead>
                            <tr>
                              <th>Year</th>
                              <th className="right">EPS</th>
                              <th className="right">Payout</th>
                              <th className="right">DPS</th>
                              <th className="right">PV (Dividend)</th>
                              <th className="right">Cum PV</th>
                            </tr>
                          </thead>
                          <tbody>
                            {ddmBaseScenario.forecast.slice(0, 12).map((row, idx) => {
                              const item = asRecord(row);
                              const metric = `Y${String(asNumber(item?.year) ?? idx + 1)}`;
                              return (
                                <tr key={`${metric}-${idx}`}>
                                  <td>{metric}</td>
                                  <td className="right">{fmtNumber(item?.eps)}</td>
                                  <td className="right">{fmtPct(item?.payout)}</td>
                                  <td className="right">{fmtNumber(item?.dps)}</td>
                                  <td className="right">
                                    {asNumber(item?.pv_dividend) != null ? formatPrice(asNumber(item?.pv_dividend) ?? 0) : "N/A"}
                                  </td>
                                  <td className="right">
                                    {asNumber(item?.cum_pv) != null ? formatPrice(asNumber(item?.cum_pv) ?? 0) : "N/A"}
                                  </td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <div style={{ color: "var(--muted)", fontSize: 12 }}>No DDM forecast rows available.</div>
                    )}
                  </>
                )}
              </div>
            )}
          </div>

          <div style={{ marginTop: 14 }}>
            <InsightBox text="Valuation is a lightweight guidance layer (analyst, DCF, RI, DDM, relative) and should be interpreted with model uncertainty in mind." />
          </div>
        </>
      )}

      {tab === "corporate" && (
        <>
          <DataWarningBanner warnings={eventsWarnings} title="Corporate Action Feed Warnings" />
          {eventsStatus === "loading" && (
            <div className="card" style={{ marginBottom: 14 }}>
              Loading corporate actions...
            </div>
          )}
          {eventsStatus === "error" && (
            <div className="card" style={{ marginBottom: 14, color: "var(--red)" }}>
              {eventsError ?? "Failed to load corporate action data."}
            </div>
          )}
          <div className="card" ref={corporateActionsRef} style={{ marginBottom: 14 }}>
            <div className="kicker" style={{ marginBottom: 12 }}>
              Corporate Actions (Splits + Dividends)
            </div>
            {corporateActions.length ? (
              <table className="table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Type</th>
                    <th className="right">Value</th>
                    <th>Description</th>
                  </tr>
                </thead>
                <tbody>
                  {corporateActions.slice(0, 120).map((row, index) => (
                    <tr key={`${row.date}-${index}`}>
                      <td>{new Date(row.date).toLocaleDateString()}</td>
                      <td>{row.action_type === "stock_split" ? "Stock Split" : "Dividend"}</td>
                      <td className="right">
                        {row.action_type === "stock_split" ? `${row.value.toFixed(2)}:1` : formatPrice(row.value)}
                      </td>
                      <td>{row.description}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div style={{ color: "var(--muted)", fontSize: 12 }}>
                No corporate action rows available yet for this symbol.
              </div>
            )}
          </div>
        </>
      )}

      {tab === "insider" && (
        <>
          <DataWarningBanner warnings={eventsWarnings} title="Insider Feed Warnings" />
          {eventsStatus === "loading" && (
            <div className="card" style={{ marginBottom: 14 }}>
              Loading insider transactions...
            </div>
          )}
          {eventsStatus === "error" && (
            <div className="card" style={{ marginBottom: 14, color: "var(--red)" }}>
              {eventsError ?? "Failed to load insider transaction data."}
            </div>
          )}
          <div className="card" ref={insiderTransactionsRef}>
            <div className="kicker" style={{ marginBottom: 12 }}>
              Insider Transactions
            </div>
            {insiderTransactions.length ? (
              <table className="table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Insider</th>
                    <th>Transaction</th>
                    <th className="right">Shares</th>
                    <th className="right">Value</th>
                    <th>Notes</th>
                  </tr>
                </thead>
                <tbody>
                  {insiderTransactions.slice(0, 120).map((row, index) => (
                    <tr key={`${row.date ?? "none"}-${row.insider ?? "na"}-${index}`}>
                      <td>{row.date ? new Date(row.date).toLocaleDateString() : "N/A"}</td>
                      <td>{row.insider ?? "N/A"}</td>
                      <td>{row.transaction ?? row.position ?? "N/A"}</td>
                      <td className="right">{row.shares != null ? row.shares.toLocaleString() : "N/A"}</td>
                      <td className="right">{row.value != null ? formatPrice(row.value) : "N/A"}</td>
                      <td>{row.text ?? "N/A"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div style={{ color: "var(--muted)", fontSize: 12 }}>
                No insider transaction rows available yet for this symbol.
              </div>
            )}
          </div>
        </>
      )}

      {tab === "news" && (
        <>
          <DataWarningBanner warnings={securityNewsWarnings} title="Ticker News Warnings" />
          {securityNewsStatus === "loading" && (
            <div className="card" style={{ marginBottom: 14 }}>
              Loading ticker news...
            </div>
          )}
          {securityNewsStatus === "error" && (
            <div className="card" style={{ marginBottom: 14, color: "var(--red)" }}>
              {securityNewsError ?? "Failed to load ticker news."}
            </div>
          )}
          {securityNewsStatus === "ready" && (
            <div className="card">
              <div className="kicker" style={{ marginBottom: 12 }}>
                {selected.symbol} News
              </div>
              {securityNews.length ? (
                <div style={{ display: "grid", gap: 12 }}>
                  {securityNews.map((article) => (
                    <article key={article.id} className="surface-soft" style={{ padding: 12 }}>
                      <div className="row-between" style={{ alignItems: "flex-start", gap: 12 }}>
                        <div style={{ minWidth: 0, flex: 1 }}>
                          <div style={{ fontSize: 16, fontWeight: 700, marginBottom: 6 }}>
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
                          <div style={{ color: "var(--muted)", fontSize: 12, marginBottom: 8 }}>
                            {article.provider ?? "Unknown source"} | {formatNewsDate(article.pub_date)}
                            {article.content_type ? ` | ${article.content_type}` : ""}
                          </div>
                          <div style={{ fontSize: 12, lineHeight: 1.6 }}>
                            {article.summary ?? "No summary available."}
                          </div>
                        </div>
                        {article.thumbnail_url ? (
                          <img
                            src={article.thumbnail_url}
                            alt={article.title}
                            style={{
                              width: 140,
                              height: 94,
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
                  No news articles available yet for this ticker.
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
