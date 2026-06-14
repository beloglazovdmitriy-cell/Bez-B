import type { Pf } from "../data";
import { Brand, IconProfile } from "./Icons";

// Переключатель «Без Б / Мой портфель». Влияет на все экраны портфеля.
export default function PortfolioSwitcher({ pf, onChange }: { pf: Pf; onChange: (p: Pf) => void }) {
  return (
    <div className="pf-switch">
      <button className={`pf-btn ${pf === "bezb" ? "on" : ""}`} onClick={() => onChange("bezb")}>
        <Brand size={16} />
      </button>
      <button className={`pf-btn ${pf === "me" ? "on" : ""}`} onClick={() => onChange("me")}>
        <IconProfile size={16} /> Мой
      </button>
      <button className={`pf-btn ${pf === "fantasy" ? "on" : ""}`} onClick={() => onChange("fantasy")}>
        🏆 Фэнтези
      </button>
    </div>
  );
}
