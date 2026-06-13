import { useState } from "react";
import type { Summary } from "../data";
import { Brand } from "./Icons";

const PRESETS = [10000, 30000, 50000, 100000];
const fmt = (n: number) => Math.round(n).toLocaleString("ru-RU").replace(/,/g, " ");

// «Повтори портфель»: вводишь свой капитал — показываем распределение по текущей
// структуре портфеля (доли позиций). Чистый клиентский расчёт.
export default function CopySheet({ summary, onClose }: { summary: Summary; onClose: () => void }) {
  const [capital, setCapital] = useState("100000");
  const cap = Number(capital) || 0;

  const total = summary.positions.reduce((a, p) => a + p.valueUsd, 0);
  const rate = summary.totalUsd > 0 ? summary.totalRub / summary.totalUsd : 0;

  return (
    <div className="sheet-overlay" onClick={onClose}>
      <div className="sheet" onClick={(e) => e.stopPropagation()}>
        <div className="sheet-grip" />
        <div className="sheet-title">Повтори портфель <Brand size={16} /></div>

        {total <= 0 ? (
          <div className="muted-note" style={{ padding: "12px 0" }}>
            В портфеле пока нет открытых позиций — распределять нечего. Загляни позже.
          </div>
        ) : (
          <>
            <div className="field">
              <div className="field-label">Твой капитал, ₽</div>
              <input className="inp" inputMode="decimal" value={capital}
                onChange={(e) => setCapital(e.target.value)} />
              <div className="chips">
                {PRESETS.map((p) => (
                  <button key={p} className={`chip ${capital === String(p) ? "on" : ""}`}
                    onClick={() => setCapital(String(p))}>{fmt(p)} ₽</button>
                ))}
              </div>
            </div>

            <div className="copy-list">
              {summary.positions.map((p) => {
                const w = p.valueUsd / total;
                const rub = cap * w;
                const usd = rate > 0 ? rub / rate : 0;
                return (
                  <div className="copy-row" key={p.ticker}>
                    <span className="copy-tk">{p.ticker}</span>
                    <span className="copy-w">{(w * 100).toFixed(0)}%</span>
                    <span className="copy-amt">{fmt(rub)} ₽<small> ≈ ${fmt(usd)}</small></span>
                  </div>
                );
              })}
            </div>

            <div className="welcome-foot" style={{ marginTop: 14 }}>
              Доли — на текущую дату. Не является индивидуальной инвестиционной рекомендацией.
            </div>
          </>
        )}

        <button className="sheet-cancel" onClick={onClose}>Закрыть</button>
      </div>
    </div>
  );
}
