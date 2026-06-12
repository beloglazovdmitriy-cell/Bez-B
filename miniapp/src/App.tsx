import { useState } from "react";
import BottomNav, { type Tab } from "./components/BottomNav";
import WelcomeModal from "./components/WelcomeModal";
import { IconLogo } from "./components/Icons";
import PortfolioScreen from "./screens/PortfolioScreen";
import ChartScreen from "./screens/ChartScreen";
import JournalScreen from "./screens/JournalScreen";
import CalcScreen from "./screens/CalcScreen";
import TradeScreen from "./screens/TradeScreen";
import ProfileScreen from "./screens/ProfileScreen";
import { useAppData } from "./useAppData";

export default function App() {
  const [tab, setTab] = useState<Tab>("portfolio");
  const [welcome, setWelcome] = useState(() => !localStorage.getItem("bezb_welcomed"));
  const data = useAppData();

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

      {tab === "portfolio" && <PortfolioScreen summary={data.summary} />}
      {tab === "chart" && <ChartScreen history={data.history} bench={data.bench} />}
      {tab === "journal" && <JournalScreen journal={data.journal} />}
      {tab === "calc" && <CalcScreen />}
      {tab === "trade" && <TradeScreen user={data.user} summary={data.summary} onDone={data.reload} />}
      {tab === "profile" && <ProfileScreen user={data.user} />}

      <BottomNav active={tab} onChange={setTab} isAdmin={data.user.isAdmin} />
    </div>
  );
}
