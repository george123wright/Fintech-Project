export type Holding = {
  sym: string;
  name: string;
  weight: number;
  price: number;
  unreal: number;
  real: number;
  color: string;
};

export type ChartEvent = {
  idx: number;
  move: string;
  date: string;
  dir: "up" | "down";
  tag: "earnings" | "news" | "macro" | "undetermined";
  reason: string | null;
};

export type ChartSeries = {
  color: string;
  prices: number[];
  events: ChartEvent[];
};

export type StockDetail = {
  consensus: "BUY" | "HOLD" | "SELL";
  buy: number;
  hold: number;
  sell: number;
  avg_target: number;
  current: number;
  day_move: string;
  coverage: Array<[string, string, string]>;
  var_1d: string;
  cvar: string;
  beta: string;
  sharpe: string;
  max_dd: string;
  vol: string;
  factors: Array<[string, number]>;
  pe: string;
  fwd_pe: string;
  ev_ebitda: string;
  peg: string;
  dcf: string;
  rev_growth: string;
  eps_growth: string;
  sector: string;
  geography: string;
  revenue_exposure: string;
  currency_risk: string;
  corr_spx: string;
  insight_analyst: string;
  insight_risk: string;
  insight_exposure: string;
  insight_valuation: string;
};

export const HOLDINGS: Holding[] = [
  {
    sym: "NVDA",
    name: "NVIDIA Corporation",
    weight: 22.4,
    price: 148.2,
    unreal: 2140,
    real: 480,
    color: "#7b6ef6",
  },
  {
    sym: "MSFT",
    name: "Microsoft Corporation",
    weight: 19.1,
    price: 415.3,
    unreal: 1820,
    real: 0,
    color: "#5b8ef0",
  },
  {
    sym: "AAPL",
    name: "Apple Inc.",
    weight: 16.8,
    price: 189.5,
    unreal: -310,
    real: 920,
    color: "#3dd68c",
  },
  {
    sym: "TLT",
    name: "iShares 20+ Year Treasury ETF",
    weight: 18.3,
    price: 92.4,
    unreal: -640,
    real: 0,
    color: "#f0b959",
  },
  {
    sym: "GLD",
    name: "SPDR Gold Shares ETF",
    weight: 12.1,
    price: 198.7,
    unreal: 390,
    real: 110,
    color: "#f05b5b",
  },
  {
    sym: "BTC",
    name: "Bitcoin",
    weight: 11.3,
    price: 68420,
    unreal: 4200,
    real: -180,
    color: "#e8a838",
  },
];

export const ALLOCATION: Record<string, number> = {
  "US Equities": 58.3,
  "Fixed Income": 18.3,
  Commodities: 12.1,
  Crypto: 11.3,
};

export const ALLOC_COLORS = ["#7b6ef6", "#f0b959", "#f05b5b", "#e8a838"];

