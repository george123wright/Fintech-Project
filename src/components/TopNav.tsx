import type { Dispatch } from "react";
import type { NavAction, NavState, Page } from "../state/nav";
import { usePortfolioData } from "../state/DataProvider";

type Props = {
  state: NavState;
  dispatch: Dispatch<NavAction>;
};

const LINKS: Array<{ label: string; page: Page }> = [
  { label: "Lens", page: "lens" },
  { label: "Overview", page: "overview" },
  { label: "Watchlist", page: "watchlist" },
  { label: "Scenarios", page: "scenarios" },
  { label: "Reports", page: "reports" },
  { label: "News", page: "portfolio_news" },
];

export default function TopNav({ state, dispatch }: Props) {
  const { state: dataState, selectPortfolio } = usePortfolioData();

  return (
    <nav className="top-nav">
      <button className="nav-brand" onClick={() => dispatch({ type: "go_page", page: "lens" })}>
        <span className="nav-brand-title">lens</span>
        <span className="nav-brand-title nav-dot">.</span>
      </button>

      <div className="nav-links">
        {LINKS.map((item) => {
          const active =
            state.page === item.page ||
            (item.page === "scenarios" && state.page === "macro");
          return (
            <button
              key={item.page}
              className={`nav-btn ${active ? "active" : ""}`}
              onClick={() => dispatch({ type: "go_page", page: item.page })}
            >
              {item.label}
            </button>
          );
        })}
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <select
          className="nav-portfolio-select"
          value={dataState.activePortfolioId ?? ""}
          onChange={(event) => {
            const id = Number(event.target.value);
            if (Number.isFinite(id) && id > 0) {
              void selectPortfolio(id);
            }
          }}
        >
          {dataState.portfolios.map((portfolio) => (
            <option key={portfolio.id} value={portfolio.id}>
              {portfolio.name}
            </option>
          ))}
        </select>

        <button className="macro-chip" onClick={() => dispatch({ type: "open_macro", event: "FOMC" })}>
          FOMC - 5 days
        </button>
      </div>
    </nav>
  );
}
