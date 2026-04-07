export type Portfolio = {
  id: number;
  name: string;
  base_currency: string;
  benchmark_symbol: string;
  created_at: string;
};

export type PortfolioCreate = {
  name: string;
  base_currency?: string;
  benchmark_symbol?: string;
};

export type ManualHoldingInput = {
  ticker: string;
  units?: number | null;
  market_value?: number | null;
  cost_basis?: number | null;
  currency?: string;
  name?: string | null;
  asset_type?: string | null;
};

export type ManualHoldingsRequest = {
  holdings: ManualHoldingInput[];
};

export type UploadValidationReport = {
  upload_id: number;
  status: string;
  accepted_rows: number;
  rejected_rows: number;
  unknown_tickers: string[];
  missing_fields: string[];
  errors: string[];
  snapshot_id?: number | null;
  as_of_date?: string | null;
};

export type HoldingPosition = {
  symbol: string;
  name: string | null;
  asset_type: string | null;
  units: number | null;
  market_value: number;
  cost_basis: number | null;
  currency: string;
  weight: number;
};

export type HoldingsLatestResponse = {
  portfolio_id: number;
  snapshot_id: number;
  as_of_date: string;
  positions: HoldingPosition[];
};

export type RiskMetric = {
  as_of_date: string;
  window: string;
  portfolio_value: number;
  ann_return: number;
  ann_vol: number;
  sharpe: number;
  sortino: number;
  max_drawdown: number;
  var_95: number;
  cvar_95: number;
  beta: number;
  top3_weight_share: number;
  hhi: number;
};

export type RiskContribution = {
  symbol: string;
  marginal_risk: number;
  component_risk: number;
  pct_total_risk: number;
};

export type RiskAnalyticsResponse = {
  portfolio_id: number;
  snapshot_id: number;
  metrics: RiskMetric;
  contributions: RiskContribution[];
};

export type ExtendedMetricSnapshot = {
  as_of_date: string;
  window: string;
  benchmark_symbol: string;
  metrics: Record<string, unknown>;
  warnings: string[];
};

export type ExtendedAnalyticsResponse = {
  portfolio_id: number;
  snapshot_id: number;
  extended: ExtendedMetricSnapshot;
};

export type RefreshJob = {
  id: number;
  trigger_type: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  error: string | null;
};

export type RefreshResponse = {
  job: RefreshJob;
  metrics: RiskMetric | null;
};

export type ValuationRun = {
  id: number;
  portfolio_id: number;
  snapshot_id: number;
  trigger_type: string;
  status: string;
  assumptions_json: string;
  started_at: string;
  finished_at: string | null;
  error: string | null;
};

export type SecurityValuation = {
  symbol: string;
  as_of_date: string;
  model_status: string;
  analyst_upside: number | null;
  dcf_fair_value: number | null;
  dcf_upside: number | null;
  ri_fair_value: number | null;
  ri_upside: number | null;
  ddm_fair_value: number | null;
  ddm_upside: number | null;
  relative_fair_value: number | null;
  relative_upside: number | null;
  composite_fair_value: number | null;
  composite_upside: number | null;
  confidence_low: number | null;
  confidence_high: number | null;
  inputs: Record<string, unknown>;
  warnings: string[];
};

export type DcfDetailScenario = {
  scenario_key: string;
  assumptions: Record<string, unknown>;
  forecast: Record<string, unknown>[];
  diagnostics: Record<string, unknown>;
  warnings: string[];
};

export type SecurityDcfDetailResponse = {
  portfolio_id: number;
  symbol: string;
  as_of_date: string | null;
  status: "ok" | "partial" | "no_data" | string;
  model_version: string | null;
  quality_score: number | null;
  anchor_mode: string | null;
  anchor_diagnostics_summary: Record<string, unknown>;
  tv_breakdown_summary: Record<string, unknown>;
  assumptions_used: Record<string, unknown>;
  scenarios: DcfDetailScenario[];
  warnings: string[];
};

export type RiDetailScenario = {
  scenario_key: string;
  assumptions: Record<string, unknown>;
  forecast: Record<string, unknown>[];
  diagnostics: Record<string, unknown>;
  warnings: string[];
};