export const CHART_DATA: Record<string, ChartSeries> = {
  NVDA: {
    color: "#7b6ef6",
    prices: [118, 121, 119, 123, 125, 122, 128, 131, 129, 135, 138, 133, 130, 136, 140, 138, 142, 145, 141, 139, 144, 148, 146, 150, 148],
    events: [
      {
        idx: 3,
        move: "+4.2%",
        date: "Feb 14",
        dir: "up",
        tag: "earnings",
        reason: "Q4 earnings beat. Data center revenue surged and guidance was well ahead of consensus.",
      },
      {
        idx: 9,
        move: "+5.1%",
        date: "Feb 20",
        dir: "up",
        tag: "news",
        reason: "Microsoft expanded Azure AI deployment plans using NVDA chips as preferred infrastructure.",
      },
      {
        idx: 12,
        move: "-3.8%",
        date: "Feb 23",
        dir: "down",
        tag: "macro",
        reason: "A hotter CPI print pushed real yields higher and hit long-duration growth stocks.",
      },
      {
        idx: 17,
        move: "+2.9%",
        date: "Mar 01",
        dir: "up",
        tag: "undetermined",
        reason: null,
      },
      {
        idx: 22,
        move: "+2.7%",
        date: "Mar 07",
        dir: "up",
        tag: "news",
        reason: "Semiconductor sentiment improved on easing export restriction expectations.",
      },
    ],
  },
  MSFT: {
    color: "#5b8ef0",
    prices: [398, 400, 402, 399, 403, 406, 404, 408, 410, 407, 412, 415, 413, 410, 414, 418, 416, 412, 415, 419, 417, 414, 418, 416, 415],
    events: [
      {
        idx: 5,
        move: "+2.1%",
        date: "Feb 16",
        dir: "up",
        tag: "earnings",
        reason: "Azure guidance improved and Copilot monetization came through faster than expected.",
      },
      {
        idx: 11,
        move: "+2.0%",
        date: "Feb 22",
        dir: "up",
        tag: "news",
        reason: "OpenAI partnership was extended with additional compute commitments.",
      },
      {
        idx: 13,
        move: "-2.4%",
        date: "Feb 24",
        dir: "down",
        tag: "macro",
        reason: "A Washington hearing on large AI partnerships raised antitrust questions.",
      },
      {
        idx: 20,
        move: "+1.4%",
        date: "Mar 04",
        dir: "up",
        tag: "undetermined",
        reason: null,
      },
    ],
  },
  AAPL: {
    color: "#3dd68c",
    prices: [202, 200, 198, 201, 199, 196, 194, 197, 193, 190, 188, 191, 189, 186, 184, 188, 186, 183, 187, 189, 186, 184, 187, 190, 189],
    events: [
      {
        idx: 4,
        move: "-2.1%",
        date: "Feb 15",
        dir: "down",
        tag: "news",
        reason: "China smartphone commentary reinforced concerns around share losses.",
      },
      {
        idx: 9,
        move: "-3.4%",
        date: "Feb 20",
        dir: "down",
        tag: "macro",
        reason: "Regulatory headlines increased concerns over App Store monetization pressure.",
      },
      {
        idx: 13,
        move: "-2.8%",
        date: "Feb 24",
        dir: "down",
        tag: "undetermined",
        reason: null,
      },
      {
        idx: 19,
        move: "+2.9%",
        date: "Mar 03",
        dir: "up",
        tag: "news",
        reason: "New AI feature announcements improved sentiment around device-cycle strength.",
      },
      {
        idx: 23,
        move: "+1.6%",
        date: "Mar 08",
        dir: "up",
        tag: "undetermined",
        reason: null,
      },
    ],
  },
  TLT: {
    color: "#f0b959",
    prices: [95.0, 94.8, 94.6, 94.7, 94.3, 94.0, 93.8, 94.1, 93.9, 93.5, 93.2, 93.0, 92.9, 92.6, 92.3, 92.1, 92.4, 92.2, 92.0, 91.8, 92.1, 92.5, 92.8, 92.6, 92.4],
    events: [
      {
        idx: 4,
        move: "-0.9%",
        date: "Feb 15",
        dir: "down",
        tag: "macro",
        reason: "Treasury yields moved higher as inflation data surprised to the upside.",
      },
      {
        idx: 10,
        move: "-1.2%",
        date: "Feb 22",
        dir: "down",
        tag: "macro",
        reason: "Markets pushed back rate-cut expectations and long-end duration sold off.",
      },
      {
        idx: 16,
        move: "+0.7%",
        date: "Mar 01",
        dir: "up",
        tag: "news",
        reason: "A softer labor-market print sparked a brief bid for duration assets.",
      },
      {
        idx: 22,
        move: "+0.8%",
        date: "Mar 07",
        dir: "up",
        tag: "undetermined",
        reason: null,
      },
    ],
  },
  GLD: {
    color: "#f05b5b",
    prices: [191, 192, 191.5, 192.4, 193.1, 194.3, 193.9, 194.8, 195.7, 196.2, 195.4, 196.6, 197.1, 196.8, 197.6, 198.4, 199.1, 198.7, 199.4, 200.1, 199.6, 198.9, 199.2, 199.0, 198.7],
    events: [
      {
        idx: 5,
        move: "+1.4%",
        date: "Feb 16",
        dir: "up",
        tag: "macro",
        reason: "Geopolitical stress increased demand for hedges and reserve assets.",
      },
      {
        idx: 11,
        move: "+1.0%",
        date: "Feb 22",
        dir: "up",
        tag: "news",
        reason: "Central-bank reserve demand commentary supported precious metals.",
      },
      {
        idx: 18,
        move: "+0.9%",
        date: "Mar 04",
        dir: "up",
        tag: "macro",
        reason: "Falling real yields improved the carry-adjusted case for gold.",
      },
      {
        idx: 22,
        move: "-0.6%",
        date: "Mar 07",
        dir: "down",
        tag: "undetermined",
        reason: null,
      },
    ],
  },
  BTC: {
    color: "#e8a838",
    prices: [61200, 62400, 61800, 63200, 64500, 65300, 64800, 66100, 67200, 66800, 68100, 69400, 68800, 67600, 68400, 70100, 69500, 68700, 69900, 70800, 70000, 69100, 69800, 69000, 68420],
    events: [
      {
        idx: 3,
        move: "+3.6%",
        date: "Feb 14",
        dir: "up",
        tag: "news",
        reason: "ETF-related flow commentary supported broader crypto risk appetite.",
      },
      {
        idx: 11,
        move: "+4.2%",
        date: "Feb 22",
        dir: "up",
        tag: "macro",
        reason: "A weaker dollar and improving liquidity expectations lifted high-beta alternatives.",
      },
      {
        idx: 17,
        move: "-2.1%",
        date: "Mar 01",
        dir: "down",
        tag: "macro",
        reason: "Real-yield strength triggered profit-taking across speculative assets.",
      },
      {
        idx: 23,
        move: "-1.1%",
        date: "Mar 08",
        dir: "down",
        tag: "undetermined",
        reason: null,
      },
    ],
  },
};

