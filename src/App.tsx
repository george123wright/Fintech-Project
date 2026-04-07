import { useReducer, type ReactNode } from "react";
import TopNav from "./components/TopNav";
import GlobalChatWidget from "./components/GlobalChatWidget";
import ChartPage from "./pages/ChartPage";
import LensPage from "./pages/LensPage";
import MacroPage from "./pages/MacroPage";
import MarketOverviewPage from "./pages/MarketOverviewPage";
import AnalystHistoryPage from "./pages/AnalystHistoryPage";
import OverviewPage from "./pages/OverviewPage";
import PortfolioNewsPage from "./pages/PortfolioNewsPage";
import ReportsPage from "./pages/ReportsPage";
import ScenariosPage from "./pages/ScenariosPage";
import StockPage from "./pages/StockPage";
import WatchlistPage from "./pages/WatchlistPage";
import { DEFAULT_NAV, navReducer } from "./state/nav";

export default function App() {
  const [state, dispatch] = useReducer(navReducer, DEFAULT_NAV);

  let page: ReactNode;
  switch (state.page) {
    case "lens":
      page = <LensPage />;
      break;
    case "overview":
      page = <OverviewPage dispatch={dispatch} />;
      break;
    case "market_overview":
      page = <MarketOverviewPage dispatch={dispatch} />;
      break;
    case "watchlist":
      page = <WatchlistPage dispatch={dispatch} />;
      break;
    case "scenarios":
      page = <ScenariosPage dispatch={dispatch} />;
      break;
    case "reports":
      page = <ReportsPage />;
      break;
    case "macro":
      page = <MacroPage dispatch={dispatch} />;
      break;
    case "stock":
      page = <StockPage state={state} dispatch={dispatch} />;
      break;
    case "chart":
      page = <ChartPage state={state} dispatch={dispatch} />;
      break;
    case "analyst_history":
      page = <AnalystHistoryPage state={state} dispatch={dispatch} />;
      break;
    case "portfolio_news":
      page = <PortfolioNewsPage dispatch={dispatch} />;
      break;
    default:
      page = <OverviewPage dispatch={dispatch} />;
  }

  return (
    <div className="lens-app">
      <TopNav state={state} dispatch={dispatch} />
      <main className="page-shell">{page}</main>
      <GlobalChatWidget />
    </div>
  );
}
