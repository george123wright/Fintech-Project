type Props = {
  warnings: string[];
  title?: string;
};

function normalizeWarning(warning: string): string {
  if (warning.startsWith("E_FACTOR_FETCH_FAILED:")) {
    const parts = warning.split(":");
    const factor = parts[1] ?? "factor";
    return `Could not fetch ${factor} data source. Using cache/fallback where available.`;
  }
  if (warning.startsWith("E_FACTOR_NO_DATA:")) {
    const factor = warning.split(":")[1] ?? "factor";
    return `No ${factor} data available yet.`;
  }
  if (warning === "E_SHOCK_CLIPPED") {
    return "Shock was outside historical range and was clipped to a defensible bound.";
  }
  if (warning.startsWith("E_SYMBOL_PRICE_GAPS:")) {
    return "Some holdings were excluded due to insufficient aligned history.";
  }
  if (warning.startsWith("E_FACTOR_STALE:")) {
    const factor = warning.split(":")[1] ?? "factor";
    return `${factor} data is stale.`;
  }
  if (warning.startsWith("E_PREVIEW_SIMS_CAPPED:")) {
    const maxSims = warning.split(":")[1] ?? "400";
    return `Preview simulations were capped at ${maxSims} for responsiveness.`;
  }
  return warning;
}

export default function DataWarningBanner({ warnings, title = "Data Warnings" }: Props) {
  const unique = Array.from(new Set(warnings.map(normalizeWarning).filter((item) => item.trim().length > 0)));
  if (!unique.length) return null;
  return (
    <div className="data-warning-banner">
      <div className="data-warning-title">{title}</div>
      <div className="data-warning-list">
        {unique.slice(0, 4).map((warning) => (
          <span className="data-warning-pill" key={warning}>
            {warning}
          </span>
        ))}
      </div>
    </div>
  );
}
