import { useEffect, useMemo, useState, type Dispatch } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
} from "recharts";
import { usePortfolioData } from "../state/DataProvider";
import type { NavAction } from "../state/nav";
import type { PricePoint } from "../types/api";
import { formatPrice } from "../utils/format";

type Props = {
  dispatch: Dispatch<NavAction>;
};

export default function WatchlistPage({ dispatch }: Props) {
  const { state: dataState, fetchPricesForActive } = usePortfolioData();
  const [priceBySymbol, setPriceBySymbol] = useState<Record<string, PricePoint[]>>({});
  const [sparkWarnings, setSparkWarnings] = useState<string[]>([]);

  const riskMap = new Map(
    (dataState.risk?.contributions ?? []).map((c) => [c.symbol, c.pct_total_risk])
  );
  const symbols = useMemo(() => dataState.holdings.map((holding) => holding.symbol), [dataState.holdings]);

  useEffect(() => {
    if (!symbols.length) {
      setPriceBySymbol({});
      setSparkWarnings([]);
      return;
    }
    let isMounted = true;
    void fetchPricesForActive(symbols, "1M")
      .then((response) => {
        if (!isMounted) return;
        const next: Record<string, PricePoint[]> = {};
        for (const series of response.series) {
          next[series.symbol] = series.points;
        }
        setPriceBySymbol(next);
        setSparkWarnings(response.warnings ?? []);
      })
      .catch(() => {
        if (!isMounted) return;
        setPriceBySymbol({});
        setSparkWarnings(["watchlist_price_fetch_failed"]);
      });
    return () => {
      isMounted = false;
    };
  }, [fetchPricesForActive, symbols]);

  const formatHoverDate = (raw: string): string => {
    const parsed = new Date(raw);
    if (!Number.isFinite(parsed.getTime())) return raw;
    return parsed.toLocaleDateString();
  };

  return (
    <div className="page-wrap">
      <div className="page-intro" style={{ marginBottom: 24 }}>
        <h1>Watchlist</h1>
        <p>Track uploaded holdings, inspect risk contribution, and jump into live charts.</p>
        {sparkWarnings.length > 0 && (
          <p style={{ color: "var(--yellow)" }}>
            Some watchlist mini-charts may be partial until another refresh completes.
          </p>
        )}
      </div>

      <div className="grid-2">
        {dataState.holdings.map((holding) => {
          const riskShare = riskMap.get(holding.symbol) ?? 0;
          const series = priceBySymbol[holding.symbol] ?? [];
          return (
            <div key={holding.symbol} className="card">
              <div>
                <div>
                  <span className="ticker-color-dot" style={{ backgroundColor: "#7b6ef6" }} />
                  <span style={{ fontFamily: "var(--sans)", fontSize: 20, fontWeight: 700 }}>
                    {holding.symbol}
                  </span>
                </div>
                <div style={{ color: "var(--muted)", fontSize: 12, marginTop: 4 }}>
                  {holding.name ?? "No security name"}
                </div>
              </div>

              <p style={{ margin: "14px 0 16px" }}>
                Weight {(holding.weight * 100).toFixed(2)}% | Risk contribution{" "}
                {(riskShare * 100).toFixed(2)}%
              </p>

              <div className="grid-3" style={{ marginBottom: 18 }}>
                <div>
                  <div style={{ color: "var(--muted)", fontSize: 10 }}>Market Value</div>
                  <div style={{ fontWeight: 600, marginTop: 4 }}>
                    {formatPrice(holding.market_value)}
                  </div>
                </div>
                <div>
                  <div style={{ color: "var(--muted)", fontSize: 10 }}>Units</div>
                  <div style={{ fontWeight: 600, marginTop: 4 }}>
                    {holding.units?.toFixed(3) ?? "N/A"}
                  </div>
                </div>
                <div>
                  <div style={{ color: "var(--muted)", fontSize: 10 }}>Asset Type</div>
                  <div style={{ fontWeight: 600, marginTop: 4 }}>{holding.asset_type ?? "N/A"}</div>
                </div>
              </div>

              <div style={{ height: 150, marginBottom: 16 }}>
                {series.length ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={series} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                      <defs>
                        <linearGradient id={`watch-${holding.symbol}-fill`} x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="#7b6ef6" stopOpacity={0.32} />
                          <stop offset="100%" stopColor="#7b6ef6" stopOpacity={0.02} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid stroke="rgba(151,161,189,0.15)" strokeDasharray="3 4" vertical={false} />
                      <XAxis
                        dataKey="date"
                        tick={{ fill: "#97a1bd", fontSize: 10 }}
                        minTickGap={32}
                        tickFormatter={(value: string) => {
                          const parsed = new Date(value);
                          if (!Number.isFinite(parsed.getTime())) return value;
                          return parsed.toLocaleDateString(undefined, { month: "short", day: "numeric" });
                        }}
                      />
                      <Tooltip
                        labelFormatter={(label: string) => `Date: ${formatHoverDate(label)}`}
                        formatter={(value) => {
                          const num =
                            typeof value === "number"
                              ? value
                              : typeof value === "string"
                                ? Number(value)
                                : NaN;
                          return Number.isFinite(num) ? [formatPrice(num), "Price on day"] : ["N/A", "Price on day"];
                        }}
                        contentStyle={{
                          background: "#11131d",
                          border: "1px solid #2f3750",
                          borderRadius: 10,
                          color: "#eceef9",
                        }}
                      />
                      <Area
                        type="monotone"
                        dataKey="close"
                        stroke="#7b6ef6"
                        strokeWidth={2}
                        fill={`url(#watch-${holding.symbol}-fill)`}
                        dot={false}
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                ) : (
                  <div style={{ color: "var(--muted)", fontSize: 11 }}>No 1M price series available yet.</div>
                )}
              </div>

              <div style={{ display: "flex", gap: 10 }}>
                <button
                  className="btn-secondary"
                  onClick={() => dispatch({ type: "open_stock", sym: holding.symbol })}
                >
                  Open detail
                </button>
                <button
                  className="btn-primary"
                  onClick={() => dispatch({ type: "open_chart", sym: holding.symbol })}
                >
                  Open chart
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
