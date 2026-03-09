import React from "react";
import { createRoot } from "react-dom/client";
import { SpecProvider } from "./SpecProvider";
import { App } from "./App";

const root = createRoot(document.getElementById("root")!);
root.render(
  <React.StrictMode>
    <SpecProvider>
      <App />
    </SpecProvider>
  </React.StrictMode>
);
