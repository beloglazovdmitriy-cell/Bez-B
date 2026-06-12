import type { Pf } from "../data";
import { IconLogo, IconProfile } from "./Icons";

// Переключатель «Без Б / Мой портфель». Влияет на все экраны портфеля.
export default function PortfolioSwitcher({ pf, onChange }: { pf: Pf; onChange: (p: Pf) => void }) {
  return (
    <div className="pf-switch">
      <button className={`pf-btn ${pf === "bezb" ? "on" : ""}`} onClick={() => onChange("bezb")}>
        <IconLogo size={18} /> Без Б
      </button>
      <button className={`pf-btn ${pf === "me" ? "on" : ""}`} onClick={() => onChange("me")}>
        <IconProfile size={16} /> Мой портфель
      </button>
    </div>
  );
}
