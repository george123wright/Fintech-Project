import type {
  AnalystDetailResponse,
  ChatQueryRequest,
  ChatQueryResponse,
  AnalystLatestResponse,
  ExtendedAnalyticsResponse,
  HoldingsLatestResponse,
  ManualHoldingsRequest,
  OverviewResponse,
  PortfolioValuationOverview,
  Portfolio,
  PortfolioCreate,
  PriceRange,
  PricesResponse,
  RefreshResponse,
  RiskAnalyticsResponse,
  SecurityEventsResponse,
  SecurityNewsResponse,
  PortfolioNewsResponse,
  UploadValidationReport,
  SecurityValuation,
  GuidedMacroWorkflowResponse,
  IndustryAnalyticsDateMode,
  IndustryAnalyticsInterval,
  IndustryAnalyticsSortBy,
  IndustryAnalyticsSortOrder,
  IndustryAnalyticsWindow,
  IndustryOverviewResponse,
  MacroForecastResponse,
  ScenarioMetadataResponse,
  ScenarioTemplate,
  ScenarioPreviewRequest,
  ScenarioResultResponse,
  ScenarioRunListResponse,
  SecurityFinancialStatementsResponse,
  SecurityFinancialRatiosResponse,
  SecurityOverviewResponse,
  SecurityDcfDetailResponse,
  SecurityDdmDetailResponse,
  SecurityRiDetailResponse,
  ValuationAssumptions,
  ValuationRecomputeResponse,
} from "../types/api";

