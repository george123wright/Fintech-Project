import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useReducer,
  type ReactNode,
} from "react";
import {
  createPortfolio,
  getScenarioMetadata,
  getScenarioRunDetail,
  listScenarioRuns,
  getAnalystDetail,
  getExtendedAnalytics,
  getAnalystLatest,
  getSecurityFinancials,
  getSecurityFinancialRatios,
  getSecurityOverview,
  getLatestHoldings,
  getOverview,
  getPortfolioNews,
  getPrices,
  getRiskAnalytics,
  getSecurityNews,
  getSecurityEvents,
  previewScenario,
  runScenario,
  getSecurityValuationLatest,
  getValuationOverview,
  listPortfolios,
  recomputePortfolioValuations,
  refreshPortfolio,
  submitManualHoldings,
  uploadHoldings,
} from "../api/client";
import {
  INITIAL_DATA_STATE,
  portfolioDataReducer,
  type PortfolioDataState,
} from "./data";
import type {
  AnalystDetailResponse,
  AnalystLatestResponse,
  ExtendedMetricSnapshot,
  ManualHoldingInput,
  PortfolioNewsResponse,
  PriceRange,
  PricesResponse,
  ScenarioPreviewRequest,
  ScenarioResultResponse,
  ScenarioRunListResponse,
  SecurityFinancialStatementsResponse,
  SecurityFinancialRatiosResponse,
  SecurityNewsResponse,
  SecurityOverviewResponse,
  SecurityEventsResponse,
  SecurityValuation,
  ValuationAssumptions,
} from "../types/api";

type DataContextValue = {
  state: PortfolioDataState;
  initialize: () => Promise<void>;
  selectPortfolio: (portfolioId: number) => Promise<void>;
  reloadActivePortfolio: () => Promise<void>;
  uploadHoldingsFile: (file: File) => Promise<void>;
  submitManualEntries: (entries: ManualHoldingInput[]) => Promise<void>;
  runManualRefresh: () => Promise<void>;
  recomputeValuations: (assumptions?: ValuationAssumptions) => Promise<void>;
  loadSymbolInsight: (symbol: string) => Promise<void>;
  fetchPricesForActive: (
    symbols: string[],
    range: PriceRange,
    options?: {
      startDate?: string;
      endDate?: string;
    }
  ) => Promise<PricesResponse>;
  fetchSecurityEventsForActive: (
    symbol: string,
    range: PriceRange,
    options?: {
      startDate?: string;
      endDate?: string;
    }
  ) => Promise<SecurityEventsResponse>;
  fetchSecurityOverview: (symbol: string) => Promise<SecurityOverviewResponse>;
  fetchSecurityFinancials: (symbol: string) => Promise<SecurityFinancialStatementsResponse>;
  fetchSecurityRatios: (symbol: string) => Promise<SecurityFinancialRatiosResponse>;
  fetchAnalystDetail: (symbol: string) => Promise<AnalystDetailResponse>;
  fetchSecurityNews: (symbol: string, limit?: number) => Promise<SecurityNewsResponse>;
  fetchPortfolioNewsForActive: (options?: {
    limit?: number;
    perSymbol?: number;
  }) => Promise<PortfolioNewsResponse>;
  previewScenarioForActive: (
    payload: ScenarioPreviewRequest,
    options?: { signal?: AbortSignal }
  ) => Promise<ScenarioResultResponse>;
  runScenarioForActive: (payload: ScenarioPreviewRequest) => Promise<ScenarioResultResponse>;
  listScenarioRunsForActive: (limit?: number) => Promise<ScenarioRunListResponse>;
  loadScenarioRunDetailForActive: (runId: number) => Promise<ScenarioResultResponse>;
};

const DataContext = createContext<DataContextValue | null>(null);

