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

const TABS: { id: Tab; icon: ComponentType<{ size?: number }>; label: string; adminOnly?: boolean }[] = [
  { id: "portfolio", icon: IconPortfolio, label: "Портфель" },
  { id: "trade", icon: IconTrade, label: "Сделки", adminOnly: true },
  { id: "chart", icon: IconChart, label: "Динамика" },
  { id: "journal", icon: IconJournal, label: "Журнал" },
  { id: "calc", icon: IconCalc, label: "Расчёт" },
  { id: "profile", icon: IconProfile, label: "Профиль" },
];

export default function BottomNav({
  active,
  onChange,
  isAdmin,
}: {
  active: Tab;
  onChange: (t: Tab) => void;
  isAdmin: boolean;
}) {
  const tabs = TABS.filter((t) => !t.adminOnly || isAdmin);
  return (
    <nav className="nav">
      {tabs.map((t) => {
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