const API_BASE_URL =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ??
  "http://127.0.0.1:8000/api/v1";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed with ${response.status}`);
  }

  return (await response.json()) as T;
}

export async function listPortfolios(): Promise<Portfolio[]> {
  return request<Portfolio[]>("/portfolios");
}

export async function createPortfolio(payload: PortfolioCreate): Promise<Portfolio> {
  return request<Portfolio>("/portfolios", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function uploadHoldings(
  portfolioId: number,
  file: File
): Promise<UploadValidationReport> {
  const formData = new FormData();
  formData.append("file", file);

  return request<UploadValidationReport>(`/portfolios/${portfolioId}/holdings/upload`, {
    method: "POST",
    body: formData,
  });
}

export async function getLatestHoldings(
  portfolioId: number
): Promise<HoldingsLatestResponse> {
  return request<HoldingsLatestResponse>(`/portfolios/${portfolioId}/holdings/latest`);
}

export async function submitManualHoldings(
  portfolioId: number,
  payload: ManualHoldingsRequest
): Promise<UploadValidationReport> {
  return request<UploadValidationReport>(`/portfolios/${portfolioId}/holdings/manual`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function refreshPortfolio(portfolioId: number): Promise<RefreshResponse> {
  return request<RefreshResponse>(`/portfolios/${portfolioId}/refresh`, {
    method: "POST",
  });
}

export async function getOverview(portfolioId: number): Promise<OverviewResponse> {
  return request<OverviewResponse>(`/portfolios/${portfolioId}/overview`);
}

export async function getRiskAnalytics(
  portfolioId: number
): Promise<RiskAnalyticsResponse> {
  return request<RiskAnalyticsResponse>(`/portfolios/${portfolioId}/analytics/risk`);
}

export async function getExtendedAnalytics(
  portfolioId: number
): Promise<ExtendedAnalyticsResponse> {
  return request<ExtendedAnalyticsResponse>(`/portfolios/${portfolioId}/analytics/extended`);
}

export async function getIndustryOverview(
  portfolioId: number,
  options?: {
    window?: IndustryAnalyticsWindow;
    dateMode?: IndustryAnalyticsDateMode;
    startDate?: string;
    endDate?: string;
    interval?: IndustryAnalyticsInterval;
    benchmark?: string;
    sortBy?: IndustryAnalyticsSortBy;
    sortOrder?: IndustryAnalyticsSortOrder;
    scope?: "holdings" | "industry_map" | "sector_map";
  }
): Promise<IndustryOverviewResponse> {
  const suffix = buildIndustryOverviewQuery(options);
  return request<IndustryOverviewResponse>(
    `/portfolios/${portfolioId}/analytics/industry${suffix}`
  );
}

export async function getMacroForecasts(portfolioId: number): Promise<MacroForecastResponse> {
  return request<MacroForecastResponse>(`/portfolios/${portfolioId}/analytics/macro-forecasts`);
}

export function buildIndustryOverviewQuery(options?: {
  window?: IndustryAnalyticsWindow;
  dateMode?: IndustryAnalyticsDateMode;
  startDate?: string;
  endDate?: string;
  interval?: IndustryAnalyticsInterval;
  benchmark?: string;
  sortBy?: IndustryAnalyticsSortBy;
  sortOrder?: IndustryAnalyticsSortOrder;
  scope?: "holdings" | "industry_map" | "sector_map";
}): string {
  const query = new URLSearchParams();
  if (options?.window) {
    query.set("window", options.window);
  }
  if (options?.dateMode) {
    query.set("date_mode", options.dateMode);
  }
  if (options?.startDate) {
    query.set("start_date", options.startDate);
  }
  if (options?.endDate) {
    query.set("end_date", options.endDate);
  }
  if (options?.interval) {
    query.set("interval", options.interval);
  }
  if (options?.benchmark) {
    query.set("benchmark", options.benchmark);
  }
  if (options?.sortBy) {
    query.set("sort_by", options.sortBy);
  }
  if (options?.sortOrder) {
    query.set("sort_order", options.sortOrder);
  }
  if (options?.scope) {
    query.set("scope", options.scope);
  }
  return query.toString() ? `?${query.toString()}` : "";
}

export async function getSectorOverview(
  portfolioId: number,
  options?: {
    window?: IndustryAnalyticsWindow;
    dateMode?: IndustryAnalyticsDateMode;
    startDate?: string;
    endDate?: string;
    interval?: IndustryAnalyticsInterval;
    benchmark?: string;
    sortBy?: IndustryAnalyticsSortBy;
    sortOrder?: IndustryAnalyticsSortOrder;
  }
): Promise<IndustryOverviewResponse> {
  return getIndustryOverview(portfolioId, { ...options, scope: "sector_map" });
}

export async function getPrices(
  portfolioId: number,
  symbols: string[],
  range: PriceRange,
  options?: {
    startDate?: string;
    endDate?: string;
  }
): Promise<PricesResponse> {
  const query = new URLSearchParams({
    symbols: symbols.join(","),
    range,
  });
  if (options?.startDate) {
    query.set("start_date", options.startDate);
  }
  if (options?.endDate) {
    query.set("end_date", options.endDate);
  }
  return request<PricesResponse>(`/portfolios/${portfolioId}/prices?${query.toString()}`);
}

export async function getSecurityEvents(
  portfolioId: number,
  symbol: string,
  range: PriceRange,
  options?: {
    startDate?: string;
    endDate?: string;
  }
): Promise<SecurityEventsResponse> {
  const query = new URLSearchParams({ range });
  if (options?.startDate) {
    query.set("start_date", options.startDate);
  }
  if (options?.endDate) {
    query.set("end_date", options.endDate);
  }
  return request<SecurityEventsResponse>(
    `/portfolios/${portfolioId}/securities/${encodeURIComponent(symbol)}/events?${query.toString()}`
  );
}

export async function getPortfolioNews(
  portfolioId: number,
  options?: {
    limit?: number;
    perSymbol?: number;
  }
): Promise<PortfolioNewsResponse> {
  const query = new URLSearchParams();
  if (options?.limit != null) {
    query.set("limit", String(options.limit));
  }
  if (options?.perSymbol != null) {
    query.set("per_symbol", String(options.perSymbol));
  }
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return request<PortfolioNewsResponse>(`/portfolios/${portfolioId}/news${suffix}`);
}

export async function getValuationOverview(
  portfolioId: number
): Promise<PortfolioValuationOverview> {
  return request<PortfolioValuationOverview>(`/portfolios/${portfolioId}/valuations/overview`);
}

export async function recomputePortfolioValuations(
  portfolioId: number,
  assumptions?: ValuationAssumptions
): Promise<ValuationRecomputeResponse> {
  return request<ValuationRecomputeResponse>(`/portfolios/${portfolioId}/valuations/recompute`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(
      assumptions ?? {
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
          terminal_clip_buffer: 0.02,
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
          terminal_clip_buffer: 0.02,
          quality_penalty_enabled: true,
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
          terminal_clip_buffer: 0.02,
          quality_penalty_enabled: true,
          cost_of_equity: null,
        },
        relative: { peer_set: "sector", multiples: ["forward_pe", "pb", "ev_ebitda"], cap_upside: 0.6 },
      }
    ),
  });
}

export async function getAnalystLatest(symbol: string): Promise<AnalystLatestResponse> {
  return request<AnalystLatestResponse>(`/securities/${encodeURIComponent(symbol)}/analyst/latest`);
}

export async function getSecurityOverview(symbol: string): Promise<SecurityOverviewResponse> {
  return request<SecurityOverviewResponse>(`/securities/${encodeURIComponent(symbol)}/overview`);
}

export async function getSecurityFinancials(symbol: string): Promise<SecurityFinancialStatementsResponse> {
  return request<SecurityFinancialStatementsResponse>(`/securities/${encodeURIComponent(symbol)}/financials`);
}

export async function getSecurityFinancialRatios(symbol: string): Promise<SecurityFinancialRatiosResponse> {
  return request<SecurityFinancialRatiosResponse>(`/securities/${encodeURIComponent(symbol)}/financial-ratios`);
}

export async function getAnalystDetail(symbol: string): Promise<AnalystDetailResponse> {
  return request<AnalystDetailResponse>(`/securities/${encodeURIComponent(symbol)}/analyst/detail`);
}

export async function getSecurityNews(
  symbol: string,
  limit = 60
): Promise<SecurityNewsResponse> {
  return request<SecurityNewsResponse>(
    `/securities/${encodeURIComponent(symbol)}/news?limit=${encodeURIComponent(String(limit))}`
  );
}

export async function getSecurityValuationLatest(
  portfolioId: number,
  symbol: string
): Promise<SecurityValuation> {
  return request<SecurityValuation>(
    `/securities/${encodeURIComponent(symbol)}/valuation/latest?portfolio_id=${portfolioId}`
  );
}

export async function getSecurityDcfDetail(
  portfolioId: number,
  symbol: string
): Promise<SecurityDcfDetailResponse> {
  return request<SecurityDcfDetailResponse>(
    `/securities/${encodeURIComponent(symbol)}/valuation/dcf-detail?portfolio_id=${portfolioId}`
  );
}

export async function getSecurityRiDetail(
  portfolioId: number,
  symbol: string
): Promise<SecurityRiDetailResponse> {
  return request<SecurityRiDetailResponse>(
    `/securities/${encodeURIComponent(symbol)}/valuation/ri-detail?portfolio_id=${portfolioId}`
  );
}

export async function getSecurityDdmDetail(
  portfolioId: number,
  symbol: string
): Promise<SecurityDdmDetailResponse> {
  return request<SecurityDdmDetailResponse>(
    `/securities/${encodeURIComponent(symbol)}/valuation/ddm-detail?portfolio_id=${portfolioId}`
  );
}

export async function recomputeSecurityValuation(
  portfolioId: number,
  symbol: string,
  assumptions?: ValuationAssumptions
): Promise<SecurityValuation> {
  return request<SecurityValuation>(
    `/securities/${encodeURIComponent(symbol)}/valuation/recompute?portfolio_id=${portfolioId}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(assumptions ?? {}),
    }
  );
}


