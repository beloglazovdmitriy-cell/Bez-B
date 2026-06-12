import { useEffect, useState, type ReactNode } from "react";
import { apiPublish } from "../data";
import { IconChannel } from "./Icons";

// Универсальное окно AI-текста: грузит текст через load(), показывает; если
// publishable — добавляет кнопки «Опубликовать в канал» и «Скопировать».
export default function AiSheet({
  title, load, publishable = false, onClose,
}: {
  title: ReactNode;
  load: () => Promise<string>;
  publishable?: boolean;
  onClose: () => void;
}) {
  const [text, setText] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);
  const [note, setNote] = useState("");

  useEffect(() => {
    let alive = true;
    load()
      .then((t) => alive && setText(t))
      .catch((e) => alive && setErr((e as Error).message))
      .finally(() => alive && setLoading(false));
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
        <div className="sheet-title">{title}</div>

        {loading && <div className="muted-note">Думаю…</div>}
        {err && <div className="form-error">{err}</div>}
        {text && <div className="ai-text">{text}</div>}
        {note && <div className="muted-note" style={{ marginTop: 8 }}>{note}</div>}

        {text && publishable && (
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
