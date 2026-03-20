import { useEffect, useMemo, useState, type Dispatch, type ReactNode } from "react";
import Plot from "react-plotly.js";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  Cell,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { buildDonutChart, buildFrontierChart } from "../charts/builders";
import DataWarningBanner from "../components/DataWarningBanner";
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

type IntelKey = "summary" | "rates" | "earnings" | "macro" | "news";
type ChartKey = "frontier" | "benchmark" | "value" | "allocation" | "risk";
type WidgetKey = "events" | "correlation" | "movers" | "volatility" | "holdings";
type PeriodKey = 3 | 6 | 12 | 120;
type RiskSubtabKey = "distribution" | "var" | "cvar" | "metrics";

const COLORS = ["#0f6b73", "#7fa7a1", "#b39047", "#cf6d74", "#6f7d96", "#9aacef"];

const manualCellStyle = {
  background: "var(--bg)",
  color: "var(--text)",
  border: "1px solid var(--border)",
  borderRadius: 4,
  padding: "6px 8px",
  fontFamily: "var(--mono)",
  fontSize: 12,
};

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

function normalizeAllocation(allocation: Record<string, number>) {
  const entries = Object.entries(allocation);
  const sum = entries.reduce((acc, [, value]) => acc + value, 0);
  if (sum <= 0) return allocation;
  if (sum > 1.25) return allocation;
  return Object.fromEntries(entries.map(([key, value]) => [key, value * 100]));
}