export async function postChatQuery(
  payload: ChatQueryRequest,
  options?: { signal?: AbortSignal }
): Promise<ChatQueryResponse> {
  return request<ChatQueryResponse>("/chat/query", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal: options?.signal,
  });
}

export async function getScenarioMetadata(
  portfolioId: number
): Promise<ScenarioMetadataResponse> {
  return request<ScenarioMetadataResponse>(`/portfolios/${portfolioId}/scenarios/metadata`);
}

export async function previewScenario(
  portfolioId: number,
  payload: ScenarioPreviewRequest,
  options?: { signal?: AbortSignal }
): Promise<ScenarioResultResponse> {
  return request<ScenarioResultResponse>(`/portfolios/${portfolioId}/scenarios/preview`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal: options?.signal,
  });
}

export async function runScenario(
  portfolioId: number,
  payload: ScenarioPreviewRequest
): Promise<ScenarioResultResponse> {
  return request<ScenarioResultResponse>(`/portfolios/${portfolioId}/scenarios/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function listScenarioRuns(
  portfolioId: number,
  limit = 100
): Promise<ScenarioRunListResponse> {
  return request<ScenarioRunListResponse>(
    `/portfolios/${portfolioId}/scenarios?limit=${encodeURIComponent(String(limit))}`
  );
}

export async function getScenarioRunDetail(
  portfolioId: number,
  runId: number
): Promise<ScenarioResultResponse> {
  return request<ScenarioResultResponse>(`/portfolios/${portfolioId}/scenarios/${runId}`);
}

export async function getSecurityScenarioSensitivity(
  portfolioId: number,
  symbol: string,
  factor: string
): Promise<Record<string, unknown>> {
  const query = new URLSearchParams({
    portfolio_id: String(portfolioId),
    factor,
  });
  return request<Record<string, unknown>>(
    `/securities/${encodeURIComponent(symbol)}/scenario-sensitivity?${query.toString()}`
  );
}


export async function getScenarioTemplates(portfolioId: number): Promise<ScenarioTemplate[]> {
  return request<ScenarioTemplate[]>(`/portfolios/${portfolioId}/scenarios/templates`);
}

export async function getGuidedMacroWorkflow(portfolioId: number): Promise<GuidedMacroWorkflowResponse> {
  return request<GuidedMacroWorkflowResponse>(`/portfolios/${portfolioId}/scenarios/workflow`);
}
