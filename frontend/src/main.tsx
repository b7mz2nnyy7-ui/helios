import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
import "./index.css";

if (window.location.pathname === "/") {
  window.history.replaceState({}, "", "/videos");
}

const root = document.getElementById("root");
if (root === null) {
  throw new Error("Helios root element is missing.");
}

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
