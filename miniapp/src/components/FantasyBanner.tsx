import { useEffect, useState } from "react";
import { apiFantasy, apiFantasyJoin, apiFantasyLeaderboard,
  type Fantasy, type FantasyLeader } from "../data";

function daysLeft(endTs: number): string {
  const s = endTs - Date.now() / 1000;
  if (s <= 0) return "сезон завершается";
  const d = Math.floor(s / 86400);
  return d > 0 ? `${d} дн до финала` : "последний день";
}

export default function FantasyBanner({ onJoined }: { onJoined: () => void }) {
  const [f, setF] = useState<Fantasy | null>(null);
  const [busy, setBusy] = useState(false);
  const [board, setBoard] = useState<FantasyLeader[] | null>(null);

  useEffect(() => { apiFantasy().then(setF).catch(() => setF(null)); }, []);

  async function join() {
    if (busy) return;
    setBusy(true);
    try { setF(await apiFantasyJoin()); onJoined(); }
    catch { /* ignore */ }
    finally { setBusy(false); }
  }
  async function openBoard() {
    setBoard([]);
    try { setBoard(await apiFantasyLeaderboard()); } catch { setBoard([]); }
  }

  if (!f) return null;

  return (
    <div className="card fantasy">
      <div className="predict-head">
        <span className="home-cap">🏆 Сезон фэнтези-портфелей</span>
        <span className="predict-timer">⏳ {daysLeft(f.season.endTs)}</span>
      </div>

      {!f.joined ? (
        <>
          <div className="fan-pitch">
            Получи <b>${f.startCapital.toLocaleString("ru-RU")}</b> виртуальных, собери портфель
            на реальных ценах и обгони рынок и Без Б. Участников: {f.players}.
          </div>
          <button className="cta" style={{ marginTop: 12 }} onClick={join} disabled={busy}>
            {busy ? "Вступаю…" : "🏆 Вступить в сезон"}
          </button>
        </>
      ) : (
        <>
          <div className="fan-row">
            <div className="fan-stat">
              <div className="fan-val" style={{ color: (f.returnPct || 0) >= 0 ? "var(--accent)" : "var(--red)" }}>
                {(f.returnPct || 0) >= 0 ? "+" : ""}{f.returnPct}%
              </div>
              <div className="fan-cap">твой результат</div>
            </div>
            <div className="fan-stat">
              <div className="fan-val">{f.rank ? `#${f.rank}` : "—"}</div>
              <div className="fan-cap">место из {f.players}</div>
            </div>
            <div className="fan-stat">
              <div className="fan-val" style={{ color: f.bezbReturnPct >= 0 ? "var(--accent)" : "var(--red)" }}>
                {f.bezbReturnPct >= 0 ? "+" : ""}{f.bezbReturnPct}%
              </div>
              <div className="fan-cap">Без Б</div>
            </div>
          </div>
          <div className="fan-hint">Покупай/продавай во вкладке «Сделки» — это виртуальные деньги.</div>
          <button className="link-btn" style={{ marginTop: 8 }} onClick={openBoard}>Таблица сезона →</button>
        </>
      )}

      {board && (
        <div className="sheet-overlay" onClick={() => setBoard(null)}>
          <div className="sheet" onClick={(e) => e.stopPropagation()}>
            <div className="sheet-grip" />
            <div className="sheet-title">🏆 Таблица сезона</div>
            {board.length === 0 ? (
              <div className="muted-note">Пока никто не собрал портфель.</div>
            ) : (
              <div className="lb">
                {board.map((u, i) => (
                  <div className="lb-row" key={i}>
                    <span className="lb-rank">{["🥇", "🥈", "🥉"][i] || i + 1}</span>
                    <span className="lb-name">{u.name}</span>
                    <span className="lb-pts" style={{ color: u.returnPct >= 0 ? "var(--accent)" : "var(--red)" }}>
                      {u.returnPct >= 0 ? "+" : ""}{u.returnPct}%
                    </span>
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