export const STOCK_DETAIL: Record<string, StockDetail> = {
  NVDA: {
    consensus: "BUY",
    buy: 32,
    hold: 8,
    sell: 2,
    avg_target: 178.5,
    current: 148.2,
    day_move: "+2.3% today",
    coverage: [
      ["Morgan Stanley", "$185", "OW"],
      ["Goldman Sachs", "$180", "Buy"],
      ["JP Morgan", "$175", "OW"],
      ["UBS", "$155", "Neutral"],
    ],
    var_1d: "-3.2%",
    cvar: "-4.8%",
    beta: "1.74",
    sharpe: "1.86",
    max_dd: "-28.4%",
    vol: "48.2%",
    factors: [
      ["Growth", 0.92],
      ["Momentum", 0.78],
      ["Quality", 0.65],
      ["Rate Sensitivity", -0.58],
      ["Value", -0.12],
    ],
    pe: "68.4x",
    fwd_pe: "35.1x",
    ev_ebitda: "52.3x",
    peg: "0.54",
    dcf: "$138-$165",
    rev_growth: "+82%",
    eps_growth: "+103%",
    sector: "Semiconductors",
    geography: "US (98%)",
    revenue_exposure: "China 21%",
    currency_risk: "USD",
    corr_spx: "0.82",
    insight_analyst:
      "Analyst consensus is strongly bullish with material upside to target. Conviction is driven by AI infrastructure demand, but valuation already assumes exceptional execution.",
    insight_risk:
      "NVDA carries the highest standalone risk in the portfolio. At 22.4% weight it is the single largest contributor to total volatility and remains sensitive to real-yield shocks.",
    insight_exposure:
      "NVDA is a concentrated growth and momentum exposure. Combined with MSFT and AAPL, it makes the portfolio more duration-sensitive than ticker count suggests.",
    insight_valuation:
      "The PEG ratio still looks supportive, but most of the AI narrative is already priced in. Main risk is multiple compression if growth slows.",
  },
  MSFT: {
    consensus: "BUY",
    buy: 28,
    hold: 10,
    sell: 1,
    avg_target: 452,
    current: 415.3,
    day_move: "+0.9% today",
    coverage: [
      ["Barclays", "$470", "OW"],
      ["BofA", "$455", "Buy"],
      ["Citi", "$445", "Buy"],
      ["Jefferies", "$420", "Hold"],
    ],
    var_1d: "-2.1%",
    cvar: "-3.1%",
    beta: "1.18",
    sharpe: "1.74",
    max_dd: "-19.2%",
    vol: "27.5%",
    factors: [
      ["Growth", 0.76],
      ["Momentum", 0.58],
      ["Quality", 0.88],
      ["Rate Sensitivity", -0.34],
      ["Value", 0.05],
    ],
    pe: "34.8x",
    fwd_pe: "30.2x",
    ev_ebitda: "24.9x",
    peg: "1.48",
    dcf: "$400-$446",
    rev_growth: "+14%",
    eps_growth: "+18%",
    sector: "Software & Cloud",
    geography: "Global",
    revenue_exposure: "Enterprise / Cloud",
    currency_risk: "USD",
    corr_spx: "0.76",
    insight_analyst:
      "MSFT has a strong quality-growth profile with broad analyst support. Debate is less about demand credibility and more about upside already reflected in the multiple.",
    insight_risk:
      "Risk is lower than NVDA, but MSFT still behaves like a growth-duration asset and retains exposure to AI sentiment and rates.",
    insight_exposure:
      "MSFT diversifies business model exposure more than factor exposure. It still loads positively on growth and negatively on rising real yields.",
    insight_valuation:
      "Valuation is premium but supported by margins, cash generation and balance-sheet quality. Upside is steadier but less explosive than NVDA.",
  },
  AAPL: {
    consensus: "HOLD",
    buy: 18,
    hold: 17,
    sell: 4,
    avg_target: 198,
    current: 189.5,
    day_move: "-0.4% today",
    coverage: [
      ["Wells Fargo", "$205", "OW"],
      ["UBS", "$190", "Neutral"],
      ["Bernstein", "$185", "Market Perform"],
      ["Evercore", "$210", "OW"],
    ],
    var_1d: "-1.8%",
    cvar: "-2.7%",
    beta: "1.05",
    sharpe: "1.24",
    max_dd: "-16.8%",
    vol: "23.1%",
    factors: [
      ["Growth", 0.41],
      ["Momentum", -0.08],
      ["Quality", 0.84],
      ["Rate Sensitivity", -0.22],
      ["Value", 0.11],
    ],
    pe: "29.7x",
    fwd_pe: "27.1x",
    ev_ebitda: "21.8x",
    peg: "2.05",
    dcf: "$176-$202",
    rev_growth: "+6%",
    eps_growth: "+9%",
    sector: "Consumer Technology",
    geography: "Global",
    revenue_exposure: "China 19%",
    currency_risk: "USD",
    corr_spx: "0.72",
    insight_analyst:
      "AAPL is less consensus-loved than MSFT or NVDA because growth is slower and hardware-cycle debates persist, but the name retains premium quality support.",
    insight_risk:
      "AAPL is lower volatility than other mega-cap tech holdings, but still adds to broad growth regime risk. China headlines remain a key shock channel.",
    insight_exposure:
      "AAPL is more platform and quality exposure than pure AI beta, but it does not diversify macro factor risk much.",
    insight_valuation:
      "Multiple looks full relative to medium-term growth. Without stronger cycle acceleration, rerating upside is modest.",
  },
  TLT: {
    consensus: "HOLD",
    buy: 9,
    hold: 15,
    sell: 3,
    avg_target: 96.5,
    current: 92.4,
    day_move: "+0.2% today",
    coverage: [
      ["Rates Strategy", "$97", "Overweight"],
      ["Macro Desk", "$95", "Neutral"],
      ["Cross-Asset", "$98", "Add"],
      ["PM Note", "$91", "Trim"],
    ],
    var_1d: "-1.4%",
    cvar: "-2.0%",
    beta: "-0.24",
    sharpe: "0.52",
    max_dd: "-23.5%",
    vol: "16.7%",
    factors: [
      ["Growth", -0.22],
      ["Momentum", -0.09],
      ["Quality", 0.18],
      ["Rate Sensitivity", 0.96],
      ["Value", 0.04],
    ],
    pe: "-",
    fwd_pe: "-",
    ev_ebitda: "-",
    peg: "-",
    dcf: "$94-$101",
    rev_growth: "Yield-driven",
    eps_growth: "Yield-driven",
    sector: "Long Duration Treasuries",
    geography: "US",
    revenue_exposure: "None",
    currency_risk: "USD duration",
    corr_spx: "-0.28",
    insight_analyst:
      "TLT is the main ballast asset but only helps when growth scares dominate inflation scares. Its role is macro hedging more than alpha.",
    insight_risk:
      "Risk is almost entirely duration. A hawkish rates repricing can still drive meaningful short-term drawdowns.",
    insight_exposure:
      "TLT is your strongest positive exposure to falling yields, useful as offset to tech-duration risk but not a perfect inflation hedge.",
    insight_valuation:
      "Valuation depends on term premium and policy-rate path. If the market is too hawkish on cuts, TLT becomes more attractive.",
  },
  GLD: {
    consensus: "BUY",
    buy: 14,
    hold: 8,
    sell: 1,
    avg_target: 205,
    current: 198.7,
    day_move: "+0.5% today",
    coverage: [
      ["Metals Desk", "$207", "Buy"],
      ["Macro Strategy", "$204", "Accumulate"],
      ["Commodities PM", "$200", "Hold"],
      ["Private Bank", "$210", "Buy"],
    ],
    var_1d: "-1.2%",
    cvar: "-1.8%",
    beta: "0.14",
    sharpe: "0.88",
    max_dd: "-12.6%",
    vol: "14.4%",
    factors: [
      ["Growth", -0.11],
      ["Momentum", 0.17],
      ["Quality", 0.02],
      ["Rate Sensitivity", 0.54],
      ["Value", 0.08],
    ],
    pe: "-",
    fwd_pe: "-",
    ev_ebitda: "-",
    peg: "-",
    dcf: "$196-$212",
    rev_growth: "Spot-price linked",
    eps_growth: "Spot-price linked",
    sector: "Gold / Commodities",
    geography: "Global",
    revenue_exposure: "None",
    currency_risk: "USD / real yields",
    corr_spx: "0.08",
    insight_analyst:
      "Gold is held for resilience more than upside narratives. The case improves when real yields fall or geopolitical risk rises.",
    insight_risk:
      "GLD is less volatile than equities or crypto, but still regime-sensitive to the dollar and real yields.",
    insight_exposure:
      "GLD provides a rare non-growth exposure and diversifies equity and crypto risk better than headline volatility suggests.",
    insight_valuation:
      "There is no traditional earnings anchor. Fair value is mostly a macro call on real rates, reserve demand and stress premia.",
  },
  BTC: {
    consensus: "BUY",
    buy: 21,
    hold: 9,
    sell: 6,
    avg_target: 76000,
    current: 68420,
    day_move: "-1.1% today",
    coverage: [
      ["Digital Assets Desk", "$78,000", "Buy"],
      ["Macro Crypto", "$74,000", "Accumulate"],
      ["Cross-Asset PM", "$68,000", "Hold"],
      ["Private Markets", "$80,000", "Buy"],
    ],
    var_1d: "-4.5%",
    cvar: "-6.9%",
    beta: "2.08",
    sharpe: "1.31",
    max_dd: "-42.7%",
    vol: "61.4%",
    factors: [
      ["Growth", 0.63],
      ["Momentum", 0.81],
      ["Quality", -0.15],
      ["Rate Sensitivity", -0.29],
      ["Value", -0.34],
    ],
    pe: "-",
    fwd_pe: "-",
    ev_ebitda: "-",
    peg: "-",
    dcf: "$60k-$79k",
    rev_growth: "Network adoption",
    eps_growth: "Network adoption",
    sector: "Digital Asset",
    geography: "Global",
    revenue_exposure: "None",
    currency_risk: "USD liquidity",
    corr_spx: "0.44",
    insight_analyst:
      "BTC brings the most upside convexity in the portfolio, but also the widest dispersion of outcomes. The case is more flow-driven than fundamental in equity terms.",
    insight_risk:
      "Bitcoin is the portfolio's largest tail-risk sleeve per euro invested. Position sizing matters more than target precision.",
    insight_exposure:
      "BTC diversifies single-name equity risk, but not always macro liquidity risk. In tightening episodes it can sell off with growth assets.",
    insight_valuation:
      "There is no single valuation anchor. Fair value is a range shaped by liquidity, flows and risk appetite.",
  },
};

