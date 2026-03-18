import type { Data, Layout } from "plotly.js";

const MUTED = "#6b6b8a";
const ACCENT = "#7b6ef6";
const LIGHT_SURFACE = "#ffffff";
const LIGHT_GRID = "#dbe3f3";
const LIGHT_TEXT = "#233047";

const PALETTE = [
  "#7b6ef6",
  "#5b8ef0",
  "#3dd68c",
  "#f0b959",
  "#f05b5b",
  "#e8a838",
  "#4cb7c5",
  "#9ea7ff",
];

export type FrontierHolding = {
  sym: string;
  weight: number;
  color?: string;
};

export type ChartMarkerEvent = {
  id: string;
  date: string;
  eventType: string;
  title: string;
  summary: string;
  detail?: string | null;
  linkTarget: string;
};

export function buildFrontierChart(
  holdings: FrontierHolding[],
  portfolioRisk?: number,
  portfolioReturn?: number
): { data: Data[]; layout: Partial<Layout> } {
  const sigmas = Array.from({ length: 180 }, (_, i) => 0.07 + (0.35 * i) / 179);
  const frontierReturns = sigmas.map((sigma) => {
    const z = Math.max(0, Math.min(1, (sigma - 0.07) / 0.35));
    return 0.055 + 0.165 * Math.sqrt(z) + 0.075 * z;
  });

  const points = holdings.slice(0, 12).map((holding, idx) => {
    const risk = 0.1 + idx * 0.035;
    const expectedReturn = 0.04 + (holding.weight / 100) * 0.45;
    const color = holding.color ?? PALETTE[idx % PALETTE.length];

    return {
      x: [risk],
      y: [expectedReturn],
      type: "scatter",
      mode: "text+markers",
      marker: { size: 9, color, line: { color, width: 1.2 } },
      text: [holding.sym],
      textposition: "top right",
      textfont: { size: 10, color },
      name: holding.sym,
      hovertemplate: `<b>${holding.sym}</b><br>Risk=${(risk * 100).toFixed(1)}% E(R)=${(
        expectedReturn * 100
      ).toFixed(1)}%<extra></extra>`,
    } as Data;
  });

  const data: Data[] = [
    {
      x: sigmas,
      y: frontierReturns,
      type: "scatter",
      mode: "lines",
      line: { color: ACCENT, width: 2 },
      hoverinfo: "skip",
      name: "Efficient Frontier",
    },
    ...points,
    {
      x: [portfolioRisk ?? 0.21],
      y: [portfolioReturn ?? 0.13],
      type: "scatter",
      mode: "text+markers",
      marker: {
        size: 14,
        color: ACCENT,
        symbol: "circle",
        line: { color: LIGHT_SURFACE, width: 2 },
      },
      text: ["Portfolio"],
      textposition: "top right",
      textfont: { size: 11, color: LIGHT_TEXT },
      name: "Portfolio",
      hovertemplate: "<b>Portfolio</b><extra></extra>",
    },
  ];

  const layout: Partial<Layout> = {
    plot_bgcolor: LIGHT_SURFACE,
    paper_bgcolor: LIGHT_SURFACE,
    font: { family: "DM Mono, monospace", color: MUTED, size: 10 },
    margin: { l: 40, r: 20, t: 20, b: 40 },
    xaxis: {
      title: "Risk (sigma)",
      gridcolor: LIGHT_GRID,
      linecolor: LIGHT_GRID,
      zerolinecolor: LIGHT_GRID,
      tickformat: ".0%",
    },
    yaxis: {
      title: "E(R)",
      gridcolor: LIGHT_GRID,
      linecolor: LIGHT_GRID,
      zerolinecolor: LIGHT_GRID,
      tickformat: ".0%",
    },
    showlegend: false,
    height: 260,
  };

  return { data, layout };
}

export function buildDonutChart(
  allocation: Record<string, number>,
  centerLabel: string
): { data: Data[]; layout: Partial<Layout> } {
  const labels = Object.keys(allocation);
  const values = Object.values(allocation);
  const colors = labels.map((_, idx) => PALETTE[idx % PALETTE.length]);

  const data: Data[] = [
    {
      type: "pie",
      labels,
      values,
      hole: 0.62,
      marker: { colors, line: { color: "#111118", width: 3 } },
      textinfo: "none",
      hovertemplate: "<b>%{label}</b><br>%{value:.1f}%<extra></extra>",
    },
  ];

  const layout: Partial<Layout> = {
    plot_bgcolor: "#111118",
    paper_bgcolor: "#111118",
    margin: { l: 10, r: 10, t: 10, b: 10 },
    showlegend: false,
    height: 220,
    annotations: [
      {
        text: centerLabel,
        x: 0.5,
        y: 0.5,
        showarrow: false,
        font: { size: 13, color: "#e8e8f0" },
      },
    ],
  };

  return { data, layout };
}

