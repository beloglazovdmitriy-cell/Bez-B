import { useState } from "react";
import { IconArrowDown, IconArrowUp, IconAI } from "../components/Icons";
import { fmtQty, fmtPrice } from "../components/PositionsList";
import TradeCommentSheet from "../components/TradeCommentSheet";
import { mockUser } from "../mock";
import type { JournalEntry, Pf } from "../data";

type User = typeof mockUser;
const fmt = (n: number) =>
  n.toLocaleString("ru-RU", { maximumFractionDigits: 0 }).replace(/,/g, " ");

export default function JournalScreen({
  journal, user, pf,
}: {
  journal: JournalEntry[];
  user: User;
  pf: Pf;
}) {
  const [commentId, setCommentId] = useState<number | null>(null);
  // разбор сделки → в канал: только владельцу и только для публичного «Без Б»
  const canComment = user.isAdmin && pf === "bezb";

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
        {journal.map((e) => {
          const buy = e.side === "buy";
          return (
            <div className="entry" key={e.id}>
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
                {canComment && (
                  <button className="entry-ai" onClick={() => setCommentId(e.id)}>
                    <IconAI size={14} /> AI-разбор → в канал
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <div className="disclaimer">
        История ведётся публично и без задним числом.
      </div>

      {commentId !== null && (
        <TradeCommentSheet pf={pf} id={commentId} onClose={() => setCommentId(null)} />
      )}
    </div>
  );
}
