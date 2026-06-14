import { useEffect, useState } from "react";
import { apiPredict, apiPredictVote, apiPredictLeaderboard,
  type Predict, type PredLeader } from "../data";

const m = (n: number) => Math.round(n).toLocaleString("ru-RU").replace(/,/g, " ");

function timeLeft(closeTs: number): string {
  const s = closeTs - Date.now() / 1000;
  if (s <= 0) return "идёт подсчёт…";
  const d = Math.floor(s / 86400);
  const h = Math.floor((s % 86400) / 3600);
  if (d > 0) return `${d} дн ${h} ч`;
  return `${h} ч`;
}

export default function PredictCard() {
  const [p, setP] = useState<Predict | null>(null);
  const [busy, setBusy] = useState(false);
  const [board, setBoard] = useState<PredLeader[] | null>(null);

  useEffect(() => { apiPredict().then(setP).catch(() => setP(null)); }, []);

  if (!p || !p.round) return null;
  const r = p.round;
  const c = p.crowd;
  const upPct = c.total ? Math.round((c.up / c.total) * 100) : 50;

  async function vote(choice: "up" | "down") {
    if (busy) return;
    setBusy(true);
    try {
      const res = await apiPredictVote(choice);
      setP({ ...p!, myVote: choice, crowd: res.crowd });
    } catch { /* раунд закрыт */ }
    finally { setBusy(false); }
  }

  async function openBoard() {
    setBoard([]);
    try { setBoard(await apiPredictLeaderboard()); } catch { setBoard([]); }
  }

  return (
    <div className="card predict">
      <div className="predict-head">
        <span className="home-cap">🔮 Прогноз недели</span>
        <span className="predict-timer">⏳ {timeLeft(r.closeTs)}</span>
      </div>
      <div className="predict-q">
        {r.symbol} будет <b>выше</b> или <b>ниже</b> <b>${m(r.target)}</b> к воскресенью?
      </div>

      <div className="predict-btns">
        <button className={"pred-btn up" + (p.myVote === "up" ? " on" : "")}
          onClick={() => vote("up")} disabled={busy}>⬆️ Выше</button>
        <button className={"pred-btn down" + (p.myVote === "down" ? " on" : "")}
          onClick={() => vote("down")} disabled={busy}>⬇️ Ниже</button>
      </div>

      {c.total > 0 && (
        <>
          <div className="predict-bar">
            <div className="pb-up" style={{ width: `${upPct}%` }} />
          </div>
          <div className="predict-split">
            <span>⬆️ {upPct}%</span>
            <span>{c.total} голос(ов)</span>
            <span>{100 - upPct}% ⬇️</span>
          </div>
        </>
      )}

      <div className="predict-foot">
        <span>Твой счёт: <b>{p.me.points}</b> из {p.me.total}</span>
        <button className="link-btn" onClick={openBoard}>Лидерборд</button>
      </div>

      {p.last && p.last.result && (
        <div className="predict-last">
          Прошлый раунд: {p.last.symbol} закрылся ${m(p.last.closePrice || 0)} —{" "}
          {p.last.result === "up" ? "выше ⬆️" : "ниже ⬇️"} ${m(p.last.target)}
        </div>
      )}

      {board && (
        <div className="sheet-overlay" onClick={() => setBoard(null)}>
          <div className="sheet" onClick={(e) => e.stopPropagation()}>
            <div className="sheet-grip" />
            <div className="sheet-title">🏆 Лучшие аналитики</div>
            {board.length === 0 ? (
              <div className="muted-note">Пока нет завершённых раундов.</div>
            ) : (
              <div className="lb">
                {board.map((u, i) => (
                  <div className="lb-row" key={u.uid}>
                    <span className="lb-rank">{["🥇", "🥈", "🥉"][i] || i + 1}</span>
                    <span className="lb-name">{u.name}</span>
                    <span className="lb-pts">{u.points}/{u.total}</span>
                  </div>
                ))}
              </div>
            )}
            <button className="sheet-cancel" onClick={() => setBoard(null)}>Закрыть</button>
          </div>
        </div>
      )}
    </div>
  );
}