export type SecurityRiDetailResponse = {
  portfolio_id: number;
  symbol: string;
  as_of_date: string | null;
  status: "ok" | "partial" | "no_data" | string;
  model_version: string | null;
  quality_score: number | null;
  anchor_mode: string | null;
  anchor_diagnostics_summary: Record<string, unknown>;
  terminal_summary: Record<string, unknown>;
  assumptions_used: Record<string, unknown>;
  scenarios: RiDetailScenario[];
  warnings: string[];
};

export type DdmDetailScenario = {
  scenario_key: string;
  assumptions: Record<string, unknown>;
  forecast: Record<string, unknown>[];
  diagnostics: Record<string, unknown>;
  warnings: string[];
};

export type SecurityDdmDetailResponse = {
  portfolio_id: number;
  symbol: string;
  as_of_date: string | null;
  status: "ok" | "partial" | "no_data" | string;
  model_version: string | null;
  quality_score: number | null;
  anchor_mode: string | null;
  coverage_mode: string | null;
  anchor_diagnostics_summary: Record<string, unknown>;
  terminal_summary: Record<string, unknown>;
  assumptions_used: Record<string, unknown>;
  scenarios: DdmDetailScenario[];
  warnings: string[];
};

export type PortfolioValuationOverview = {
  portfolio_id: number;
  snapshot_id: number | null;
  as_of_date: string | null;
  status: string;
  weighted_analyst_upside: number | null;
  weighted_dcf_upside: number | null;
  weighted_ri_upside: number | null;
  weighted_ddm_upside: number | null;
  weighted_relative_upside: number | null;
  weighted_composite_upside: number | null;
  coverage_ratio: number;
  overvalued_weight: number;
  undervalued_weight: number;
  summary: Record<string, unknown>;
  run: ValuationRun | null;
  results: SecurityValuation[];
  warnings: string[];
};

export type AnalystLatestResponse = {
  symbol: string;
  as_of_date: string | null;
  current_price: number | null;
  target_mean: number | null;
  target_high: number | null;
  target_low: number | null;
  analyst_count: number | null;
  recommendation_key: string | null;
  recommendation_mean: number | null;
  analyst_upside: number | null;
  status: string;
  warnings: string[];
};

export type AnalystCoverageDetail = {
  analyst_count: number | null;
  recommendation_key: string | null;
  recommendation_mean: number | null;
};

export type AnalystPriceTargetSnapshot = {
  as_of_date: string | null;
  current: number | null;
  high: number | null;
  low: number | null;
  mean: number | null;
  median: number | null;
};

export type AnalystTargetScenario = {
  label: string;
  target: number | null;
  return_pct: number | null;
};

export type RecommendationBucket = {
  label: string;
  count: number;
};

export type ShareholderBreakdownItem = {
  label: string;
  value: number | null;
  display_value: string | null;
};

export type InstitutionalHolder = {
  date_reported: string | null;
  holder: string;
  pct_held: number | null;
  shares: number | null;
  value: number | null;
  pct_change: number | null;
};

export type SecurityOverviewResponse = {
  symbol: string;
  status: "ok" | "partial" | "no_data";
  warnings: string[];
  name: string | null;
  description: string | null;
  industry: string | null;
  sector: string | null;
  country: string | null;
  full_address: string | null;
  website: string | null;
  market_cap: number | null;
  current_price: number | null;
  daily_return: number | null;
  ytd_return: number | null;
  one_year_return: number | null;
  beta: number | null;
  pe: number | null;
  dividend_yield: number | null;
  shareholder_breakdown: ShareholderBreakdownItem[];
  institutional_holders: InstitutionalHolder[];
};

export type FinancialStatementCell = string | number | boolean | null;
export type FinancialStatementRow = Record<string, FinancialStatementCell>;

export type SecurityFinancialStatementsResponse = {
  symbol: string;
  status: "ok" | "partial" | "no_data";
  warnings: string[];
  income_statement_annual: FinancialStatementRow[];
  income_statement_quarterly: FinancialStatementRow[];
  balance_sheet_annual: FinancialStatementRow[];
  balance_sheet_quarterly: FinancialStatementRow[];
  cashflow_annual: FinancialStatementRow[];
  cashflow_quarterly: FinancialStatementRow[];
};

export type FinancialRatioMetric = {
  key: string;
  label: string;
  category: string;
  unit: "pct" | "x" | "days" | string;
  value: number | null;
  source: string;
  description: string;
};

export type SecurityFinancialRatiosResponse = {
  symbol: string;
  status: "ok" | "partial" | "no_data";
  warnings: string[];
  annual: FinancialRatioMetric[];
  quarterly: FinancialRatioMetric[];
};