async function loadPortfolioPayload(portfolioId: number) {
  const overviewPromise = getOverview(portfolioId).catch(() => null);
  const holdingsPromise = getLatestHoldings(portfolioId).catch(() => null);
  const riskPromise = getRiskAnalytics(portfolioId).catch(() => null);
  const extendedPromise = getExtendedAnalytics(portfolioId).catch(() => null);
  const valuationPromise = getValuationOverview(portfolioId).catch(() => null);
  const scenarioMetaPromise = getScenarioMetadata(portfolioId).catch(() => null);
  const scenarioRunsPromise = listScenarioRuns(portfolioId, 80).catch(() => null);

  const [overview, holdings, risk, extendedRaw, valuationOverviewRaw, scenarioMetadata, scenarioRuns] = await Promise.all([
    overviewPromise,
    holdingsPromise,
    riskPromise,
    extendedPromise,
    valuationPromise,
    scenarioMetaPromise,
    scenarioRunsPromise,
  ]);

  const extendedMetrics: ExtendedMetricSnapshot | null = extendedRaw?.extended ?? null;
  const valuationOverview = valuationOverviewRaw ?? overview?.valuation_summary ?? null;
  const dataWarnings: string[] = [];

  if (extendedMetrics?.warnings?.length) {
    dataWarnings.push(...extendedMetrics.warnings);
  }
  if (valuationOverview?.warnings?.length) {
    dataWarnings.push(...valuationOverview.warnings);
  }
  if (scenarioMetadata?.warnings?.length) {
    dataWarnings.push(...scenarioMetadata.warnings);
  }

  const refreshError = overview?.last_refresh?.error;
  if (refreshError) {
    dataWarnings.push(refreshError);
  }

  return {
    overview,
    holdings: holdings?.positions ?? [],
    risk,
    extendedMetrics,
    valuationOverview,
    scenarioMetadata,
    scenarioRuns: scenarioRuns?.runs ?? [],
    dataWarnings: Array.from(new Set(dataWarnings)),
  };
}

