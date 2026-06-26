import { useEffect, useState } from "react";
import {
  apiContentGenerate, apiContentDrafts, apiContentPublish, apiContentDelete,
  apiContentUpdate, apiContentCustom, apiContentPlan, apiZenGenerate, apiZenCustom,
  type Draft, type ContentPlan,
} from "../data";
import { IconAI, IconChannel } from "./Icons";

// Конвейер Дзена — статьи-лонгриды (публикуются копипастом в Дзен).
const ZEN: { kind: string; label: string }[] = [
  { kind: "zen_scam", label: "🚩 Разоблачение" },
  { kind: "zen_story", label: "🙋 Личный путь" },
  { kind: "zen_pain", label: "💸 Болевая тема" },
  { kind: "zen_explain", label: "📚 Объяснение" },
  { kind: "zen_mistakes", label: "⚠️ Ошибки новичка" },
];

// Типы картинки к посту в канал (одиночный выбор под тему).
const PIC_TYPES: { v: string; label: string }[] = [
  { v: "auto", label: "Авто" },
  { v: "ta", label: "📈 ТА BTC" },
  { v: "gauge", label: "🌡 Страх/жадность" },
  { v: "portfolio", label: "🥧 Портфель Без Б" },
  { v: "index", label: "📊 Индекс" },
  { v: "card", label: "🪙 Карточка" },
  { v: "analysis", label: "🤖 AI-разбор" },
  { v: "none", label: "🚫 Без картинки" },
];

interface ZenArt {
  title: string; body: string;
  titles?: string[]; cover?: string; tags?: string[]; question?: string;
}
function parseZen(text: string): ZenArt | null {
  try {
    const z = JSON.parse(text);
    if (z && typeof z.title === "string" && typeof z.body === "string") return z as ZenArt;
  } catch { /* не статья */ }
  return null;
}

// Превью поста как в Telegram: экранируем всё, возвращаем разрешённые теги, \n→<br>.
// Те же теги, что рендерит сервер при публикации (parse_mode=HTML).
const POST_TAGS = ["b", "strong", "i", "em", "u", "s", "code", "pre", "blockquote", "tg-spoiler"];
function renderPostHtml(text: string): string {
  let s = text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  for (const t of POST_TAGS) {
    s = s.split(`&lt;${t}&gt;`).join(`<${t}>`).split(`&lt;/${t}&gt;`).join(`</${t}>`);
  }
  return s.replace(/\n/g, "<br>");
}

