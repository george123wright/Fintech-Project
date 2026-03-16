import { REPORT_CARDS } from "../data/mockData";

export default function ReportsPage() {
  return (
    <div className="page-wrap">
      <div className="page-intro" style={{ marginBottom: 24 }}>
        <h1>Reports</h1>
        <p>Mock reporting outputs for portfolio review and client-ready communication.</p>
      </div>

      <div className="grid-3">
        {REPORT_CARDS.map((card) => (
          <div key={card.title} className="card">
            <h3>{card.title}</h3>
            <p>{card.description}</p>
            <span
              className={`pill ${card.status === "Ready" ? "status-ready" : "status-draft"}`}
              style={{ marginTop: 14, display: "inline-block" }}
            >
              {card.status}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
