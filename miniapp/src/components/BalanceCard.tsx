import type { Summary } from "../mock";
import { Brand } from "./Icons";

const fmt = (n: number) =>
  n.toLocaleString("ru-RU", { maximumFractionDigits: 0 }).replace(/,/g, " ");
const sign = (n: number) => (n > 0 ? "▲" : n < 0 ? "▼" : "•");
const cls = (n: number) => (n > 0 ? "pos" : n < 0 ? "neg" : "");

export default function BalanceCard({ s }: { s: Summary }) {
  const empty = s.totalUsd <= 0;   // всё продано и выведено — индекс не имеет смысла
  return (
    <div className="card balance">
      <div className="row1">
        <span className="usd">${fmt(s.totalUsd)}</span>
        <span className="rub">{fmt(s.totalRub)} ₽</span>
      </div>

      <div className="pnl">
        <div className="item">
          <span className={`val ${cls(s.profitRubPct)}`}>
            {sign(s.profitRubPct)} {s.profitRubPct.toFixed(1)}%
          </span>
          <span className="lbl">в рублях</span>
        </div>
        <div className="item">
          <span className={`val ${cls(s.profitUsdPct)}`}>
            {sign(s.profitUsdPct)} {s.profitUsdPct.toFixed(1)}%
          </span>
          <span className="lbl">в долларах</span>
        </div>
      </div>

      <div className="index">
        <span>Индекс <Brand size={13} /></span>
        {empty ? (
          <span><b>—</b></span>
        ) : (
          <span>
            <b>{s.index.toFixed(1)}</b> пт{" "}
            <span className={cls(s.index - 100)}>
              ({s.index - 100 > 0 ? "+" : ""}
              {(s.index - 100).toFixed(1)})
            </span>
          </span>
        )}
      </div>
    </div>
  );
}