export type AnalystTableCell = string | number | boolean | null;
export type AnalystTableRow = Record<string, AnalystTableCell>;

export type AnalystDetailResponse = {
  symbol: string;
  status: "ok" | "partial" | "no_data";
  warnings: string[];
  snapshot: AnalystPriceTargetSnapshot;
  coverage: AnalystCoverageDetail;
  target_scenarios: AnalystTargetScenario[];
  current_recommendations: RecommendationBucket[];
  recommendations_history: AnalystTableRow[];
  recommendations_table: AnalystTableRow[];
  eps_trend: AnalystTableRow[];
  eps_revisions: AnalystTableRow[];
  earnings_estimate: AnalystTableRow[];
  revenue_estimate: AnalystTableRow[];
  growth_estimates: AnalystTableRow[];
};

export type ValuationAssumptions = {
  dcf: {
    terminal_growth: number;
    steady_state_growth?: number;
    discount_rate?: number | null;
    explicit_years: number;
    rf: number;
    erp: number;
    anchor_mode?: string;
    tv_method?: string;
    tv_blend_weight?: number;
    reinvestment_blend_weight?: number;
    fallback_rev_spread?: number;
    fallback_eps_spread?: number;
    terminal_clip_buffer?: number;
    quality_penalty_enabled?: boolean;
  };
  ri: {
    explicit_years: number;
    anchor_mode?: string;
    terminal_method?: string;
    terminal_blend_weight?: number;
    steady_state_growth?: number;
    long_run_roe: number;
    long_run_payout?: number;
    payout_smoothing_weight?: number;
    fade_years_post_horizon?: number;
    fallback_rev_spread?: number;
    fallback_eps_spread?: number;
    terminal_clip_buffer?: number;
    quality_penalty_enabled?: boolean;
    cost_of_equity?: number | null;
  };
  ddm: {
    explicit_years: number;
    anchor_mode?: string;
    coverage_mode?: string;
    terminal_method?: string;
    steady_state_growth?: number;
    long_run_payout?: number;
    payout_smoothing_weight?: number;
    initiation_payout_floor?: number;
    payout_cap?: number;
    fallback_eps_spread?: number;
    fallback_payout_spread?: number;
    terminal_clip_buffer?: number;
    quality_penalty_enabled?: boolean;
    cost_of_equity?: number | null;
  };
  relative: {
    peer_set: string;
    multiples: string[];
    cap_upside: number;
  };
};

export type ValuationRecomputeResponse = {
  run: ValuationRun;
  overview: PortfolioValuationOverview | null;
};

export type ExposureBucket = {
  label: string;
  direct_weight: number;
  lookthrough_weight: number;
  direct_weight_pct: number;
  lookthrough_weight_pct: number;
};

export type ExposureHolding = {
  symbol: string;
  name: string | null;
  weight: number;
  weight_pct: number;
  market_value?: number | null;
  sector: string | null;
  currency: string | null;
  asset_type: string | null;
};

export type ConcentrationFlag = {
  level: string;
  title: string;
  detail: string;
};

export type ExposureCoverage = {
  holding_count: number;
  lookthrough_positions: number;
  constituent_positions: number;
  covered_weight: number;
  covered_weight_pct: number;
};

export type OverlapPair = {
  left_symbol: string;
  right_symbol: string;
  overlap_weight: number;
  overlap_pct_of_pair: number;
  overlap_type: string;
};

export type ConcentrationSignal = {
  signal_key: string;
  signal_value: number;
  severity: string;
  summary: string;
};

export type ExposureSummary = {
  methodology_version: string;
  coverage: ExposureCoverage;
  breakdowns: Record<string, ExposureBucket[]>;
  top_lookthrough_holdings: ExposureHolding[];
  overlap_pairs: OverlapPair[];
  concentration_signals: ConcentrationSignal[];
  warnings: string[];
  snapshot_id?: number | null;
  as_of_date?: string | null;
};

export type EvidenceChip = {
  label: string;
  value: string;
};

export type NarrativeCard = {
  id: string;
  title: string;
  tone: string;
  summary: string;
  evidence_chips: EvidenceChip[];
};

export type Watchout = {
  level: string;
  title: string;
  detail: string;
};

export type ChangeSummary = {
  headline: string;
  prior_top3_weight?: number | null;
};

