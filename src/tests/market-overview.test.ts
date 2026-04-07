import { describe, expect, it } from "vitest";
import { getNextSortState, sortIndustryRows } from "../pages/MarketOverviewPage";
import { reorderMatrix } from "../components/IndustryMatrixHeatmap";

const rows = [
  { industry: "Utilities", weight: 10, ret: 1, vol: 5, sharpe: 0.2, beta: 0.5 },
  { industry: "Energy", weight: 5, ret: 3, vol: 8, sharpe: 0.4, beta: 1.2 },
  { industry: "Software", weight: 15, ret: 2, vol: 7, sharpe: 0.5, beta: 1.0 },
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
