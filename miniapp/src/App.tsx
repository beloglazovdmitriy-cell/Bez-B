import { useState, useEffect } from "react";
import BottomNav, { type Tab } from "./components/BottomNav";
import WelcomeModal from "./components/WelcomeModal";
import { IconLogo } from "./components/Icons";
import FeedScreen from "./screens/FeedScreen";
import PortfolioTab from "./screens/PortfolioTab";
import CalcScreen from "./screens/CalcScreen";
import GameScreen from "./screens/GameScreen";
import ProfileScreen from "./screens/ProfileScreen";
import { useAppData } from "./useAppData";
import { apiStreakPing, apiAppOpen, type Pf } from "./data";

export default function App() {
  const [tab, setTab] = useState<Tab>("feed");
  const [pf, setPf] = useState<Pf>("bezb");
  const [welcome, setWelcome] = useState(() => !localStorage.getItem("bezb_welcomed"));
  const data = useAppData(pf);

  // отметить ежедневный визит (стрик входов) + учёт захода/источника (start_param)
  useEffect(() => {
    apiStreakPing().catch(() => {});
    const sp = (window as any).Telegram?.WebApp?.initDataUnsafe?.start_param;
    apiAppOpen(sp ? String(sp) : "").catch(() => {});   // вызываем всегда — учёт каждого открытия
  }, []);

  function closeWelcome() {
    localStorage.setItem("bezb_welcomed", "1");
    setWelcome(false);
  }

  return (
    <div className="app">
      {welcome && <WelcomeModal onClose={closeWelcome} />}
      <header className="header">
        <div className="brand">
          Bez <IconLogo size={26} className="brand-btc" />
        </div>
        <div className="tagline">Публичный портфель · инвестиции без буллшита</div>
      </header>

      {tab === "feed" && <FeedScreen isAdmin={!!data.user.isAdmin} />}
      {tab === "game" && <GameScreen />}
      {tab === "portfolio" && <PortfolioTab data={data} pf={pf} setPf={setPf} />}
      {tab === "calc" && <CalcScreen />}
      {tab === "profile" && <ProfileScreen user={data.user} />}

      <BottomNav active={tab} onChange={setTab} />
    </div>
  );
}
