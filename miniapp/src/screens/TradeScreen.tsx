import { IconArrowDown, IconArrowUp, IconWallet, IconTrade } from "../components/Icons";
import { mockUser } from "../mock";

type User = typeof mockUser;

const ACTIONS = [
  { id: "buy", label: "Купить", sub: "актив за USDT", Icon: IconTrade, tone: "accent" },
  { id: "sell", label: "Продать", sub: "актив в USDT", Icon: IconArrowUp, tone: "red" },
  { id: "depo", label: "Пополнить", sub: "₽ → USDT", Icon: IconArrowDown, tone: "accent" },
  { id: "wd", label: "Вывести", sub: "USDT из портфеля", Icon: IconWallet, tone: "muted" },
];

const REASONS = [
  "Плановая закупка (DCA)", "Докупка на просадке", "Ребаланс портфеля",
  "Долгосрочный тренд", "Свободный кэш", "Фиксация прибыли",
];

export default function TradeScreen({ user }: { user: User }) {
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
          <button className={`action ${a.tone}`} key={a.id}>
            <span className="action-ic"><a.Icon size={22} /></span>
            <span className="action-label">{a.label}</span>
            <span className="action-sub">{a.sub}</span>
          </button>
        ))}
      </div>

      <div className="card">
        <div className="section-title" style={{ marginTop: 0, marginBottom: 8 }}>
          Причина сделки → в журнал и пост в канал
        </div>
        <div className="chips">
          {REASONS.map((r) => (
            <span className="chip" key={r}>{r}</span>
          ))}
        </div>
      </div>

      <div className="disclaimer">Каждая сделка публикуется в канал автоматически.</div>
    </div>
  );
}
