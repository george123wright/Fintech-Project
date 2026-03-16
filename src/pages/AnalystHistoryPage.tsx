import { useEffect, useMemo, useState, type Dispatch } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import DataWarningBanner from "../components/DataWarningBanner";
import type { NavAction, NavState } from "../state/nav";
import { usePortfolioData } from "../state/DataProvider";
import type { AnalystDetailResponse, AnalystTableRow } from "../types/api";

type Props = {
  state: NavState;
  dispatch: Dispatch<NavAction>;
};

const RECOMMENDATION_KEYS = [
  { key: "strongBuy", label: "Strong Buy", color: "#42d4a6" },
  { key: "buy", label: "Buy", color: "#26b98d" },
  { key: "hold", label: "Hold", color: "#f0be6b" },
  { key: "sell", label: "Sell", color: "#f08b6e" },
  { key: "strongSell", label: "Strong Sell", color: "#f07575" },
];

function asNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim().length > 0) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function formatCell(value: unknown): string {
  if (value == null) return "N/A";
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : value.toFixed(2);
  return String(value);
}

function historyLabel(row: AnalystTableRow, fallback: number): string {
  const period = row.period ?? row.Period;
  const date = row.Date ?? row.date;
  if (period != null) return String(period);
  if (date != null) return String(date);
  return `row_${fallback + 1}`;
}

export default function AnalystHistoryPage({ state, dispatch }: Props) {
  const sym = state.sym ?? "NVDA";
  const { fetchAnalystDetail } = usePortfolioData();
  const [detail, setDetail] = useState<AnalystDetailResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    void fetchAnalystDetail(sym)
      .then((payload) => {
        if (!active) return;
        setDetail(payload);
      })
      .catch((err: Error) => {
        if (!active) return;
        setError(err.message);
      })
      .finally(() => {
        if (!active) return;
        setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [fetchAnalystDetail, sym]);

  const currentData = useMemo(() => {
    return (detail?.current_recommendations ?? []).map((bucket) => ({
      label: bucket.label,
      count: bucket.count,
    }));
  }, [detail?.current_recommendations]);

  const historyData = useMemo(() => {
    return (detail?.recommendations_history ?? [])
      .slice(0, 24)
      .map((row, index) => ({
        period: historyLabel(row, index),
        strongBuy: asNumber(row.strongBuy) ?? 0,
        buy: asNumber(row.buy) ?? 0,
        hold: asNumber(row.hold) ?? 0,
        sell: asNumber(row.sell) ?? 0,
        strongSell: asNumber(row.strongSell) ?? 0,
      }))
      .reverse();
  }, [detail?.recommendations_history]);

  const tableRows = detail?.recommendations_table ?? [];
  const tableColumns = useMemo(() => {
    const first = tableRows[0];
    return first ? Object.keys(first) : [];
  }, [tableRows]);

  return (
    <div className="page-wrap" style={{ maxWidth: 1200, margin: "0 auto" }}>
      <button className="back-btn" onClick={() => dispatch({ type: "open_stock", sym, tab: "analyst" })}>
        {"<- Back to Analyst View"}
      </button>

      <div className="row-between" style={{ marginTop: 16, marginBottom: 16 }}>
        <div>
          <div style={{ fontFamily: "var(--sans)", fontSize: 28, fontWeight: 700, letterSpacing: "-0.03em" }}>
            {sym} Analyst Recommendations
          </div>
          <div style={{ color: "var(--muted)", fontSize: 12, marginTop: 6 }}>
            Historical and current recommendation mix from Yahoo analyst datasets.
          </div>
        </div>
      </div>

      <DataWarningBanner warnings={detail?.warnings ?? []} title="Analyst Data Warnings" />

      {loading ? (
        <div className="card">Loading analyst recommendation history...</div>
      ) : error ? (
        <div className="card" style={{ color: "var(--red)" }}>
          {error}
        </div>
      ) : (
        <>
          <div className="grid-2" style={{ marginBottom: 14 }}>
            <div className="card">
              <div className="kicker" style={{ marginBottom: 10 }}>
                Current Recommendation Mix
              </div>
              {currentData.length ? (
                <ResponsiveContainer width="100%" height={240}>
                  <BarChart data={currentData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                    <CartesianGrid stroke="rgba(151,161,189,0.18)" strokeDasharray="3 4" />
                    <XAxis dataKey="label" tick={{ fill: "#97a1bd", fontSize: 10 }} />
                    <YAxis tick={{ fill: "#97a1bd", fontSize: 10 }} />
                    <Tooltip
                      contentStyle={{
                        background: "#11131d",
                        border: "1px solid #2f3750",
                        borderRadius: 10,
                        color: "#eceef9",
                      }}
                    />
                    <Bar dataKey="count" fill="#6f7cff" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div style={{ color: "var(--muted)", fontSize: 12 }}>No current recommendation mix available.</div>
              )}
            </div>

            <div className="card">
              <div className="kicker" style={{ marginBottom: 10 }}>
                Historical Recommendation Mix
              </div>
              {historyData.length ? (
                <ResponsiveContainer width="100%" height={240}>
                  <BarChart data={historyData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                    <CartesianGrid stroke="rgba(151,161,189,0.18)" strokeDasharray="3 4" />
                    <XAxis dataKey="period" tick={{ fill: "#97a1bd", fontSize: 10 }} />
                    <YAxis tick={{ fill: "#97a1bd", fontSize: 10 }} />
                    <Tooltip
                      contentStyle={{
                        background: "#11131d",
                        border: "1px solid #2f3750",
                        borderRadius: 10,
                        color: "#eceef9",
                      }}
                    />
                    <Legend />
                    {RECOMMENDATION_KEYS.map((item) => (
                      <Bar key={item.key} dataKey={item.key} stackId="hist" fill={item.color} />
                    ))}
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div style={{ color: "var(--muted)", fontSize: 12 }}>
                  No historical recommendation rows available.
                </div>
              )}
            </div>
          </div>

          <div className="card">
            <div className="kicker" style={{ marginBottom: 10 }}>
              Recommendations Data Frame
            </div>
            {tableRows.length ? (
              <div style={{ overflowX: "auto" }}>
                <table className="table">
                  <thead>
                    <tr>
                      {tableColumns.map((column) => (
                        <th key={column}>{column}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {tableRows.slice(0, 250).map((row, index) => (
                      <tr key={index}>
                        {tableColumns.map((column) => (
                          <td key={`${index}-${column}`}>{formatCell(row[column])}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div style={{ color: "var(--muted)", fontSize: 12 }}>No recommendation table rows available.</div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
