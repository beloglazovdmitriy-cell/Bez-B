import { useState } from "react";
import BalanceCard from "../components/BalanceCard";
import CompositionDonut from "../components/CompositionDonut";
import PositionsList from "../components/PositionsList";
import CopySheet from "../components/CopySheet";
import AnalysisSheet from "../components/AnalysisSheet";
import AiSheet from "../components/AiSheet";
import FantasyBanner from "../components/FantasyBanner";
import { IconCopy, IconAI, IconScenario } from "../components/Icons";
import { apiScenarios, type Summary, type Pf } from "../data";

export default function PortfolioScreen({ summary, pf, onReload }:
  { summary: Summary; pf: Pf; onReload?: () => void }) {
  const [copy, setCopy] = useState(false);
  const [analyze, setAnalyze] = useState(false);
  const [scen, setScen] = useState(false);
  const hasPositions = summary.positions.length > 0;
  return (
    <div className="content">
      {pf === "fantasy" && <FantasyBanner onJoined={() => onReload?.()} />}
      <BalanceCard s={summary} />
      {hasPositions ? (
        <>
          <CompositionDonut s={summary} />
          <PositionsList positions={summary.positions} />
          <button className="cta cta-ai" onClick={() => setAnalyze(true)}>
            <IconAI size={18} />
            AI-разбор портфеля
          </button>
          <button className="cta cta-ghost" onClick={() => setScen(true)}>
            <IconScenario size={18} />
            Сценарии «если рынок дёрнется»
          </button>
          {pf === "bezb" && (
            <button className="cta cta-ghost" onClick={() => setCopy(true)}>
              <IconCopy size={18} />
              Повторить портфель
            </button>
          )}
        </>
      ) : (
        <div className="card stub-card">
          {pf === "me" ? (
            <>Твой портфель пока пуст.<br />
              Перейди во вкладку «Сделки» → «Пополнить» и начни строить капитал.</>
          ) : (
            <>Открытых позиций пока нет.<br />
              Следи за публичным портфелём — сделки появятся здесь в реальном времени.</>
          )}
        </div>
      )}
      <div className="disclaimer">
        Не является индивидуальной инвестиционной рекомендацией.
      </div>

      {copy && <CopySheet summary={summary} onClose={() => setCopy(false)} />}
      {analyze && <AnalysisSheet pf={pf} onClose={() => setAnalyze(false)} />}
      {scen && (
        <AiSheet
          title={<><IconScenario size={20} /> Сценарии</>}
          load={() => apiScenarios(pf)}
          onClose={() => setScen(false)}
        />
      )}
    </div>
  );
}
