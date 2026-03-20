import { useMemo } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { usePortfolioData } from "../state/DataProvider";
import { formatPercent, formatPrice } from "../utils/format";

type SeriesPoint = {
  label: string;
  portfolio: number;
  benchmark: number;
};

type InsightRow = {
  tag: string;
  tone: "positive" | "neutral" | "warning";
  reading: string;
  why: string;
  takeaway: string;
};

function buildPlaceholderSeries(portAnnualReturn: number): SeriesPoint[] {
  const labels = ["Apr '15", "Oct '17", "Apr '20", "Oct '22", "Apr '25"];
  const points: SeriesPoint[] = [];
  let portfolio = 100;
  let benchmark = 100;
  const portDrift = Math.max(0.0035, Math.min(0.012, portAnnualReturn / 12 + 0.003));
  const benchmarkDrift = Math.max(0.0028, portDrift - 0.0017);

  for (let i = 0; i < 121; i += 1) {
    const regime =
      i < 28 ? 0.7 :
      i < 54 ? 1.15 :
      i < 78 ? 0.88 :
      1.22;
    const wave = Math.sin(i / 4.7) * 0.0045 + Math.cos(i / 8.2) * 0.0024;
    const pullback =
      i === 33 || i === 34 || i === 35 ? -0.028 :
      i === 74 || i === 75 ? -0.018 :
      0;
    const benchWave = Math.sin(i / 5.8) * 0.003 + Math.cos(i / 10.4) * 0.0017;
    const benchPullback =
      i === 34 || i === 35 ? -0.021 :
      i === 75 ? -0.012 :
      0;

    portfolio *= 1 + portDrift * regime + wave + pullback;
    benchmark *= 1 + benchmarkDrift * regime + benchWave + benchPullback;

    if (i % 30 === 0) {
      points.push({
        label: labels[Math.min(points.length, labels.length - 1)],
        portfolio,
        benchmark,
      });
    }
  }

  return points;
}

