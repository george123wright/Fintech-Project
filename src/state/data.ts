import type {
  AnalystLatestResponse,
  ExtendedMetricSnapshot,
  HoldingPosition,
  OverviewResponse,
  PortfolioValuationOverview,
  Portfolio,
  RefreshResponse,
  RiskAnalyticsResponse,
  ScenarioMetadataResponse,
  ScenarioResultResponse,
  ScenarioRunListItem,
  SecurityValuation,
  UploadValidationReport,
} from "../types/api";

export type DataStatus = "idle" | "loading" | "ready" | "error";

export type PortfolioDataState = {
  status: DataStatus;
  error: string | null;
  portfolios: Portfolio[];
  activePortfolioId: number | null;
  overview: OverviewResponse | null;
  holdings: HoldingPosition[];
  risk: RiskAnalyticsResponse | null;
  extendedMetrics: ExtendedMetricSnapshot | null;
  valuationOverview: PortfolioValuationOverview | null;
  analystBySymbol: Record<string, AnalystLatestResponse | undefined>;
  valuationBySymbol: Record<string, SecurityValuation | undefined>;
  scenarioMetadata: ScenarioMetadataResponse | null;
  scenarioPreview: ScenarioResultResponse | null;
  scenarioRuns: ScenarioRunListItem[];
  dataWarnings: string[];
  lastUpload: UploadValidationReport | null;
  lastRefresh: RefreshResponse | null;
};

export const INITIAL_DATA_STATE: PortfolioDataState = {
  status: "idle",
  error: null,
  portfolios: [],
  activePortfolioId: null,
  overview: null,
  holdings: [],
  risk: null,
  extendedMetrics: null,
  valuationOverview: null,
  analystBySymbol: {},
  valuationBySymbol: {},
  scenarioMetadata: null,
  scenarioPreview: null,
  scenarioRuns: [],
  dataWarnings: [],
  lastUpload: null,
  lastRefresh: null,
};

export type PortfolioDataAction =
  | { type: "loading" }
  | { type: "error"; message: string }
  | { type: "set_portfolios"; portfolios: Portfolio[] }
  | { type: "set_active"; portfolioId: number }
  | {
      type: "set_payload";
      overview: OverviewResponse | null;
      holdings: HoldingPosition[];
      risk: RiskAnalyticsResponse | null;
      extendedMetrics: ExtendedMetricSnapshot | null;
      valuationOverview: PortfolioValuationOverview | null;
      scenarioMetadata: ScenarioMetadataResponse | null;
      scenarioRuns: ScenarioRunListItem[];
      dataWarnings: string[];
    }
  | {
      type: "set_symbol_payload";
      symbol: string;
      analyst: AnalystLatestResponse | undefined;
      valuation: SecurityValuation | undefined;
    }
  | { type: "set_upload"; upload: UploadValidationReport | null }
  | { type: "set_refresh"; refresh: RefreshResponse | null }
  | { type: "set_scenario_preview"; preview: ScenarioResultResponse | null }
  | { type: "set_scenario_runs"; runs: ScenarioRunListItem[] }
  | { type: "ready" };

export function portfolioDataReducer(
  state: PortfolioDataState,
  action: PortfolioDataAction
): PortfolioDataState {
  switch (action.type) {
    case "loading":
      return { ...state, status: "loading", error: null };
    case "error":
      return { ...state, status: "error", error: action.message };
    case "set_portfolios":
      return { ...state, portfolios: action.portfolios };
    case "set_active":
      return { ...state, activePortfolioId: action.portfolioId };
    case "set_payload":
      return {
        ...state,
        overview: action.overview,
        holdings: action.holdings,
        risk: action.risk,
        extendedMetrics: action.extendedMetrics,
        valuationOverview: action.valuationOverview,
        scenarioMetadata: action.scenarioMetadata,
        scenarioRuns: action.scenarioRuns,
        dataWarnings: action.dataWarnings,
      };
    case "set_symbol_payload":
      return {
        ...state,
        analystBySymbol: {
          ...state.analystBySymbol,
          [action.symbol]: action.analyst,
        },
        valuationBySymbol: {
          ...state.valuationBySymbol,
          [action.symbol]: action.valuation,
        },
      };
    case "set_upload":
      return { ...state, lastUpload: action.upload };
    case "set_refresh":
      return { ...state, lastRefresh: action.refresh };
    case "set_scenario_preview":
      return { ...state, scenarioPreview: action.preview };
    case "set_scenario_runs":
      return { ...state, scenarioRuns: action.runs };
    case "ready":
      return { ...state, status: "ready", error: null };
    default:
      return state;
  }
}
