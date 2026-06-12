import { useState } from "react";
import type { Summary } from "../data";
import { apiBuy, apiSell, apiDeposit, apiWithdraw } from "../data";

export type Action = "buy" | "sell" | "deposit" | "withdraw";

const TITLES: Record<Action, string> = {
  buy: "Купить актив",
  sell: "Продать актив",
  deposit: "Пополнить (₽ → USDT)",
  withdraw: "Вывести USDT",
};

const TICKERS = ["BTC", "ETH", "SOL", "XRP", "TON", "AAPL", "NVDA", "TSLA", "SPY"];
const AMOUNTS = [50, 100, 250, 500, 1000];
const RUB = [5000, 10000, 25000, 50000];
const REASONS = [
  "Плановая закупка (DCA)", "Докупка на просадке", "Ребаланс портфеля",
  "Долгосрочный тренд", "Свободный кэш", "Фиксация прибыли",
];

export default function TradeSheet({
  action, summary, onClose, onDone,
}: {
  action: Action;
  summary: Summary;
  onClose: () => void;
  onDone: () => void;
}) {
  const [ticker, setTicker] = useState("");
  const [amount, setAmount] = useState("");
  const [rate, setRate] = useState("");
  const [reason, setReason] = useState("");
  const [sellAll, setSellAll] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const needsTicker = action === "buy" || action === "sell";

  async function submit() {
    setError(""); setBusy(true);
    try {
      if (action === "buy") {
        await apiBuy({ ticker, amountUsdt: Number(amount), reason: reason || undefined });
      } else if (action === "sell") {
        await apiSell({ ticker, amountUsdt: sellAll ? null : Number(amount), reason: reason || undefined });
      } else if (action === "deposit") {
        await apiDeposit({ rub: Number(amount), rate: Number(rate) });
      } else {
        await apiWithdraw({ amountUsdt: Number(amount) });
      }
      onDone();
      onClose();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  // валидность формы
  const valid =
    action === "deposit" ? Number(amount) > 0 && Number(rate) > 0 :
    action === "withdraw" ? Number(amount) > 0 :
    action === "buy" ? !!ticker && Number(amount) > 0 :
    /* sell */ !!ticker && (sellAll || Number(amount) > 0);

  return (
    <div className="sheet-overlay" onClick={onClose}>
      <div className="sheet" onClick={(e) => e.stopPropagation()}>
        <div className="sheet-grip" />
        <div className="sheet-title">{TITLES[action]}</div>

        {/* выбор тикера */}
        {action === "buy" && (
          <Field label="Актив">
            <input className="inp" placeholder="Тикер, напр. BTC"
              value={ticker} onChange={(e) => setTicker(e.target.value.toUpperCase())} />
            <Chips items={TICKERS} active={ticker} onPick={setTicker} />
          </Field>
        )}
        {action === "sell" && (
          <Field label="Позиция">
            {summary.positions.length === 0 ? (
              <div className="muted-note">Открытых позиций нет.</div>
            ) : (
              <Chips items={summary.positions.map((p) => p.ticker)} active={ticker} onPick={setTicker} />
            )}
          </Field>
        )}

        {/* пополнение: рубли + курс */}
        {action === "deposit" ? (
          <>
            <Field label="Сумма, ₽">
              <input className="inp" inputMode="decimal" placeholder="30000"
                value={amount} onChange={(e) => setAmount(e.target.value)} />
              <Chips items={RUB.map(String)} active={amount} onPick={setAmount} suffix=" ₽" />
            </Field>
            <Field label="Курс ₽ за 1 USDT">
              <input className="inp" inputMode="decimal" placeholder="100"
                value={rate} onChange={(e) => setRate(e.target.value)} />
            </Field>
          </>
        ) : action === "withdraw" ? (
          <Field label={`Сумма USDT (доступно ${summary.cashUsdt.toFixed(0)})`}>
            <input className="inp" inputMode="decimal" placeholder="100"
              value={amount} onChange={(e) => setAmount(e.target.value)} />
          </Field>
        ) : (
          <Field label="Сумма, USDT">
            <input className="inp" inputMode="decimal" placeholder="100"
              value={amount} onChange={(e) => setAmount(e.target.value)} disabled={action === "sell" && sellAll} />
            <div className="chips">
              {AMOUNTS.map((a) => (
                <button key={a} className={`chip ${amount === String(a) ? "on" : ""}`}
                  onClick={() => { setSellAll(false); setAmount(String(a)); }}>${a}</button>
              ))}
              {action === "sell" && (
                <button className={`chip ${sellAll ? "on" : ""}`} onClick={() => setSellAll(!sellAll)}>
                  Продать всё
                </button>
              )}
            </div>
          </Field>
        )}

        {/* причина — для покупки/продажи */}
        {needsTicker && (
          <Field label="Причина (в журнал и канал)">
            <Chips items={REASONS} active={reason} onPick={(r) => setReason(r === reason ? "" : r)} wrap />
          </Field>
        )}

        {error && <div className="form-error">{error}</div>}

        <button className="cta" disabled={!valid || busy} onClick={submit}>
          {busy ? "Отправляю…" : "Подтвердить"}
        </button>
        <button className="sheet-cancel" onClick={onClose}>Отмена</button>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="field">
      <div className="field-label">{label}</div>
      {children}
    </div>
  );
}

function Chips({
  items, active, onPick, suffix = "", wrap = false,
}: {
  items: string[]; active: string; onPick: (v: string) => void; suffix?: string; wrap?: boolean;
}) {
  return (
    <div className={`chips ${wrap ? "wrap" : ""}`}>
      {items.map((it) => (
        <button key={it} className={`chip ${active === it ? "on" : ""}`} onClick={() => onPick(it)}>
          {it}{suffix}
        </button>
      ))}
    </div>
  );
}
