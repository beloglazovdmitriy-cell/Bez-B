import { useEffect, useState } from "react";
import { apiTradeComment, apiPublish, type Pf } from "../data";
import { IconAI, IconChannel } from "./Icons";

// Окно AI-разбора сделки: генерирует черновик поста, позволяет скопировать
// или опубликовать в канал.
export default function TradeCommentSheet({
  pf, id, onClose,
}: {
  pf: Pf; id: number; onClose: () => void;
}) {
  const [text, setText] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);
  const [note, setNote] = useState("");

  useEffect(() => {
    let alive = true;
    apiTradeComment(pf, id)
      .then((t) => alive && setText(t))
      .catch((e) => alive && setErr((e as Error).message))
      .finally(() => alive && setLoading(false));
    return () => { alive = false; };
  }, [pf, id]);

  async function copy() {
    try { await navigator.clipboard.writeText(text); setNote("Скопировано ✓"); }
    catch { setNote("Скопируй вручную"); }
  }
  async function publish() {
    setNote("Публикую…");
    try { await apiPublish(text); setNote("Опубликовано в канал ✓"); }
    catch (e) { setNote((e as Error).message); }
  }

  return (
    <div className="sheet-overlay" onClick={onClose}>
      <div className="sheet" onClick={(e) => e.stopPropagation()}>
        <div className="sheet-grip" />
        <div className="sheet-title"><IconAI size={20} /> Разбор сделки → в канал</div>

        {loading && <div className="muted-note">Готовлю черновик поста…</div>}
        {err && <div className="form-error">{err}</div>}
        {text && <div className="ai-text">{text}</div>}
        {note && <div className="muted-note" style={{ marginTop: 8 }}>{note}</div>}

        {text && (
          <>
            <button className="cta" onClick={publish}><IconChannel size={18} /> Опубликовать в канал</button>
            <button className="cta cta-ghost" style={{ marginTop: 8 }} onClick={copy}>Скопировать текст</button>
          </>
        )}
        <button className="sheet-cancel" onClick={onClose}>Закрыть</button>
      </div>
    </div>
  );
}
