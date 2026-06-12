import { IconArrowDown, IconArrowUp } from "../components/Icons";
import { fmtQty, fmtPrice } from "../components/PositionsList";
import type { JournalEntry } from "../data";

const fmt = (n: number) =>
  n.toLocaleString("ru-RU", { maximumFractionDigits: 0 }).replace(/,/g, " ");

export default function JournalScreen({ journal }: { journal: JournalEntry[] }) {
  if (journal.length === 0) {
    return (
      <div className="content">
        <div className="card stub-card">Сделок пока нет — журнал появится с первой операцией.</div>
      </div>
    );
  }
  return (
    <div className="content">
      <div className="section-title" style={{ marginTop: 4 }}>
        Журнал решений · все сделки открыто
      </div>

      <div className="feed">
        {journal.map((e, i) => {
          const buy = e.side === "buy";
          return (
            <div className="entry" key={i}>
              <div className={`entry-ic ${buy ? "buy" : "sell"}`}>
                {buy ? <IconArrowDown size={18} /> : <IconArrowUp size={18} />}
              </div>
              <div className="entry-body">
                <div className="entry-top">
                  <span className="entry-title">
                    {buy ? "Купил" : "Продал"} <b>{e.ticker}</b> на ${fmt(e.amountUsd)}
                  </span>
                  <span className="entry-date">{e.date}</span>
                </div>
                <div className="entry-sub">
                  {fmtQty(e.qty)} {e.ticker} по ${fmtPrice(e.price)} · доля {e.sharePct}%
                </div>
                {e.reason && <div className="entry-reason">{e.reason}</div>}
              </div>
            </div>
          );
        })}
      </div>

      <div className="disclaimer">
        История ведётся публично и без задним числом.
      </div>
    </div>
  );
}
