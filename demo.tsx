import React, { useMemo, useState } from "react";
import {
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Tooltip,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  LineChart,
  Line,
  AreaChart,
  Area,
} from "recharts";
import Plot from "react-plotly.js";
import {
  AlertTriangle,
  Bell,
  Calendar,
  ChevronRight,
  DollarSign,
  FileSpreadsheet,
  Globe,
  Info,
  LineChart as LineChartIcon,
  PieChart as PieChartIcon,
  Search,
  Settings,
  ShieldAlert,
  Upload,
} from "lucide-react";

type PortfolioHolding = {
  ticker: string;
  name: string;
  shares: number;
  price: number;
  dayChangePct: number;
  pnl: number;
  weight: number;
  riskContribution: number;
  sector: string;
  geography: string;
  currency: string;
  factorTilt: "Growth" | "Value" | "Momentum" | "Quality";
  beta: number;
  dividendYield: number;
  analystTarget: number;
  overlapFlag?: string;
  story: string;
};

type TabKey =
  | "overview"
  | "exposures"
  | "stress"
  | "stock"
  | "settings"
  | "upload";

const holdings: PortfolioHolding[] = [
  {
    ticker: "NVDA",
    name: "NVIDIA",
    shares: 15,
    price: 118.2,
    dayChangePct: 1.9,
    pnl: 1240,
    weight: 0.22,
    riskContribution: 0.28,
    sector: "Technology",
    geography: "US",
    currency: "USD",
    factorTilt: "Growth",
    beta: 1.72,
    dividendYield: 0.1,
    analystTarget: 132,
    overlapFlag: "High overlap with S&P 500 ETF",
    story: "Main source of upside, but also a major contributor to concentration and rate sensitivity.",
  },
  {
    ticker: "VOO",
    name: "Vanguard S&P 500 ETF",
    shares: 10,
    price: 518.4,
    dayChangePct: 0.5,
    pnl: 880,
    weight: 0.27,
    riskContribution: 0.23,
    sector: "Broad Market ETF",
    geography: "US",
    currency: "USD",
    factorTilt: "Growth",
    beta: 1.0,
    dividendYield: 1.3,
    analystTarget: 545,
    overlapFlag: "Contains NVDA, MSFT, AAPL top holdings",
    story: "Broad US exposure, but overlaps with direct tech holdings and amplifies US growth tilt.",
  },
  {
    ticker: "ASML",
    name: "ASML Holding",
    shares: 4,
    price: 912.7,
    dayChangePct: -0.8,
    pnl: 420,
    weight: 0.16,
    riskContribution: 0.17,
    sector: "Semiconductors",
    geography: "Europe",
    currency: "EUR",
    factorTilt: "Quality",
    beta: 1.18,
    dividendYield: 0.8,
    analystTarget: 975,
    story: "Diversifies geography slightly, but still reinforces semiconductor-cycle exposure.",
  },
  {
    ticker: "JPM",
    name: "JPMorgan Chase",
    shares: 18,
    price: 214.6,
    dayChangePct: 0.2,
    pnl: 310,
    weight: 0.18,
    riskContribution: 0.14,
    sector: "Financials",
    geography: "US",
    currency: "USD",
    factorTilt: "Value",
    beta: 0.92,
    dividendYield: 2.2,
    analystTarget: 228,
    story: "Provides some offset to growth-duration risk, but adds US concentration.",
  },
  {
    ticker: "NESN",
    name: "Nestlé",
    shares: 30,
    price: 102.4,
    dayChangePct: -0.3,
    pnl: 150,
    weight: 0.17,
    riskContribution: 0.08,
    sector: "Consumer Staples",
    geography: "Europe",
    currency: "CHF",
    factorTilt: "Quality",
    beta: 0.58,
    dividendYield: 2.8,
    analystTarget: 108,
    story: "Acts as a stabiliser in weaker growth scenarios and lowers portfolio beta.",
  },
];

