import { useState, useEffect } from "react";
import {
  IconCrown, IconLock, IconCheck, IconShare, IconChannel, IconChevron, IconAI, Brand,
} from "../components/Icons";
import ContentStudio from "../components/ContentStudio";
import QaSheet from "../components/QaSheet";
import QuizSheet from "../components/QuizSheet";
import AboutSheet from "../components/AboutSheet";
import Onboarding from "../components/Onboarding";
import { apiSubscribe, apiUnsubscribe, apiPayInvoice, apiPayConfig, payCloudPayments, apiReferral } from "../data";
import { mockUser } from "../mock";

type User = typeof mockUser;

const CHANNEL = "BezBlogfin";   // @BezBlogfin
const BOT = "BezzBot_bot";      // t.me/BezzBot_bot

function tgOpen(url: string) {
  const tg = (window as any).Telegram?.WebApp;
  if (tg?.openTelegramLink) tg.openTelegramLink(url);
  else window.open(url, "_blank");
}
function openExt(url: string) {
  const tg = (window as any).Telegram?.WebApp;
  if (tg?.openLink) tg.openLink(url);
  else window.open(url, "_blank");
}
const DOC_BASE = (typeof location !== "undefined" ? location.origin : "") + "/landing";
function openChannel() {
  tgOpen(`https://t.me/${CHANNEL}`);
}
function shareResult() {
  const text =
    "Слежу за публичным портфелём «Без Б» — инвестиции без буллшита, всё открыто 📈";
  const url = `https://t.me/${BOT}`;
  tgOpen(`https://t.me/share/url?url=${encodeURIComponent(url)}&text=${encodeURIComponent(text)}`);
}

const PREMIUM = [
  "Мгновенные пуш-уведомления о каждой сделке",
  "Машина времени — портфель на любую дату",
  "AI-разбор: твой портфель против Без Б",
  "Закрытый чат и еженедельные эфиры",
];

