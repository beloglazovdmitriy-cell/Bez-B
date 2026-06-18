import { useEffect, useState } from "react";
import {
  apiQuizToday, apiQuizTodayAnswer,
  type QuizToday, type QuizDayResult, type QuizDayStats,
} from "../data";

// «Детектор буллшита · карточка дня» — одна карточка в сутки на главной.
export default function DailyQuiz() {
  const [data, setData] = useState<QuizToday | null>(null);
  const [result, setResult] = useState<QuizDayResult | null>(null);
  const [stats, setStats] = useState<QuizDayStats | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    apiQuizToday().then((d) => {
      setData(d); setStats(d.stats);
      if (d.answeredToday && d.result) setResult(d.result);
    }).catch(() => setData(null));
  }, []);

  if (!data) return null;

  async function answer(bs: boolean) {
    if (busy || result) return;
    setBusy(true);
    try {
      const r = await apiQuizTodayAnswer(bs);
      setResult({ bs: r.bs, explain: r.explain, myChoice: r.myChoice, correct: r.correct });
      setStats(r.stats);
    } catch { /* аноним/ошибка — кнопки останутся */ }
    finally { setBusy(false); }
  }

  return (
    <div className="card daily-quiz">
      <div className="home-cap">🚩 Детектор буллшита · карточка дня</div>
      <div className="dq-text">{data.card.text}</div>

      {!result ? (
        data.anon ? (
          <div className="muted-note">Открой приложение из Telegram, чтобы ответить и копить серию.</div>
        ) : (
          <div className="dq-actions">
            <button className="dq-btn bs" disabled={busy} onClick={() => answer(true)}>🚩 Буллшит</button>
            <button className="dq-btn ok" disabled={busy} onClick={() => answer(false)}>✅ Норм</button>
          </div>
        )
      ) : (
        <div className="dq-result">
          <div className={"dq-verdict " + (result.correct ? "right" : "wrong")}>
            {result.correct ? "✅ Верно!" : "❌ Мимо"} · это {result.bs ? "🚩 буллшит" : "✅ здравая мысль"}
          </div>
          <div className="dq-explain">{result.explain}</div>
          <div className="muted-note" style={{ marginTop: 6 }}>Новая карточка — завтра.</div>
        </div>
      )}

      {stats && (
        <div className="dq-stats">
          🔥 серия {stats.streak} · рекорд {stats.best} · верно {stats.correct}/{stats.total}
        </div>
      )}
    </div>
  );
}
