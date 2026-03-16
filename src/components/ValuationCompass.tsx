import { formatPercent } from "../utils/format";

type Props = {
  weightedAnalystUpside: number | null | undefined;
  weightedDcfUpside: number | null | undefined;
  weightedRiUpside: number | null | undefined;
  weightedDdmUpside: number | null | undefined;
  weightedRelativeUpside: number | null | undefined;
  coverageRatio: number | null | undefined;
  overvaluedWeight: number | null | undefined;
  undervaluedWeight: number | null | undefined;
};

function metricColor(value: number | null | undefined): string {
  if (value == null) return "var(--muted)";
  if (value > 0) return "var(--green)";
  if (value < 0) return "var(--red)";
  return "var(--muted)";
}

export default function ValuationCompass({
  weightedAnalystUpside,
  weightedDcfUpside,
  weightedRiUpside,
  weightedDdmUpside,
  weightedRelativeUpside,
  coverageRatio,
  overvaluedWeight,
  undervaluedWeight,
}: Props) {
  const coverage = coverageRatio ?? 0;
  const over = overvaluedWeight ?? 0;
  const under = undervaluedWeight ?? 0;

  return (
    <div className="valuation-compass">
      <div className="valuation-row">
        <span>Weighted Analyst</span>
        <strong style={{ color: metricColor(weightedAnalystUpside) }}>
          {weightedAnalystUpside == null ? "N/A" : formatPercent(weightedAnalystUpside * 100)}
        </strong>
      </div>
      <div className="valuation-row">
        <span>Weighted DCF</span>
        <strong style={{ color: metricColor(weightedDcfUpside) }}>
          {weightedDcfUpside == null ? "N/A" : formatPercent(weightedDcfUpside * 100)}
        </strong>
      </div>
      <div className="valuation-row">
        <span>Weighted RI</span>
        <strong style={{ color: metricColor(weightedRiUpside) }}>
          {weightedRiUpside == null ? "N/A" : formatPercent(weightedRiUpside * 100)}
        </strong>
      </div>
      <div className="valuation-row">
        <span>Weighted DDM</span>
        <strong style={{ color: metricColor(weightedDdmUpside) }}>
          {weightedDdmUpside == null ? "N/A" : formatPercent(weightedDdmUpside * 100)}
        </strong>
      </div>
      <div className="valuation-row">
        <span>Weighted Relative</span>
        <strong style={{ color: metricColor(weightedRelativeUpside) }}>
          {weightedRelativeUpside == null ? "N/A" : formatPercent(weightedRelativeUpside * 100)}
        </strong>
      </div>
      <div className="valuation-row">
        <span>Coverage</span>
        <strong>{formatPercent(coverage * 100)}</strong>
      </div>
      <div className="valuation-row">
        <span>Undervalued Weight</span>
        <strong style={{ color: "var(--green)" }}>{formatPercent(under * 100)}</strong>
      </div>
      <div className="valuation-row">
        <span>Overvalued Weight</span>
        <strong style={{ color: "var(--red)" }}>{formatPercent(over * 100)}</strong>
      </div>
    </div>
  );
}