// Ручная генерация ВНЕ плана. Экспертные (утро) — ценность/авторитет.
const EXPERT: { kind: string; label: string }[] = [
  { kind: "news", label: "📰 Новости" },
  { kind: "digest", label: "📊 Дайджест" },
  { kind: "crowd", label: "🌡 Разбор толпы" },
  { kind: "scenarios", label: "🔮 Сценарии" },
  { kind: "ta", label: "📐 Теханализ" },
  { kind: "edu", label: "📚 Ликбез" },
  { kind: "bullshit", label: "🚩 Детектор Б" },
  { kind: "psych", label: "🧠 Психология" },
  { kind: "case", label: "💡 Кейс" },
  { kind: "fun", label: "😄 Развлекательный" },
  { kind: "manifest", label: "🧭 Манифест" },
  { kind: "personal", label: "🙋 Личное" },
];
// Вовлечение (опросы) и продажа (низ воронки → премиум, со скрином/карточкой Mini App).
const ENGAGE: { kind: string; label: string }[] = [
  { kind: "poll_decision", label: "🗳 Что бы ты сделал?" },
  { kind: "poll_predict", label: "🗳 BTC выше/ниже?" },
  { kind: "poll_choose", label: "🗳 Что разобрать?" },
  { kind: "poll_mood", label: "🗳 Страшно/жадно?" },
  { kind: "promo_results", label: "🎯 Итоги + оффер" },
  { kind: "promo_underdog", label: "🎯 Нелюбимчик" },
  { kind: "promo_ai", label: "🎯 AI-разбор" },
  { kind: "promo_speed", label: "🎯 Скорость" },
  { kind: "promo_alert", label: "🎯 Алерты" },
  { kind: "promo_sandbox", label: "🎯 Песочница" },
];
const LABEL: Record<string, string> = {
  news: "📰 Новости", digest: "📊 Дайджест", ta: "📐 Теханализ", crowd: "🌡 Разбор толпы",
  scenarios: "🔮 Сценарии", edu: "📚 Ликбез", manifest: "🧭 Манифест",
  bullshit: "🚩 Детектор буллшита", psych: "🧠 Психология", case: "💡 Кейс",
  fun: "😄 Развлекательный", personal: "🙋 Личное", trade: "🧠 Сделка", custom: "✍️ Моя тема",
  poll: "🗳 Опрос",
  promo_results: "🎯 Промо · Итоги+оффер", promo_underdog: "🎯 Промо · Нелюбимчик",
  promo_ai: "🎯 Промо · AI-разбор", promo_speed: "🎯 Промо · Скорость",
  promo_alert: "🎯 Промо · Алерты", promo_sandbox: "🎯 Промо · Песочница",
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
  const [plan, setPlan] = useState<ContentPlan | null>(null);
  const [busy, setBusy] = useState("");        // kind генерации в работе
  const [note, setNote] = useState("");
  const [loading, setLoading] = useState(true);
  const [editId, setEditId] = useState<number | null>(null);  // id черновика в правке
  const [editText, setEditText] = useState("");
  const [topic, setTopic] = useState("");                     // своя тема/задача
  const [showManual, setShowManual] = useState(false);        // блок ручной генерации свёрнут
  const [showZen, setShowZen] = useState(false);              // конвейер Дзена свёрнут
  const [zenTopic, setZenTopic] = useState("");               // своя тема статьи Дзена
  const [copied, setCopied] = useState("");                   // что скопировано (фидбэк)
  const [picType, setPicType] = useState<Record<number, string>>({});
  const [noCta, setNoCta] = useState<Record<number, boolean>>({});
  const [imgs, setImgs] = useState<Record<number, File | null>>({});

  function refresh() {
    apiContentDrafts().then(setDrafts).catch((e) => setNote((e as Error).message))
      .finally(() => setLoading(false));
  }
  useEffect(() => {
    refresh();
    apiContentPlan().then(setPlan).catch(() => { /* план не критичен */ });
    /* eslint-disable-next-line */
  }, []);

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
        cta: !noCta[id], pic: picType[id] || "auto", image: imgs[id] || null,
      });
      setNote("Опубликовано в канал ✓"); refresh();
    } catch (e) { setNote((e as Error).message); }
  }
  async function genZen(kind: string) {
    setBusy(kind); setNote("");
    try { await apiZenGenerate(kind); refresh(); }
    catch (e) { setNote((e as Error).message); }
    finally { setBusy(""); }
  }
  async function genZenCustom() {
    const t = zenTopic.trim();
    if (!t) { setNote("Опиши тему статьи"); return; }
    setBusy("zen_custom"); setNote("");
    try { await apiZenCustom(t); setZenTopic(""); refresh(); }
    catch (e) { setNote((e as Error).message); }
    finally { setBusy(""); }
  }
  async function copyText(text: string, what: string) {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(what); setTimeout(() => setCopied(""), 1500);
    } catch { setNote("Не удалось скопировать"); }
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

        {/* ── Недельный план: что бот готовит сам ── */}
        {plan && (
          <>
            <div className="field-label">План на неделю · бот готовит сам</div>
            <div className="muted-note" style={{ marginBottom: 8 }}>
              Каждый день бот делает 2 черновика (утро {plan.morningHour}:00, вечер{" "}
              {plan.eveningHour}:00 МСК) и пингует тебя в ЛС. В канал публикуешь ты — ниже.
            </div>
            <div className="plan-grid" style={{ marginBottom: 14 }}>
              {plan.days.map((d) => (
                <div key={d.day} className={"plan-row" + (d.isToday ? " today" : "")}>
                  <div className="plan-dow">{d.dow}{d.isToday ? " ·" : ""}</div>
                  <div className="plan-slot">🌅 {d.morning.label}</div>
                  <div className="plan-slot">🌆 {d.evening.label}</div>
                </div>
              ))}
            </div>
          </>
        )}

        {note && <div className="muted-note" style={{ marginBottom: 8 }}>{note}</div>}

        {/* ── Черновики на публикацию (главное действие) ── */}
        <div className="field-label">Черновики на публикацию</div>
        {loading ? (
          <div className="muted-note">Загружаю…</div>
        ) : drafts.filter((d) => d.kind !== "zen").length === 0 ? (
          <div className="muted-note">
            Пусто. Бот подготовит по плану — или сделай внеплановый пост ниже.
          </div>
        ) : (
          <div className="feed">
            {drafts.filter((d) => d.kind !== "zen").map((d) => (
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
                      ) : <div className="ai-text draft-text"
                            dangerouslySetInnerHTML={{ __html: renderPostHtml(d.text) }} />;
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
                    <div className="ai-text draft-text"
                      dangerouslySetInnerHTML={{ __html: renderPostHtml(d.text) }} />
                    <div className="muted-note" style={{ margin: "2px 0 4px" }}>Картинка:</div>
                    <div className="chips" style={{ marginBottom: 8 }}>
                      {PIC_TYPES.map((p) => (
                        <button key={p.v}
                          className={"chip" + ((picType[d.id] || "auto") === p.v ? " on" : "")}
                          disabled={!!imgs[d.id]}
                          onClick={() => setPicType({ ...picType, [d.id]: p.v })}>
                          {p.label}
                        </button>
                      ))}
                    </div>
                    <div className="pub-opts">
                      <label className="pub-opt">
                        <input type="checkbox" checked={!noCta[d.id]}
                          onChange={(e) => setNoCta({ ...noCta, [d.id]: !e.target.checked })} />
                        🔗 Кнопка бота
                      </label>
                      <label className="pub-opt file">
                        🖼 {imgs[d.id] ? "Своя картинка ✓ (заменяет тип)" : "Своя картинка"}
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

        {/* ── Внеплановый пост (ручная генерация, свёрнуто) ── */}
        <button className="chip" style={{ width: "100%", marginTop: 14, marginBottom: 8 }}
          onClick={() => setShowManual((v) => !v)}>
          {showManual ? "▲ Скрыть внеплановый пост" : "➕ Сделать внеплановый пост"}
        </button>
        {showManual && (
          <>
            <div className="muted-note" style={{ marginBottom: 8 }}>
              Это не нужно для плана выше — только если хочешь дополнительный пост вне расписания.
            </div>
            <div className="field-label">Экспертные (ценность)</div>
            <div className="chips" style={{ marginBottom: 10 }}>
              {EXPERT.map((r) => (
                <button key={r.kind} className="chip" disabled={!!busy}
                  onClick={() => generate(r.kind)}>
                  {busy === r.kind ? "…" : r.label}
                </button>
              ))}
            </div>
            <div className="field-label">Опросы и продажа</div>
            <div className="chips" style={{ marginBottom: 10 }}>
              {ENGAGE.map((r) => (
                <button key={r.kind} className="chip" disabled={!!busy}
                  onClick={() => generate(r.kind)}>
                  {busy === r.kind ? "…" : r.label}
                </button>
              ))}
            </div>
            <div className="field-label">Своя тема / задача</div>
            <textarea className="draft-edit" rows={3} value={topic}
              placeholder="Напр.: объясни, почему DCA спасает новичков от паники"
              onChange={(e) => setTopic(e.target.value)} style={{ minHeight: 70 }} />
            <button className="cta" disabled={!!busy} onClick={generateCustom}
              style={{ marginTop: 8 }}>
              <IconAI size={16} /> {busy === "custom" ? "Создаю…" : "Создать по моей теме"}
            </button>
          </>
        )}

        {/* ── Конвейер Дзена: статьи-лонгриды (копипаст в Дзен) ── */}
        <button className="chip" style={{ width: "100%", marginTop: 14, marginBottom: 8 }}
          onClick={() => setShowZen((v) => !v)}>
          {showZen ? "▲ Скрыть Дзен-статьи" : "📝 Дзен-статьи (лонгриды)"}
        </button>
        {showZen && (
          <>
            <div className="muted-note" style={{ marginBottom: 8 }}>
              AI пишет статью под Дзен (заголовок + текст на дочитывания + мягкий призыв в канал).
              Сгенерируй → скопируй → вставь в редактор Дзена.
            </div>
            {plan && plan.zen && plan.zen.length > 0 && (
              <>
                <div className="field-label">План Дзена · бот готовит сам</div>
                <div className="muted-note" style={{ marginBottom: 8 }}>
                  Каждый день в {plan.zenHour}:00 МСК бот делает 1 статью-черновик и пингует
                  тебя в ЛС. Публикуешь копипастом в Дзен — статьи ниже.
                </div>
                <div className="plan-grid" style={{ marginBottom: 12 }}>
                  {plan.zen.map((z) => (
                    <div key={z.day} className={"plan-row" + (z.isToday ? " today" : "")}>
                      <div className="plan-dow">{z.dow}{z.isToday ? " ·" : ""}</div>
                      <div className="plan-slot">📝 {z.label}</div>
                    </div>
                  ))}
                </div>
              </>
            )}
            <div className="field-label">Сделать статью сейчас · рубрика</div>
            <div className="chips" style={{ marginBottom: 10 }}>
              {ZEN.map((r) => (
                <button key={r.kind} className="chip" disabled={!!busy}
                  onClick={() => genZen(r.kind)}>
                  {busy === r.kind ? "…" : r.label}
                </button>
              ))}
            </div>
            <div className="field-label">Своя тема статьи</div>
            <textarea className="draft-edit" rows={3} value={zenTopic}
              placeholder="Напр.: как я считаю риск по портфелю и почему не верю прогнозам"
              onChange={(e) => setZenTopic(e.target.value)} style={{ minHeight: 70 }} />
            <button className="cta" disabled={!!busy} onClick={genZenCustom}
              style={{ marginTop: 8, marginBottom: 8 }}>
              <IconAI size={16} /> {busy === "zen_custom" ? "Пишу статью…" : "Написать статью по теме"}
            </button>

            {drafts.filter((d) => d.kind === "zen").length > 0 && (
              <>
                <div className="field-label">Готовые статьи</div>
                <div className="feed">
                  {drafts.filter((d) => d.kind === "zen").map((d) => {
                    const z = parseZen(d.text);
                    if (!z) return null;
                    return (
                      <div className="card draft" key={d.id}>
                        <div className="muted-note">Заголовки (выбери лучший):</div>
                        {(z.titles && z.titles.length ? z.titles : [z.title]).map((t, i) => (
                          <div className="zen-title-row" key={i}>
                            <span className="zen-title">{t}</span>
                            <button className="chip" onClick={() => copyText(t, `t${d.id}_${i}`)}>
                              {copied === `t${d.id}_${i}` ? "✓" : "📋"}
                            </button>
                          </div>
                        ))}
                        {z.cover && (
                          <div className="zen-meta">🖼 Обложка: <b>{z.cover}</b>
                            <button className="chip" onClick={() => copyText(z.cover!, `c${d.id}`)}>
                              {copied === `c${d.id}` ? "✓" : "📋"}
                            </button>
                          </div>
                        )}
                        {z.tags && z.tags.length > 0 && (
                          <div className="zen-meta">🏷 Теги: {z.tags.join(", ")}
                            <button className="chip" onClick={() => copyText(z.tags!.join(", "), `g${d.id}`)}>
                              {copied === `g${d.id}` ? "✓" : "📋"}
                            </button>
                          </div>
                        )}
                        {z.question && <div className="zen-meta">💬 Вопрос: {z.question}</div>}
                        <div className="ai-text draft-text zen-body">{z.body}</div>
                        <div className="draft-actions">
                          <button className="cta" onClick={() => copyText(z.body, `b${d.id}`)}>
                            {copied === `b${d.id}` ? "Скопировано ✓" : "📋 Текст статьи"}
                          </button>
                          <button className="chip" onClick={() => remove(d.id)}>Удалить</button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </>
            )}
          </>
        )}

        <button className="sheet-cancel" onClick={onClose}>Закрыть</button>
      </div>
    </div>
  );
}
