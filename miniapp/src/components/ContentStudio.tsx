import { useState } from "react";
import { apiContentPublishDirect } from "../data";
import { IconChannel } from "./Icons";

// Превью Telegram HTML. Разрешаем тот же небольшой набор тегов, что и API.
const POST_TAGS = [
  "b", "strong", "i", "em", "u", "s", "code", "pre", "blockquote", "tg-spoiler",
];

function renderPostHtml(text: string): string {
  let result = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
  for (const tag of POST_TAGS) {
    result = result
      .split(`&lt;${tag}&gt;`).join(`<${tag}>`)
      .split(`&lt;/${tag}&gt;`).join(`</${tag}>`);
  }
  return result.replace(/\n/g, "<br>");
}

export default function ContentStudio({ onClose }: { onClose: () => void }) {
  const [text, setText] = useState("");
  const [image, setImage] = useState<File | null>(null);
  const [cta, setCta] = useState(true);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");

  async function publish() {
    const body = text.trim();
    if (!body) {
      setNote("Вставьте готовый текст публикации");
      return;
    }
    if (body.length > 4096) {
      setNote("Текст длиннее лимита Telegram — 4096 символов");
      return;
    }

    setBusy(true);
    setNote("Публикую…");
    try {
      await apiContentPublishDirect(body, { cta, image });
      setText("");
      setImage(null);
      setNote("Опубликовано в канал ✓");
    } catch (error) {
      setNote((error as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="sheet-overlay" onClick={onClose}>
      <div className="sheet" onClick={(event) => event.stopPropagation()}>
        <div className="sheet-grip" />
        <div className="sheet-title">
          <IconChannel size={20} /> Редактор публикации
        </div>

        <div className="muted-note" style={{ marginBottom: 12 }}>
          Вставьте согласованный текст от помощника. Здесь нет AI-генерации,
          очереди и автоматических картинок — AI-токены не расходуются.
        </div>

        <div className="field-label">Текст поста</div>
        <textarea
          className="draft-edit"
          rows={12}
          value={text}
          placeholder="Вставьте готовый текст…"
          onChange={(event) => {
            setText(event.target.value);
            setNote("");
          }}
          style={{ minHeight: 210 }}
        />
        <div className="muted-note" style={{ textAlign: "right", marginTop: 4 }}>
          {text.length} / 4096
        </div>

        {text.trim() && (
          <>
            <div className="field-label" style={{ marginTop: 12 }}>Предпросмотр</div>
            <div className="card draft">
              <div
                className="ai-text draft-text"
                dangerouslySetInnerHTML={{ __html: renderPostHtml(text.trim()) }}
              />
            </div>
          </>
        )}

        <div className="field-label" style={{ marginTop: 12 }}>Оформление</div>
        <div className="pub-opts">
          <label className="pub-opt">
            <input
              type="checkbox"
              checked={cta}
              onChange={(event) => setCta(event.target.checked)}
            />
            📊 Кнопка «Портфель и все сделки»
          </label>
          <label className="pub-opt file">
            🖼 {image ? `Своя картинка: ${image.name}` : "Приложить свою картинку"}
            <input
              type="file"
              accept="image/*"
              hidden
              onChange={(event) => {
                setImage(event.target.files?.[0] || null);
                setNote("");
              }}
            />
          </label>
        </div>

        {image && (
          <button className="chip" onClick={() => setImage(null)} style={{ marginTop: 8 }}>
            Убрать картинку
          </button>
        )}

        {note && <div className="muted-note" style={{ marginTop: 12 }}>{note}</div>}

        <button
          className="cta"
          disabled={busy || !text.trim()}
          onClick={publish}
          style={{ width: "100%", marginTop: 14 }}
        >
          <IconChannel size={16} /> {busy ? "Публикую…" : "Опубликовать сейчас"}
        </button>

        <button className="sheet-cancel" onClick={onClose}>Закрыть</button>
      </div>
    </div>
  );
}
