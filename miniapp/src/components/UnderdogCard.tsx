import { useEffect, useState } from "react";
import { apiUnderdog, type Underdog } from "../data";

// «Нелюбимчик недели» — премиум. Free видит тизер с призывом открыть в премиуме.
export default function UnderdogCard() {
  const [u, setU] = useState<Underdog | null>(null);
  const [open, setOpen] = useState(false);
  useEffect(() => { apiUnderdog().then(setU).catch(() => setU(null)); }, []);

  if (!u) return null;
  if (!u.locked && !u.ticker) return null;   // нечего показывать

  if (u.locked) {
    return (
      <div className="card underdog underdog-locked">
        <div className="home-cap">🔎 Нелюбимчик недели · премиум</div>
        <div className="underdog-teaser">{u.teaser}</div>
        <div className="underdog-cta">🔒 Открыть в премиуме → вкладка «Профиль»</div>
      </div>
    );
  }

  const s = u.stats;
  return (
    <div className="card underdog">
      {/* свёрнуто: заголовок + тикер + просадка всегда видны, разбор по тапу */}
      <button className="underdog-bar" onClick={() => setOpen((v) => !v)}>
        <span className="home-cap" style={{ margin: 0 }}>🔎 Нелюбимчик недели</span>
        <span className="underdog-head">
          <span className="underdog-ticker">{u.ticker}</span>
          {s && <span className="underdog-dd">{s.dd}% от макс.</span>}
          <span className="underdog-chev">{open ? "▲" : "▼"}</span>
        </span>
      </button>
      {open && (
        <>
          {s && (
            <div className="underdog-stats">
              RSI {s.rsi ?? "—"} · за 7д {s.ret7}% · за 30д {s.ret30}%
              {s.belowSma200 ? " · ниже 200д" : ""}
            </div>
          )}
          {u.analysis && <div className="ai-text underdog-analysis">{u.analysis}</div>}
          {u.top3 && u.top3.length > 1 && (
            <div className="underdog-top3">
              Ещё на радаре: {u.top3.slice(1).map((t) => t.ticker).join(" · ")}
            </div>
          )}
        </>
      )}
    </div>
  );
}
