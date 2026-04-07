import { describe, expect, it } from "vitest";
import { buildIndustryOverviewQuery } from "../api/client";

describe("industry query mapping", () => {
  it("maps UI control options into API query parameters", () => {
    const query = buildIndustryOverviewQuery({
      window: "6M",
      interval: "weekly",
      benchmark: "QQQ",
      sortBy: "vol",
      sortOrder: "asc",
    });

    expect(query).toBe("?window=6M&interval=weekly&benchmark=QQQ&sort_by=vol&sort_order=asc");
  });

  it("returns empty suffix when no options provided", () => {
    expect(buildIndustryOverviewQuery()).toBe("");
  });
});