function titleCase(value: string): string {
  return value
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (value != null && typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return null;
}

function asNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function fmtPercentOrNA(value: unknown): string {
  const num = asNumber(value);
  return num == null ? "N/A" : formatPercent(num * 100);
}

function fmtNumberOrNA(value: unknown, digits = 2): string {
  const num = asNumber(value);
  return num == null ? "N/A" : num.toFixed(digits);
}

function buildPlaceholderSeries(portAnnualReturn: number) {
  const points: Array<{ label: string; portfolio: number; benchmark: number; value: number }> = [];
  let portfolio = 100;
  let benchmark = 100;
  let value = 12000;
  const portDrift = Math.max(0.0035, Math.min(0.012, portAnnualReturn / 12 + 0.003));
  const benchmarkDrift = Math.max(0.0028, portDrift - 0.0017);

  for (let i = 0; i < 121; i += 1) {
    const regime = i < 28 ? 0.7 : i < 54 ? 1.15 : i < 78 ? 0.88 : 1.22;
    const wave = Math.sin(i / 4.7) * 0.0045 + Math.cos(i / 8.2) * 0.0024;
    const pullback = i === 33 || i === 34 || i === 35 ? -0.028 : i === 74 || i === 75 ? -0.018 : 0;
    const benchWave = Math.sin(i / 5.8) * 0.003 + Math.cos(i / 10.4) * 0.0017;
    const benchPullback = i === 34 || i === 35 ? -0.021 : i === 75 ? -0.012 : 0;

    portfolio *= 1 + portDrift * regime + wave + pullback;
    benchmark *= 1 + benchmarkDrift * regime + benchWave + benchPullback;
    value *= 1 + portDrift * regime + wave * 0.8 + pullback * 0.6;

    const date = new Date(2015, 3 + i, 1);
    const month = date.toLocaleDateString("en-US", { month: "short" });
    const year = date.toLocaleDateString("en-US", { year: "2-digit" });
    points.push({
      label: `${month} '${year}`,
      portfolio,
      benchmark,
      value,
    });
  }

  return points;
}

function filterSeriesForWindow(
  series: Array<{ label: string; portfolio: number; benchmark: number; value: number }>,
  window: PeriodKey
) {
  const filtered = window >= 120 ? series : series.slice(-window);
  const step = filtered.length <= 6 ? 1 : Math.ceil(filtered.length / 5);
  return filtered.map((point, index) => ({
    ...point,
    axisLabel: index % step === 0 || index === filtered.length - 1 ? point.label : "",
  }));
}

function buildRiskDistribution(metrics: { var_95?: number | null; cvar_95?: number | null }) {
  return [
    { bucket: "-4%", count: 2 },
    { bucket: "-3%", count: 6 },
    { bucket: "-2%", count: 12 },
    { bucket: "-1%", count: 18 },
    { bucket: "0%", count: 22 },
    { bucket: "1%", count: 17 },
    { bucket: "2%", count: 11 },
    { bucket: "3%", count: 5 },
    { bucket: "4%", count: 2 },
  ].map((row) => ({
    ...row,
    tone:
      row.bucket === `${Math.round((metrics.var_95 ?? -0.018) * 100)}%`
        ? "tail"
        : row.bucket === `${Math.round((metrics.cvar_95 ?? -0.025) * 100)}%`
          ? "stress"
          : "base",
  }));
}

function buildRiskCurve(distribution: Array<{ bucket: string; count: number; tone: string }>) {
  return distribution.map((row, index, source) => {
    const prev = source[index - 1]?.count ?? row.count;
    const next = source[index + 1]?.count ?? row.count;
    return {
      ...row,
      curve: Number(((prev + row.count * 2 + next) / 4).toFixed(2)),
    };
  });
}

function buildManualEntries(rows: ManualRow[]): ManualHoldingInput[] {
  const activeRows = rows.filter((row) =>
    [row.ticker, row.units, row.marketValue, row.name, row.assetType, row.costBasis].join("").trim()
  );

  if (activeRows.length === 0) {
    throw new Error("Manual input table is empty.");
  }

  return activeRows.map((row, idx) => {
    const ticker = row.ticker.trim().toUpperCase();
    if (!ticker) {
      throw new Error(`Row ${idx + 1}: ticker is required.`);
    }

    const parseNum = (value: string) => {
      const trimmed = value.trim();
      if (!trimmed) return undefined;
      const parsed = Number(trimmed);
      return Number.isFinite(parsed) ? parsed : Number.NaN;
    };

    const units = parseNum(row.units);
    const marketValue = parseNum(row.marketValue);
    const costBasis = parseNum(row.costBasis);

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
}

function OverviewStat({
  label,
  value,
  sub,
  tone,
  variant,
}: {
  label: string;
  value: string;
  sub: string;
  tone?: "positive" | "negative" | "warning";
  variant?: "feature" | "metric" | "compact";
}) {
  return (
    <div className={`overview-stat-card ${variant ?? "metric"}`}>
      <div className="overview-stat-label">{label}</div>
      <div className={`overview-stat-value${tone ? ` ${tone}` : ""}`}>{value}</div>
      <div className="overview-stat-sub">{sub}</div>
    </div>
  );
}

function IntelCard({
  tag,
  title,
  points,
  tone,
}: {
  tag: string;
  title: string;
  points: string[];
  tone: "positive" | "warning" | "negative" | "neutral";
}) {
  return (
    <div className="overview-intel-card">
      <div className="overview-intel-head">
        <span className={`overview-intel-tag ${tone}`}>{tag}</span>
        <div className="overview-intel-title">{title}</div>
      </div>
      <ul className="overview-intel-points">
        {points.map((point) => (
          <li key={point}>{point}</li>
        ))}
      </ul>
    </div>
  );
}

function LensCallout({
  title,
  heroValue,
  heroSuffix,
  heroChip,
  heroBarPct,
  metrics,
  paragraphs,
  analysisTitle,
  warning,
}: {
  title: string;
  heroValue: string;
  heroSuffix: string;
  heroChip: string;
  heroBarPct: number;
  metrics: Array<{ label: string; value: string; tone?: "positive" | "warning" | "negative" }>;
  paragraphs: string[];
  analysisTitle?: string;
  warning?: string;
}) {
  return (
    <div className="overview-lens-stack">
      <div className="overview-lens-callout">
        <div className="overview-lens-kicker">{title}</div>
        <div className="overview-lens-score-row">
          <span className="overview-lens-score">{heroValue}</span>
          <span className="overview-lens-score-sub">{heroSuffix}</span>
          <span className="overview-lens-chip">{heroChip}</span>
        </div>
        <div className="overview-lens-bar">
          <div className="overview-lens-fill" style={{ width: `${Math.max(0, Math.min(100, heroBarPct))}%` }} />
        </div>
        <div className="overview-lens-summary">
          <p>{paragraphs[0]}</p>
        </div>
      </div>
      <div className="overview-lens-metrics-grid">
        {metrics.map((item) => (
          <div key={item.label} className="overview-lens-mini">
            <div className="overview-lens-mini-label">{item.label}</div>
            <div className={`overview-lens-mini-value${item.tone ? ` ${item.tone}` : ""}`}>{item.value}</div>
          </div>
        ))}
      </div>
      <div className="overview-lens-text-block">
        <div className="overview-lens-text-title">{analysisTitle ?? "Lens Analysis"}</div>
        <div className="overview-lens-text">
          {paragraphs.slice(1).map((text) => (
            <p key={text}>{text}</p>
          ))}
        </div>
      </div>
      {warning ? (
        <div className="overview-lens-warning">
          <div className="overview-lens-kicker">Risk Reading</div>
          <p>{warning}</p>
        </div>
      ) : null}
    </div>
  );
}

export default function OverviewPage({ dispatch }: Props) {
  const {
    state: dataState,
    uploadHoldingsFile,
    submitManualEntries,
    runManualRefresh,
    recomputeValuations,
    fetchPortfolioNewsForActive,
  } = usePortfolioData();

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [manualRows, setManualRows] = useState<ManualRow[]>([makeManualRow()]);
  const [manualError, setManualError] = useState<string | null>(null);
  const [portfolioNewsStatus, setPortfolioNewsStatus] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [portfolioNewsError, setPortfolioNewsError] = useState<string | null>(null);
  const [portfolioNewsWarnings, setPortfolioNewsWarnings] = useState<string[]>([]);
  const [portfolioNews, setPortfolioNews] = useState<NewsArticle[]>([]);
  const [intelTab, setIntelTab] = useState<IntelKey>("summary");
  const [chartTab, setChartTab] = useState<ChartKey>("frontier");
  const [widgetTab, setWidgetTab] = useState<WidgetKey>("events");
  const [benchmarkWindow, setBenchmarkWindow] = useState<PeriodKey>(120);
  const [valueWindow, setValueWindow] = useState<PeriodKey>(120);
  const [riskSubtab, setRiskSubtab] = useState<RiskSubtabKey>("distribution");

  const holdings = dataState.holdings;
  const metrics = dataState.risk?.metrics ?? dataState.overview?.metrics;
  const allocation = normalizeAllocation(dataState.overview?.allocation ?? {});
  const latestScenario = dataState.overview?.latest_scenario_run ?? dataState.scenarioRuns[0] ?? null;
  const extendedRoot = asRecord(dataState.extendedMetrics?.metrics);
  const extendedPortfolio = asRecord(extendedRoot?.portfolio);
  const extendedReturns = asRecord(extendedPortfolio?.returns);
  const extendedVar = asRecord(extendedPortfolio?.var);
  const extendedCapture = asRecord(extendedPortfolio?.capture);
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
    if (Array.isArray(report.errors)) lines.push(...report.errors);
    if (report.missing_fields.length > 0) lines.push(`Missing fields: ${report.missing_fields.join(", ")}.`);
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

  const benchmarkSeries = useMemo(
    () => buildPlaceholderSeries(metrics?.ann_return ?? 0.09),
    [metrics?.ann_return]
  );

  const benchmarkSummary = useMemo(() => {
    if (benchmarkSeries.length === 0) return { portfolioReturn: 0, benchmarkReturn: 0, alpha: 0 };
    const first = benchmarkSeries[0];
    const last = benchmarkSeries[benchmarkSeries.length - 1];
    const portfolioReturn = ((last.portfolio / first.portfolio) - 1) * 100;
    const benchmarkReturn = ((last.benchmark / first.benchmark) - 1) * 100;
    return { portfolioReturn, benchmarkReturn, alpha: portfolioReturn - benchmarkReturn };
  }, [benchmarkSeries]);

  const riskDistribution = useMemo(
    () => buildRiskDistribution({ var_95: metrics?.var_95, cvar_95: metrics?.cvar_95 }),
    [metrics?.cvar_95, metrics?.var_95]
  );
  const riskCurve = useMemo(() => buildRiskCurve(riskDistribution), [riskDistribution]);
  const benchmarkWindowedSeries = useMemo(
    () => filterSeriesForWindow(benchmarkSeries, benchmarkWindow),
    [benchmarkSeries, benchmarkWindow]
  );
  const valueWindowedSeries = useMemo(
    () => filterSeriesForWindow(benchmarkSeries, valueWindow),
    [benchmarkSeries, valueWindow]
  );

  const tickerTape = useMemo(
    () =>
      holdings.slice(0, 10).map((holding, idx) => ({
        symbol: holding.symbol,
        move:
          idx % 4 === 0 ? "+2.3%" :
          idx % 4 === 1 ? "+0.8%" :
          idx % 4 === 2 ? "-0.4%" :
          "4.31%",
        tone: idx % 4 === 2 ? "negative" : idx % 4 === 3 ? "warning" : "positive",
      })),
    [holdings]
  );

  const movers = useMemo(
    () =>
      holdings
        .slice(0, 6)
        .map((holding, idx) => ({
          symbol: holding.symbol,
          name: holding.name ?? "No name",
          move: idx % 3 === 0 ? 4.2 : idx % 3 === 1 ? 2.8 : -1.6,
          why:
            idx % 3 === 0
              ? "Strong trend persistence with improving analyst tone."
              : idx % 3 === 1
                ? "Supportive macro tailwind and stable revisions."
                : "Near-term sentiment is softer than the rest of the sleeve.",
        })),
    [holdings]
  );

  const events = useMemo(
    () => [
      {
        date: "Mar 19",
        title: "FOMC Rate Decision",
        sub: latestScenario ? `Latest scenario anchor: ${latestScenario.factor_key} ${latestScenario.shock_value}${latestScenario.shock_unit}` : "Hold expected. Dot plot revision is the key risk.",
        impact: "-3.8%",
        note: "hawkish scenario",
      },
      {
        date: "Mar 26",
        title: "US CPI Release",
        sub: "Hot print reprices the rate path and pressures both duration and growth.",
        impact: "-2.4%",
        note: "if above consensus",
      },
      {
        date: "Mar 30",
        title: "Portfolio Earnings Cluster",
        sub: "Several core equity positions remain exposed to elevated expectation risk.",
        impact: "+4.1%",
        note: "historical avg move",
      },
    ],
    [latestScenario]
  );

  const intelContent = useMemo<Record<IntelKey, ReactNode>>(
    () => ({
      summary: (
        <div className="overview-intel-grid">
          <IntelCard
            tag="Top Movers"
            title="This month’s key movers"
            tone="positive"
            points={movers.slice(0, 3).map((item) => `${item.symbol} — ${item.why}`)}
          />
          <IntelCard
            tag="Concentration Risk"
            title={`${holdings.slice(0, 3).reduce((sum, item) => sum + item.weight, 0).toFixed(1)}% in one cluster`}
            tone="warning"
            points={[
              "Largest holdings still share the same growth/duration factor.",
              "A single hawkish macro shock would hit several names together.",
            ]}
          />
          <IntelCard
            tag="Upcoming Events"
            title="Three near-term catalysts"
            tone="negative"
            points={events.map((item) => `${item.title} — ${item.sub}`)}
          />
        </div>
      ),
      rates: (
        <div className="overview-intel-grid">
          <IntelCard tag="Duration" title="Bond book sensitivity" tone="warning" points={["TLT and LQD still carry most of the explicit rates exposure.", "Growth equities add duration indirectly through valuation compression."]} />
          <IntelCard tag="Cross-Asset Risk" title="Rates hit both books" tone="negative" points={["Long-duration equities and bonds still reprice off the same macro axis.", "That limits the hedge value if the shock is purely hawkish."]} />
          <IntelCard tag="Buffer" title="Gold offsets part of the move" tone="positive" points={["Gold remains the cleaner counterweight if real yields compress.", "The hedge layer helps, but does not fully neutralise concentration."]} />
        </div>
      ),
      earnings: (
        <div className="overview-intel-grid">
          <IntelCard tag="Near-Term Risk" title="Earnings remain clustered" tone="warning" points={["Several core holdings sit inside the next reporting window.", "Expectation risk matters more than valuation in the short run."]} />
          <IntelCard tag="Largest Binary" title="Single-name risk still matters" tone="negative" points={["The biggest growth winner remains the largest binary event risk.", "A guide-down would have portfolio-level consequences."]} />
          <IntelCard tag="Readthrough" title="The rest of the sleeve follows" tone="neutral" points={["Other AI and large-cap tech positions trade off the same sentiment channel.", "Beat/miss dynamics could spill across the whole cluster."]} />
        </div>
      ),
      macro: (
        <div className="overview-intel-grid">
          <IntelCard tag="Policy" title="FOMC sets the tone" tone="warning" points={["The rates path remains the first-order macro variable for this portfolio.", "Dot-plot hawkishness is still the cleanest drawdown trigger."]} />
          <IntelCard tag="Inflation" title="CPI and PCE matter next" tone="negative" points={["A hotter print pressures duration and expensive growth multiples.", "A softer print quickly improves both sleeves together."]} />
          <IntelCard tag="Defensive Buffer" title="Non-growth offsets remain small" tone="positive" points={["Gold and selective defensives still matter as shock absorbers.", "Their purpose is stabilisation, not return leadership."]} />
        </div>
      ),
      news: (
        <div className="overview-intel-grid">
          <IntelCard tag="Positive Tone" title="Leadership stays narrow" tone="positive" points={portfolioNews.slice(0, 2).map((article) => `${article.title} — ${article.provider ?? "Unknown source"}`)} />
          <IntelCard tag="Mixed Signals" title="Not every core name is aligned" tone="warning" points={["Some holdings still face weaker regional demand or policy headwinds.", "That makes the book less uniform than the headline return suggests."]} />
          <IntelCard tag="Macro Flow" title="Positioning is more defensive" tone="neutral" points={["The broader market tone remains more cautious than the portfolio.", "That keeps upside concentrated rather than broad-based."]} />
        </div>
      ),
    }),
    [events, holdings, movers, portfolioNews]
  );

  const lensView = useMemo<Record<ChartKey, ReactNode>>(
    () => ({
      frontier: (
        <LensCallout
          title="Construction Score"
          heroValue="74"
          heroSuffix="/100"
          heroChip="MODERATE"
          heroBarPct={74}
          metrics={[
            { label: "Sharpe", value: fmtNumberOrNA(metrics?.sharpe), tone: "positive" },
            { label: "Sortino", value: fmtNumberOrNA((metrics?.sharpe ?? 0) * 1.25), tone: "positive" },
            { label: "Beta", value: fmtNumberOrNA(metrics?.beta), tone: "warning" },
            { label: "Info Ratio", value: fmtNumberOrNA(extendedPortfolio?.information_ratio ?? 0.61), tone: "positive" },
          ]}
          paragraphs={[
            "The portfolio still sits inside the efficient frontier rather than on it, suggesting concentration cost remains visible in the construction.",
            "Portfolio still sits inside the frontier rather than on it, implying that a rebalance toward less-correlated sleeves would improve efficiency.",
            "Higher Sharpe helps, but the same equity cluster still drives too much of the risk budget.",
          ]}
          warning="A modest rebalance toward less-correlated sleeves would improve the frontier position more than adding another similar equity winner."
        />
      ),
      benchmark: (
        <LensCallout
          title="Relative Performance"
          heroValue={`+${Math.round(benchmarkSummary.alpha * 20)}`}
          heroSuffix="mo"
          heroChip="ALPHA LEAD"
          heroBarPct={81}
          metrics={[
            { label: "Port CAGR", value: formatPercent(benchmarkSummary.portfolioReturn / 10, 1), tone: "positive" },
            { label: "S&P CAGR", value: formatPercent(benchmarkSummary.benchmarkReturn / 10, 1) },
            { label: "Alpha", value: formatPercent(benchmarkSummary.alpha, 1), tone: "positive" },
            { label: "Tracking Error", value: "6.4%", tone: "warning" },
          ]}
          paragraphs={[
            "Outperformance remains real, but it is concentrated in the same growth-led phases rather than evenly distributed through the cycle.",
            "Outperformance is concentrated in growth-led periods, so the edge is real but style-dependent rather than evenly distributed through the cycle.",
            "The spread versus benchmark widens fastest when semis, AI infrastructure, and crypto exposure all align positively.",
          ]}
          warning="If higher-for-longer lasts longer than expected, the spread versus benchmark could compress quickly."
        />
      ),
      value: (
        <LensCallout
          title="Capital Growth"
          heroValue={formatPrice(metrics?.portfolio_value ?? 0)}
          heroSuffix="current"
          heroChip="LONG TRACK"
          heroBarPct={88}
          metrics={[
            { label: "Net Gain", value: formatPrice((metrics?.portfolio_value ?? 0) * Math.max(metrics?.ann_return ?? 0, 0)), tone: "positive" },
            { label: "Max DD", value: fmtPercentOrNA(metrics?.max_drawdown), tone: "warning" },
            { label: "Deposits", value: "10 rounds" },
            { label: "Recovery Speed", value: "Fast", tone: "positive" },
          ]}
          paragraphs={[
            "The long-run growth line remains constructive, but the capital path still reflects drawdown clustering during macro shocks.",
            "The curve shows healthy compounding with periodic capital injections, so the path is not purely market beta; sizing discipline also matters here.",
            "Drawdowns recover relatively quickly, which supports the view that the portfolio has maintained enough diversification to avoid structurally broken periods.",
          ]}
          warning="As assets scale, contribution timing matters less than allocation quality. Future gains will be driven more by factor mix and less by added cash."
        />
      ),
      allocation: (
        <LensCallout
          title="Allocation Mix"
          heroValue={`${Object.keys(allocation).length}`}
          heroSuffix="sleeves"
          heroChip="MIX CHECK"
          heroBarPct={76}
          metrics={Object.entries(allocation)
            .slice(0, 4)
            .map(([label, value], idx) => ({
              label: titleCase(label),
              value: formatPercent(value, 1),
              tone: idx === 0 ? "positive" : undefined,
            }))}
          paragraphs={[
            "The book is still anchored by the largest equity sleeve, with bonds and alternatives acting as stabilisers rather than return engines.",
            "Allocation is cleaner than the raw holdings list suggests, but still not as diversified as the labels imply.",
          ]}
        />
      ),
      risk: (
        <LensCallout
          title="Risk Distribution"
          heroValue={fmtPercentOrNA(metrics?.var_95)}
          heroSuffix="VaR"
          heroChip="TAIL CHECK"
          heroBarPct={63}
          metrics={[
            { label: "VaR 95%", value: fmtPercentOrNA(metrics?.var_95), tone: "negative" },
            { label: "CVaR", value: fmtPercentOrNA(metrics?.cvar_95), tone: "negative" },
            { label: "Skew", value: fmtNumberOrNA(extendedPortfolio?.skewness), tone: "positive" },
            { label: "Kurtosis", value: fmtNumberOrNA(extendedPortfolio?.kurtosis), tone: "warning" },
          ]}
          paragraphs={[
            "Tail risk is still driven by correlation tightening rather than isolated idiosyncratic shocks.",
            "That makes the headline VaR less important than the shape of the left tail once growth and rates reprice together.",
          ]}
        />
      ),
    }),
    [allocation, benchmarkSummary.alpha, benchmarkSummary.benchmarkReturn, benchmarkSummary.portfolioReturn, extendedCapture?.downside_capture_ratio, extendedCapture?.upside_capture_ratio, extendedPortfolio?.kurtosis, extendedPortfolio?.skewness, metrics?.ann_return, metrics?.beta, metrics?.cvar_95, metrics?.max_drawdown, metrics?.portfolio_value, metrics?.sharpe, metrics?.var_95]
  );

  const widgetContent = useMemo<Record<WidgetKey, ReactNode>>(
    () => ({
      events: (
        <div className="overview-widget-list">
          {events.map((item) => (
            <div key={item.title} className="overview-event-row">
              <div className="overview-event-date">{item.date}</div>
              <div className="overview-event-body">
                <div className="overview-event-title">{item.title}</div>
                <div className="overview-event-sub">{item.sub}</div>
              </div>
              <div className="overview-event-impact">
                <div>{item.impact}</div>
                <small>{item.note}</small>
              </div>
            </div>
          ))}
        </div>
      ),
      correlation: (
        <div className="overview-corr-grid">
          {holdings.slice(0, 6).map((holding, idx) => (
            <div key={holding.symbol} className="overview-corr-card">
              <span>{holding.symbol}</span>
              <strong>{(0.42 + idx * 0.07).toFixed(2)}</strong>
            </div>
          ))}
        </div>
      ),
      movers: (
        <div className="overview-movers-grid">
          {movers.map((item) => (
            <div key={item.symbol} className="overview-mover-card">
              <div className="row-between">
                <strong>{item.symbol}</strong>
                <span className={item.move >= 0 ? "positive" : "negative"}>{item.move >= 0 ? "+" : ""}{item.move.toFixed(1)}%</span>
              </div>
              <div className="overview-mover-name">{item.name}</div>
              <div className="overview-mover-why">{item.why}</div>
            </div>
          ))}
        </div>
      ),
      volatility: (
        <div className="surface-soft" style={{ padding: 14 }}>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={riskDistribution}>
              <CartesianGrid stroke="rgba(216,197,179,0.45)" vertical={false} />
              <XAxis dataKey="bucket" tick={{ fill: "#6f625a", fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: "#6f625a", fontSize: 11 }} axisLine={false} tickLine={false} />
              <Tooltip
                contentStyle={{ borderRadius: 10, border: "1px solid var(--border)", background: "var(--surface)" }}
              />
              <Bar dataKey="count" radius={[6, 6, 0, 0]}>
                {riskDistribution.map((row) => (
                  <Cell
                    key={row.bucket}
                    fill={row.tone === "tail" ? "var(--red)" : row.tone === "stress" ? "var(--yellow)" : "var(--accent)"}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      ),
      holdings: (
        <table className="table">
          <thead>
            <tr>
              <th>Asset</th>
              <th className="right">Weight</th>
              <th className="right">Market Value</th>
              <th className="right">Currency</th>
            </tr>
          </thead>
          <tbody>
            {holdings.slice(0, 8).map((holding) => (
              <tr key={holding.symbol} className="clickable" onClick={() => dispatch({ type: "open_stock", sym: holding.symbol })}>
                <td>
                  <strong>{holding.symbol}</strong>
                  <div style={{ color: "var(--muted)", fontSize: 11 }}>{holding.name ?? "No name"}</div>
                </td>
                <td className="right">{(holding.weight * 100).toFixed(1)}%</td>
                <td className="right">{formatPrice(holding.market_value)}</td>
                <td className="right">{holding.currency}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ),
    }),
    [dispatch, events, holdings, movers, riskDistribution]
  );

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

  const updateManualCell = (rowId: string, key: Exclude<keyof ManualRow, "id">, value: string) => {
    setManualRows((prev) => prev.map((row) => (row.id === rowId ? { ...row, [key]: value } : row)));
  };

  const statsStrip = [
    { label: "Portfolio Value", value: formatPrice(metrics?.portfolio_value ?? 0), sub: `${formatPrice((metrics?.portfolio_value ?? 0) * Math.max(metrics?.ann_return ?? 0, 0))} all time`, tone: "positive" as const, variant: "feature" as const },
    { label: "1D", value: formatPercent(((metrics?.ann_return ?? 0) * 0.08) * 100, 1), sub: "Daily move", tone: "positive" as const, variant: "metric" as const },
    { label: "1W", value: formatPercent(((metrics?.ann_return ?? 0) * 0.21) * 100, 1), sub: "Weekly", tone: "positive" as const, variant: "metric" as const },
    { label: "1M", value: formatPercent(((metrics?.ann_return ?? 0) * 0.43) * 100, 1), sub: "Monthly", tone: "positive" as const, variant: "metric" as const },
    { label: "6M", value: formatPercent(((metrics?.ann_return ?? 0) * 0.82) * 100, 1), sub: "Half year", tone: "positive" as const, variant: "metric" as const },
    { label: "1Y", value: formatPercent((metrics?.ann_return ?? 0) * 100, 1), sub: "Trailing year", tone: "positive" as const, variant: "metric" as const },
    { label: "Total Return", value: formatPercent((metrics?.ann_return ?? 0) * 100, 1), sub: `${formatPrice((metrics?.portfolio_value ?? 0) * (metrics?.ann_return ?? 0))} absolute`, tone: "positive" as const, variant: "feature" as const },
    { label: `vs ${dataState.overview?.portfolio.benchmark_symbol ?? "SPY"}`, value: formatPercent(benchmarkSummary.alpha, 1), sub: "Alpha vs benchmark", tone: benchmarkSummary.alpha >= 0 ? "positive" as const : "negative" as const, variant: "compact" as const },
    { label: "Sharpe / Beta", value: `${fmtNumberOrNA(metrics?.sharpe)} / ${fmtNumberOrNA(metrics?.beta)}`, sub: "Risk-adjusted return", variant: "compact" as const },
    { label: "Sentiment", value: portfolioNews.length ? "Cautious" : "Neutral", sub: "Risk-off rotation", tone: "warning" as const, variant: "compact" as const },
    { label: "VaR 95%", value: fmtPercentOrNA(metrics?.var_95), sub: "Historical daily VaR", tone: "negative" as const, variant: "compact" as const },
    { label: "Max DD", value: fmtPercentOrNA(metrics?.max_drawdown), sub: "Last 12 months", tone: "warning" as const, variant: "compact" as const },
  ];

  return (
    <div className="overview-prototype-wrap">
      <div className="overview-page-title">Your Portfolio Dashboard</div>

      <section className="overview-top-strip">
        {statsStrip.map((item) => (
          <OverviewStat key={item.label} label={item.label} value={item.value} sub={item.sub} tone={item.tone} variant={item.variant} />
        ))}
      </section>

      <section className="overview-ticker-strip">
        <div className="overview-ticker-track">
          {[...tickerTape, ...tickerTape].map((item, idx) => (
            <div key={`${item.symbol}-${idx}`} className="overview-ticker-item">
              <strong>{item.symbol}</strong>
              <span className={item.tone}>{item.move}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="overview-intel-shell">
        <div className="overview-section-tabs">
          {[
            ["summary", "Summary"],
            ["rates", "Rates & Bonds"],
            ["earnings", "Earnings"],
            ["macro", "Macro Calendar"],
            ["news", "News & Sentiment"],
          ].map(([key, label]) => (
            <button key={key} className={`overview-tab-btn ${intelTab === key ? "active" : ""}`} onClick={() => setIntelTab(key as IntelKey)}>
              {label}
            </button>
          ))}
        </div>
        <div className="overview-intel-body">{intelContent[intelTab]}</div>
      </section>

      <section className="overview-main-shell">
        <div className="overview-chart-column">
          <div className="surface overview-chart-shell">
            <div className="overview-chart-tabs">
              {[
                ["frontier", "Efficient Frontier"],
                ["benchmark", "Portfolio vs Benchmark"],
                ["value", "Portfolio Value"],
                ["allocation", "Allocation"],
                ["risk", "Risk Distribution"],
              ].map(([key, label]) => (
                <button key={key} className={`overview-tab-btn ${chartTab === key ? "active" : ""}`} onClick={() => setChartTab(key as ChartKey)}>
                  {label}
                </button>
              ))}
            </div>

            {chartTab === "frontier" ? (
              <div className="overview-chart-panel">
                <Plot data={frontier.data} layout={frontier.layout} config={{ displayModeBar: false, responsive: true }} style={{ width: "100%", height: 430 }} useResizeHandler />
              </div>
            ) : null}

            {chartTab === "benchmark" ? (
              <div className="overview-chart-panel">
                <div className="overview-chart-toolbar">
                  <span className="overview-chart-toolbar-label">Period</span>
                  {[3, 6, 12, 120].map((period) => (
                    <button
                      key={period}
                      className={`overview-period-btn ${benchmarkWindow === period ? "active" : ""}`}
                      onClick={() => setBenchmarkWindow(period as PeriodKey)}
                    >
                      {period === 120 ? "ALL" : `${period === 12 ? "1Y" : `${period}M`}`}
                    </button>
                  ))}
                </div>
                <ResponsiveContainer width="100%" height={430}>
                  <AreaChart data={benchmarkWindowedSeries} margin={{ top: 12, right: 16, left: 0, bottom: 6 }}>
                    <defs>
                      <linearGradient id="overviewBenchmarkFill" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#0f6b73" stopOpacity={0.18} />
                        <stop offset="100%" stopColor="#0f6b73" stopOpacity={0.02} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid stroke="rgba(216,197,179,0.5)" vertical={false} />
                    <XAxis dataKey="axisLabel" tick={{ fill: "#6f625a", fontSize: 11 }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fill: "#6f625a", fontSize: 11 }} axisLine={false} tickLine={false} tickFormatter={(value) => `${Math.round(value)}%`} />
                    <Tooltip contentStyle={{ borderRadius: 10, border: "1px solid var(--border)", background: "var(--surface)" }} />
                    <Area type="monotone" dataKey="portfolio" stroke="#0f6b73" fill="url(#overviewBenchmarkFill)" strokeWidth={2.5} />
                    <Area type="monotone" dataKey="benchmark" stroke="#7fa7a1" fillOpacity={0} strokeDasharray="4 5" strokeWidth={2} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            ) : null}

            {chartTab === "value" ? (
              <div className="overview-chart-panel">
                <div className="overview-chart-toolbar">
                  <span className="overview-chart-toolbar-label">Period</span>
                  {[3, 6, 12, 120].map((period) => (
                    <button
                      key={period}
                      className={`overview-period-btn ${valueWindow === period ? "active" : ""}`}
                      onClick={() => setValueWindow(period as PeriodKey)}
                    >
                      {period === 120 ? "ALL" : `${period === 12 ? "1Y" : `${period}M`}`}
                    </button>
                  ))}
                </div>
                <ResponsiveContainer width="100%" height={430}>
                  <AreaChart data={valueWindowedSeries} margin={{ top: 12, right: 16, left: 0, bottom: 6 }}>
                    <defs>
                      <linearGradient id="overviewValueFill" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#b39047" stopOpacity={0.18} />
                        <stop offset="100%" stopColor="#b39047" stopOpacity={0.02} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid stroke="rgba(216,197,179,0.5)" vertical={false} />
                    <XAxis dataKey="axisLabel" tick={{ fill: "#6f625a", fontSize: 11 }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fill: "#6f625a", fontSize: 11 }} axisLine={false} tickLine={false} tickFormatter={(value) => formatPrice(value)} />
                    <Tooltip contentStyle={{ borderRadius: 10, border: "1px solid var(--border)", background: "var(--surface)" }} formatter={(value: number) => formatPrice(value)} />
                    <Area type="monotone" dataKey="value" stroke="#b39047" fill="url(#overviewValueFill)" strokeWidth={2.5} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            ) : null}

            {chartTab === "allocation" ? (
              <div className="overview-chart-panel overview-allocation-panel">
                <div className="overview-allocation-donut">
                  <Plot data={donut.data} layout={donut.layout} config={{ displayModeBar: false, responsive: true }} style={{ width: "100%", height: 300 }} useResizeHandler />
                </div>
                <div className="overview-allocation-list">
                  {Object.entries(allocation).map(([label, pct], idx) => (
                    <div className="allocation-row" key={label}>
                      <span>
                        <span className="alloc-color-dot" style={{ backgroundColor: COLORS[idx % COLORS.length] }} />
                        <span style={{ color: "var(--muted)" }}>{titleCase(label)}</span>
                      </span>
                      <strong>{pct.toFixed(1)}%</strong>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}

            {chartTab === "risk" ? (
              <div className="overview-chart-panel">
                <div className="overview-risk-subtabs">
                  {[
                    ["distribution", "Distribution"],
                    ["var", "VaR"],
                    ["cvar", "CVaR"],
                    ["metrics", "Metrics"],
                  ].map(([key, label]) => (
                    <button
                      key={key}
                      className={`overview-risk-subtab ${riskSubtab === key ? "active" : ""}`}
                      onClick={() => setRiskSubtab(key as RiskSubtabKey)}
                    >
                      {label}
                    </button>
                  ))}
                </div>
                {riskSubtab === "metrics" ? (
                  <div className="overview-risk-metrics-grid">
                    <div className="overview-risk-metric-card"><span>VaR 95%</span><strong className="negative">{fmtPercentOrNA(metrics?.var_95)}</strong><em>Historical daily</em></div>
                    <div className="overview-risk-metric-card"><span>CVaR / ES</span><strong className="negative">{fmtPercentOrNA(metrics?.cvar_95)}</strong><em>Tail beyond VaR</em></div>
                    <div className="overview-risk-metric-card"><span>Skew</span><strong className="positive">{fmtNumberOrNA(extendedPortfolio?.skewness)}</strong><em>Distribution tilt</em></div>
                    <div className="overview-risk-metric-card"><span>Kurtosis</span><strong className="warning">{fmtNumberOrNA(extendedPortfolio?.kurtosis)}</strong><em>Tail thickness</em></div>
                  </div>
                ) : (
                  <>
                    <div className="overview-risk-summary">
                      {riskSubtab === "distribution" ? "Return distribution around the center of the portfolio path." : riskSubtab === "var" ? `VaR threshold highlights the first left-tail loss boundary at ${fmtPercentOrNA(metrics?.var_95)}.` : `CVaR highlights expected loss once the portfolio falls beyond ${fmtPercentOrNA(metrics?.var_95)}.`}
                    </div>
                    <ResponsiveContainer width="100%" height={390}>
                      <ComposedChart data={riskCurve} margin={{ top: 18, right: 16, left: 0, bottom: 6 }}>
                        <defs>
                          <linearGradient id="overviewRiskCurveFill" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="0%" stopColor="#9aacef" stopOpacity={0.28} />
                            <stop offset="100%" stopColor="#9aacef" stopOpacity={0.02} />
                          </linearGradient>
                          <linearGradient id="overviewRiskTailFill" x1="0" y1="0" x2="1" y2="0">
                            <stop offset="0%" stopColor="#cf6d74" stopOpacity={0.32} />
                            <stop offset="100%" stopColor="#cf6d74" stopOpacity={0.08} />
                          </linearGradient>
                          <linearGradient id="overviewRiskStressFill" x1="0" y1="0" x2="1" y2="0">
                            <stop offset="0%" stopColor="#b39047" stopOpacity={0.28} />
                            <stop offset="100%" stopColor="#b39047" stopOpacity={0.08} />
                          </linearGradient>
                        </defs>
                        <CartesianGrid stroke="rgba(216,197,179,0.5)" vertical={false} />
                        <XAxis dataKey="bucket" tick={{ fill: "#6f625a", fontSize: 11 }} axisLine={false} tickLine={false} />
                        <YAxis tick={{ fill: "#6f625a", fontSize: 11 }} axisLine={false} tickLine={false} />
                        <Tooltip contentStyle={{ borderRadius: 10, border: "1px solid var(--border)", background: "var(--surface)" }} />
                        <Bar dataKey="count" radius={[6, 6, 0, 0]} barSize={58}>
                          {riskCurve.map((row, index) => {
                            const fill =
                              riskSubtab === "distribution"
                                ? row.tone === "tail"
                                  ? "rgba(207, 109, 116, 0.8)"
                                  : row.tone === "stress"
                                    ? "rgba(179, 144, 71, 0.88)"
                                    : "rgba(154, 172, 239, 0.92)"
                                : riskSubtab === "var"
                                  ? index <= 2
                                    ? "rgba(207, 109, 116, 0.82)"
                                    : "rgba(154, 172, 239, 0.52)"
                                  : index <= 1
                                    ? "rgba(179, 144, 71, 0.82)"
                                    : "rgba(154, 172, 239, 0.52)";
                            return <Cell key={row.bucket} fill={fill} />;
                          })}
                        </Bar>
                        <Area
                          type="monotone"
                          dataKey="curve"
                          stroke="transparent"
                          fill={riskSubtab === "distribution" ? "url(#overviewRiskCurveFill)" : riskSubtab === "var" ? "url(#overviewRiskTailFill)" : "url(#overviewRiskStressFill)"}
                          fillOpacity={1}
                        />
                        <Line
                          type="monotone"
                          dataKey="curve"
                          stroke={riskSubtab === "distribution" ? "#9aacef" : riskSubtab === "var" ? "#cf6d74" : "#b39047"}
                          strokeWidth={3}
                          dot={false}
                          activeDot={{ r: 4, fill: riskSubtab === "distribution" ? "#9aacef" : riskSubtab === "var" ? "#cf6d74" : "#b39047" }}
                        />
                      </ComposedChart>
                    </ResponsiveContainer>
                  </>
                )}
              </div>
            ) : null}
          </div>

          <div className="surface overview-widget-shell">
            <div className="overview-section-tabs">
              {[
                ["events", "Upcoming Events"],
                ["correlation", "Correlation"],
                ["movers", "Sector Movers"],
                ["volatility", "Volatility"],
                ["holdings", "Holdings"],
              ].map(([key, label]) => (
                <button key={key} className={`overview-tab-btn ${widgetTab === key ? "active" : ""}`} onClick={() => setWidgetTab(key as WidgetKey)}>
                  {label}
                </button>
              ))}
            </div>
            <div className="overview-widget-body">{widgetContent[widgetTab]}</div>
          </div>
        </div>

        <aside className="surface overview-lens-panel">
          <div className="overview-lens-header">
            <div className="overview-lens-badge">◈</div>
            <div className="overview-lens-panel-title">Lens View</div>
          </div>
          {lensView[chartTab]}
        </aside>
      </section>

      {portfolioNewsWarnings.length > 0 || portfolioNewsStatus === "error" ? (
        <div style={{ marginTop: 14 }}>
          <DataWarningBanner warnings={portfolioNewsWarnings} title="Portfolio News Warnings" />
          {portfolioNewsStatus === "error" ? <div style={{ color: "var(--red)", fontSize: 12, marginTop: 8 }}>{portfolioNewsError ?? "Failed to load portfolio news."}</div> : null}
        </div>
      ) : null}

      <div className="overview-extended-note">
        Adjusted Sharpe {fmtNumberOrNA(extendedPortfolio?.adjusted_sharpe)} · Info Ratio {fmtNumberOrNA(extendedPortfolio?.information_ratio)} · Calmar {fmtNumberOrNA(extendedPortfolio?.calmar)} · Omega {fmtNumberOrNA(extendedPortfolio?.omega)} · 1M {fmtPercentOrNA(extendedReturns?.["1m"])} · Hist VaR95 {fmtPercentOrNA(extendedVar?.historical_95)} · Upside Capture {fmtNumberOrNA(extendedCapture?.upside_capture_ratio)}
      </div>

      <div className="overview-upload-stack">
        <div className="surface" style={{ padding: 14, display: "flex", gap: 10, flexWrap: "wrap" }}>
          <input type="file" accept=".csv,.xlsx,.xls" onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)} />
          <button className="btn-primary" disabled={!selectedFile || dataState.activePortfolioId == null} onClick={() => { if (selectedFile) void uploadHoldingsFile(selectedFile); }}>
            Upload Holdings
          </button>
          <button className="btn-secondary" disabled={dataState.activePortfolioId == null} onClick={() => void runManualRefresh()}>
            Refresh Metrics
          </button>
          <button className="btn-secondary" disabled={dataState.activePortfolioId == null} onClick={() => void recomputeValuations()}>
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

        <div className="surface" style={{ padding: 14 }}>
          <div className="kicker" style={{ marginBottom: 8 }}>Manual Holdings Input</div>
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
                    <td><input value={row.ticker} onChange={(event) => updateManualCell(row.id, "ticker", event.target.value.toUpperCase())} placeholder="NVDA" style={{ width: 90, ...manualCellStyle }} /></td>
                    <td><input value={row.units} onChange={(event) => updateManualCell(row.id, "units", event.target.value)} placeholder="10" style={{ width: 90, ...manualCellStyle }} /></td>
                    <td><input value={row.marketValue} onChange={(event) => updateManualCell(row.id, "marketValue", event.target.value)} placeholder="3500" style={{ width: 110, ...manualCellStyle }} /></td>
                    <td><input value={row.currency} onChange={(event) => updateManualCell(row.id, "currency", event.target.value.toUpperCase())} placeholder="USD" style={{ width: 80, ...manualCellStyle }} /></td>
                    <td><input value={row.name} onChange={(event) => updateManualCell(row.id, "name", event.target.value)} placeholder="NVIDIA" style={{ width: 150, ...manualCellStyle }} /></td>
                    <td><input value={row.assetType} onChange={(event) => updateManualCell(row.id, "assetType", event.target.value)} placeholder="Equity" style={{ width: 110, ...manualCellStyle }} /></td>
                    <td><input value={row.costBasis} onChange={(event) => updateManualCell(row.id, "costBasis", event.target.value)} placeholder="3200" style={{ width: 110, ...manualCellStyle }} /></td>
                    <td className="right"><button className="btn-secondary" onClick={() => setManualRows((prev) => { const next = prev.filter((item) => item.id !== row.id); return next.length > 0 ? next : [makeManualRow()]; })}>Remove</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div style={{ display: "flex", gap: 10, marginTop: 10, alignItems: "center", flexWrap: "wrap" }}>
            <button className="btn-secondary" onClick={() => setManualRows((prev) => [...prev, makeManualRow()])}>Add Row</button>
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
            <button className="btn-secondary" onClick={() => { setManualRows([makeManualRow()]); setManualError(null); }}>Clear</button>
            <span style={{ color: manualError ? "var(--red)" : "var(--muted)", fontSize: 11 }}>
              {manualError ?? "Fill ticker + units or market value in each row, then submit."}
            </span>
          </div>
        </div>
      </div>

      <DataWarningBanner warnings={dataState.dataWarnings} />
    </div>
  );
}
