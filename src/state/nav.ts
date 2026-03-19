export type Page =
  | "lens"
  | "overview"
  | "watchlist"
  | "scenarios"
  | "reports"
  | "macro"
  | "stock"
  | "chart"
  | "analyst_history"
  | "portfolio_news";

export type RangeKey = "1M" | "3M" | "6M" | "1Y" | "5Y" | "CUSTOM";
export type StockTabKey =
  | "overview"
  | "income"
  | "balance"
  | "cashflow"
  | "ratios"
  | "analyst"
  | "risk"
  | "exposure"
  | "valuation"
  | "corporate"
  | "insider"
  | "news";
export type StockSectionKey = "corporate_actions" | "insider_transactions" | "analyst_revisions" | null;

export type NavState = {
  page: Page;
  sym: string | null;
  chartSym: string;
  highlightIdx: number | null;
  chartRange: RangeKey;
  stockTab: StockTabKey;
  stockSection: StockSectionKey;
  macro: "FOMC";
};

export const DEFAULT_NAV: NavState = {
  page: "lens",
  sym: null,
  chartSym: "NVDA",
  highlightIdx: null,
  chartRange: "1M",
  stockTab: "overview",
  stockSection: null,
  macro: "FOMC",
};

export type NavAction =
  | { type: "go_page"; page: Page }
  | { type: "go_overview" }
  | { type: "open_stock"; sym: string; tab?: StockTabKey; section?: StockSectionKey }
  | { type: "open_stock_section"; sym: string; section: Exclude<StockSectionKey, null> }
  | { type: "open_chart"; sym: string }
  | { type: "open_analyst_history"; sym: string }
  | { type: "open_macro"; event: "FOMC" }
  | { type: "set_highlight"; idx: number | null }
  | { type: "set_range"; range: RangeKey }
  | { type: "set_stock_section"; section: StockSectionKey }
  | { type: "back"; target?: Page };

export function navReducer(state: NavState, action: NavAction): NavState {
  switch (action.type) {
    case "go_overview":
      return { ...DEFAULT_NAV, page: "overview" };
    case "go_page":
      if (action.page === "overview") {
        return { ...DEFAULT_NAV, page: "overview" };
      }
      return {
        ...state,
        page: action.page,
        highlightIdx: null,
        stockSection: action.page === "stock" ? state.stockSection : null,
      };
    case "open_stock":
      return {
        ...state,
        page: "stock",
        sym: action.sym,
        highlightIdx: null,
        stockTab: action.tab ?? "overview",
        stockSection: action.section ?? null,
      };
    case "open_stock_section":
      {
        const destinationTab: StockTabKey =
          action.section === "analyst_revisions"
            ? "analyst"
            : action.section === "insider_transactions"
              ? "insider"
              : "corporate";
      return {
        ...state,
        page: "stock",
        sym: action.sym,
        stockTab: destinationTab,
        stockSection: action.section,
        highlightIdx: null,
      };
      }
    case "open_chart":
      return {
        ...state,
        page: "chart",
        chartSym: action.sym,
        chartRange: "1M",
        highlightIdx: null,
        stockSection: null,
      };
    case "open_analyst_history":
      return {
        ...state,
        page: "analyst_history",
        sym: action.sym,
        highlightIdx: null,
      };
    case "open_macro":
      return {
        ...state,
        page: "macro",
        macro: action.event,
        highlightIdx: null,
      };
    case "set_highlight":
      return { ...state, highlightIdx: action.idx };
    case "set_range":
      return { ...state, chartRange: action.range };
    case "set_stock_section":
      return { ...state, stockSection: action.section };
    case "back":
      if (!action.target || action.target === "overview") {
        return { ...DEFAULT_NAV, page: "overview" };
      }
      return { ...DEFAULT_NAV, page: action.target };
    default:
      return state;
  }
}
