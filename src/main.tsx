import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "katex/dist/katex.min.css";
import "./styles/lens.css";
import { DataProvider } from "./state/DataProvider";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <DataProvider>
      <App />
    </DataProvider>
  </React.StrictMode>
);
