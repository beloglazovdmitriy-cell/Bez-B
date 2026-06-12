import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./theme.css";

// Подхватываем Telegram WebApp, если запущены внутри Telegram.
const tg = (window as any).Telegram?.WebApp;
if (tg) {
  tg.ready();
  tg.expand();
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
