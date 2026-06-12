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
  // безопасные отступы под чёлку/статус-бар в полноэкранном режиме.
  // Полный верхний отступ = чёлка устройства + панель управления Telegram.
  const apply = () => {
    const dev = tg.safeAreaInset?.top ?? 0;
    const ctl = tg.contentSafeAreaInset?.top ?? 0;
    document.documentElement.style.setProperty("--tg-top", `${dev + ctl}px`);
  };
  apply();
  tg.onEvent?.("safeAreaChanged", apply);
  tg.onEvent?.("fullscreenChanged", apply);
  tg.onEvent?.("viewportChanged", apply);
  // полноэкранный режим «устаканивается» с задержкой — пересчитываем несколько раз
  [150, 400, 900, 1600].forEach((ms) => setTimeout(apply, ms));
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
