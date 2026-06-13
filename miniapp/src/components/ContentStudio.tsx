import { useEffect, useState } from "react";
import {
  apiContentGenerate, apiContentDrafts, apiContentPublish, apiContentDelete,
  apiContentUpdate, apiContentCustom, type Draft,
} from "../data";
import { IconAI, IconChannel } from "./Icons";

const RUBRICS: { kind: string; label: string }[] = [
  { kind: "digest", label: "📰 Дайджест" },
  { kind: "crowd", label: "🌡 Разбор толпы" },
  { kind: "scenarios", label: "🔮 Сценарии" },
  { kind: "edu", label: "📚 Ликбез" },
  { kind: "manifest", label: "🧭 Манифест" },
  { kind: "bullshit", label: "🚩 Детектор Б" },
];
const LABEL: Record<string, string> = {
  digest: "📰 Дайджест", crowd: "🌡 Разбор толпы", scenarios: "🔮 Сценарии",
  edu: "📚 Ликбез", manifest: "🧭 Манифест", bullshit: "🚩 Детектор буллшита",
  trade: "🧠 Сделка", custom: "✍️ Моя тема",
};

export default function ContentStudio({ onClose }: { onClose: () => void }) {
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [busy, setBusy] = useState("");        // kind генерации в работе
  const [note, setNote] = useState("");
  const [loading, setLoading] = useState(true);
  const [editId, setEditId] = useState<number | null>(null);  // id черновика в правке
  const [editText, setEditText] = useState("");
  const [topic, setTopic] = useState("");                     // своя тема/задача

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
    try { await apiContentPublish(id); setNote("Опубликовано в канал ✓"); refresh(); }
    catch (e) { setNote((e as Error).message); }
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

        <div className="field-label">Сгенерировать черновик</div>
        <div className="chips" style={{ marginBottom: 12 }}>
          {RUBRICS.map((r) => (
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
                ) : (
                  <>
                    <div className="ai-text draft-text">{d.text}</div>
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
