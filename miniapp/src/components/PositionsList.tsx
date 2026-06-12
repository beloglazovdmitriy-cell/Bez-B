import type { Position } from "../mock";

const fmt = (n: number) =>
  n.toLocaleString("ru-RU", { maximumFractionDigits: 0 }).replace(/,/g, " ");

export default function PositionsList({ positions }: { positions: Position[] }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <div className="section-title">Позиции</div>
      {positions.map((p) => {
        const up = p.profitPct >= 0;
        return (
          <div className="position" key={p.ticker}>
            <span className="bullet" style={{ background: up ? "var(--accent)" : "var(--red)" }} />
            <div>
              <div className="tk">{p.ticker}</div>
              <div className="sub">
                ср. ${fmt(p.avgPrice)} → ${fmt(p.priceNow)}
              </div>
            </div>
            <div className="right">
              <div className="value">${fmt(p.valueUsd)}</div>
              <div className={`chg ${up ? "pos" : "neg"}`}>
                {up ? "+" : ""}
                {p.profitPct.toFixed(1)}%
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
