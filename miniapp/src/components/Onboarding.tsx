import { useEffect, useState } from "react";
import { apiOnboarding, apiOnboardingRead, type Onboarding as Ob } from "../data";

const LESSONS: { t: string; b: string }[] = [
  {
    t: "🎯 Зачем вообще инвестировать",
    b: "Деньги под подушкой дешевеют — инфляция тихо съедает их каждый год. "
      + "Инвестиции — это способ заставить капитал работать, а не таять. "
      + "Цель не «угадать иксы», а сохранить и медленно нарастить. Без буллшита: "
      + "богатеют не на одной сделке, а на годах дисциплины.",
  },
  {
    t: "🔁 DCA — регулярность важнее тайминга",
    b: "Никто не знает дно и пик. Поэтому вместо «поймать момент» — покупай по чуть-чуть "
      + "и регулярно (раз в 2 недели/месяц). Так ты усредняешь цену входа и убираешь "
      + "эмоции. Это и есть DCA. Скучно? Да. Работает на дистанции? Тоже да.",
  },
  {
    t: "⚖️ Риск и диверсификация",
    b: "Не клади всё в один актив — даже если «он точно вырастет». Один проект может "
      + "обнулиться, портфель из нескольких — нет. Размер позиции важнее, чем выбор актива: "
      + "вкладывай столько, чтобы спать спокойно при −50%.",
  },
  {
    t: "⏳ Сложный процент и время",
    b: "Главный союзник инвестора — время, а не сумма. Доход начинает приносить доход, "
      + "и кривая разгоняется. Поэтому $50 сегодня сильнее, чем $200 «когда-нибудь потом». "
      + "Промедление дороже ошибки в выборе актива.",
  },
  {
    t: "🧠 Психология: страх и жадность",
    b: "Толпа покупает на эйфории и продаёт на панике — и теряет. Твоё преимущество не в "
      + "инсайде, а в дисциплине: план важнее настроения рынка. Когда все жадничают — "
      + "осторожнее; когда в страхе — без паники. Это и есть «без буллшита».",
  },
];

export default function Onboarding() {
  const [ob, setOb] = useState<Ob | null>(null);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => { apiOnboarding().then(setOb).catch(() => setOb(null)); }, []);

  if (!ob || ob.anon || ob.finished) return null;

  const idx = Math.min(ob.done, LESSONS.length - 1);
  const lesson = LESSONS[idx];

  async function markRead() {
    if (busy) return;
    setBusy(true);
    try { setOb(await apiOnboardingRead()); setOpen(false); }
    catch { /* молча */ }
    finally { setBusy(false); }
  }

  return (
    <div className="card onb">
      <div className="onb-head">
        <span className="home-cap">Мини-курс · урок {ob.done + 1} из {ob.total}</span>
        <div className="onb-dots">
          {Array.from({ length: ob.total }).map((_, i) => (
            <span key={i} className={"onb-dot" + (i < ob.done ? " on" : "")} />
          ))}
        </div>
      </div>

      {ob.canRead ? (
        <>
          <div className="onb-title">{lesson.t}</div>
          {open && <div className="onb-body">{lesson.b}</div>}
          {open ? (
            <button className="cta onb-btn" onClick={markRead} disabled={busy}>
              Прочитал ✓
            </button>
          ) : (
            <button className="cta onb-btn" onClick={() => setOpen(true)}>
              Читать урок
            </button>
          )}
        </>
      ) : (
        <div className="onb-next">
          Сегодня урок пройден 🎉 Следующий — через {ob.nextInHours} ч.
        </div>
      )}
    </div>
  );
}