export function buildPriceChartFromSeries(
  sym: string,
  points: Array<{ date: string; close: number }>,
  events: ChartMarkerEvent[] = [],
  highlightedEventId: string | null = null
): { data: Data[]; layout: Partial<Layout> } {
  const x = points.map((p) => p.date);
  const y = points.map((p) => p.close);

  const baseSeries: Data = {
    x,
    y,
    type: "scatter",
    fill: "tozeroy",
    fillcolor: "#7b6ef622",
    line: { color: ACCENT, width: 2 },
    mode: "lines",
    hovertemplate: "<b>%{x}</b><br>Price on day: $%{y:.2f}<extra></extra>",
    name: sym,
  };

  const colorByType: Record<string, string> = {
    dividend: "#f0be6b",
    stock_split: "#7b6ef6",
    insider_transaction: "#3dd68c",
    analyst_revision: "#5b8ef0",
  };
  const labelByType: Record<string, string> = {
    dividend: "Dividends",
    stock_split: "Splits",
    insider_transaction: "Insider",
    analyst_revision: "Analyst Revisions",
  };

  const pointTimes = points.map((point) => new Date(point.date).getTime());
  const findNearestPointIndex = (eventDate: string): number | null => {
    if (!pointTimes.length) return null;
    const targetTime = new Date(eventDate).getTime();
    if (!Number.isFinite(targetTime)) return null;

    let nearestIndex = 0;
    let nearestDistance = Math.abs(pointTimes[0] - targetTime);
    for (let idx = 1; idx < pointTimes.length; idx += 1) {
      const distance = Math.abs(pointTimes[idx] - targetTime);
      if (distance < nearestDistance) {
        nearestDistance = distance;
        nearestIndex = idx;
      }
    }
    return nearestIndex;
  };

  const grouped = new Map<
    string,
    Array<{ pointDate: string; pointPrice: number; event: ChartMarkerEvent }>
  >();
  for (const event of events) {
    const pointIndex = findNearestPointIndex(event.date);
    if (pointIndex == null) continue;
    const bucket = grouped.get(event.eventType) ?? [];
    bucket.push({
      pointDate: points[pointIndex].date,
      pointPrice: points[pointIndex].close,
      event,
    });
    grouped.set(event.eventType, bucket);
  }

  const markerTraces: Data[] = [];
  for (const [eventType, rows] of grouped.entries()) {
    markerTraces.push({
      type: "scatter",
      mode: "markers",
      x: rows.map((row) => row.pointDate),
      y: rows.map((row) => row.pointPrice),
      name: labelByType[eventType] ?? eventType,
      marker: {
        color: colorByType[eventType] ?? "#e8e8f0",
        size: rows.map((row) => (row.event.id === highlightedEventId ? 10 : 7)),
        symbol: "circle",
        line: {
          color: "#0f1322",
          width: rows.map((row) => (row.event.id === highlightedEventId ? 2.1 : 1.2)),
        },
      },
      customdata: rows.map((row) => [
        row.event.id,
        row.event.title,
        row.event.summary,
        row.event.linkTarget,
      ]),
      hovertemplate:
        "<b>%{customdata[1]}</b><br>%{x}<br>%{customdata[2]}<br><span style='color:#97a1bd'>Click marker for details</span><extra></extra>",
    });
  }

  const data: Data[] = [baseSeries, ...markerTraces];

  const layout: Partial<Layout> = {
    plot_bgcolor: "#0a0a0f",
    paper_bgcolor: "#0a0a0f",
    font: { family: "DM Mono, monospace", color: MUTED, size: 10 },
    margin: { l: 50, r: 20, t: 20, b: 40 },
    xaxis: { gridcolor: "#1a1a28" },
    yaxis: { gridcolor: "#1a1a28", tickprefix: "$" },
    showlegend: markerTraces.length > 0,
    legend: {
      orientation: "h",
      yanchor: "bottom",
      y: 1.01,
      xanchor: "right",
      x: 1,
      font: { color: MUTED, size: 10 },
    },
    height: 420,
    hovermode: "closest",
  };

  return { data, layout };
}
