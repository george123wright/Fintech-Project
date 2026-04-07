import { describe, expect, it } from "vitest";
import { getNextSortState, getVisibleMarketColumns, sortIndustryRows } from "../pages/MarketOverviewPage";
import { reorderMatrix } from "../components/IndustryMatrixHeatmap";

const rows = [
  {
    industry: "Utilities",
    weight: 10,
    window_return: 0.01,
    annualized_return: 0.1,
    volatility_periodic: 0.05,
    volatility_annualized: 0.12,
    skewness: 0.1,
    kurtosis: 3.2,
    var_95: 0.04,
    cvar_95: 0.05,
    sharpe: 0.2,
    sortino: 0.3,
    upside_capture: 0.9,
    downside_capture: 0.8,
    beta: 0.5,
    tracking_error: 0.06,
    information_ratio: 0.1,
    max_drawdown: -0.2,
    hit_rate: 0.55,
  },
  {
    industry: "Energy",
    weight: 5,
    window_return: 0.03,
    annualized_return: 0.2,
    volatility_periodic: 0.08,
    volatility_annualized: 0.2,
    skewness: -0.2,
    kurtosis: 4.1,
    var_95: 0.08,
    cvar_95: 0.1,
    sharpe: 0.4,
    sortino: 0.5,
    upside_capture: 1.2,
    downside_capture: 1.1,
    beta: 1.2,
    tracking_error: 0.08,
    information_ratio: 0.3,
    max_drawdown: -0.35,
    hit_rate: 0.48,
  },
  {
    industry: "Software",
    weight: 15,
    window_return: 0.02,
    annualized_return: 0.18,
    volatility_periodic: 0.07,
    volatility_annualized: 0.18,
    skewness: 0.3,
    kurtosis: 3.6,
    var_95: 0.05,
    cvar_95: 0.07,
    sharpe: 0.5,
    sortino: 0.7,
    upside_capture: 1.1,
    downside_capture: 0.9,
    beta: 1.0,
    tracking_error: 0.07,
    information_ratio: 0.4,
    max_drawdown: -0.25,
    hit_rate: 0.6,
  },
];

describe("sortable industry table behavior", () => {
  it("sorts by metric descending by default", () => {
    const sorted = sortIndustryRows(rows, "weight", "desc");
    expect(sorted.map((row) => row.industry)).toEqual(["Software", "Utilities", "Energy"]);
  });

  it("toggles direction when same column is clicked", () => {
    expect(getNextSortState("weight", "desc", "weight")).toEqual({ sortBy: "weight", sortDir: "asc" });
  });
});

describe("matrix reorder correctness", () => {
  it("reorders rows and columns with the same index permutation", () => {
    const matrix = [
      [1, 2, 3],
      [4, 5, 6],
      [7, 8, 9],
    ];

    expect(reorderMatrix(matrix, [2, 0, 1])).toEqual([
      [9, 7, 8],
      [3, 1, 2],
      [6, 4, 5],
    ]);
  });
});

describe("column preset visibility", () => {
  it("returns expected visible header counts for each preset", () => {
    expect(getVisibleMarketColumns("core")).toHaveLength(6);
    expect(getVisibleMarketColumns("risk")).toHaveLength(10);
    expect(getVisibleMarketColumns("relative")).toHaveLength(9);
    expect(getVisibleMarketColumns("all")).toHaveLength(13);
  });

  it("switches between presets with expected key headers", () => {
    expect(getVisibleMarketColumns("core").map((column) => column.key)).toEqual([
      "industry",
      "weight",
      "window_return",
      "volatility_annualized",
      "sharpe",
      "beta",
    ]);

    expect(getVisibleMarketColumns("all").map((column) => column.key)).toContain("information_ratio");
    expect(getVisibleMarketColumns("all").map((column) => column.key)).toContain("tracking_error");
    expect(getVisibleMarketColumns("all").map((column) => column.key)).toContain("upside_capture");
  });
});
