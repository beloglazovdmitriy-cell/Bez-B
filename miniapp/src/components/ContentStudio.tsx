import { useEffect, useState } from "react";
import {
  apiContentGenerate, apiContentDrafts, apiContentPublish, apiContentDelete,
  type Draft,
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
  trade: "🧠 Сделка",
};

export default function ContentStudio({ onClose }: { onClose: () => void }) {
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [busy, setBusy] = useState("");        // kind генерации в работе
  const [note, setNote] = useState("");
  const [loading, setLoading] = useState(true);

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
  async function publish(id: number) {
    setNote("Публикую…");
    try { await apiContentPublish(id); setNote("Опубликовано в канал ✓"); refresh(); }
    catch (e) { setNote((e as Error).message); }
  }
  async function remove(id: number) {
    try { await apiContentDelete(id); refresh(); } catch (e) { setNote((e as Error).message); }
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
                <div className="ai-text draft-text">{d.text}</div>
                <div className="draft-actions">
                  <button className="cta" onClick={() => publish(d.id)}>
                    <IconChannel size={16} /> Опубликовать
                  </button>
                  <button className="chip" onClick={() => remove(d.id)}>Удалить</button>
                </div>
              </div>
            ))}
          </div>
        )}

        <button className="sheet-cancel" onClick={onClose}>Закрыть</button>
      </div>
    </div>
  );
}
