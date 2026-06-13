import { useEffect, useState } from "react";
import { apiHome, type Home } from "../data";
import DcaStreak from "./DcaStreak";

const SIDE_LABEL = { buy: "купил", sell: "продал" } as const;

/** Цвет зоны индекса страха/жадности. */
function moodColor(v: number): string {
  if (v < 25) return "#ef5350";       // крайний страх
  if (v < 45) return "#ff9800";       // страх
  if (v < 55) return "#ffd54f";       // нейтрально
  if (v < 75) return "#9ccc65";       // жадность
  return "#26a69a";                   // крайняя жадность
}

/** Полукруглый спидометр 0–100. */
function Gauge({ value }: { value: number }) {
  const cx = 100, cy = 100, r = 78;
  const theta = (Math.PI * (100 - value)) / 100;   // 0→π (лево), 100→0 (право)
  const nx = cx + r * Math.cos(theta);
  const ny = cy - r * Math.sin(theta);
  const col = moodColor(value);
  return (
    <svg viewBox="0 0 200 116" className="gauge">
      <defs>
        <linearGradient id="gaugeGrad" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor="#ef5350" />
          <stop offset="50%" stopColor="#ffd54f" />
          <stop offset="100%" stopColor="#26a69a" />
        </linearGradient>
      </defs>
      <path d={`M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}`}
        fill="none" stroke="url(#gaugeGrad)" strokeWidth="12" strokeLinecap="round" />
      <line x1={cx} y1={cy} x2={nx} y2={ny} stroke={col} strokeWidth="3" strokeLinecap="round" />
      <circle cx={cx} cy={cy} r="6" fill={col} />
      <text x={cx} y={cy - 18} textAnchor="middle" className="gauge-val" fill={col}>{value}</text>
    </svg>
  );
}

export default function HomeHeader() {
  const [h, setH] = useState<Home | null>(null);

  useEffect(() => { apiHome().then(setH).catch(() => setH(null)); }, []);

  const m = h?.mood;
  const t = h?.bezbToday;
  return (
    <div className="home">
      <DcaStreak />
      {m && (
        <div className="card home-mood">
          <Gauge value={m.value} />
          <div className="home-mood-side">
            <div className="home-cap">Индекс страха и жадности · крипторынок</div>
            <div className="home-mood-label" style={{ color: moodColor(m.value) }}>{m.label}</div>
            <div className="home-mood-prev">
              вчера {m.prev} {m.trend === "up" ? "↑" : m.trend === "down" ? "↓" : "→"}
            </div>
          </div>
        </div>
      )}

      {t && (
        <div className="card home-trade">
          <div className="home-cap">Что сделал Без Б {t.isToday ? "сегодня" : `· ${t.date}`}</div>
          <div className="home-trade-body">
            <span className={"home-trade-side " + t.side}>{SIDE_LABEL[t.side]}</span>
            <span className="home-trade-main">{t.ticker} на ${t.amountUsd}</span>
          </div>
          {t.reason && <div className="home-trade-reason">«{t.reason}»</div>}
        </div>
      )}

      {h?.digest && (
        <div className="card home-digest">
          <div className="home-cap">📰 Рынок за 60 секунд</div>
          <div className="ai-text home-digest-text">{h.digest.text}</div>
        </div>
      )}
    </div>
  );
}
