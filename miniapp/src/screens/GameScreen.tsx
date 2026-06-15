import { useEffect, useState } from "react";
import PositionsList from "../components/PositionsList";
import TradeSheet, { type Action } from "../components/TradeSheet";
import {
  apiFantasy, apiFantasyJoin, apiFantasyLeaderboard, apiProfileLevel, apiFantasyMentor,
  apiStreakPing, apiEventToday, apiEventChoose, apiReferral, apiBadges,
  loadSummary, type Fantasy, type FantasyLeader, type PlayerLevel, type Summary,
  type Streak, type DailyEvent, type Referral, type Badge,
} from "../data";

const m = (n: number) => Math.round(n).toLocaleString("ru-RU").replace(/,/g, " ");

export default function GameScreen() {
  const [f, setF] = useState<Fantasy | null>(null);
  const [lvl, setLvl] = useState<PlayerLevel | null>(null);
  const [sum, setSum] = useState<Summary | null>(null);
  const [busy, setBusy] = useState(false);
  const [action, setAction] = useState<Action | null>(null);
  const [board, setBoard] = useState<FantasyLeader[] | null>(null);
  const [mentor, setMentor] = useState<string | null>(null);
  const [mentorBusy, setMentorBusy] = useState(false);
  const [streak, setStreak] = useState<Streak | null>(null);
  const [ev, setEv] = useState<DailyEvent | null>(null);
  const [ref, setRef] = useState<Referral | null>(null);
  const [badges, setBadges] = useState<Badge[] | null>(null);

  function shareBrag() {
    if (!ref) return;
    const r = f?.returnPct ?? 0;
    const text = f?.joined
      ? `Я в игре «Инвестор с нуля» от «Без Б» иду ${r >= 0 ? "+" : ""}${r}%${f?.rank ? ` (место #${f.rank})` : ""}. Слабо обогнать? 🏆`
      : "Играю в «Инвестор с нуля» от «Без Б» — учусь инвестировать без буллшита. Залетай 🚀";
    const url = `https://t.me/share/url?url=${encodeURIComponent(ref.link)}&text=${encodeURIComponent(text)}`;
    const tg = (window as any).Telegram?.WebApp;
    if (tg?.openTelegramLink) tg.openTelegramLink(url); else window.open(url, "_blank");
  }
  async function openBadges() {
    setBadges([]);
    try { setBadges(await apiBadges()); } catch { setBadges([]); }
  }

  function reload() {
    apiFantasy().then(setF).catch(() => {});
    apiProfileLevel().then(setLvl).catch(() => {});
    loadSummary("fantasy").then(setSum).catch(() => {});
  }
  useEffect(() => {
    reload();
    apiStreakPing().then(setStreak).catch(() => {});
    apiEventToday().then(setEv).catch(() => {});
    apiReferral().then(setRef).catch(() => {});
  }, []);

  async function chooseEvent(key: string) {
    if (!ev || ev.myChoice) return;
    try {
      const r = await apiEventChoose(key);
      setEv({ ...ev, myChoice: r.myChoice, takeaway: r.takeaway, crowd: r.crowd, total: r.total });
      apiProfileLevel().then(setLvl).catch(() => {});
    } catch { /* */ }
  }

  async function join() {
    if (busy) return;
    setBusy(true);
    try { setF(await apiFantasyJoin()); reload(); } catch { /* */ } finally { setBusy(false); }
  }
  async function askMentor() {
    setMentor(""); setMentorBusy(true);
    try { setMentor((await apiFantasyMentor()).text); }
    catch (e) { setMentor((e as Error).message); }
    finally { setMentorBusy(false); }
  }
  async function openBoard() {
    setBoard([]);
    try { setBoard(await apiFantasyLeaderboard()); } catch { setBoard([]); }
  }

  const pct = lvl && lvl.nextXp
    ? Math.min(100, Math.round(((lvl.xp - lvl.curXp) / (lvl.nextXp - lvl.curXp)) * 100))
    : 100;

  return (
    <div className="content">
      <div className="section-title" style={{ marginTop: 4 }}>🎮 Инвестор с нуля</div>

      {/* уровень */}
      {lvl && (
        <div className="card lvl-card">
          <div className="lvl-top">
            <span className="lvl-badge">{lvl.level}</span>
            <div style={{ flex: 1 }}>
              <div className="lvl-title">{lvl.title}</div>
              <div className="lvl-xp">{lvl.xp} XP{lvl.nextXp ? ` · до ур. ${lvl.level + 1}: ${lvl.nextXp}` : " · макс."}</div>
            </div>
            {streak && streak.streak > 0 && (
              <span className="streak-pill">🔥 {streak.streak}</span>
            )}
          </div>
          <div className="lvl-bar"><div className="lvl-fill" style={{ width: `${pct}%` }} /></div>
          <button className="link-btn" style={{ marginTop: 8 }} onClick={openBadges}>🎖 Мои достижения</button>
        </div>
      )}

      {/* событие дня */}
      {ev && (
        <div className="card event-card">
          <div className="home-cap">{ev.title}</div>
          <div className="event-text">{ev.text}</div>
          {!ev.myChoice ? (
            <div className="event-choices">
              {ev.choices.map((c) => (
                <button key={c.key} className="event-choice" onClick={() => chooseEvent(c.key)}>
                  {c.label}
                </button>
              ))}
            </div>
          ) : (
            <>
              {ev.choices.map((c) => {
                const n = ev.crowd[c.key] || 0;
                const p = ev.total ? Math.round((n / ev.total) * 100) : 0;
                const mine = c.key === ev.myChoice;
                return (
                  <div key={c.key} className={"event-res" + (mine ? " mine" : "")}>
                    <div className="event-res-bar" style={{ width: `${p}%` }} />
                    <span className="event-res-label">{mine ? "✓ " : ""}{c.label}</span>
                    <span className="event-res-pct">{p}%</span>
                  </div>
                );
              })}
              <div className="event-takeaway">{ev.takeaway}</div>
            </>
          )}
        </div>
      )}

      {!f ? (
        <div className="muted-note">Загружаю…</div>
      ) : !f.joined ? (
        <div className="card game-hero">
          <div className="game-hero-emoji">🚀</div>
          <div className="game-hero-title">Стань инвестором с нуля</div>
          <div className="game-hero-sub">
            Получи <b>${m(f.startCapital)}</b> виртуальных, собери портфель на реальных ценах,
            учись у AI-наставника и обгони Без Б. Без риска — на учебных деньгах.
          </div>
          <button className="cta" onClick={join} disabled={busy}>
            {busy ? "Старт…" : "🚀 Начать игру"}
          </button>
        </div>
      ) : (
        <>
          <div className="card game-stat-row">
            <div className="game-stat">
              <div className="game-val" style={{ color: (f.returnPct || 0) >= 0 ? "var(--accent)" : "var(--red)" }}>
                {(f.returnPct || 0) >= 0 ? "+" : ""}{f.returnPct}%
              </div>
              <div className="fan-cap">доходность</div>
            </div>
            <div className="game-stat">
              <div className="game-val">${m(f.value || 0)}</div>
              <div className="fan-cap">портфель</div>
            </div>
            <div className="game-stat">
              <div className="game-val">{f.rank ? `#${f.rank}` : "—"}</div>
              <div className="fan-cap">место</div>
            </div>
          </div>

          {sum && sum.positions.length > 0 ? (
            <PositionsList positions={sum.positions} />
          ) : (
            <div className="card stub-card">Портфель пуст — купи первый актив и начни игру.</div>
          )}

          <div className="game-actions">
            <button className="cta" onClick={() => setAction("buy")}>Купить</button>
            <button className="cta cta-ghost" onClick={() => setAction("sell")}>Продать</button>
          </div>
          <div className="game-actions">
            <button className="cta cta-ai" onClick={askMentor} disabled={mentorBusy}>
              🤖 {mentorBusy ? "Наставник думает…" : "Разбор от наставника"}
            </button>
            <button className="cta cta-ghost" onClick={openBoard}>🏆 Рейтинг</button>
          </div>
          <button className="cta cta-ghost" style={{ marginTop: 10, width: "100%" }} onClick={shareBrag}>
            📣 Похвастаться · обгони меня
          </button>

          <div className="disclaimer">Учебная игра на виртуальные деньги. Не ИИР.</div>
        </>
      )}

      {action && sum && (
        <TradeSheet action={action} summary={sum} pf="fantasy"
          onClose={() => setAction(null)} onDone={() => { setAction(null); reload(); }} />
      )}

      {mentor !== null && (
        <div className="sheet-overlay" onClick={() => setMentor(null)}>
          <div className="sheet" onClick={(e) => e.stopPropagation()}>
            <div className="sheet-grip" />
            <div className="sheet-title">🤖 AI-наставник</div>
            <div className="ai-text" style={{ whiteSpace: "pre-wrap", minHeight: 60 }}>
              {mentorBusy && !mentor ? "Разбираю твои решения…" : mentor}
            </div>
            <button className="sheet-cancel" onClick={() => setMentor(null)}>Закрыть</button>
          </div>
        </div>
      )}

      {badges && (
        <div className="sheet-overlay" onClick={() => setBadges(null)}>
          <div className="sheet" onClick={(e) => e.stopPropagation()}>
            <div className="sheet-grip" />
            <div className="sheet-title">🎖 Достижения{ref && ref.count > 0 ? ` · 👥 ${ref.count}` : ""}</div>
            <div className="badge-grid">
              {badges.map((b, i) => (
                <div key={i} className={"badge-cell" + (b.earned ? " earned" : "")}>
                  <span className="badge-ic">{b.icon}</span>
                  <span className="badge-lbl">{b.label}</span>
                </div>
              ))}
            </div>
            <button className="cta cta-ghost" style={{ marginTop: 14 }} onClick={shareBrag}>
              📣 Позвать друга (+{ref?.days ?? 3} дня премиума за каждого)
            </button>
            <button className="sheet-cancel" onClick={() => setBadges(null)}>Закрыть</button>
          </div>
        </div>
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
