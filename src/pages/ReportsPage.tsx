import PortfolioExposureSummary from "../components/PortfolioExposureSummary";
import PortfolioNarrativePanel from "../components/PortfolioNarrativePanel";
import ValuationCompass from "../components/ValuationCompass";
import { usePortfolioData } from "../state/DataProvider";
import { formatPercent } from "../utils/format";

export default function ReportsPage() {
  const { state } = usePortfolioData();
  const overview = state.overview;
  const valuation = state.valuationOverview ?? overview?.valuation_summary ?? null;
  const valuationRows = valuation?.results ?? [];

  return (
    <div className="page-wrap">
      <div className="page-intro" style={{ marginBottom: 24 }}>
        <h1>Reports</h1>
        <p>Generated portfolio review outputs built from persisted exposures, narrative diagnostics, scenario anchors, and valuation coverage.</p>
      </div>

      <PortfolioNarrativePanel narrative={overview?.narrative} />
      <PortfolioExposureSummary summary={overview?.exposure_summary} />

      {valuation ? (
        <div className="card" style={{ marginBottom: 18 }}>
          <div className="kicker">Valuation summary</div>
          <div style={{ display: "grid", gridTemplateColumns: "320px 1fr", gap: 18 }}>
            <ValuationCompass
              weightedAnalystUpside={valuation.weighted_analyst_upside}
              weightedDcfUpside={valuation.weighted_dcf_upside}
              weightedRiUpside={valuation.weighted_ri_upside}
              weightedDdmUpside={valuation.weighted_ddm_upside}
              weightedRelativeUpside={valuation.weighted_relative_upside}
              coverageRatio={valuation.coverage_ratio}
              overvaluedWeight={valuation.overvalued_weight}
              undervaluedWeight={valuation.undervalued_weight}
            />
            <div>
              <div className="kicker" style={{ marginBottom: 8 }}>Security coverage</div>
              <div style={{ overflowX: "auto" }}>
                <table className="table" style={{ margin: 0 }}>
                  <thead>
                    <tr>
                      <th>Symbol</th>
                      <th>Status</th>
                      <th className="right">Composite upside</th>
                      <th className="right">DCF</th>
                      <th className="right">RI</th>
                      <th className="right">Relative</th>
                    </tr>
                  </thead>
                  <tbody>
                    {valuationRows.map((row) => (
                      <tr key={row.symbol}>
                        <td>{row.symbol}</td>
                        <td>{row.model_status}</td>
                        <td className="right">{row.composite_upside == null ? "N/A" : formatPercent(row.composite_upside * 100)}</td>
                        <td className="right">{row.dcf_upside == null ? "N/A" : formatPercent(row.dcf_upside * 100)}</td>
                        <td className="right">{row.ri_upside == null ? "N/A" : formatPercent(row.ri_upside * 100)}</td>
                        <td className="right">{row.relative_upside == null ? "N/A" : formatPercent(row.relative_upside * 100)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      ) : null}

      <div className="grid-3">
        <div className="card">
          <div className="kicker">Refresh status</div>
          <h3 style={{ marginTop: 6 }}>{overview?.last_refresh?.status ?? "No refresh yet"}</h3>
          <p style={{ color: "var(--muted)" }}>{overview?.last_refresh?.error ?? "Run refresh to persist the latest report package."}</p>
        </div>
        <div className="card">
          <div className="kicker">Latest scenario anchor</div>
          <h3 style={{ marginTop: 6 }}>{overview?.latest_scenario_run ? `${overview.latest_scenario_run.factor_key} ${overview.latest_scenario_run.shock_value}` : "No saved scenario"}</h3>
          <p style={{ color: "var(--muted)" }}>{overview?.latest_scenario_run ? `Horizon ${overview.latest_scenario_run.horizon_days} days · ${overview.latest_scenario_run.status}` : "Use the guided macro workflow to save a comparable stress run."}</p>
        </div>
        <div className="card">
          <div className="kicker">Report coverage</div>
          <h3 style={{ marginTop: 6 }}>{overview?.exposure_summary?.coverage.covered_weight_pct.toFixed(1) ?? "0.0"}%</h3>
          <p style={{ color: "var(--muted)" }}>Exposure look-through coverage included in the review package.</p>
        </div>
      </div>
    </div>
  );
}
