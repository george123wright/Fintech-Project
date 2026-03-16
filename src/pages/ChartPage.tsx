import { useEffect, useMemo, useState, type Dispatch } from "react";
import Plot from "react-plotly.js";
import { buildPriceChartFromSeries, type ChartMarkerEvent } from "../charts/builders";
import DataWarningBanner from "../components/DataWarningBanner";
import type { NavAction, NavState, RangeKey } from "../state/nav";
import { formatPrice } from "../utils/format";
import { usePortfolioData } from "../state/DataProvider";
import type { MarketEvent, PricePoint, PriceRange } from "../types/api";

type Props = {
  state: NavState;
  dispatch: Dispatch<NavAction>;
};

type EventToggleKey = "dividend" | "stock_split" | "insider_transaction" | "analyst_revision";

const PRESET_RANGE_KEYS: Array<Exclude<RangeKey, "CUSTOM">> = ["1M", "3M", "6M", "1Y", "5Y"];

const EVENT_TOGGLE_LABELS: Array<{ key: EventToggleKey; label: string }> = [
  { key: "dividend", label: "Dividends" },
  { key: "stock_split", label: "Splits" },
  { key: "insider_transaction", label: "Insider" },
  { key: "analyst_revision", label: "Analyst Revisions" },
];

const EVENT_TYPE_LABEL: Record<string, string> = {
  dividend: "Dividend",
  stock_split: "Stock Split",
  insider_transaction: "Insider Transaction",
  analyst_revision: "Analyst Revision",
};

function isoDateToday(): string {
  return new Date().toISOString().slice(0, 10);
}

function isoDateDaysAgo(days: number): string {
  const now = new Date();
  now.setDate(now.getDate() - days);
  return now.toISOString().slice(0, 10);
}

function formatEventDate(raw: string): string {
  const parsed = new Date(raw);
  if (!Number.isFinite(parsed.getTime())) return raw;
  return parsed.toLocaleString();
}

function mapEventTargetToSection(target: string): "corporate_actions" | "insider_transactions" | "analyst_revisions" {
  if (target === "insider_transactions") return "insider_transactions";
  if (target === "analyst_revisions") return "analyst_revisions";
  return "corporate_actions";
}

function toChartEvent(event: MarketEvent): ChartMarkerEvent {
  return {
    id: event.id,
    date: event.date,
    eventType: event.event_type,
    title: event.title,
    summary: event.summary,
    detail: event.detail,
    linkTarget: event.link_target,
  };
}

function uniqueWarnings(...groups: string[][]): string[] {
  return Array.from(new Set(groups.flat().filter((item) => item.trim().length > 0)));
}

