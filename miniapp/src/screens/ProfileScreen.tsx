import {
  IconCrown, IconLock, IconCheck, IconShare, IconChannel, IconChevron,
} from "../components/Icons";
import { mockUser } from "../mock";

type User = typeof mockUser;

const PREMIUM = [
  "Мгновенные пуш-уведомления о каждой сделке",
  "Машина времени — портфель на любую дату",
  "AI-разбор: твой портфель против Без Б",
  "Закрытый чат и еженедельные эфиры",
];

export default function ProfileScreen({ user }: { user: User }) {
  const u = user;
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

      {/* подписка */}
      <div className="card premium">
        <div className="premium-head">
          <span className="premium-title"><IconCrown size={20} /> Премиум «Без Б»</span>
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
        {!u.isPremium && (
          <button className="cta" style={{ marginTop: 14 }}>
            <IconCrown size={18} /> Оформить премиум · USDT
          </button>
        )}
      </div>

      {/* действия */}
      <div className="list">
        <button className="list-row">
          <span className="lr-ic accent"><IconShare size={18} /></span>
          <span>Поделиться результатом</span>
          <IconChevron size={18} className="lr-chev" />
        </button>
        <button className="list-row">
          <span className="lr-ic accent"><IconChannel size={18} /></span>
          <span>Подписаться на канал @BezBlogfin</span>
          <IconChevron size={18} className="lr-chev" />
        </button>
      </div>

      <div className="disclaimer">Не является индивидуальной инвестиционной рекомендацией.</div>
    </div>
  );
}