export function DataProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(portfolioDataReducer, INITIAL_DATA_STATE);

  const initialize = useCallback(async () => {
    dispatch({ type: "loading" });
    try {
      let portfolios = await listPortfolios();
      if (portfolios.length === 0) {
        await createPortfolio({ name: "My Portfolio" });
        portfolios = await listPortfolios();
      }

      const activePortfolioId = portfolios[0]?.id;
      dispatch({ type: "set_portfolios", portfolios });

      if (activePortfolioId != null) {
        dispatch({ type: "set_active", portfolioId: activePortfolioId });
        const payload = await loadPortfolioPayload(activePortfolioId);
        dispatch({
          type: "set_payload",
          overview: payload.overview,
          holdings: payload.holdings,
          risk: payload.risk,
          extendedMetrics: payload.extendedMetrics,
          valuationOverview: payload.valuationOverview,
          scenarioMetadata: payload.scenarioMetadata,
          scenarioRuns: payload.scenarioRuns,
          dataWarnings: payload.dataWarnings,
        });
      }

      dispatch({ type: "ready" });
    } catch (error) {
      dispatch({ type: "error", message: (error as Error).message });
    }
  }, []);

  const selectPortfolio = useCallback(async (portfolioId: number) => {
    dispatch({ type: "loading" });
    try {
      dispatch({ type: "set_active", portfolioId });
      const payload = await loadPortfolioPayload(portfolioId);
      dispatch({
        type: "set_payload",
        overview: payload.overview,
        holdings: payload.holdings,
        risk: payload.risk,
        extendedMetrics: payload.extendedMetrics,
        valuationOverview: payload.valuationOverview,
        scenarioMetadata: payload.scenarioMetadata,
        scenarioRuns: payload.scenarioRuns,
        dataWarnings: payload.dataWarnings,
      });
      dispatch({ type: "ready" });
    } catch (error) {
      dispatch({ type: "error", message: (error as Error).message });
    }
  }, []);

  const reloadActivePortfolio = useCallback(async () => {
    if (state.activePortfolioId == null) {
      await initialize();
      return;
    }

    dispatch({ type: "loading" });
    try {
      const payload = await loadPortfolioPayload(state.activePortfolioId);
      dispatch({
        type: "set_payload",
        overview: payload.overview,
        holdings: payload.holdings,
        risk: payload.risk,
        extendedMetrics: payload.extendedMetrics,
        valuationOverview: payload.valuationOverview,
        scenarioMetadata: payload.scenarioMetadata,
        scenarioRuns: payload.scenarioRuns,
        dataWarnings: payload.dataWarnings,
      });
      dispatch({ type: "ready" });
    } catch (error) {
      dispatch({ type: "error", message: (error as Error).message });
    }
  }, [initialize, state.activePortfolioId]);

  const runManualRefresh = useCallback(async () => {
    if (state.activePortfolioId == null) return;

    dispatch({ type: "loading" });
    try {
      const refresh = await refreshPortfolio(state.activePortfolioId);
      dispatch({ type: "set_refresh", refresh });
      const payload = await loadPortfolioPayload(state.activePortfolioId);
      dispatch({
        type: "set_payload",
        overview: payload.overview,
        holdings: payload.holdings,
        risk: payload.risk,
        extendedMetrics: payload.extendedMetrics,
        valuationOverview: payload.valuationOverview,
        scenarioMetadata: payload.scenarioMetadata,
        scenarioRuns: payload.scenarioRuns,
        dataWarnings: payload.dataWarnings,
      });
      dispatch({ type: "ready" });
    } catch (error) {
      dispatch({ type: "error", message: (error as Error).message });
    }
  }, [state.activePortfolioId]);

  const recomputeValuations = useCallback(async (assumptions?: ValuationAssumptions) => {
    if (state.activePortfolioId == null) return;

    dispatch({ type: "loading" });
    try {
      await recomputePortfolioValuations(state.activePortfolioId, assumptions);
      const payload = await loadPortfolioPayload(state.activePortfolioId);
      dispatch({
        type: "set_payload",
        overview: payload.overview,
        holdings: payload.holdings,
        risk: payload.risk,
        extendedMetrics: payload.extendedMetrics,
        valuationOverview: payload.valuationOverview,
        scenarioMetadata: payload.scenarioMetadata,
        scenarioRuns: payload.scenarioRuns,
        dataWarnings: payload.dataWarnings,
      });
      dispatch({ type: "ready" });
    } catch (error) {
      dispatch({ type: "error", message: (error as Error).message });
    }
  }, [state.activePortfolioId]);

  const uploadHoldingsFile = useCallback(
    async (file: File) => {
      if (state.activePortfolioId == null) return;

      dispatch({ type: "loading" });
      try {
        const upload = await uploadHoldings(state.activePortfolioId, file);
        dispatch({ type: "set_upload", upload });

        if (upload.accepted_rows > 0) {
          const refresh = await refreshPortfolio(state.activePortfolioId);
          dispatch({ type: "set_refresh", refresh });
        }

        const payload = await loadPortfolioPayload(state.activePortfolioId);
        dispatch({
          type: "set_payload",
          overview: payload.overview,
          holdings: payload.holdings,
          risk: payload.risk,
          extendedMetrics: payload.extendedMetrics,
          valuationOverview: payload.valuationOverview,
          scenarioMetadata: payload.scenarioMetadata,
          scenarioRuns: payload.scenarioRuns,
          dataWarnings: payload.dataWarnings,
        });
        dispatch({ type: "ready" });
      } catch (error) {
        dispatch({ type: "error", message: (error as Error).message });
      }
    },
    [state.activePortfolioId]
  );

  const submitManualEntries = useCallback(
    async (entries: ManualHoldingInput[]) => {
      if (state.activePortfolioId == null) return;

      dispatch({ type: "loading" });
      try {
        const upload = await submitManualHoldings(state.activePortfolioId, {
          holdings: entries,
        });
        dispatch({ type: "set_upload", upload });

        if (upload.accepted_rows > 0) {
          const refresh = await refreshPortfolio(state.activePortfolioId);
          dispatch({ type: "set_refresh", refresh });
        }

        const payload = await loadPortfolioPayload(state.activePortfolioId);
        dispatch({
          type: "set_payload",
          overview: payload.overview,
          holdings: payload.holdings,
          risk: payload.risk,
          extendedMetrics: payload.extendedMetrics,
          valuationOverview: payload.valuationOverview,
          scenarioMetadata: payload.scenarioMetadata,
          scenarioRuns: payload.scenarioRuns,
          dataWarnings: payload.dataWarnings,
        });
        dispatch({ type: "ready" });
      } catch (error) {
        dispatch({ type: "error", message: (error as Error).message });
      }
    },
    [state.activePortfolioId]
  );

  const loadSymbolInsight = useCallback(
    async (symbol: string) => {
      const cleaned = symbol.trim().toUpperCase();
      if (!cleaned) return;

      let analyst: AnalystLatestResponse | undefined;
      let valuation: SecurityValuation | undefined;

      try {
        analyst = await getAnalystLatest(cleaned);
      } catch {
        analyst = undefined;
      }

      if (state.activePortfolioId != null) {
        try {
          valuation = await getSecurityValuationLatest(state.activePortfolioId, cleaned);
        } catch {
          valuation = undefined;
        }
      }

      dispatch({
        type: "set_symbol_payload",
        symbol: cleaned,
        analyst,
        valuation,
      });
    },
    [state.activePortfolioId]
  );

  const fetchPricesForActive = useCallback(
    async (
      symbols: string[],
      range: PriceRange,
      options?: {
        startDate?: string;
        endDate?: string;
      }
    ): Promise<PricesResponse> => {
      if (state.activePortfolioId == null) {
        throw new Error("No active portfolio.");
      }
      return getPrices(state.activePortfolioId, symbols, range, options);
    },
    [state.activePortfolioId]
  );

  const fetchSecurityEventsForActive = useCallback(
    async (
      symbol: string,
      range: PriceRange,
      options?: {
        startDate?: string;
        endDate?: string;
      }
    ): Promise<SecurityEventsResponse> => {
      if (state.activePortfolioId == null) {
        throw new Error("No active portfolio.");
      }
      return getSecurityEvents(state.activePortfolioId, symbol, range, options);
    },
    [state.activePortfolioId]
  );

  const fetchSecurityOverview = useCallback(async (symbol: string): Promise<SecurityOverviewResponse> => {
    const cleaned = symbol.trim().toUpperCase();
    if (!cleaned) {
      throw new Error("Symbol is required.");
    }
    return getSecurityOverview(cleaned);
  }, []);

  const fetchSecurityFinancials = useCallback(async (symbol: string): Promise<SecurityFinancialStatementsResponse> => {
    const cleaned = symbol.trim().toUpperCase();
    if (!cleaned) {
      throw new Error("Symbol is required.");
    }
    return getSecurityFinancials(cleaned);
  }, []);

  const fetchSecurityRatios = useCallback(async (symbol: string): Promise<SecurityFinancialRatiosResponse> => {
    const cleaned = symbol.trim().toUpperCase();
    if (!cleaned) {
      throw new Error("Symbol is required.");
    }
    return getSecurityFinancialRatios(cleaned);
  }, []);

  const fetchAnalystDetail = useCallback(async (symbol: string): Promise<AnalystDetailResponse> => {
    const cleaned = symbol.trim().toUpperCase();
    if (!cleaned) {
      throw new Error("Symbol is required.");
    }
    return getAnalystDetail(cleaned);
  }, []);

  const fetchSecurityNews = useCallback(async (symbol: string, limit = 60): Promise<SecurityNewsResponse> => {
    const cleaned = symbol.trim().toUpperCase();
    if (!cleaned) {
      throw new Error("Symbol is required.");
    }
    return getSecurityNews(cleaned, limit);
  }, []);

  const fetchPortfolioNewsForActive = useCallback(
    async (options?: { limit?: number; perSymbol?: number }): Promise<PortfolioNewsResponse> => {
      if (state.activePortfolioId == null) {
        throw new Error("No active portfolio.");
      }
      return getPortfolioNews(state.activePortfolioId, options);
    },
    [state.activePortfolioId]
  );

  const previewScenarioForActive = useCallback(
    async (
      payload: ScenarioPreviewRequest,
      options?: { signal?: AbortSignal }
    ): Promise<ScenarioResultResponse> => {
      if (state.activePortfolioId == null) {
        throw new Error("No active portfolio.");
      }
      const response = await previewScenario(state.activePortfolioId, payload, options);
      dispatch({ type: "set_scenario_preview", preview: response });
      return response;
    },
    [state.activePortfolioId]
  );

  const runScenarioForActive = useCallback(
    async (payload: ScenarioPreviewRequest): Promise<ScenarioResultResponse> => {
      if (state.activePortfolioId == null) {
        throw new Error("No active portfolio.");
      }
      const response = await runScenario(state.activePortfolioId, payload);
      dispatch({ type: "set_scenario_preview", preview: response });
      const runs = await listScenarioRuns(state.activePortfolioId, 120);
      dispatch({ type: "set_scenario_runs", runs: runs.runs });
      return response;
    },
    [state.activePortfolioId]
  );

  const listScenarioRunsForActive = useCallback(
    async (limit = 100): Promise<ScenarioRunListResponse> => {
      if (state.activePortfolioId == null) {
        throw new Error("No active portfolio.");
      }
      const response = await listScenarioRuns(state.activePortfolioId, limit);
      dispatch({ type: "set_scenario_runs", runs: response.runs });
      return response;
    },
    [state.activePortfolioId]
  );

  const loadScenarioRunDetailForActive = useCallback(
    async (runId: number): Promise<ScenarioResultResponse> => {
      if (state.activePortfolioId == null) {
        throw new Error("No active portfolio.");
      }
      const response = await getScenarioRunDetail(state.activePortfolioId, runId);
      dispatch({ type: "set_scenario_preview", preview: response });
      return response;
    },
    [state.activePortfolioId]
  );

  const value = useMemo<DataContextValue>(
    () => ({
      state,
      initialize,
      selectPortfolio,
      reloadActivePortfolio,
      uploadHoldingsFile,
      submitManualEntries,
      runManualRefresh,
      recomputeValuations,
      loadSymbolInsight,
      fetchPricesForActive,
      fetchSecurityEventsForActive,
      fetchSecurityOverview,
      fetchSecurityFinancials,
      fetchSecurityRatios,
      fetchAnalystDetail,
      fetchSecurityNews,
      fetchPortfolioNewsForActive,
      previewScenarioForActive,
      runScenarioForActive,
      listScenarioRunsForActive,
      loadScenarioRunDetailForActive,
    }),
    [
      fetchPricesForActive,
      initialize,
      loadSymbolInsight,
      recomputeValuations,
      reloadActivePortfolio,
      runManualRefresh,
      selectPortfolio,
      state,
      submitManualEntries,
      uploadHoldingsFile,
      fetchSecurityEventsForActive,
      fetchSecurityOverview,
      fetchSecurityFinancials,
      fetchSecurityRatios,
      fetchAnalystDetail,
      fetchSecurityNews,
      fetchPortfolioNewsForActive,
      previewScenarioForActive,
      runScenarioForActive,
      listScenarioRunsForActive,
      loadScenarioRunDetailForActive,
    ]
  );

  useEffect(() => {
    void initialize();
  }, [initialize]);

  return <DataContext.Provider value={value}>{children}</DataContext.Provider>;
}

export function usePortfolioData(): DataContextValue {
  const ctx = useContext(DataContext);
  if (ctx == null) {
    throw new Error("usePortfolioData must be used within DataProvider");
  }
  return ctx;
}
