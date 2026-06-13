import { useState } from "react";
import BottomNav, { type Tab } from "./components/BottomNav";
import WelcomeModal from "./components/WelcomeModal";
import PortfolioSwitcher from "./components/PortfolioSwitcher";
import { IconLogo } from "./components/Icons";
import FeedScreen from "./screens/FeedScreen";
import PortfolioScreen from "./screens/PortfolioScreen";
import ChartScreen from "./screens/ChartScreen";
import JournalScreen from "./screens/JournalScreen";
import CalcScreen from "./screens/CalcScreen";
import TradeScreen from "./screens/TradeScreen";
import ProfileScreen from "./screens/ProfileScreen";
import { useAppData } from "./useAppData";
import type { Pf } from "./data";

export default function App() {
  const [tab, setTab] = useState<Tab>("feed");
  const [pf, setPf] = useState<Pf>("bezb");
  const [welcome, setWelcome] = useState(() => !localStorage.getItem("bezb_welcomed"));
  const data = useAppData(pf);

  function closeWelcome() {
    localStorage.setItem("bezb_welcomed", "1");
    setWelcome(false);
  }

  // переключатель портфеля нужен на экранах, зависящих от портфеля
  const showSwitch = tab === "portfolio" || tab === "chart" || tab === "journal" || tab === "trade";

  return (
    <div className="app">
      {welcome && <WelcomeModal onClose={closeWelcome} />}
      <header className="header">
        <div className="brand">
          Bez <IconLogo size={26} className="brand-btc" />
        </div>
        <div className="tagline">Публичный портфель · инвестиции без буллшита</div>
      </header>

      {showSwitch && <PortfolioSwitcher pf={pf} onChange={setPf} />}

      {tab === "feed" && <FeedScreen />}
      {tab === "portfolio" && <PortfolioScreen summary={data.summary} pf={pf} />}
      {tab === "chart" && <ChartScreen history={data.history} bench={data.bench} />}
      {tab === "journal" && <JournalScreen journal={data.journal} user={data.user} pf={pf} />}
      {tab === "calc" && <CalcScreen />}
      {tab === "trade" && (
        <TradeScreen user={data.user} summary={data.summary} onDone={data.reload} pf={pf} />
      )}
      {tab === "profile" && <ProfileScreen user={data.user} />}

      <BottomNav active={tab} onChange={setTab} />
    </div>
  );
}
