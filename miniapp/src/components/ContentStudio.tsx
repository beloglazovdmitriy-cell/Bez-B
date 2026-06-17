import { useEffect, useState } from "react";
import {
  apiContentGenerate, apiContentDrafts, apiContentPublish, apiContentDelete,
  apiContentUpdate, apiContentCustom, type Draft,
} from "../data";
import { IconAI, IconChannel } from "./Icons";

// Утро — экспертные посты (ценность, доверие)
const EXPERT: { kind: string; label: string }[] = [
  { kind: "digest", label: "📰 Дайджест" },
  { kind: "crowd", label: "🌡 Разбор толпы" },
  { kind: "scenarios", label: "🔮 Сценарии" },
  { kind: "ta", label: "📐 Теханализ" },
  { kind: "edu", label: "📚 Ликбез" },
  { kind: "bullshit", label: "🚩 Детектор Б" },
  { kind: "manifest", label: "🧭 Манифест" },
  { kind: "psych", label: "🧠 Психология" },
  { kind: "case", label: "💡 Кейс" },
];
// Вечер — вовлечение (опросы) и конверсия (к премиуму)
const ENGAGE: { kind: string; label: string }[] = [
  { kind: "poll_decision", label: "🗳 Что бы ты сделал?" },
  { kind: "poll_predict", label: "🗳 BTC выше/ниже?" },
  { kind: "poll_choose", label: "🗳 Что разобрать?" },
  { kind: "poll_mood", label: "🗳 Страшно/жадно?" },
  { kind: "promo_underdog", label: "🎯 Нелюбимчик" },
  { kind: "promo_ai", label: "🎯 AI-разбор" },
  { kind: "promo_speed", label: "🎯 Скорость" },
  { kind: "promo_alert", label: "🎯 Алерты" },
  { kind: "promo_sandbox", label: "🎯 Песочница" },
];
const LABEL: Record<string, string> = {
  digest: "📰 Дайджест", ta: "📐 Теханализ", crowd: "🌡 Разбор толпы", scenarios: "🔮 Сценарии",
  edu: "📚 Ликбез", manifest: "🧭 Манифест", bullshit: "🚩 Детектор буллшита",
  psych: "🧠 Психология", case: "💡 Кейс", trade: "🧠 Сделка", custom: "✍️ Моя тема",
  poll: "🗳 Опрос",
  promo_underdog: "🎯 Промо · Нелюбимчик", promo_ai: "🎯 Промо · AI-разбор",
  promo_speed: "🎯 Промо · Скорость", promo_alert: "🎯 Промо · Алерты",
  promo_sandbox: "🎯 Промо · Песочница",
};

// Распарсить черновик-опрос (kind "poll", text = JSON {question, options}).
function parsePoll(text: string): { question: string; options: string[] } | null {
  try {
    const p = JSON.parse(text);
    if (p && p.question && Array.isArray(p.options)) return p;
  } catch { /* не опрос */ }
  return null;
}

