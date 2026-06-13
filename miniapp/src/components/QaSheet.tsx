import { useEffect, useState } from "react";
import { apiQaAsk, apiQaMine, apiQaAll, apiQaAnswer, type QaItem } from "../data";
import { IconAI } from "./Icons";

export default function QaSheet({ isAdmin, onClose }: { isAdmin: boolean; onClose: () => void }) {
  const [tab, setTab] = useState<"ask" | "all">("ask");
  const [mine, setMine] = useState<QaItem[]>([]);
  const [all, setAll] = useState<QaItem[]>([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");
  const [reply, setReply] = useState<Record<number, string>>({});

  function refresh() {
    apiQaMine().then(setMine).catch(() => {});
    if (isAdmin) apiQaAll().then(setAll).catch(() => {});
  }
  useEffect(() => { refresh(); /* eslint-disable-next-line */ }, []);

  async function ask() {
    const text = q.trim();
    if (text.length < 5) { setNote("Сформулируй вопрос подробнее"); return; }
    setBusy(true); setNote("AI думает…");
    try {
      await apiQaAsk(text);
      setQ(""); setNote("Готово ✓"); refresh();
    } catch (e) { setNote((e as Error).message); }
    finally { setBusy(false); }
  }

  async function sendReply(id: number) {
    const text = (reply[id] || "").trim();
    if (!text) return;
    try {
      await apiQaAnswer(id, text);
      setReply({ ...reply, [id]: "" }); setNote("Ответ отправлен пользователю ✓"); refresh();
    } catch (e) { setNote((e as Error).message); }
  }

  return (
    <div className="sheet-overlay" onClick={onClose}>
      <div className="sheet" onClick={(e) => e.stopPropagation()}>
        <div className="sheet-grip" />
        <div className="sheet-title"><IconAI size={20} /> Вопрос-ответ</div>

        {isAdmin && (
          <div className="seg" style={{ marginBottom: 12 }}>
            <button className={"seg-btn " + (tab === "ask" ? "on" : "")} onClick={() => setTab("ask")}>Мои вопросы</button>
            <button className={"seg-btn " + (tab === "all" ? "on" : "")} onClick={() => setTab("all")}>Все вопросы</button>
          </div>
        )}

        {tab === "ask" && (
          <>
            <div className="field-label">Задай вопрос про инвестиции, рынок или портфель</div>
            <textarea className="draft-edit" rows={3} value={q} style={{ minHeight: 70 }}
              placeholder="Напр.: стоит ли докупать на падении или ждать?"
              onChange={(e) => setQ(e.target.value)} />
            <button className="cta" disabled={busy} onClick={ask} style={{ marginTop: 8 }}>
              <IconAI size={16} /> {busy ? "Спрашиваю…" : "Спросить"}
            </button>
            {note && <div className="muted-note" style={{ margin: "8px 0" }}>{note}</div>}

            <div className="field-label" style={{ marginTop: 14 }}>История</div>
            {mine.length === 0 ? (
              <div className="muted-note">Пока пусто. Задай первый вопрос — ответит AI, при необходимости дополнит автор.</div>
            ) : (
              <div className="feed">
                {mine.map((it) => (
                  <div className="card qa-item" key={it.id}>
                    <div className="qa-q">❓ {it.question}</div>
                    {it.answer ? (
                      <div className="qa-a">
                        <span className="qa-by">{it.answeredBy === "owner" ? "💬 Автор" : "🤖 AI"}</span>
                        {it.answer}
                      </div>
                    ) : (
                      <div className="muted-note">Ждёт ответа автора…</div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </>
        )}

        {tab === "all" && isAdmin && (
          <div className="feed">
            {all.length === 0 ? (
              <div className="muted-note">Вопросов пока нет.</div>
            ) : all.map((it) => (
              <div className="card qa-item" key={it.id}>
                <div className="qa-q">❓ {it.name || "Юзер"}: {it.question}</div>
                {it.answer && (
                  <div className="qa-a">
                    <span className="qa-by">{it.answeredBy === "owner" ? "💬 Автор" : "🤖 AI"}</span>
                    {it.answer}
                  </div>
                )}
                <textarea className="draft-edit" rows={2} style={{ minHeight: 50, marginTop: 8 }}
                  placeholder="Личный ответ автора (придёт пользователю в Telegram)"
                  value={reply[it.id] || ""} onChange={(e) => setReply({ ...reply, [it.id]: e.target.value })} />
                <button className="chip" style={{ marginTop: 6 }} onClick={() => sendReply(it.id)}>Ответить лично</button>
              </div>
            ))}
            {note && <div className="muted-note" style={{ marginTop: 8 }}>{note}</div>}
          </div>
        )}

        <button className="sheet-cancel" onClick={onClose}>Закрыть</button>
      </div>
    </div>
  );
}
