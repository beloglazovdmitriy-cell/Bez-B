import { useState } from "react";
import BalanceCard from "../components/BalanceCard";
import CompositionDonut from "../components/CompositionDonut";
import PositionsList from "../components/PositionsList";
import CopySheet from "../components/CopySheet";
import { IconCopy } from "../components/Icons";
import type { Summary } from "../data";

export default function PortfolioScreen({ summary }: { summary: Summary }) {
  const [copy, setCopy] = useState(false);
  const hasPositions = summary.positions.length > 0;
  return (
    <div className="content">
      <BalanceCard s={summary} />
      {hasPositions ? (
        <>
          <CompositionDonut s={summary} />
          <PositionsList positions={summary.positions} />
          <button className="cta" onClick={() => setCopy(true)}>
            <IconCopy size={18} />
            Повторить портфель
          </button>
        </>
      ) : (
        <div className="card stub-card">
          Открытых позиций пока нет.<br />
          Следи за публичным портфелём — сделки появятся здесь в реальном времени.
        </div>
      )}
      <div className="disclaimer">
        Не является индивидуальной инвестиционной рекомендацией.
      </div>

      {copy && <CopySheet summary={summary} onClose={() => setCopy(false)} />}
    </div>
  );
}