export type PortfolioNarrative = {
  status: string;
  cards: NarrativeCard[];
  watchouts: Watchout[];
  change_summary?: ChangeSummary | null;
  evidence_chips: EvidenceChip[];
  warnings: string[];
};

export type OverviewResponse = {
  portfolio: Portfolio;
  snapshot_id: number | null;
  as_of_date: string | null;
  holdings_count: number;
  top_holdings: HoldingPosition[];
  allocation: Record<string, number>;
  metrics: RiskMetric | null;
  last_refresh: RefreshJob | null;
  exposure_summary: ExposureSummary | null;
  narrative: PortfolioNarrative | null;
  valuation_summary: PortfolioValuationOverview | null;
  latest_scenario_run?: ScenarioRunListItem | null;
};

export type PricePoint = {
  date: string;
  close: number;
};

export type PriceRange = "1M" | "3M" | "6M" | "1Y" | "5Y" | "CUSTOM";

export type SymbolPriceSeries = {
  symbol: string;
  points: PricePoint[];
};

export type PricesResponse = {
  portfolio_id: number;
  range: PriceRange;
  status: "ok" | "partial" | "no_data";
  warnings: string[];
  missing_symbols: string[];
  series: SymbolPriceSeries[];
};

export type MarketEvent = {
  id: string;
  date: string;
  event_type: "dividend" | "stock_split" | "insider_transaction" | "analyst_revision" | string;
  title: string;
  summary: string;
  detail: string | null;
  link_target: "corporate_actions" | "insider_transactions" | "analyst_revisions" | string;
};

export type CorporateActionRow = {
  date: string;
  action_type: "dividend" | "stock_split" | string;
  value: number;
  description: string;
};

export type InsiderTransactionRow = {
  date: string | null;
  insider: string | null;
  position: string | null;
  transaction: string | null;
  shares: number | null;
  value: number | null;
  ownership: string | null;
  text: string | null;
};

export type AnalystRevisionRow = {
  date: string;
  firm: string | null;
  action: string | null;
  to_grade: string | null;
  from_grade: string | null;
  current_price_target: number | null;
  prior_price_target: number | null;
  price_target_action: string | null;
};

export type SecurityEventsResponse = {
  symbol: string;
  range: PriceRange;
  status: "ok" | "partial" | "no_data";
  warnings: string[];
  events: MarketEvent[];
  corporate_actions: CorporateActionRow[];
  insider_transactions: InsiderTransactionRow[];
  analyst_revisions: AnalystRevisionRow[];
};

export type IndustryAnalyticsWindow = "1M" | "3M" | "6M" | "1Y" | "5Y";

export type IndustryAnalyticsInterval = "daily" | "weekly" | "monthly";

export type IndustryAnalyticsSortBy = "return" | "vol" | "sharpe" | "alphabetical";

export type IndustryAnalyticsSortOrder = "asc" | "desc";

export type IndustryMetricRow = {
  industry: string;
  weight: number;
  window_return: number | null;
  annualized_return: number | null;
  volatility_periodic: number | null;
  volatility_annualized: number | null;
  skewness: number | null;
  kurtosis: number | null;
  var_95: number | null;
  cvar_95: number | null;
  sharpe: number | null;
  sortino: number | null;
  upside_capture: number | null;
  downside_capture: number | null;
  beta: number | null;
  tracking_error: number | null;
  information_ratio: number | null;
  max_drawdown: number | null;
  hit_rate: number | null;
};

export type IndustryMatrix = {
  labels: string[];
  values: Array<Array<number | null>>;
  sort_context: Record<string, unknown>;
};

export type IndustryOverviewResponse = {
  portfolio_id: number;
  snapshot_id: number;
  as_of_date: string;
  window: IndustryAnalyticsWindow;
  interval: IndustryAnalyticsInterval;
  benchmark: string;
  sort_by: IndustryAnalyticsSortBy;
  sort_order: IndustryAnalyticsSortOrder;
  rows: IndustryMetricRow[];
  covariance_matrix: IndustryMatrix;
  correlation_matrix: IndustryMatrix;
};

export type NewsArticle = {
  id: string;
  title: string;
  summary: string | null;
  pub_date: string | null;
  provider: string | null;
  url: string | null;
  thumbnail_url: string | null;
  content_type: string | null;
  symbols: string[];
};

export type SecurityNewsResponse = {
  symbol: string;
  status: "ok" | "partial" | "no_data";
  warnings: string[];
  articles: NewsArticle[];
};