export default function ContentStudio({ onClose }: { onClose: () => void }) {
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [busy, setBusy] = useState("");        // kind генерации в работе
  const [note, setNote] = useState("");
  const [loading, setLoading] = useState(true);
  const [editId, setEditId] = useState<number | null>(null);  // id черновика в правке
  const [editText, setEditText] = useState("");
  const [topic, setTopic] = useState("");                     // своя тема/задача
  const [noChart, setNoChart] = useState<Record<number, boolean>>({});
  const [noCta, setNoCta] = useState<Record<number, boolean>>({});
  const [imgs, setImgs] = useState<Record<number, File | null>>({});

  function refresh() {
    apiContentDrafts().then(setDrafts).catch((e) => setNote((e as Error).message))
      .finally(() => setLoading(false));
  }
  useEffect(() => { refresh(); /* eslint-disable-next-line */ }, []);

  async function generate(kind: string) {
    setBusy(kind); setNote("");
    try { await apiContentGenerate(kind); refresh(); }
    catch (e) { setNote((e as Error).message); }
    finally { setBusy(""); }
  }
  async function generateCustom() {
    const t = topic.trim();
    if (!t) { setNote("Опиши тему или задачу"); return; }
    setBusy("custom"); setNote("");
    try { await apiContentCustom(t); setTopic(""); refresh(); }
    catch (e) { setNote((e as Error).message); }
    finally { setBusy(""); }
  }
  async function publish(id: number) {
    setNote("Публикую…");
    try {
      await apiContentPublish(id, {
        cta: !noCta[id], chart: !noChart[id], image: imgs[id] || null,
      });
      setNote("Опубликовано в канал ✓"); refresh();
    } catch (e) { setNote((e as Error).message); }
  }
  async function remove(id: number) {
    try { await apiContentDelete(id); refresh(); } catch (e) { setNote((e as Error).message); }
  }
  function startEdit(d: Draft) { setEditId(d.id); setEditText(d.text); setNote(""); }
  async function saveEdit() {
    if (editId == null) return;
    setNote("Сохраняю…");
    try {
      await apiContentUpdate(editId, editText);
      setEditId(null); setNote("Изменения сохранены ✓"); refresh();
    } catch (e) { setNote((e as Error).message); }
  }

  return (
    <div className="sheet-overlay" onClick={onClose}>
      <div className="sheet" onClick={(e) => e.stopPropagation()}>
        <div className="sheet-grip" />
        <div className="sheet-title"><IconAI size={20} /> Контент-студия</div>

        <div className="field-label">Утро · экспертный пост</div>
        <div className="chips" style={{ marginBottom: 12 }}>
          {EXPERT.map((r) => (
            <button key={r.kind} className="chip" disabled={!!busy}
              onClick={() => generate(r.kind)}>
              {busy === r.kind ? "…" : r.label}
            </button>
          ))}
        </div>

        <div className="field-label">Вечер · вовлечение и конверсия</div>
        <div className="chips" style={{ marginBottom: 12 }}>
          {ENGAGE.map((r) => (
            <button key={r.kind} className="chip" disabled={!!busy}
              onClick={() => generate(r.kind)}>
              {busy === r.kind ? "…" : r.label}
            </button>
          ))}
        </div>

        <div className="field-label">Своя тема / задача</div>
        <textarea className="draft-edit" rows={3} value={topic}
          placeholder="Напр.: объясни, почему usd-cost-averaging спасает новичков от паники"
          onChange={(e) => setTopic(e.target.value)} style={{ minHeight: 70 }} />
        <button className="cta" disabled={!!busy} onClick={generateCustom}
          style={{ marginTop: 8, marginBottom: 12 }}>
          <IconAI size={16} /> {busy === "custom" ? "Создаю…" : "Создать по моей теме"}
        </button>

        {note && <div className="muted-note" style={{ marginBottom: 8 }}>{note}</div>}

        <div className="field-label">Очередь черновиков</div>
        {loading ? (
          <div className="muted-note">Загружаю…</div>
        ) : drafts.length === 0 ? (
          <div className="muted-note">Пусто. Сгенерируй черновик кнопкой выше.</div>
        ) : (
          <div className="feed">
            {drafts.map((d) => (
              <div className="card draft" key={d.id}>
                <div className="draft-kind">{LABEL[d.kind] || d.kind}</div>
                {editId === d.id ? (
                  <>
                    <textarea className="draft-edit" value={editText}
                      onChange={(e) => setEditText(e.target.value)} rows={10} />
                    <div className="draft-actions">
                      <button className="cta" onClick={saveEdit}>Сохранить</button>
                      <button className="chip" onClick={() => setEditId(null)}>Отмена</button>
                    </div>
                  </>
                ) : d.kind === "poll" ? (
                  <>
                    {(() => {
                      const p = parsePoll(d.text);
                      return p ? (
                        <div className="poll-preview">
                          <div className="poll-q">{p.question}</div>
                          {p.options.map((o, i) => (
                            <div className="poll-opt" key={i}>○ {o}</div>
                          ))}
                          <div className="muted-note" style={{ marginTop: 6 }}>
                            Опубликуется как настоящий Telegram-опрос
                          </div>
                        </div>
                      ) : <div className="ai-text draft-text">{d.text}</div>;
                    })()}
                    <div className="draft-actions">
                      <button className="cta" onClick={() => publish(d.id)}>
                        <IconChannel size={16} /> Опубликовать опрос
                      </button>
                      <button className="chip" onClick={() => startEdit(d)}>Править</button>
                      <button className="chip" onClick={() => remove(d.id)}>Удалить</button>
                    </div>
                  </>
                ) : (
                  <>
                    <div className="ai-text draft-text">{d.text}</div>
                    <div className="pub-opts">
                      <label className="pub-opt">
                        <input type="checkbox" checked={!noChart[d.id]}
                          onChange={(e) => setNoChart({ ...noChart, [d.id]: !e.target.checked })} />
                        📊 График
                      </label>
                      <label className="pub-opt">
                        <input type="checkbox" checked={!noCta[d.id]}
                          onChange={(e) => setNoCta({ ...noCta, [d.id]: !e.target.checked })} />
                        🔗 Кнопка бота
                      </label>
                      <label className="pub-opt file">
                        🖼 {imgs[d.id] ? "Картинка ✓" : "Картинка"}
                        <input type="file" accept="image/*" hidden
                          onChange={(e) => setImgs({ ...imgs, [d.id]: e.target.files?.[0] || null })} />
                      </label>
                    </div>
                    <div className="draft-actions">
                      <button className="cta" onClick={() => publish(d.id)}>
                        <IconChannel size={16} /> Опубликовать
                      </button>
                      <button className="chip" onClick={() => startEdit(d)}>Править</button>
                      <button className="chip" onClick={() => remove(d.id)}>Удалить</button>
                    </div>
                  </>
                )}
              </div>
            ))}
          </div>
        )}

        <button className="sheet-cancel" onClick={onClose}>Закрыть</button>
      </div>
    </div>
  );
}
