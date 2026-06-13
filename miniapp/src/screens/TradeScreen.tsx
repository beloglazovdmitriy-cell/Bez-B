import { useState } from "react";
import { IconArrowDown, IconArrowUp, IconWallet, IconTrade, Brand } from "../components/Icons";
import TradeSheet, { type Action } from "../components/TradeSheet";
import { mockUser } from "../mock";
import type { Summary, Pf } from "../data";

type User = typeof mockUser;

const ACTIONS: { id: Action; label: string; sub: string; Icon: typeof IconTrade; tone: string }[] = [
  { id: "buy", label: "Купить", sub: "актив за USDT", Icon: IconTrade, tone: "accent" },
  { id: "sell", label: "Продать", sub: "актив в USDT", Icon: IconArrowUp, tone: "red" },
  { id: "deposit", label: "Пополнить", sub: "₽ → USDT или активом", Icon: IconArrowDown, tone: "accent" },
  { id: "withdraw", label: "Вывести", sub: "USDT из портфеля", Icon: IconWallet, tone: "muted" },
];

export default function TradeScreen({
  user, summary, onDone, pf,
}: {
  user: User;
  summary: Summary;
  onDone: () => void;
  pf: Pf;
}) {
  const [action, setAction] = useState<Action | null>(null);

  // «Без Б» меняет только владелец; свой портфель ведёт каждый
  const canEdit = pf === "me" || user.isAdmin;
  if (!canEdit) {
    return (
      <div className="content">
        <div className="card stub-card">
          Портфель <Brand size={14} /> ведёт только автор.<br />
          Переключись на «Мой портфель» вверху — и веди свой: покупай, продавай,
          контролируй рост.
        </div>
      </div>
    );
  }

  return (
    <div className="content">
      <div className="section-title" style={{ marginTop: 4 }}>
        {pf === "me" ? "Мой портфель · операции" : <><Brand size={14} /> · операции (владелец)</>}
      </div>

      <div className="actions-grid">
        {ACTIONS.map((a) => (
          <button className={`action ${a.tone}`} key={a.id} onClick={() => setAction(a.id)}>
            <span className="action-ic"><a.Icon size={22} /></span>
            <span className="action-label">{a.label}</span>
            <span className="action-sub">{a.sub}</span>
          </button>
        ))}
      </div>

      <div className="disclaimer">
        {pf === "me"
          ? "Это твой личный портфель — виден только тебе."
          : "Сделки попадают в журнал и (если подключён) в канал."}
      </div>

      {action && (
        <TradeSheet
          action={action}
          summary={summary}
          pf={pf}
          onClose={() => setAction(null)}
          onDone={onDone}
        />
      )}
    </div>
  );
}