const performanceSeries = [
  { month: "Jan", portfolio: 100, benchmark: 100 },
  { month: "Feb", portfolio: 104, benchmark: 102 },
  { month: "Mar", portfolio: 101, benchmark: 100 },
  { month: "Apr", portfolio: 108, benchmark: 104 },
  { month: "May", portfolio: 111, benchmark: 106 },
  { month: "Jun", portfolio: 116, benchmark: 109 },
  { month: "Jul", portfolio: 118, benchmark: 111 },
  { month: "Aug", portfolio: 121, benchmark: 113 },
  { month: "Sep", portfolio: 119, benchmark: 112 },
  { month: "Oct", portfolio: 126, benchmark: 116 },
  { month: "Nov", portfolio: 129, benchmark: 118 },
  { month: "Dec", portfolio: 132, benchmark: 121 },
];

const sectorExposure = [
  { name: "Technology", value: 22 },
  { name: "Broad ETF", value: 27 },
  { name: "Semiconductors", value: 16 },
  { name: "Financials", value: 18 },
  { name: "Consumer Staples", value: 17 },
];

const geographyExposure = [
  { name: "US", value: 67 },
  { name: "Europe", value: 33 },
];

const currencyExposure = [
  { name: "USD", value: 67 },
  { name: "EUR", value: 16 },
  { name: "CHF", value: 17 },
];

const factorExposure = [
  { factor: "Growth", exposure: 0.71 },
  { factor: "Value", exposure: 0.28 },
  { factor: "Momentum", exposure: 0.55 },
  { factor: "Quality", exposure: 0.36 },
  { factor: "Market", exposure: 1.08 },
  { factor: "Size", exposure: -0.12 },
];

const scenarioTemplates = {
  rates: {
    title: "+100 bps rates shock",
    summary:
      "Estimated portfolio impact: -6.4% to -8.1%. Main contributors: NVDA, VOO, ASML.",
    impacts: [
      { ticker: "NVDA", impact: -10.2 },
      { ticker: "VOO", impact: -5.8 },
      { ticker: "ASML", impact: -6.6 },
      { ticker: "JPM", impact: 1.7 },
      { ticker: "NESN", impact: -1.1 },
    ],
  },
  inflation: {
    title: "Inflation surprise",
    summary:
      "Estimated portfolio impact: -3.2% to -5.0%. Broad market duration pressure outweighs defensives.",
    impacts: [
      { ticker: "NVDA", impact: -6.3 },
      { ticker: "VOO", impact: -3.7 },
      { ticker: "ASML", impact: -3.8 },
      { ticker: "JPM", impact: 0.9 },
      { ticker: "NESN", impact: 0.5 },
    ],
  },
  recession: {
    title: "Recession / GDP slowdown",
    summary:
      "Estimated portfolio impact: -4.6% to -7.3%. Nestlé cushions some downside.",
    impacts: [
      { ticker: "NVDA", impact: -8.0 },
      { ticker: "VOO", impact: -4.1 },
      { ticker: "ASML", impact: -7.1 },
      { ticker: "JPM", impact: -5.6 },
      { ticker: "NESN", impact: -0.4 },
    ],
  },
} as const;

type ScenarioKey = keyof typeof scenarioTemplates;

const macroEvents = [
  {
    date: "2026-03-18",
    title: "Fed decision",
    relevance: "High",
    note: "Portfolio has elevated rates sensitivity due to growth tilt and tech concentration.",
  },
  {
    date: "2026-03-21",
    title: "EU CPI release",
    relevance: "Medium",
    note: "ASML and Nestlé may respond differently depending on inflation persistence.",
  },
  {
    date: "2026-03-24",
    title: "NVIDIA earnings",
    relevance: "High",
    note: "Single-stock event risk is material because NVDA contributes 28% of total risk.",
  },
];

const alertCards = [
  {
    title: "Hidden overlap detected",
    body: "VOO overlaps with your direct NVIDIA exposure, increasing US growth concentration.",
    tone: "amber",
  },
  {
    title: "Macro sensitivity elevated",
    body: "Your portfolio is more rate-sensitive than a simple sector split suggests.",
    tone: "red",
  },
  {
    title: "Stabiliser in portfolio",
    body: "Nestlé reduces drawdown risk in recession and inflation scenarios.",
    tone: "green",
  },
] as const;

const colorPalette = ["#3B82F6", "#10B981", "#8B5CF6", "#F59E0B", "#EF4444", "#14B8A6"];

