import { useState } from "react";
import BalanceCard from "../components/BalanceCard";
import CompositionDonut from "../components/CompositionDonut";
import PositionsList from "../components/PositionsList";
import CopySheet from "../components/CopySheet";
import { IconCopy } from "../components/Icons";
import type { Summary, Pf } from "../data";

export default function PortfolioScreen({ summary, pf }: { summary: Summary; pf: Pf }) {
  const [copy, setCopy] = useState(false);
  const hasPositions = summary.positions.length > 0;
  return (
    <div className="content">
      <BalanceCard s={summary} />
      {hasPositions ? (
        <>
          <CompositionDonut s={summary} />
          <PositionsList positions={summary.positions} />
          {pf === "bezb" && (
            <button className="cta" onClick={() => setCopy(true)}>
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
    </div>
  );
}
