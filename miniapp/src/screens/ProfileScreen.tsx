import { useState } from "react";
import {
  IconCrown, IconLock, IconCheck, IconShare, IconChannel, IconChevron, IconAI, Brand,
} from "../components/Icons";
import ContentStudio from "../components/ContentStudio";
import QaSheet from "../components/QaSheet";
import { apiSubscribe, apiUnsubscribe, apiPayInvoice } from "../data";
import { mockUser } from "../mock";

type User = typeof mockUser;

const CHANNEL = "BezBlogfin";   // @BezBlogfin
const BOT = "BezzBot_bot";      // t.me/BezzBot_bot

function tgOpen(url: string) {
  const tg = (window as any).Telegram?.WebApp;
  if (tg?.openTelegramLink) tg.openTelegramLink(url);
  else window.open(url, "_blank");
}
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
  const [subscribed, setSubscribed] = useState(!!(u as any).isSubscribed);
  const [subBusy, setSubBusy] = useState(false);
  const [payNote, setPayNote] = useState("");

  async function buyPremium() {
    setPayNote("");
    const tg = (window as any).Telegram?.WebApp;
    try {
      const { link } = await apiPayInvoice();
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

  async function toggleSub() {
    if (subBusy) return;
    const next = !subscribed;
    setSubBusy(true);
    setSubscribed(next);            // оптимистично
    try {
      const r = next ? await apiSubscribe() : await apiUnsubscribe();
      setSubscribed(r.isSubscribed);
    } catch {
      setSubscribed(!next);         // откат при ошибке
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

      {/* уведомления о сделках Без Б */}
      <div className="card sub-card" onClick={toggleSub}>
        <div className="sub-text">
          <div className="sub-title">🔔 Сделки Без Б — мгновенно</div>
          <div className="sub-sub">Пуш при каждой покупке/продаже, раньше канала</div>
        </div>
        <span className={"switch" + (subscribed ? " on" : "")} aria-hidden>
          <span className="knob" />
        </span>
      </div>

      {/* подписка */}
      <div className="card premium">
        <div className="premium-head">
          <span className="premium-title"><IconCrown size={20} /> Премиум <Brand size={16} /></span>
          <span className="premium-price">990 ₽/мес</span>
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
          <button className="cta" style={{ marginTop: 14 }} onClick={buyPremium}>
            <IconCrown size={18} /> Оформить премиум · 990 ₽
          </button>
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
      </div>

      <div className="disclaimer">Не является индивидуальной инвестиционной рекомендацией.</div>

      {studio && <ContentStudio onClose={() => setStudio(false)} />}
      {qa && <QaSheet isAdmin={u.isAdmin} onClose={() => setQa(false)} />}
    </div>
  );
}
