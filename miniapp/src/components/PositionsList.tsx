import type { Position } from "../mock";

const fmtMoney = (n: number) =>
  n.toLocaleString("ru-RU", { maximumFractionDigits: 0 }).replace(/,/g, " ");
// количество: для крупных — без дробей, для дробных крипто — больше знаков
export const fmtQty = (q: number) => {
  const d = q >= 1000 ? 0 : q >= 1 ? 4 : 6;
  return q.toFixed(d).replace(/\.?0+$/, "");
};
// цена: мелкие активы (напр. ONDO ~$0.8) показываем с дробями, а не как $1
export const fmtPrice = (p: number) =>
  p >= 100 ? fmtMoney(p) : p >= 1 ? p.toFixed(2) : p.toFixed(4);

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
              <div className="tk">{p.ticker} · {fmtQty(p.qty)} шт</div>
              <div className="sub">
                ср. ${fmtPrice(p.avgPrice)} → ${fmtPrice(p.priceNow)}
              </div>
            </div>
            <div className="right">
              <div className="value">${fmtMoney(p.valueUsd)}</div>
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
