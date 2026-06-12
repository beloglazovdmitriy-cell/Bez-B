import { IconBitcoin } from "./Icons";

// Приветственное окно при первом открытии (флаг в localStorage).
export default function WelcomeModal({ onClose }: { onClose: () => void }) {
  return (
    <div className="sheet-overlay welcome-overlay" onClick={onClose}>
      <div className="welcome" onClick={(e) => e.stopPropagation()}>
        <div className="welcome-logo">
          Bez <IconBitcoin size={30} className="brand-btc" />
        </div>
        <div className="welcome-sub">инвестиции без буллшита</div>

        <p className="welcome-text">
          Привет! Я веду инвестпортфель <b>публично и в реальном времени</b> —
          каждая сделка открыто, с причиной, без задним числом. Никаких обещаний
          «иксов», только честные результаты и ошибки.
        </p>

        <div className="welcome-list">
          <div><b>📊 Портфель</b> — баланс и доходность в ₽ и $</div>
          <div><b>📈 Динамика</b> — рост капитала и сравнение с рынком</div>
          <div><b>📔 Журнал</b> — все сделки с причинами</div>
          <div><b>🧮 Расчёт</b> — как создаётся капитал, если начать сейчас</div>
        </div>

        <button className="cta" onClick={onClose}>Поехали</button>
        <div className="welcome-foot">Не является индивидуальной инвестиционной рекомендацией.</div>
      </div>
    </div>
  );
}
