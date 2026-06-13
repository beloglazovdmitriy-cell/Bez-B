import { useEffect, useState } from "react";
import { apiFeed, type Draft } from "../data";
import { IconFeed } from "../components/Icons";

const LABEL: Record<string, string> = {
  digest: "📰 Дайджест", crowd: "🌡 Разбор толпы", scenarios: "🔮 Сценарии",
  edu: "📚 Ликбез", manifest: "🧭 Манифест", bullshit: "🚩 Детектор буллшита",
  trade: "🧠 Разбор сделки", custom: "✍️ Пост",
};

function when(ts: number): string {
  const d = new Date(ts * 1000);
  const now = new Date();
  const day = (a: Date) => new Date(a.getFullYear(), a.getMonth(), a.getDate()).getTime();
  const diff = (day(now) - day(d)) / 86400000;
  if (diff === 0) return "сегодня";
  if (diff === 1) return "вчера";
  return d.toLocaleDateString("ru-RU", { day: "2-digit", month: "2-digit" });
}

export default function FeedScreen() {
  const [posts, setPosts] = useState<Draft[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  useEffect(() => {
    apiFeed().then(setPosts).catch((e) => setErr((e as Error).message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="content">
      {loading ? (
        <div className="muted-note">Загружаю ленту…</div>
      ) : err ? (
        <div className="muted-note">{err}</div>
      ) : posts.length === 0 ? (
        <div className="stub-card">
          <div style={{ marginBottom: 8 }}><IconFeed size={34} /></div>
          Здесь будет лента разборов рынка, сценариев и ликбеза.<br />
          Скоро появятся первые посты — загляни позже.
        </div>
      ) : (
        <div className="feed">
          {posts.map((p) => (
            <div className="card feed-post" key={p.id}>
              <div className="feed-head">
                <span className="feed-kind">{LABEL[p.kind] || p.kind}</span>
                <span className="feed-date">{when(p.ts)}</span>
              </div>
              <div className="ai-text feed-text">{p.text}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
