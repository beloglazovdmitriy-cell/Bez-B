import { useState } from "react";
import { IconArrowDown, IconArrowUp, IconWallet, IconTrade } from "../components/Icons";
import TradeSheet, { type Action } from "../components/TradeSheet";
import { mockUser } from "../mock";
import type { Summary } from "../data";

type User = typeof mockUser;

const ACTIONS: { id: Action; label: string; sub: string; Icon: typeof IconTrade; tone: string }[] = [
  { id: "buy", label: "Купить", sub: "актив за USDT", Icon: IconTrade, tone: "accent" },
  { id: "sell", label: "Продать", sub: "актив в USDT", Icon: IconArrowUp, tone: "red" },
  { id: "deposit", label: "Пополнить", sub: "₽ → USDT", Icon: IconArrowDown, tone: "accent" },
  { id: "withdraw", label: "Вывести", sub: "USDT из портфеля", Icon: IconWallet, tone: "muted" },
];

export default function TradeScreen({
  user, summary, onDone,
}: {
  user: User;
  summary: Summary;
  onDone: () => void;
}) {
  const [action, setAction] = useState<Action | null>(null);

  if (!user.isAdmin) {
    return (
      <div className="content">
        <div className="stub">Раздел доступен только владельцу портфеля.</div>
      </div>
    );
  }

  return (
    <div className="content">
      <div className="section-title" style={{ marginTop: 4 }}>Операции · только владелец</div>

      <div className="actions-grid">
        {ACTIONS.map((a) => (
          <button className={`action ${a.tone}`} key={a.id} onClick={() => setAction(a.id)}>
            <span className="action-ic"><a.Icon size={22} /></span>
            <span className="action-label">{a.label}</span>
            <span className="action-sub">{a.sub}</span>
          </button>
        ))}
      </div>

      <div className="disclaimer">Каждая сделка попадает в журнал и (если подключён) в канал.</div>

      {action && (
        <TradeSheet
          action={action}
          summary={summary}
          onClose={() => setAction(null)}
          onDone={onDone}
        />
      )}
    </div>
  );
}
