export function formatPrice(value: number, currency = "USD"): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    maximumFractionDigits: value > 1000 ? 0 : 2,
  }).format(value);
}

export function formatPnL(value: number): string {
  const sign = value >= 0 ? "+" : "";
  return `${sign}${value.toLocaleString("en-US")}`;
}

export function formatPercent(value: number, digits = 1): string {
  const sign = value >= 0 ? "+" : "";
  return `${sign}${value.toFixed(digits)}%`;
}

export function consensusColor(consensus: string): string {
  const mapping: Record<string, string> = {
    BUY: "var(--green)",
    HOLD: "var(--yellow)",
    SELL: "var(--red)",
  };
  return mapping[consensus.toUpperCase()] ?? "var(--accent)";
}