export default function ChartPage({ state, dispatch }: Props) {
  const { fetchPricesForActive, fetchSecurityEventsForActive, runManualRefresh } = usePortfolioData();
  const sym = state.chartSym;

  const [points, setPoints] = useState<PricePoint[]>([]);
  const [events, setEvents] = useState<MarketEvent[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [apiWarnings, setApiWarnings] = useState<string[]>([]);
  const [apiStatus, setApiStatus] = useState<"ok" | "partial" | "no_data">("ok");
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);
  const [customStartDate, setCustomStartDate] = useState<string>(isoDateDaysAgo(365));
  const [customEndDate, setCustomEndDate] = useState<string>(isoDateToday());
  const [appliedCustomRange, setAppliedCustomRange] = useState<{ startDate: string; endDate: string } | null>(null);
  const [enabledEventTypes, setEnabledEventTypes] = useState<Record<EventToggleKey, boolean>>({
    dividend: true,
    stock_split: true,
    insider_transaction: true,
    analyst_revision: true,
  });

  useEffect(() => {
    let isMounted = true;
    const range = state.chartRange as PriceRange;

    const customOptions = range === "CUSTOM" ? appliedCustomRange : undefined;

    if (range === "CUSTOM" && customOptions == null) {
      setError("Pick dates and click Apply Dates to load a custom range.");
      setLoading(false);
      setPoints([]);
      setEvents([]);
      setApiWarnings([]);
      setApiStatus("ok");
      return () => {
        isMounted = false;
      };
    }
    const requestOptions = customOptions ?? undefined;

    setLoading(true);
    setError(null);

    void Promise.all([
      fetchPricesForActive([sym], range, requestOptions),
      fetchSecurityEventsForActive(sym, range, requestOptions),
    ])
      .then(([priceResponse, eventResponse]) => {
        if (!isMounted) return;

        const series = priceResponse.series.find((item) => item.symbol === sym);
        const nextPoints = series?.points ?? [];
        setPoints(nextPoints);
        setEvents(eventResponse.events ?? []);

        const nextWarnings = uniqueWarnings(priceResponse.warnings ?? [], eventResponse.warnings ?? []);
        setApiWarnings(nextWarnings);

        let status: "ok" | "partial" | "no_data" = priceResponse.status;
        if (status === "ok" && eventResponse.status === "partial") {
          status = "partial";
        }
        if (status === "ok" && nextPoints.length === 0) {
          status = "no_data";
        }
        setApiStatus(status);
      })
      .catch((err: Error) => {
        if (!isMounted) return;
        setError(err.message);
        setApiStatus("partial");
        setApiWarnings(["E_CHART_REQUEST_FAILED"]);
        setPoints([]);
        setEvents([]);
      })
      .finally(() => {
        if (!isMounted) return;
        setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [
    appliedCustomRange,
    fetchPricesForActive,
    fetchSecurityEventsForActive,
    state.chartRange,
    sym,
  ]);

  const filteredEvents = useMemo(() => {
    return events.filter((event) => {
      const key = event.event_type as EventToggleKey;
      return enabledEventTypes[key] ?? false;
    });
  }, [enabledEventTypes, events]);

  const listedEvents = useMemo(() => {
    return [...filteredEvents].sort(
      (left, right) => new Date(right.date).getTime() - new Date(left.date).getTime()
    );
  }, [filteredEvents]);

  useEffect(() => {
    if (listedEvents.length === 0) {
      setSelectedEventId(null);
      return;
    }
    if (!selectedEventId || !listedEvents.some((event) => event.id === selectedEventId)) {
      setSelectedEventId(listedEvents[0].id);
    }
  }, [listedEvents, selectedEventId]);

  const selectedEvent = useMemo(
    () => listedEvents.find((event) => event.id === selectedEventId) ?? null,
    [listedEvents, selectedEventId]
  );

  const chartEvents = useMemo(() => filteredEvents.map(toChartEvent), [filteredEvents]);

  const chart = useMemo(
    () => buildPriceChartFromSeries(sym, points, chartEvents, selectedEventId),
    [chartEvents, points, selectedEventId, sym]
  );

  const first = points[0]?.close ?? 0;
  const last = points[points.length - 1]?.close ?? 0;
  const changePct = first > 0 ? (last / first) * 100 - 100 : 0;
  const rangeLabel =
    state.chartRange === "CUSTOM" && appliedCustomRange != null
      ? `${appliedCustomRange.startDate} to ${appliedCustomRange.endDate}`
      : state.chartRange;
  const changeLabel = `${changePct >= 0 ? "+" : ""}${changePct.toFixed(1)}% (${rangeLabel})`;
  const changeColor = changePct >= 0 ? "var(--green)" : "var(--red)";

  const handleMarkerInteraction = (payload: { points?: Array<{ customdata?: unknown }> }) => {
    const customData = payload.points?.[0]?.customdata;
    if (!Array.isArray(customData)) return;
    const eventId = customData[0];
    if (typeof eventId === "string") {
      setSelectedEventId(eventId);
    }
  };

  const applyCustomRange = () => {
    if (!customStartDate || !customEndDate) {
      setError("Custom range requires both start and end dates.");
      return;
    }
    if (customStartDate > customEndDate) {
      setError("Custom range start date must be before end date.");
      return;
    }
    setError(null);
    setAppliedCustomRange({ startDate: customStartDate, endDate: customEndDate });
    dispatch({ type: "set_range", range: "CUSTOM" });
  };

  return (
    <div>
      <div className="row-between" style={{ padding: "18px 28px", borderBottom: "1px solid var(--border)" }}>
        <button className="back-btn" onClick={() => dispatch({ type: "go_page", page: "overview" })}>
          {"<- Back"}
        </button>
        <div>
          <span style={{ fontFamily: "var(--sans)", fontSize: 18, fontWeight: 700, marginRight: 12 }}>{sym}</span>
          <span style={{ color: "var(--muted)", fontSize: 13, marginRight: 8 }}>{formatPrice(last)}</span>
          <span style={{ color: changeColor, fontSize: 13, fontWeight: 600 }}>{changeLabel}</span>
        </div>
        <div style={{ width: 80 }} />
      </div>

      <div className="chart-layout">
        <div style={{ padding: "24px 28px", minWidth: 0 }}>
          <DataWarningBanner warnings={apiWarnings} title="Chart Data Warnings" />
          <div className="range-row" style={{ marginBottom: 10 }}>
            {PRESET_RANGE_KEYS.map((key) => (
              <button
                key={key}
                className={`range-btn ${state.chartRange === key ? "active" : ""}`}
                onClick={() => dispatch({ type: "set_range", range: key })}
              >
                {key}
              </button>
            ))}
            <button
              className={`range-btn ${state.chartRange === "CUSTOM" ? "active" : ""}`}
              onClick={() => dispatch({ type: "set_range", range: "CUSTOM" })}
            >
              Custom
            </button>
          </div>

          {state.chartRange === "CUSTOM" && (
            <div className="custom-range-panel">
              <label className="custom-range-field">
                <span>Start</span>
                <input
                  type="date"
                  value={customStartDate}
                  onChange={(event) => setCustomStartDate(event.target.value)}
                />
              </label>
              <label className="custom-range-field">
                <span>End</span>
                <input
                  type="date"
                  value={customEndDate}
                  onChange={(event) => setCustomEndDate(event.target.value)}
                />
              </label>
              <button className="btn-secondary" onClick={applyCustomRange}>
                Apply Dates
              </button>
            </div>
          )}

          <div className="event-toggle-row">
            {EVENT_TOGGLE_LABELS.map((toggle) => (
              <label key={toggle.key} className="event-toggle-chip">
                <input
                  type="checkbox"
                  checked={enabledEventTypes[toggle.key]}
                  onChange={() =>
                    setEnabledEventTypes((current) => ({
                      ...current,
                      [toggle.key]: !current[toggle.key],
                    }))
                  }
                />
                <span>{toggle.label}</span>
              </label>
            ))}
          </div>

          {loading ? (
            <div className="surface" style={{ padding: 20 }}>
              Loading chart data...
            </div>
          ) : error ? (
            <div className="surface" style={{ padding: 20, color: "var(--red)" }}>
              {error}
            </div>
          ) : apiStatus === "no_data" || points.length === 0 ? (
            <div className="surface" style={{ padding: 20 }}>
              <div style={{ color: "var(--yellow)", marginBottom: 8, fontWeight: 600 }}>
                No chart data for {sym} in {rangeLabel}
              </div>
              <div style={{ color: "var(--muted)", fontSize: 12, marginBottom: 10 }}>
                Run a manual refresh to populate cached prices, then try again.
              </div>
              <button className="btn-secondary" onClick={() => void runManualRefresh()}>
                Run Manual Refresh
              </button>
            </div>
          ) : (
            <Plot
              data={chart.data}
              layout={chart.layout}
              config={{ displayModeBar: false, responsive: true }}
              style={{ width: "100%", height: 420 }}
              useResizeHandler
              onHover={handleMarkerInteraction}
              onClick={handleMarkerInteraction}
            />
          )}
        </div>

        <aside className="event-list">
          <div className="kicker" style={{ marginBottom: 14 }}>
            Timeline Events
          </div>

          {selectedEvent != null && (
            <div className="event-card active" style={{ marginBottom: 12 }}>
              <div className="event-date">{formatEventDate(selectedEvent.date)}</div>
              <div className="event-move" style={{ color: "var(--accent)" }}>
                {EVENT_TYPE_LABEL[selectedEvent.event_type] ?? selectedEvent.event_type}
              </div>
              <div className="event-reason" style={{ marginBottom: 8 }}>
                {selectedEvent.summary}
                {selectedEvent.detail ? ` ${selectedEvent.detail}` : ""}
              </div>
              <button
                className="inline-link"
                onClick={() =>
                  dispatch({
                    type: "open_stock_section",
                    sym,
                    section: mapEventTargetToSection(selectedEvent.link_target),
                  })
                }
              >
                see more
              </button>
            </div>
          )}

          {listedEvents.map((event) => {
            const active = selectedEventId === event.id;
            return (
              <div
                key={event.id}
                className={`event-card ${active ? "active" : ""}`}
                onClick={() => setSelectedEventId(event.id)}
              >
                <div className="event-date">{formatEventDate(event.date)}</div>
                <div className="event-move" style={{ color: "var(--muted)" }}>
                  {EVENT_TYPE_LABEL[event.event_type] ?? event.event_type}
                </div>
                <div className="event-reason">{event.summary}</div>
                <button
                  className="inline-link"
                  style={{ marginTop: 8 }}
                  onClick={(clickEvent) => {
                    clickEvent.stopPropagation();
                    dispatch({
                      type: "open_stock_section",
                      sym,
                      section: mapEventTargetToSection(event.link_target),
                    });
                  }}
                >
                  see more
                </button>
              </div>
            );
          })}

          {listedEvents.length === 0 && (
            <div style={{ color: "var(--muted)", fontSize: 12 }}>
              No enabled event markers for this date range. Try toggling event types or widening range.
            </div>
          )}

          <div style={{ color: "var(--muted)", fontSize: 11, marginTop: 8 }}>
            {listedEvents.length} event markers currently visible.
          </div>
        </aside>
      </div>
    </div>
  );
}
