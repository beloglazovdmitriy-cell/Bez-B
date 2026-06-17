import { useEffect, useState } from "react";
import {
  apiFeed, apiFeedReact, apiComments, apiAddComment, apiDeleteComment,
  FEED_REACTIONS, type Draft, type Comment,
} from "../data";
import { IconFeed, IconLogo } from "../components/Icons";
import HomeHeader from "../components/HomeHeader";

const LABEL: Record<string, string> = {
  digest: "📰 Дайджест", ta: "📐 Теханализ", crowd: "🌡 Разбор толпы", scenarios: "🔮 Сценарии",
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

// Блок комментариев под постом: счётчик-кнопка раскрывает список + поле ввода.
function Comments({ post, isAdmin }: { post: Draft; isAdmin: boolean }) {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<Comment[]>([]);
  const [count, setCount] = useState(post.comments || 0);
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  async function toggle() {
    const next = !open;
    setOpen(next);
    if (next && items.length === 0) {
      setLoading(true);
      try { setItems(await apiComments(post.id)); }
      catch { /* молча */ }
      finally { setLoading(false); }
    }
  }

  async function send() {
    const t = text.trim();
    if (!t || busy) return;
    setBusy(true); setErr("");
    try {
      const c = await apiAddComment(post.id, t);
      setItems((xs) => [...xs, c]);
      setCount((n) => n + 1);
      setText("");
    } catch (e) { setErr((e as Error).message); }
    finally { setBusy(false); }
  }

  async function del(id: number) {
    try {
      await apiDeleteComment(id);
      setItems((xs) => xs.filter((c) => c.id !== id));
      setCount((n) => Math.max(0, n - 1));
    } catch { /* молча */ }
  }

  return (
    <div className="comments">
      <button className="comments-toggle" onClick={toggle}>
        💬 {count > 0 ? `Комментарии · ${count}` : "Комментировать"}
      </button>
      {open && (
        <div className="comments-body">
          {loading ? (
            <div className="muted-note">Загружаю…</div>
          ) : (
            items.map((c) => (
              <div className="comment" key={c.id}>
                <div className="comment-head">
                  <span className="comment-name">{c.name}</span>
                  <span className="comment-date">{when(c.ts)}</span>
                  {isAdmin && (
                    <button className="comment-del" onClick={() => del(c.id)} title="Удалить">✕</button>
                  )}
                </div>
                <div className="comment-text">{c.text}</div>
              </div>
            ))
          )}
          {!loading && items.length === 0 && (
            <div className="muted-note">Пока без комментариев. Будь первым 👇</div>
          )}
          <div className="comment-form">
            <input
              className="comment-input"
              value={text}
              maxLength={600}
              placeholder="Написать комментарий…"
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") send(); }}
            />
            <button className="comment-send" onClick={send} disabled={busy || !text.trim()}>
              ➤
            </button>
          </div>
          {err && <div className="muted-note">{err}</div>}
        </div>
      )}
    </div>
  );
}

export default function FeedScreen({ isAdmin = false }: { isAdmin?: boolean }) {
  const [posts, setPosts] = useState<Draft[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  useEffect(() => {
    apiFeed().then(setPosts).catch((e) => setErr((e as Error).message))
      .finally(() => setLoading(false));
  }, []);

  async function react(post: Draft, emoji: string) {
    try {
      const r = await apiFeedReact(post.id, emoji);
      setPosts((ps) => ps.map((p) =>
        p.id === post.id ? { ...p, reactions: r.counts, mine: r.mine } : p));
    } catch { /* молча: не критично */ }
  }

  return (
    <div className="content">
      <HomeHeader />
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
              <div className="feed-reactions">
                {FEED_REACTIONS.map((emoji) => {
                  const mine = (p.mine || []).includes(emoji);
                  const n = (p.reactions || {})[emoji] || 0;
                  return (
                    <button
                      key={emoji}
                      className={"react-btn" + (mine ? " active" : "")}
                      onClick={() => react(p, emoji)}
                    >
                      <span className="react-emoji">
                        {emoji === "bez" ? <IconLogo size={18} /> : emoji}
                      </span>
                      {n > 0 && <span className="react-count">{n}</span>}
                    </button>
                  );
                })}
              </div>
              <Comments post={p} isAdmin={isAdmin} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
