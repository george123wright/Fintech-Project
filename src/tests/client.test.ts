import { describe, expect, it } from "vitest";
import { buildIndustryOverviewQuery } from "../api/client";

describe("industry query mapping", () => {
  it("maps UI control options into API query parameters", () => {
    const query = buildIndustryOverviewQuery({
      window: "3Y",
      dateMode: "custom",
      startDate: "2026-01-01",
      endDate: "2026-03-31",
      interval: "weekly",
      benchmark: "QQQ",
      sortBy: "vol",
      sortOrder: "asc",
    });

    expect(query).toBe(
      "?window=3Y&date_mode=custom&start_date=2026-01-01&end_date=2026-03-31&interval=weekly&benchmark=QQQ&sort_by=vol&sort_order=asc"
    );
  });

  it("returns empty suffix when no options provided", () => {
    expect(buildIndustryOverviewQuery()).toBe("");
  });
});
