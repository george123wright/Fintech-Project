import { useEffect, useMemo, useState, type Dispatch } from "react";
import DataWarningBanner from "../components/DataWarningBanner";
import { usePortfolioData } from "../state/DataProvider";
import type { NewsArticle } from "../types/api";
import type { NavAction } from "../state/nav";

type Props = {
  dispatch: Dispatch<NavAction>;
};

type NewsSortKey = "most_recent" | "oldest" | "provider_az";

function formatNewsDate(value: string | null): string {
  if (!value) return "N/A";
  const parsed = new Date(value);
  if (!Number.isFinite(parsed.getTime())) return value;
  return parsed.toLocaleString();
}

export default function PortfolioNewsPage({ dispatch }: Props) {
  const { state: dataState, fetchPortfolioNewsForActive } = usePortfolioData();
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState<string | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [articles, setArticles] = useState<NewsArticle[]>([]);
  const [tickerFilter, setTickerFilter] = useState<string>("ALL");
  const [sortKey, setSortKey] = useState<NewsSortKey>("most_recent");

  useEffect(() => {
    if (dataState.activePortfolioId == null) {
      setStatus("ready");
      setError(null);
      setWarnings([]);
      setArticles([]);
      return;
    }
    let isMounted = true;
    setStatus("loading");
    setError(null);
    void fetchPortfolioNewsForActive({ limit: 500, perSymbol: 80 })
      .then((response) => {
        if (!isMounted) return;
        setArticles(response.articles ?? []);
        setWarnings(response.warnings ?? []);
        setStatus("ready");
      })
      .catch((err: Error) => {
        if (!isMounted) return;
        setError(err.message);
        setStatus("error");
      });

    return () => {
      isMounted = false;
    };
  }, [dataState.activePortfolioId, fetchPortfolioNewsForActive]);

  const groupedCount = useMemo(() => {
    const symbols = new Set<string>();
    for (const article of articles) {
      for (const symbol of article.symbols ?? []) symbols.add(symbol);
    }
    return symbols.size;
  }, [articles]);

  const symbolOptions = useMemo(() => {
    const symbols = new Set<string>();
    for (const article of articles) {
      for (const symbol of article.symbols ?? []) {
        const clean = String(symbol ?? "").trim().toUpperCase();
        if (clean) symbols.add(clean);
      }
    }
    return Array.from(symbols).sort((a, b) => a.localeCompare(b));
  }, [articles]);

  useEffect(() => {
    if (tickerFilter === "ALL") return;
    if (!symbolOptions.includes(tickerFilter)) {
      setTickerFilter("ALL");
    }
  }, [symbolOptions, tickerFilter]);

  const visibleArticles = useMemo(() => {
    let rows = articles;
    if (tickerFilter !== "ALL") {
      rows = rows.filter((article) =>
        (article.symbols ?? []).some((symbol) => String(symbol ?? "").toUpperCase() === tickerFilter)
      );
    }

    const sorted = [...rows];
    sorted.sort((a, b) => {
      if (sortKey === "provider_az") {
        return (a.provider ?? "").localeCompare(b.provider ?? "");
      }
      const ta = a.pub_date ? new Date(a.pub_date).getTime() : 0;
      const tb = b.pub_date ? new Date(b.pub_date).getTime() : 0;
      return sortKey === "oldest" ? ta - tb : tb - ta;
    });
    return sorted;
  }, [articles, sortKey, tickerFilter]);

  return (
    <div className="page-wrap" style={{ maxWidth: 1200, margin: "0 auto" }}>
      <button className="back-btn" onClick={() => dispatch({ type: "go_page", page: "overview" })}>
        {"<- Back to Overview"}
      </button>

      <div className="row-between" style={{ marginTop: 16, marginBottom: 16 }}>
        <div>
          <div style={{ fontFamily: "var(--sans)", fontSize: 30, fontWeight: 700, letterSpacing: "-0.03em" }}>
            Portfolio News
          </div>
          <div style={{ color: "var(--muted)", fontSize: 12, marginTop: 6 }}>
            Latest articles aggregated across portfolio tickers.
          </div>
        </div>
        <div style={{ color: "var(--muted)", fontSize: 12, textAlign: "right" }}>
          {visibleArticles.length} shown of {articles.length} articles
          <br />
          {groupedCount} symbols covered
        </div>
      </div>

      <div className="card" style={{ marginBottom: 14 }}>
        <div className="kicker" style={{ marginBottom: 10 }}>
          News Filters
        </div>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
            gap: 10,
          }}
        >
          <label className="custom-range-field" style={{ textTransform: "none", fontSize: 11 }}>
            Ticker
            <select
              value={tickerFilter}
              onChange={(event) => setTickerFilter(event.target.value)}
              style={{
                border: "1px solid var(--border-soft)",
                background: "rgba(255,255,255,0.02)",
                color: "var(--text)",
                borderRadius: 8,
                padding: "8px 10px",
              }}
            >
              <option value="ALL">All tickers</option>
              {symbolOptions.map((symbol) => (
                <option key={symbol} value={symbol}>
                  {symbol}
                </option>
              ))}
            </select>
          </label>

          <label className="custom-range-field" style={{ textTransform: "none", fontSize: 11 }}>
            Sort
            <select
              value={sortKey}
              onChange={(event) => setSortKey(event.target.value as NewsSortKey)}
              style={{
                border: "1px solid var(--border-soft)",
                background: "rgba(255,255,255,0.02)",
                color: "var(--text)",
                borderRadius: 8,
                padding: "8px 10px",
              }}
            >
              <option value="most_recent">Most recent</option>
              <option value="oldest">Oldest</option>
              <option value="provider_az">Provider A-Z</option>
            </select>
          </label>
        </div>
      </div>

      <DataWarningBanner warnings={warnings} title="News Feed Warnings" />

      {status === "loading" && <div className="card">Loading portfolio news...</div>}
      {status === "error" && (
        <div className="card" style={{ color: "var(--red)" }}>
          {error ?? "Failed to load portfolio news."}
        </div>
      )}

      {status === "ready" && (
        <div className="card">
          {visibleArticles.length ? (
            <div style={{ display: "grid", gap: 12 }}>
              {visibleArticles.map((article) => (
                <article key={article.id} className="surface-soft" style={{ padding: 12 }}>
                  <div className="row-between" style={{ alignItems: "flex-start", gap: 12 }}>
                    <div style={{ minWidth: 0 }}>
                      <div style={{ fontSize: 17, fontWeight: 700, marginBottom: 6 }}>
                        {article.url ? (
                          <a
                            href={article.url}
                            target="_blank"
                            rel="noreferrer"
                            style={{ color: "var(--text)", textDecoration: "underline" }}
                          >
                            {article.title}
                          </a>
                        ) : (
                          article.title
                        )}
                      </div>
                      <div style={{ color: "var(--muted)", fontSize: 12, marginBottom: 8 }}>
                        {article.provider ?? "Unknown source"} | {formatNewsDate(article.pub_date)}
                        {article.content_type ? ` | ${article.content_type}` : ""}
                      </div>
                      <div style={{ fontSize: 12, color: "var(--text)", lineHeight: 1.6 }}>
                        {article.summary ?? "No summary available."}
                      </div>
                    </div>
                    {article.thumbnail_url ? (
                      <img
                        src={article.thumbnail_url}
                        alt={article.title}
                        style={{
                          width: 180,
                          height: 110,
                          objectFit: "cover",
                          borderRadius: 8,
                          border: "1px solid var(--border)",
                          flexShrink: 0,
                        }}
                      />
                    ) : null}
                    <div style={{ textAlign: "right", minWidth: 140 }}>
                      <div className="kicker" style={{ marginBottom: 6 }}>
                        Symbols
                      </div>
                      <div style={{ display: "flex", flexWrap: "wrap", gap: 6, justifyContent: "flex-end" }}>
                        {(article.symbols ?? []).map((symbol) => (
                          <span
                            key={`${article.id}-${symbol}`}
                            style={{
                              border: "1px solid var(--border)",
                              borderRadius: 999,
                              padding: "2px 8px",
                              fontSize: 11,
                              color: "var(--muted)",
                            }}
                          >
                            {symbol}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <div style={{ color: "var(--muted)", fontSize: 12 }}>
              No portfolio news articles match the current filter.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