export type PortfolioNewsResponse = {
  portfolio_id: number;
  status: "ok" | "partial" | "no_data";
  warnings: string[];
  count: number;
  articles: NewsArticle[];
};

export type ScenarioFactorMeta = {
  key: string;
  label: string;
  unit: string;
  min_value: number;
  max_value: number;
  step: number;
  default_value: number;
  source: string;
  description: string;
};

export type ScenarioMetadataResponse = {
  portfolio_id: number;
  status: "ok" | "partial" | "no_data";
  warnings: string[];
  factors: ScenarioFactorMeta[];
  default_confidence_level: number;
  default_n_sims: number;
  max_n_sims: number;
  horizons: number[];
};

export type ScenarioPreviewRequest = {
  factor_key: string;
  shock_value: number;
  shock_unit: string;
  horizon_days: number;
  confidence_level: number;
  n_sims: number;
  selected_symbol?: string | null;
  include_baseline: boolean;
  shrinkage_lambda: number;
};

export type ScenarioImpact = {
  symbol: string;
  current_value: number | null;
  expected_return_pct: number | null;
  shock_only_return_pct: number | null;
  expected_value: number | null;
  shock_only_value_delta: number | null;
  quantile_low_pct: number | null;
  quantile_high_pct: number | null;
};

export type ScenarioContribution = {
  symbol: string;
  weight: number;
  beta: number | null;
  contribution_pct: number | null;
};

export type ScenarioDistributionBin = {
  series_key: string;
  bin_index: number;
  bin_start: number;
  bin_end: number;
  count: number;
  density: number;
};

export type ScenarioPathPoint = {
  step: number;
  label: string;
  cumulative_return_pct: number;
  value: number | null;
};

export type ScenarioPath = {
  series_key: string;
  path_id: string;
  points: ScenarioPathPoint[];
};

export type ScenarioRelationshipStats = {
  alpha: number | null;
  beta: number | null;
  beta_std_error: number | null;
  beta_t_stat: number | null;
  beta_p_value: number | null;
  r2: number | null;
  adj_r2: number | null;
  n_obs: number;
  correlation: number | null;
  covariance: number | null;
  residual_mean: number | null;
  residual_std: number | null;
  residual_skew: number | null;
  residual_kurtosis: number | null;
  shock_z_score: number | null;
  shock_percentile: number | null;
  flags: string[];
};

export type ScenarioSimulationStats = {
  mean_pct: number | null;
  median_pct: number | null;
  std_pct: number | null;
  skew: number | null;
  kurtosis: number | null;
  var_95_pct: number | null;
  cvar_95_pct: number | null;
  var_99_pct: number | null;
  cvar_99_pct: number | null;
  quantile_low_pct: number | null;
  quantile_high_pct: number | null;
};

export type ScenarioResultResponse = {
  status: "ok" | "partial" | "no_data";
  warnings: string[];
  model_version: string;
  inputs: Record<string, unknown>;
  assumptions: Record<string, unknown>;
  portfolio_impact: ScenarioImpact;
  selected_stock_impact: ScenarioImpact | null;
  contributions: ScenarioContribution[];
  distribution_bins: ScenarioDistributionBin[];
  simulation_paths: ScenarioPath[];
  relationship_stats: Record<string, ScenarioRelationshipStats>;
  simulation_stats: Record<string, ScenarioSimulationStats>;
  narrative: string[];
  run_id: number | null;
  created_at: string | null;
};

export type ScenarioRunListItem = {
  id: number;
  status: string;
  factor_key: string;
  shock_value: number;
  shock_unit: string;
  horizon_days: number;
  confidence_level: number;
  n_sims: number;
  selected_symbol: string | null;
  started_at: string;
  finished_at: string | null;
  error: string | null;
};

export type ScenarioRunListResponse = {
  portfolio_id: number;
  runs: ScenarioRunListItem[];
};


export type ScenarioTemplate = {
  key: string;
  display_name: string;
  factor_key: string;
  shock_value: number;
  shock_unit: string;
  horizon_days: number;
  confidence_level: number;
  n_sims: number;
  narrative: string;
  objective: string;
};

export type MacroWorkflowStep = {
  step_key: string;
  title: string;
  detail: string;
};

export type GuidedMacroWorkflowResponse = {
  workflow_key: string;
  title: string;
  description: string;
  steps: MacroWorkflowStep[];
  templates: ScenarioTemplate[];
};
