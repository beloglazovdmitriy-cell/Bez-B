import { useState } from "react";
import BottomNav, { type Tab } from "./components/BottomNav";
import { IconBitcoin } from "./components/Icons";
import PortfolioScreen from "./screens/PortfolioScreen";
import ChartScreen from "./screens/ChartScreen";
import JournalScreen from "./screens/JournalScreen";
import TradeScreen from "./screens/TradeScreen";
import ProfileScreen from "./screens/ProfileScreen";
import { useAppData } from "./useAppData";

export default function App() {
  const [tab, setTab] = useState<Tab>("portfolio");
  const data = useAppData();

  return (
    <div className="app">
      <header className="header">
        <div className="brand">
          Bez <IconBitcoin size={26} className="brand-btc" />
        </div>
        <div className="tagline">Публичный портфель · инвестиции без буллшита</div>
      </header>

      {tab === "portfolio" && <PortfolioScreen summary={data.summary} />}
      {tab === "chart" && <ChartScreen history={data.history} bench={data.bench} />}
      {tab === "journal" && <JournalScreen journal={data.journal} />}
      {tab === "trade" && <TradeScreen user={data.user} />}
      {tab === "profile" && <ProfileScreen user={data.user} />}

      <BottomNav active={tab} onChange={setTab} />
    </div>
  );
}
