import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./theme.css";

// Подхватываем Telegram WebApp, если запущены внутри Telegram.
const tg = (window as any).Telegram?.WebApp;
if (tg) {
  tg.ready();
  tg.expand();                                  // на всю высоту (не «шторкой»)
  try { tg.requestFullscreen?.(); } catch { /* старые клиенты не поддерживают */ }
  try { tg.disableVerticalSwipes?.(); } catch { /* чтобы свайп не закрывал */ }
  // безопасные отступы под чёлку/статус-бар в полноэкранном режиме
  const apply = () => {
    const top = tg.contentSafeAreaInset?.top ?? tg.safeAreaInset?.top ?? 0;
    document.documentElement.style.setProperty("--tg-top", `${top}px`);
  };
  apply();
  tg.onEvent?.("safeAreaChanged", apply);
  tg.onEvent?.("fullscreenChanged", apply);
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
