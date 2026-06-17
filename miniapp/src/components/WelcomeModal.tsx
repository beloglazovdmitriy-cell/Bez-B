import { IconLogo } from "./Icons";

// Приветственное окно при первом открытии (флаг в localStorage).
export default function WelcomeModal({ onClose }: { onClose: () => void }) {
  return (
    <div className="sheet-overlay welcome-overlay" onClick={onClose}>
      <div className="welcome" onClick={(e) => e.stopPropagation()}>
        <div className="welcome-logo">
          Bez <IconLogo size={32} className="brand-btc" />
        </div>
        <div className="welcome-head">Инвестиции — это просто</div>

        <div className="manifesto">
          <div><b>Без</b> обещаний иксов</div>
          <div><b>Без</b> сделок задним числом</div>
          <div><b>Без</b> буллшита — только реальные действия</div>
        </div>

        <p className="welcome-text">
          Я веду публичный портфель для тебя — чтобы показать на живом примере,
          что инвестировать просто и по силам каждому. Каждый шаг открыт: покупки,
          продажи, ошибки и результат в ₽ и $. А ты можешь следить, считать свой
          план и повторять стратегию под свой капитал.
        </p>

        <button className="cta" onClick={onClose}>Начать</button>
        <div className="welcome-foot">Не является индивидуальной инвестиционной рекомендацией.</div>
      </div>
    </div>
  );
}