export const WATCHLIST_NOTES: Record<string, string> = {
  NVDA: "Dominant AI capex beneficiary, but heavily owned and rate-sensitive.",
  MSFT: "Quality compounder with broad AI monetization optionality.",
  AAPL: "Platform strength remains intact, but growth expectations are lower.",
  TLT: "Main duration hedge if growth weakens faster than inflation.",
  GLD: "Useful macro diversifier when real yields or geopolitical stress shifts.",
  BTC: "High-convexity liquidity trade; powerful but position-size sensitive.",
};

export const RANGE_CONFIG = {
  "1M": 25,
  "3M": 65,
  "6M": 130,
  "1Y": 260,
} as const;

export const PORTFOLIO_VALUE = 47284.6;
export const PORTFOLIO_PNL = 2766.2;
export const PORTFOLIO_PNL_PCT = 6.2;

export const MACRO_EVENTS = [
  {
    event: "FOMC",
    label: "FOMC Rate Decision",
    eta: "5 days",
    summary:
      "Market pricing implies a modestly hawkish path. Your tech-duration concentration makes surprise direction more important than size.",
    impact: "-3.8%",
  },
] as const;

export const REPORT_CARDS = [
  {
    title: "Weekly exposure memo",
    description: "Summarizes factor crowding, concentration and diversification gaps.",
    status: "Ready",
  },
  {
    title: "Scenario summary",
    description: "One-page view of hawkish, dovish and inflation-shock outcomes.",
    status: "Ready",
  },
  {
    title: "Valuation snapshot",
    description: "Rough DCF, RI and relative-value guide for the current holdings.",
    status: "Draft",
  },
] as const;
