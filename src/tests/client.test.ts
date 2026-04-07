import { afterEach, describe, expect, it, vi } from "vitest";
import { buildIndustryOverviewQuery, postChatQuery } from "../api/client";

const originalFetch = globalThis.fetch;

afterEach(() => {
  vi.restoreAllMocks();
  globalThis.fetch = originalFetch;
});

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

  it("includes scope when provided", () => {
    expect(buildIndustryOverviewQuery({ scope: "sector_map" })).toBe("?scope=sector_map");
  });
});

describe("postChatQuery", () => {
  it("posts to chat query route with JSON payload", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        assistant_message: "hello",
        citations: [],
        latency: { total_ms: 12, provider: "openrouter" },
        warnings: [],
      }),
    });
    globalThis.fetch = fetchMock as typeof fetch;

    const payload = {
      portfolio_id: 42,
      question: "Summarize my risk.",
      conversation_history: [{ role: "user" as const, content: "Previous question" }],
    };

    await postChatQuery(payload);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/v1/chat/query",
      expect.objectContaining({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      })
    );
  });

  it("forwards AbortSignal for cancellation", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        assistant_message: "ok",
        citations: [],
        latency: { total_ms: 1, provider: "openrouter" },
        warnings: [],
      }),
    });
    globalThis.fetch = fetchMock as typeof fetch;

    const controller = new AbortController();
    await postChatQuery({ portfolio_id: 7, question: "Hi" }, { signal: controller.signal });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/v1/chat/query",
      expect.objectContaining({ signal: controller.signal })
    );
  });
});
