import { useState } from "react";
import PortfolioSwitcher from "../components/PortfolioSwitcher";
import PortfolioScreen from "./PortfolioScreen";
import ChartScreen from "./ChartScreen";
import JournalScreen from "./JournalScreen";
import TradeScreen from "./TradeScreen";
import type { Pf } from "../data";
import type { AppData } from "../useAppData";

type View = "positions" | "chart" | "journal" | "trade";

export default function PortfolioTab(
  { data, pf, setPf }: { data: AppData; pf: Pf; setPf: (p: Pf) => void },
) {
  const [view, setView] = useState<View>("positions");
  const canEdit = pf === "me" || data.user.isAdmin;

  return (
    <>
      <PortfolioSwitcher pf={pf} onChange={setPf} />
      <div className="seg" style={{ margin: "0 16px 6px" }}>
        <button className={"seg-btn " + (view === "positions" ? "on" : "")} onClick={() => setView("positions")}>Портфель</button>
        <button className={"seg-btn " + (view === "chart" ? "on" : "")} onClick={() => setView("chart")}>Динамика</button>
        <button className={"seg-btn " + (view === "journal" ? "on" : "")} onClick={() => setView("journal")}>Журнал</button>
        {canEdit && (
          <button className={"seg-btn " + (view === "trade" ? "on" : "")} onClick={() => setView("trade")}>Сделки</button>
        )}
      </div>

      {view === "positions" && <PortfolioScreen summary={data.summary} pf={pf} />}
      {view === "chart" && <ChartScreen history={data.history} bench={data.bench} />}
      {view === "journal" && <JournalScreen journal={data.journal} user={data.user} pf={pf} />}
      {view === "trade" && canEdit && (
        <TradeScreen user={data.user} summary={data.summary} onDone={data.reload} pf={pf} />
      )}
    </>
  );
}
