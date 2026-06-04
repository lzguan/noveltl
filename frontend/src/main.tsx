import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import "./index.css";
import { App } from "./App.tsx";
import { client } from "./client/client.gen";

client.setConfig({
  baseUrl: import.meta.env.VITE_API_BASE_URL ?? "/api",
  auth: () => {
    if (typeof window === "undefined") {
      return undefined;
    }

    const candidates = [
      window.localStorage.getItem("access_token"),
      window.localStorage.getItem("accessToken"),
      window.localStorage.getItem("token"),
      window.sessionStorage.getItem("access_token"),
      window.sessionStorage.getItem("accessToken"),
      window.sessionStorage.getItem("token"),
    ];

    const token = candidates.find(
      (candidate) => typeof candidate === "string" && candidate.length > 0,
    );
    return token ?? undefined;
  },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>,
);
