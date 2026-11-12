import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { Cursor } from "./components/Cursor";
import { Page } from "./components/Page";
import { CONTENT } from "./content";
import "./styles/tokens.css";
import "./styles/global.css";

for (const [name, value] of Object.entries(CONTENT.vars)) document.documentElement.style.setProperty(name, value);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Page />
    <Cursor />
  </StrictMode>,
);