function currency(n: number) {
  return new Intl.NumberFormat("en-IE", {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 0,
  }).format(n);
}

function percent(n: number, digits = 1) {
  return `${n >= 0 ? "+" : ""}${n.toFixed(digits)}%`;
}

function classNames(...parts: Array<string | false | null | undefined>) {
  return parts.filter(Boolean).join(" ");
}

function StatCard({ title, value, subtitle }: { title: string; value: string; subtitle: string }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="text-xs font-medium uppercase tracking-wide text-slate-500">{title}</div>
      <div className="mt-2 text-2xl font-semibold text-slate-900">{value}</div>
      <div className="mt-1 text-sm text-slate-500">{subtitle}</div>
    </div>
  );
}

function SectionCard({
  title,
  action,
  children,
}: {
  title: string;
  action?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-lg font-semibold text-slate-900">{title}</h3>
        {action}
      </div>
      {children}
    </div>
  );
}

export default function QuickBalanceFrontendPrototype() {
  const [activeTab, setActiveTab] = useState<TabKey>("overview");
  const [selectedTicker, setSelectedTicker] = useState<string>("NVDA");
  const [selectedScenario, setSelectedScenario] = useState<ScenarioKey>("rates");
  const [riskTolerance, setRiskTolerance] = useState("Balanced");
  const [singleStockLimit, setSingleStockLimit] = useState(20);

  const portfolioValue = useMemo(
    () => holdings.reduce((sum, h) => sum + h.shares * h.price, 0),
    []
  );

  const selectedHolding = holdings.find((h) => h.ticker === selectedTicker) ?? holdings[0];
  const scenario = scenarioTemplates[selectedScenario];

  const tabs: Array<{ key: TabKey; label: string; icon: React.ReactNode }> = [
    { key: "overview", label: "Overview", icon: <PieChartIcon className="h-4 w-4" /> },
    { key: "exposures", label: "Exposures", icon: <Globe className="h-4 w-4" /> },
    { key: "stress", label: "Stress Test", icon: <ShieldAlert className="h-4 w-4" /> },
    { key: "stock", label: "Stock Detail", icon: <LineChartIcon className="h-4 w-4" /> },
    { key: "settings", label: "Settings / Goals", icon: <Settings className="h-4 w-4" /> },
    { key: "upload", label: "Upload Flow", icon: <Upload className="h-4 w-4" /> },
  ];

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <div className="mx-auto grid min-h-screen max-w-7xl grid-cols-1 lg:grid-cols-[260px_1fr]">
        <aside className="border-r border-slate-200 bg-white px-4 py-6">
          <div className="mb-8 flex items-center gap-3 px-2">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-900 text-white">
              QB
            </div>
            <div>
              <div className="text-lg font-semibold">Quick Balance</div>
              <div className="text-xs text-slate-500">Portfolio intelligence layer</div>
            </div>
          </div>

          <nav className="space-y-2">
            {tabs.map((tab) => (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={classNames(
                  "flex w-full items-center gap-3 rounded-xl px-3 py-3 text-left text-sm font-medium transition",
                  activeTab === tab.key
                    ? "bg-slate-900 text-white"
                    : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                )}
              >
                {tab.icon}
                {tab.label}
              </button>
            ))}
          </nav>

          <div className="mt-8 rounded-2xl border border-amber-200 bg-amber-50 p-4">
            <div className="flex items-start gap-3">
              <AlertTriangle className="mt-0.5 h-5 w-5 text-amber-600" />
              <div>
                <div className="font-medium text-amber-900">Main hidden risk</div>
                <div className="mt-1 text-sm text-amber-800">
                  Portfolio looks diversified by ticker count, but 49% of risk comes from US growth-linked exposures.
                </div>
              </div>
            </div>
          </div>
        </aside>

        <main className="p-4 md:p-6 lg:p-8">
          <header className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <h1 className="text-2xl font-semibold tracking-tight md:text-3xl">Portfolio cockpit</h1>
              <p className="mt-1 text-sm text-slate-500">
                Static prototype with a 5-stock portfolio, mock metrics, and mock scenario outputs.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <button className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm">
                <Bell className="h-4 w-4" /> Alerts
              </button>
              <button className="inline-flex items-center gap-2 rounded-xl bg-slate-900 px-4 py-2 text-sm font-medium text-white shadow-sm">
                <Upload className="h-4 w-4" /> Import holdings
              </button>
            </div>
          </header>

          {activeTab === "overview" && (
            <div className="space-y-6">
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
                <StatCard title="Portfolio value" value={currency(portfolioValue)} subtitle="5 holdings across 3 currencies" />
                <StatCard title="1Y return" value={percent(32.0)} subtitle="Benchmark: +21.0%" />
                <StatCard title="Sharpe" value="1.42" subtitle="Concentration score: 7.8 / 10" />
                <StatCard title="VaR / CVaR" value="-5.9% / -8.4%" subtitle="95% one-month estimate" />
              </div>

              <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1.6fr_1fr]">
                <SectionCard title="How you are positioned">
                  <div className="h-[360px]">
                    <Plot
                      data={[
                        {
                          x: [0.11, 0.14, 0.18, 0.21, 0.27],
                          y: [0.09, 0.11, 0.13, 0.145, 0.155],
                          mode: "lines+markers",
                          type: "scatter",
                          name: "Efficient frontier",
                        },
                        {
                          x: holdings.map((h) => Math.max(0.07, h.beta / 6)),
                          y: holdings.map((h) => 0.06 + h.weight * 0.35),
                          mode: "markers+text",
                          type: "scatter",
                          text: holdings.map((h) => h.ticker),
                          textposition: "top center",
                          name: "Holdings",
                        },
                        {
                          x: [0.19],
                          y: [0.122],
                          mode: "markers+text",
                          type: "scatter",
                          text: ["Portfolio"],
                          textposition: "bottom right",
                          marker: { size: 14, symbol: "diamond" },
                          name: "Portfolio",
                        },
                      ]}
                      layout={{
                        autosize: true,
                        margin: { l: 45, r: 10, t: 20, b: 40 },
                        paper_bgcolor: "#ffffff",
                        plot_bgcolor: "#ffffff",
                        xaxis: { title: "Risk (std dev proxy)" },
                        yaxis: { title: "Expected return" },
                        showlegend: true,
                      }}
                      config={{ displayModeBar: false, responsive: true }}
                      style={{ width: "100%", height: "100%" }}
                    />
                  </div>
                </SectionCard>

                <SectionCard title="Where you stand">
                  <div className="grid grid-cols-1 gap-4">
                    <div className="h-[220px]">
                      <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                          <Pie data={holdings} dataKey="weight" nameKey="ticker" innerRadius={55} outerRadius={85}>
                            {holdings.map((entry, index) => (
                              <Cell key={entry.ticker} fill={colorPalette[index % colorPalette.length]} />
                            ))}
                          </Pie>
                          <Tooltip formatter={(value: number) => `${(value * 100).toFixed(1)}%`} />
                        </PieChart>
                      </ResponsiveContainer>
                    </div>
                    <div className="space-y-2">
                      {holdings.map((h, i) => (
                        <div key={h.ticker} className="flex items-center justify-between text-sm">
                          <div className="flex items-center gap-2">
                            <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: colorPalette[i % colorPalette.length] }} />
                            <span className="font-medium text-slate-700">{h.ticker}</span>
                          </div>
                          <span className="text-slate-500">{(h.weight * 100).toFixed(1)}%</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </SectionCard>
              </div>

              <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1.5fr_1fr]">
                <SectionCard title="What is coming" action={<Calendar className="h-4 w-4 text-slate-400" />}>
                  <div className="space-y-3">
                    {macroEvents.map((event) => (
                      <div key={event.date + event.title} className="rounded-xl border border-slate-200 p-3">
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <div className="font-medium text-slate-900">{event.title}</div>
                            <div className="mt-1 text-sm text-slate-500">{event.date}</div>
                            <div className="mt-2 text-sm text-slate-700">{event.note}</div>
                          </div>
                          <span
                            className={classNames(
                              "rounded-full px-2.5 py-1 text-xs font-medium",
                              event.relevance === "High"
                                ? "bg-rose-100 text-rose-700"
                                : "bg-amber-100 text-amber-700"
                            )}
                          >
                            {event.relevance}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </SectionCard>

                <SectionCard title="Explanation cards">
                  <div className="space-y-3">
                    {alertCards.map((card) => (
                      <div
                        key={card.title}
                        className={classNames(
                          "rounded-xl border p-3",
                          card.tone === "red" && "border-rose-200 bg-rose-50",
                          card.tone === "amber" && "border-amber-200 bg-amber-50",
                          card.tone === "green" && "border-emerald-200 bg-emerald-50"
                        )}
                      >
                        <div className="font-medium text-slate-900">{card.title}</div>
                        <div className="mt-1 text-sm text-slate-700">{card.body}</div>
                      </div>
                    ))}
                  </div>
                </SectionCard>
              </div>

              <SectionCard title="Portfolio holdings">
                <div className="overflow-x-auto">
                  <table className="min-w-full text-sm">
                    <thead>
                      <tr className="border-b border-slate-200 text-left text-slate-500">
                        <th className="pb-3 pr-4 font-medium">Symbol</th>
                        <th className="pb-3 pr-4 font-medium">Position</th>
                        <th className="pb-3 pr-4 font-medium">Weight</th>
                        <th className="pb-3 pr-4 font-medium">Day</th>
                        <th className="pb-3 pr-4 font-medium">P/L</th>
                        <th className="pb-3 pr-4 font-medium">Risk contribution</th>
                        <th className="pb-3 pr-4 font-medium">Note</th>
                      </tr>
                    </thead>
                    <tbody>
                      {holdings.map((h) => (
                        <tr key={h.ticker} className="border-b border-slate-100">
                          <td className="py-3 pr-4 font-semibold text-slate-900">{h.ticker}</td>
                          <td className="py-3 pr-4 text-slate-600">{currency(h.shares * h.price)}</td>
                          <td className="py-3 pr-4 text-slate-600">{(h.weight * 100).toFixed(1)}%</td>
                          <td className={classNames("py-3 pr-4 font-medium", h.dayChangePct >= 0 ? "text-emerald-600" : "text-rose-600")}>
                            {percent(h.dayChangePct)}
                          </td>
                          <td className="py-3 pr-4 text-slate-600">{currency(h.pnl)}</td>
                          <td className="py-3 pr-4 text-slate-600">{(h.riskContribution * 100).toFixed(1)}%</td>
                          <td className="py-3 pr-4 text-slate-500">{h.overlapFlag ?? h.story}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </SectionCard>
            </div>
          )}

          {activeTab === "exposures" && (
            <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
              <SectionCard title="Sector exposure">
                <div className="h-72">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={sectorExposure}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="name" angle={-15} textAnchor="end" height={60} />
                      <YAxis />
                      <Tooltip />
                      <Bar dataKey="value" fill="#334155" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </SectionCard>

              <SectionCard title="Geography and currency">
                <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
                  <div className="h-64">
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie data={geographyExposure} dataKey="value" nameKey="name" outerRadius={80}>
                          {geographyExposure.map((entry, index) => (
                            <Cell key={entry.name} fill={colorPalette[index % colorPalette.length]} />
                          ))}
                        </Pie>
                        <Tooltip />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                  <div className="h-64">
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie data={currencyExposure} dataKey="value" nameKey="name" outerRadius={80}>
                          {currencyExposure.map((entry, index) => (
                            <Cell key={entry.name} fill={colorPalette[(index + 2) % colorPalette.length]} />
                          ))}
                        </Pie>
                        <Tooltip />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              </SectionCard>

              <SectionCard title="Factor tilts">
                <div className="h-72">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={factorExposure} layout="vertical" margin={{ left: 20 }}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis type="number" />
                      <YAxis dataKey="factor" type="category" width={100} />
                      <Tooltip />
                      <Bar dataKey="exposure" fill="#0f766e" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </SectionCard>

              <SectionCard title="Overlap and hidden concentration">
                <div className="space-y-4">
                  <div className="rounded-xl border border-slate-200 p-4">
                    <div className="text-sm font-medium text-slate-900">Top hidden concentration warning</div>
                    <div className="mt-2 text-sm text-slate-600">
                      Although the portfolio contains 5 positions, 49% of total risk maps to a US large-cap growth cluster.
                    </div>
                  </div>
                  <div className="rounded-xl border border-slate-200 p-4">
                    <div className="text-sm font-medium text-slate-900">ETF overlap insight</div>
                    <div className="mt-2 text-sm text-slate-600">
                      VOO duplicates exposure already held directly through NVDA. Consider whether both are serving the same role.
                    </div>
                  </div>
                  <div className="rounded-xl border border-slate-200 p-4">
                    <div className="text-sm font-medium text-slate-900">Diversification score</div>
                    <div className="mt-2 text-2xl font-semibold text-slate-900">6.2 / 10</div>
                    <div className="mt-1 text-sm text-slate-500">Geography helps, but sector-factor concentration remains elevated.</div>
                  </div>
                </div>
              </SectionCard>
            </div>
          )}

          {activeTab === "stress" && (
            <div className="space-y-6">
              <SectionCard title="Scenario selector">
                <div className="flex flex-wrap gap-3">
                  {Object.entries(scenarioTemplates).map(([key, value]) => (
                    <button
                      key={key}
                      onClick={() => setSelectedScenario(key as ScenarioKey)}
                      className={classNames(
                        "rounded-xl px-4 py-2 text-sm font-medium",
                        selectedScenario === key ? "bg-slate-900 text-white" : "bg-slate-100 text-slate-700"
                      )}
                    >
                      {value.title}
                    </button>
                  ))}
                </div>
              </SectionCard>

              <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1.2fr_1fr]">
                <SectionCard title="Scenario impact">
                  <div className="mb-4 rounded-xl bg-slate-50 p-4 text-sm text-slate-700">{scenario.summary}</div>
                  <div className="h-72">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={scenario.impacts}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="ticker" />
                        <YAxis />
                        <Tooltip formatter={(v: number) => `${v.toFixed(1)}%`} />
                        <Bar dataKey="impact" fill="#7c3aed" />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </SectionCard>

                <SectionCard title="Monte Carlo distribution">
                  <div className="h-[320px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart
                        data={Array.from({ length: 60 }, (_, i) => ({
                          x: i - 30,
                          density: Math.max(0, 100 - Math.abs(i - 28) * 4 - (i % 7) * 1.8),
                        }))}
                      >
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="x" tickFormatter={(v) => `${v / 5}%`} />
                        <YAxis hide />
                        <Tooltip />
                        <Area type="monotone" dataKey="density" stroke="#2563eb" fill="#93c5fd" />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                </SectionCard>
              </div>

              <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
                <SectionCard title="Interpretation box">
                  <div className="space-y-3 text-sm text-slate-700">
                    <p>
                      In this scenario, the portfolio behaves like a growth-duration portfolio. That means higher discount rates reduce the present value of future cash flows, which hits NVDA, VOO, and ASML hardest.
                    </p>
                    <p>
                      JPM partially offsets the shock because banks can benefit from higher rates up to a point. Nestlé adds some stability because defensive consumer businesses tend to be less sensitive to growth shocks.
                    </p>
                  </div>
                </SectionCard>

                <SectionCard title="Assumptions panel">
                  <div className="space-y-3 text-sm text-slate-600">
                    <div className="rounded-xl border border-slate-200 p-3">
                      Shock size: <span className="font-medium text-slate-900">+100 bps</span>
                    </div>
                    <div className="rounded-xl border border-slate-200 p-3">
                      Horizon: <span className="font-medium text-slate-900">20 trading days</span>
                    </div>
                    <div className="rounded-xl border border-slate-200 p-3">
                      Confidence band: <span className="font-medium text-slate-900">95%</span>
                    </div>
                    <div className="rounded-xl border border-slate-200 p-3">
                      Method: <span className="font-medium text-slate-900">Static mock values for prototype only</span>
                    </div>
                  </div>
                </SectionCard>
              </div>
            </div>
          )}

          {activeTab === "stock" && (
            <div className="space-y-6">
              <SectionCard
                title="Stock selector"
                action={
                  <div className="flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-500">
                    <Search className="h-4 w-4" /> Search mock ticker
                  </div>
                }
              >
                <div className="flex flex-wrap gap-3">
                  {holdings.map((h) => (
                    <button
                      key={h.ticker}
                      onClick={() => setSelectedTicker(h.ticker)}
                      className={classNames(
                        "rounded-xl px-4 py-2 text-sm font-medium",
                        selectedTicker === h.ticker ? "bg-slate-900 text-white" : "bg-slate-100 text-slate-700"
                      )}
                    >
                      {h.ticker}
                    </button>
                  ))}
                </div>
              </SectionCard>

              <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1.3fr_1fr]">
                <SectionCard title={`${selectedHolding.name} (${selectedHolding.ticker})`}>
                  <div className="mb-4 grid grid-cols-2 gap-4 md:grid-cols-4">
                    <StatCard title="Price" value={currency(selectedHolding.price)} subtitle="Static demo value" />
                    <StatCard title="Analyst target" value={currency(selectedHolding.analystTarget)} subtitle="Consensus placeholder" />
                    <StatCard title="Beta" value={selectedHolding.beta.toFixed(2)} subtitle={`Factor tilt: ${selectedHolding.factorTilt}`} />
                    <StatCard title="Dividend yield" value={`${selectedHolding.dividendYield.toFixed(1)}%`} subtitle={selectedHolding.sector} />
                  </div>
                  <div className="h-80">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={performanceSeries.map((d, i) => ({ ...d, stock: 90 + i * 4 + (i % 3) * 2 }))}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="month" />
                        <YAxis />
                        <Tooltip />
                        <Line type="monotone" dataKey="stock" stroke="#1d4ed8" strokeWidth={2} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </SectionCard>

                <SectionCard title="Role in portfolio">
                  <div className="space-y-4 text-sm text-slate-700">
                    <div>
                      <div className="font-medium text-slate-900">Story</div>
                      <div className="mt-1">{selectedHolding.story}</div>
                    </div>
                    <div>
                      <div className="font-medium text-slate-900">Portfolio weight</div>
                      <div className="mt-1">{(selectedHolding.weight * 100).toFixed(1)}%</div>
                    </div>
                    <div>
                      <div className="font-medium text-slate-900">Risk contribution</div>
                      <div className="mt-1">{(selectedHolding.riskContribution * 100).toFixed(1)}%</div>
                    </div>
                    <div>
                      <div className="font-medium text-slate-900">Valuation compass</div>
                      <div className="mt-1">DCF: Fair to slightly undervalued · RI: Fair · Relative valuation: Premium vs peers</div>
                    </div>
                  </div>
                </SectionCard>
              </div>

              <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
                <SectionCard title="News feed">
                  <div className="space-y-3 text-sm text-slate-700">
                    <div className="rounded-xl border border-slate-200 p-3">Mock headline: Analysts raise FY revenue expectations after stronger AI demand.</div>
                    <div className="rounded-xl border border-slate-200 p-3">Mock headline: Market watching valuation premium versus sector peers.</div>
                    <div className="rounded-xl border border-slate-200 p-3">Mock headline: Options market implies elevated earnings volatility.</div>
                  </div>
                </SectionCard>

                <SectionCard title="Scenario sensitivity">
                  <div className="space-y-3 text-sm text-slate-700">
                    <div className="rounded-xl border border-slate-200 p-3">Rates shock sensitivity: High</div>
                    <div className="rounded-xl border border-slate-200 p-3">Inflation surprise sensitivity: Medium-high</div>
                    <div className="rounded-xl border border-slate-200 p-3">GDP slowdown sensitivity: Medium-high</div>
                  </div>
                </SectionCard>

                <SectionCard title="Editable assumptions">
                  <div className="space-y-3 text-sm text-slate-700">
                    <div className="rounded-xl border border-slate-200 p-3">DCF discount rate: 9.0%</div>
                    <div className="rounded-xl border border-slate-200 p-3">Terminal growth: 2.0%</div>
                    <div className="rounded-xl border border-slate-200 p-3">RI cost of equity: 10.0%</div>
                  </div>
                </SectionCard>
              </div>
            </div>
          )}

          {activeTab === "settings" && (
            <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
              <SectionCard title="Goals and preferences">
                <div className="space-y-5">
                  <div>
                    <label className="mb-2 block text-sm font-medium text-slate-700">Risk tolerance</label>
                    <select
                      value={riskTolerance}
                      onChange={(e) => setRiskTolerance(e.target.value)}
                      className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm"
                    >
                      <option>Conservative</option>
                      <option>Balanced</option>
                      <option>Growth</option>
                    </select>
                  </div>
                  <div>
                    <label className="mb-2 block text-sm font-medium text-slate-700">Max single-stock exposure</label>
                    <input
                      type="range"
                      min={5}
                      max={40}
                      value={singleStockLimit}
                      onChange={(e) => setSingleStockLimit(Number(e.target.value))}
                      className="w-full"
                    />
                    <div className="mt-2 text-sm text-slate-500">Current limit: {singleStockLimit}%</div>
                  </div>
                  <div>
                    <label className="mb-2 block text-sm font-medium text-slate-700">Benchmark</label>
                    <select className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm">
                      <option>MSCI World</option>
                      <option>S&P 500</option>
                      <option>60/40 Global</option>
                    </select>
                  </div>
                </div>
              </SectionCard>

              <SectionCard title="Alerts and compliance display">
                <div className="space-y-4 text-sm text-slate-700">
                  <div className="rounded-xl border border-slate-200 p-3">
                    Upcoming event alerts: <span className="font-medium text-slate-900">Enabled</span>
                  </div>
                  <div className="rounded-xl border border-slate-200 p-3">
                    Risk drift alerts: <span className="font-medium text-slate-900">Enabled</span>
                  </div>
                  <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                    Scenario outputs and portfolio insights are analytical estimates based on historical relationships and selected assumptions. They are intended for educational and decision-support purposes only.
                  </div>
                </div>
              </SectionCard>
            </div>
          )}

          {activeTab === "upload" && (
            <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1.1fr_1fr]">
              <SectionCard title="Upload wizard">
                <div className="space-y-4">
                  <div className="rounded-2xl border-2 border-dashed border-slate-300 bg-slate-50 p-8 text-center">
                    <Upload className="mx-auto h-10 w-10 text-slate-400" />
                    <div className="mt-3 text-lg font-medium text-slate-900">Drop CSV or XLSX here</div>
                    <div className="mt-1 text-sm text-slate-500">Or connect a broker API later in the roadmap.</div>
                    <button className="mt-4 rounded-xl bg-slate-900 px-4 py-2 text-sm font-medium text-white">
                      Choose file
                    </button>
                  </div>

                  <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                    <div className="rounded-xl border border-slate-200 p-4">
                      <FileSpreadsheet className="h-5 w-5 text-slate-500" />
                      <div className="mt-2 font-medium">CSV upload</div>
                      <div className="mt-1 text-sm text-slate-500">Map ticker, units, cost basis, and currency.</div>
                    </div>
                    <div className="rounded-xl border border-slate-200 p-4">
                      <DollarSign className="h-5 w-5 text-slate-500" />
                      <div className="mt-2 font-medium">Manual entry</div>
                      <div className="mt-1 text-sm text-slate-500">Add 5 holdings by ticker and number of shares.</div>
                    </div>
                    <div className="rounded-xl border border-slate-200 p-4">
                      <Info className="h-5 w-5 text-slate-500" />
                      <div className="mt-2 font-medium">Broker API</div>
                      <div className="mt-1 text-sm text-slate-500">Planned for later phases, not implemented in this prototype.</div>
                    </div>
                  </div>
                </div>
              </SectionCard>

              <SectionCard title="Expected flow">
                <div className="space-y-4">
                  {[
                    "1. Upload holdings file",
                    "2. Validate fields and normalise tickers",
                    "3. Enrich with sector, geography, currency, factor, and ETF data",
                    "4. Calculate exposures, overlap, metrics, and scenarios",
                    "5. Render plain-English explanation cards",
                  ].map((step) => (
                    <div key={step} className="flex items-center gap-3 rounded-xl border border-slate-200 p-3">
                      <ChevronRight className="h-4 w-4 text-slate-400" />
                      <span className="text-sm text-slate-700">{step}</span>
                    </div>
                  ))}
                </div>
              </SectionCard>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