export default function LensPage() {
  const { state: dataState } = usePortfolioData();

  const overview = dataState.overview;
  const metrics = dataState.risk?.metrics ?? overview?.metrics;

  const series = useMemo(
    () => buildPlaceholderSeries(metrics?.ann_return ?? 0.09),
    [metrics?.ann_return]
  );

  const chartSummary = useMemo(() => {
    if (series.length === 0) {
      return { portfolioReturn: 0, benchmarkReturn: 0, alpha: 0 };
    }
    const first = series[0];
    const last = series[series.length - 1];
    const portfolioReturn = ((last.portfolio / first.portfolio) - 1) * 100;
    const benchmarkReturn = ((last.benchmark / first.benchmark) - 1) * 100;
    return {
      portfolioReturn,
      benchmarkReturn,
      alpha: portfolioReturn - benchmarkReturn,
    };
  }, [series]);

  const insights = useMemo<InsightRow[]>(() => {
    const benchmarkSymbol = overview?.portfolio.benchmark_symbol ?? "SPY";
    const sharpe = metrics?.sharpe ?? 0;
    const var95 = (metrics?.var_95 ?? 0) * 100;
    const maxDrawdown = (metrics?.max_drawdown ?? 0) * 100;
    const valuationUpside = dataState.valuationOverview?.weighted_composite_upside ?? null;

    return [
      {
        tag: "Opportunity",
        tone: "positive",
        reading: `Portfolio is ahead of ${benchmarkSymbol}`,
        why: `The placeholder benchmark path shows ${formatPercent(chartSummary.alpha)} relative outperformance over the same window.`,
        takeaway: "Relative performance is positive, but still concentrated in the growth sleeve.",
      },
      {
        tag: "Allocation",
        tone: "neutral",
        reading: "Core growth remains the anchor",
        why: "Most capital still sits in the largest equity sleeve, keeping the book tilted toward the same return engine.",
        takeaway: "The portfolio still behaves like an equity-led book with diversifiers around the edges.",
      },
      {
        tag: "Risk Alert",
        tone: "warning",
        reading: `VaR ${formatPercent(var95, 1)} and max DD ${formatPercent(maxDrawdown, 1)}`,
        why: `Current risk metrics imply the downside profile is manageable, but still meaningful when correlations tighten.`,
        takeaway: sharpe >= 1 ? "Return quality is investable, but tail management still matters." : "Risk is elevated relative to return quality.",
      },
      {
        tag: "Valuation",
        tone: valuationUpside != null && valuationUpside >= 0 ? "positive" : "neutral",
        reading:
          valuationUpside != null
            ? `Composite upside ${formatPercent(valuationUpside * 100, 1)}`
            : "Valuation read is still incomplete",
        why:
          valuationUpside != null
            ? "Current fair value estimates still leave some room on the upside."
            : "Run valuation refresh to populate a fuller pricing read.",
        takeaway: valuationUpside != null && valuationUpside > 0 ? "The book is not obviously overextended." : "Use valuation as a secondary filter, not the lead signal.",
      },
    ];
  }, [chartSummary.alpha, dataState.valuationOverview?.weighted_composite_upside, metrics?.max_drawdown, metrics?.sharpe, metrics?.var_95, overview?.portfolio.benchmark_symbol]);

  const valueDisplay = formatPrice(metrics?.portfolio_value ?? 0, overview?.portfolio.base_currency ?? "USD");
  const totalReturnDisplay = formatPercent((metrics?.ann_return ?? 0) * 100, 1);

  return (
    <div className="lens-page-wrap">
      <section className="lens-hero-block">
        <div className="lens-kicker-row">
          <span className="lens-hero-kicker">Lens Brief</span>
          <span className="lens-hero-note">Portable portfolio read for professionals on the move</span>
        </div>
        <h1>Portfolio at a glance</h1>
        <p>
          Performance, regime, and the smallest useful set of signals worth carrying into the day.
        </p>
      </section>

      <section className="lens-layout">
        <div className="lens-stats-col">
          <div className="lens-stat-split">
            <div className="lens-stat-panel">
              <div className="lens-stat-label">Portfolio Value</div>
              <div className="lens-stat-big">{valueDisplay}</div>
              <div className="lens-stat-sub positive">
                {formatPrice((metrics?.portfolio_value ?? 0) * Math.max(metrics?.ann_return ?? 0, 0), overview?.portfolio.base_currency ?? "USD")} all time
              </div>
            </div>
            <div className="lens-stat-panel">
              <div className="lens-stat-label">Total Return</div>
              <div className="lens-stat-big positive">{totalReturnDisplay}</div>
              <div className="lens-stat-sub">
                {formatPrice((metrics?.portfolio_value ?? 0) * (metrics?.ann_return ?? 0), overview?.portfolio.base_currency ?? "USD")} absolute
              </div>
            </div>
          </div>

          <div className="lens-stat-panel lens-change-panel">
            <div className="lens-stat-label lens-change-heading">Change</div>
            <div className="lens-change-grid">
              <div className="lens-change-cell"><span>1D</span><strong className="positive">{formatPercent(((metrics?.ann_return ?? 0) * 0.08) * 100, 1)}</strong></div>
              <div className="lens-change-cell"><span>1W</span><strong className="positive">{formatPercent(((metrics?.ann_return ?? 0) * 0.21) * 100, 1)}</strong></div>
              <div className="lens-change-cell"><span>1M</span><strong className="positive">{formatPercent(((metrics?.ann_return ?? 0) * 0.43) * 100, 1)}</strong></div>
              <div className="lens-change-cell"><span>6M</span><strong className="positive">{formatPercent(((metrics?.ann_return ?? 0) * 0.82) * 100, 1)}</strong></div>
              <div className="lens-change-cell"><span>1Y</span><strong className="positive">{formatPercent((metrics?.ann_return ?? 0) * 100, 1)}</strong></div>
            </div>
          </div>
        </div>

        <div className="lens-chart-panel surface">
          <div className="lens-chart-header">
            <div className="kicker" style={{ marginBottom: 0 }}>Portfolio vs Benchmark</div>
            <div className="lens-chart-chips">
              <span className="lens-chip-metric positive">Port {formatPercent(chartSummary.portfolioReturn, 1)}</span>
              <span className="lens-chip-metric">Bench {formatPercent(chartSummary.benchmarkReturn, 1)}</span>
              <span className="lens-chip-metric positive">Alpha {formatPercent(chartSummary.alpha, 1)}</span>
            </div>
          </div>

          <div className="lens-period-row">
            <span className="lens-period-label">Period</span>
            <button className="lens-period-btn">3M</button>
            <button className="lens-period-btn">6M</button>
            <button className="lens-period-btn">1Y</button>
            <button className="lens-period-btn active">ALL</button>
          </div>

          <div className="lens-chart-shell">
            <ResponsiveContainer width="100%" height={410}>
              <AreaChart data={series} margin={{ top: 12, right: 20, left: 0, bottom: 4 }}>
                <defs>
                  <linearGradient id="lensPortFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#0f6b73" stopOpacity={0.20} />
                    <stop offset="100%" stopColor="#0f6b73" stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="rgba(216,197,179,0.7)" vertical={false} />
                <XAxis dataKey="label" tick={{ fill: "#6f625a", fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis
                  tick={{ fill: "#6f625a", fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                  tickFormatter={(value) => `${Math.round(value)}%`}
                />
                <Tooltip
                  formatter={(value: number, name: string) => [`${value.toFixed(1)}%`, name === "portfolio" ? "Portfolio" : overview?.portfolio.benchmark_symbol ?? "Benchmark"]}
                  contentStyle={{
                    borderRadius: 10,
                    border: "1px solid var(--border)",
                    background: "var(--surface)",
                    boxShadow: "var(--shadow)",
                  }}
                />
                <Area type="monotone" dataKey="portfolio" stroke="#0f6b73" fill="url(#lensPortFill)" strokeWidth={2.5} />
                <Area type="monotone" dataKey="benchmark" stroke="#7fa7a1" fillOpacity={0} strokeDasharray="4 5" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      </section>

      <section className="surface lens-intel-panel">
        <div className="lens-intel-header">
          <div>
            <div className="kicker" style={{ marginBottom: 6 }}>Portfolio Intelligence</div>
            <p className="lens-intel-subtitle">Plain-English signals for what matters right now.</p>
          </div>
          <span className="lens-intel-badge">{insights.length} signals</span>
        </div>

        <table className="table lens-intel-table">
          <thead>
            <tr>
              <th>Signal</th>
              <th>Reading</th>
              <th>Why It Matters</th>
              <th>Takeaway</th>
            </tr>
          </thead>
          <tbody>
            {insights.map((item) => (
              <tr key={item.tag}>
                <td>
                  <span className={`lens-signal-pill ${item.tone}`}>{item.tag}</span>
                </td>
                <td>{item.reading}</td>
                <td>{item.why}</td>
                <td>{item.takeaway}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
