import { useEffect, useState } from "react";
import { apiQuizNext, apiQuizAnswer, apiQuizReset,
  type QuizNext, type QuizResult } from "../data";

const BADGES = [
  { n: 3, ic: "🥉", label: "Новичок" },
  { n: 7, ic: "🔥", label: "Чуйка" },
  { n: 12, ic: "🏆", label: "Детектор" },
  { n: 16, ic: "👑", label: "Не проведёшь" },
];

export default function QuizSheet({ onClose }: { onClose: () => void }) {
  const [data, setData] = useState<QuizNext | null>(null);
  const [res, setRes] = useState<QuizResult | null>(null);
  const [busy, setBusy] = useState(false);

  function load() { setRes(null); apiQuizNext().then(setData).catch(() => setData(null)); }
  useEffect(() => { load(); }, []);

  async function answer(bs: boolean) {
    if (busy || !data?.question) return;
    setBusy(true);
    try { setRes(await apiQuizAnswer(data.question.id, bs)); }
    catch { /* ignore */ }
    finally { setBusy(false); }
  }
  async function reset() { await apiQuizReset().catch(() => {}); load(); }

  const stats = res?.stats || data?.stats;

  return (
    <div className="sheet-overlay" onClick={onClose}>
      <div className="sheet" onClick={(e) => e.stopPropagation()}>
        <div className="sheet-grip" />
        <div className="sheet-title">🚩 Детектор буллшита</div>

        {stats && (
          <div className="quiz-stats">
            <span>✅ {stats.score}</span>
            <span>🔥 серия {stats.streak}</span>
            <span>🏅 рекорд {stats.best}</span>
          </div>
        )}
        {stats && (
          <div className="quiz-badges">
            {BADGES.map((b) => (
              <span key={b.n} className={"dca-badge" + (stats.best >= b.n ? " earned" : "")}
                title={b.label}>{b.ic}</span>
            ))}
          </div>
        )}

        {!data ? (
          <div className="muted-note">Загружаю…</div>
        ) : data.done && !res ? (
          <div className="card stub-card" style={{ marginTop: 12 }}>
            Ты прошёл все {data.total} карточек! Счёт: {data.stats.score}/{data.total}.<br />
            <button className="cta" style={{ marginTop: 12 }} onClick={reset}>Пройти заново</button>
          </div>
        ) : !res ? (
          <>
            <div className="quiz-q">{data.question!.text}</div>
            <div className="quiz-btns">
              <button className="pred-btn down" disabled={busy} onClick={() => answer(true)}>🚩 Буллшит</button>
              <button className="pred-btn up" disabled={busy} onClick={() => answer(false)}>✅ Норм</button>
            </div>
            <div className="quiz-progress">Пройдено {data.answeredCount} из {data.total}</div>
          </>
        ) : (
          <>
            <div className={"quiz-verdict " + (res.correct ? "ok" : "no")}>
              {res.correct ? "Верно! 🎯" : "Мимо 🙃"} — это {res.bs ? "🚩 буллшит" : "✅ норм"}
            </div>
            <div className="quiz-explain">{res.explain}</div>
            <button className="cta" style={{ marginTop: 14 }} onClick={load}>Дальше →</button>
          </>
        )}

        <button className="sheet-cancel" onClick={onClose}>Закрыть</button>
      </div>
    </div>
  );
}
