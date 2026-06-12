import type { ComponentType } from "react";
import {
  IconPortfolio,
  IconChart,
  IconJournal,
  IconTrade,
  IconProfile,
  IconCalc,
} from "./Icons";

export type Tab = "portfolio" | "chart" | "journal" | "calc" | "trade" | "profile";

const TABS: { id: Tab; icon: ComponentType<{ size?: number }>; label: string }[] = [
  { id: "portfolio", icon: IconPortfolio, label: "Портфель" },
  { id: "chart", icon: IconChart, label: "Динамика" },
  { id: "journal", icon: IconJournal, label: "Журнал" },
  { id: "calc", icon: IconCalc, label: "Расчёт" },
  { id: "trade", icon: IconTrade, label: "Сделки" },
  { id: "profile", icon: IconProfile, label: "Профиль" },
];

export default function BottomNav({
  active,
  onChange,
}: {
  active: Tab;
  onChange: (t: Tab) => void;
}) {
  return (
    <nav className="nav">
      {TABS.map((t) => {
        const Icon = t.icon;
        return (
          <button
            key={t.id}
            className={`tab ${active === t.id ? "active" : ""}`}
            onClick={() => onChange(t.id)}
          >
            <span className="ic">
              <Icon size={22} />
            </span>
            <span>{t.label}</span>
          </button>
        );
      })}
    </nav>
  );
}