export default function ProfileScreen({ user }: { user: User }) {
  const u = user;
  const [studio, setStudio] = useState(false);
  const [qa, setQa] = useState(false);
  const [quiz, setQuiz] = useState(false);
  const [about, setAbout] = useState(false);
  const [subscribed, setSubscribed] = useState(!!(u as any).isSubscribed);
  const [subBusy, setSubBusy] = useState(false);
  const [payNote, setPayNote] = useState("");
  const [consent, setConsent] = useState(false);
  const [refInfo, setRefInfo] = useState<{ link: string; count: number; days: number } | null>(null);
  useEffect(() => { apiReferral().then(setRefInfo).catch(() => {}); }, []);

  function inviteFriend() {
    if (!refInfo) return;
    const text = "Инвестирую без буллшита в «Без Б» — публичный портфель, AI-разбор и игра «Инвестор с нуля». Залетай 🚀";
    const url = `https://t.me/share/url?url=${encodeURIComponent(refInfo.link)}&text=${encodeURIComponent(text)}`;
    tgOpen(url);
  }

  async function buyPremium() {
    if (!consent) { setPayNote("Поставь галочку согласия, чтобы продолжить."); return; }
    setPayNote("");
    const tg = (window as any).Telegram?.WebApp;
    try {
      const cfg = await apiPayConfig();
      if (cfg.provider === "cloudpayments") {
        // Виджет CloudPayments прямо в Mini App (удобнее пользователю). 3DS показывается
        // в оверлее виджета. Skin не "mini", чтобы окну ввода кода из СМС хватало места.
        await payCloudPayments(cfg, {
          onSuccess: () => setPayNote("Оплачено ✓ Премиум активируется. Переоткрой приложение."),
          onFail: (r) => setPayNote(r ? `Платёж не прошёл: ${r}` : "Платёж не прошёл. Попробуй ещё раз."),
        });
        return;
      }
      if (cfg.provider === "none") { setPayNote("Оплата скоро будет подключена."); return; }
      const { link } = await apiPayInvoice();   // telegram-инвойс
      if (tg?.openInvoice) {
        tg.openInvoice(link, (status: string) => {
          if (status === "paid") setPayNote("Оплачено ✓ Премиум активируется. Переоткрой приложение.");
          else if (status === "failed") setPayNote("Платёж не прошёл. Попробуй ещё раз.");
        });
      } else {
        window.open(link, "_blank");
      }
    } catch (e) {
      setPayNote((e as Error).message);
    }
  }

  const [subNote, setSubNote] = useState("");

  async function toggleSub() {
    if (subBusy) return;
    if (!u.isPremium && !subscribed) {     // включить пуши можно только в премиуме
      setSubNote("Мгновенные пуши о сделках — в премиуме 👇");
      return;
    }
    const next = !subscribed;
    setSubBusy(true); setSubNote("");
    setSubscribed(next);            // оптимистично
    try {
      const r = next ? await apiSubscribe() : await apiUnsubscribe();
      setSubscribed(r.isSubscribed);
    } catch (e) {
      setSubscribed(!next);         // откат при ошибке
      setSubNote((e as Error).message);
    } finally {
      setSubBusy(false);
    }
  }

  return (
    <div className="content">
      {/* профиль */}
      <div className="card profile-card">
        <div className="avatar">{u.name[0]}</div>
        <div>
          <div className="profile-name">{u.name}</div>
          <div className="profile-role">
            {u.isAdmin ? "Владелец портфеля" : u.isPremium ? "Премиум-подписчик" : "Бесплатный доступ"}
          </div>
        </div>
      </div>

      {/* мини-курс (онбординг) — самоскрывается после прохождения */}
      <Onboarding />

      {/* уведомления о сделках Без Б (премиум) */}
      <div className="card sub-card" onClick={toggleSub}>
        <div className="sub-text">
          <div className="sub-title">🔔 Сделки Без Б — мгновенно
            {!u.isPremium && <span className="prem-tag">премиум</span>}</div>
          <div className="sub-sub">Пуш при каждой покупке/продаже, раньше канала</div>
        </div>
        <span className={"switch" + (subscribed ? " on" : "")} aria-hidden>
          <span className="knob" />
        </span>
      </div>
      {subNote && <div className="muted-note" style={{ marginTop: -4, marginBottom: 4 }}>{subNote}</div>}

      {/* подписка */}
      <div className="card premium">
        <div className="premium-head">
          <span className="premium-title"><IconCrown size={20} /> Премиум <Brand size={16} /></span>
          <span className="premium-price">{(u as any).premiumPrice ?? 990} ₽/мес</span>
        </div>
        <div className="premium-list">
          {PREMIUM.map((f, i) => (
            <div className="premium-item" key={i}>
              <span className="pi-ic">
                {u.isPremium ? <IconCheck size={16} /> : <IconLock size={15} />}
              </span>
              {f}
            </div>
          ))}
        </div>
        {u.isPremium ? (
          <div className="premium-active">
            ✓ Премиум активен{(u as any).premiumUntil
              ? ` до ${new Date((u as any).premiumUntil * 1000).toLocaleDateString("ru-RU")}`
              : ""}
          </div>
        ) : (
          <>
            {(u as any).premiumEarlyBird && (
              <div className="eb-note">🐦 Early-bird: {(u as any).premiumPrice} ₽ навсегда · осталось {(u as any).earlyBirdLeft} мест</div>
            )}
            <label className="consent" style={{ marginTop: 14 }}>
              <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
              <span>Принимаю условия{" "}
                <a onClick={(e) => { e.preventDefault(); openExt(`${DOC_BASE}/offer.html`); }}>оферты</a>{" "}
                и даю{" "}
                <a onClick={(e) => { e.preventDefault(); openExt(`${DOC_BASE}/privacy.html`); }}>
                  согласие на обработку персональных данных</a> (152-ФЗ).</span>
            </label>
            <button className="cta" style={{ marginTop: 12 }} onClick={buyPremium} disabled={!consent}>
              <IconCrown size={18} /> Оформить премиум · {(u as any).premiumPrice ?? 990} ₽
            </button>
          </>
        )}
        {payNote && <div className="muted-note" style={{ marginTop: 10 }}>{payNote}</div>}
      </div>

      {/* инструменты автора */}
      {u.isAdmin && (
        <button className="cta cta-ai" onClick={() => setStudio(true)}>
          <IconAI size={18} /> Контент-студия
        </button>
      )}

      {/* действия */}
      <div className="list">
        <button className="list-row" onClick={() => setQa(true)}>
          <span className="lr-ic accent"><IconAI size={18} /></span>
          <span>Задать вопрос {u.isAdmin ? "· ответить" : "(AI / автор)"}</span>
          <IconChevron size={18} className="lr-chev" />
        </button>
        <button className="list-row" onClick={() => setQuiz(true)}>
          <span className="lr-ic accent">🚩</span>
          <span>Квиз «Детектор буллшита»</span>
          <IconChevron size={18} className="lr-chev" />
        </button>
        <button className="list-row" onClick={inviteFriend}>
          <span className="lr-ic accent">👥</span>
          <span>Пригласить друга{refInfo && refInfo.count > 0 ? ` · ${refInfo.count} 🎉` : ` · +${refInfo?.days ?? 3} дня премиума`}</span>
          <IconChevron size={18} className="lr-chev" />
        </button>
        <button className="list-row" onClick={shareResult}>
          <span className="lr-ic accent"><IconShare size={18} /></span>
          <span>Поделиться результатом</span>
          <IconChevron size={18} className="lr-chev" />
        </button>
        <button className="list-row" onClick={openChannel}>
          <span className="lr-ic accent"><IconChannel size={18} /></span>
          <span>Подписаться на канал <Brand size={14} /></span>
          <IconChevron size={18} className="lr-chev" />
        </button>
        <button className="list-row" onClick={() => setAbout(true)}>
          <span className="lr-ic accent">📜</span>
          <span>О проекте · манифест</span>
          <IconChevron size={18} className="lr-chev" />
        </button>
      </div>

      <div className="disclaimer">Не является индивидуальной инвестиционной рекомендацией.</div>

      {studio && <ContentStudio onClose={() => setStudio(false)} />}
      {qa && <QaSheet isAdmin={u.isAdmin} onClose={() => setQa(false)} />}
      {quiz && <QuizSheet onClose={() => setQuiz(false)} />}
      {about && <AboutSheet onClose={() => setAbout(false)} />}
    </div>
  );
}
