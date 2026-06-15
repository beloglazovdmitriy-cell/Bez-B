import type { ComponentType } from "react";
import {
  IconFeed,
  IconPortfolio,
  IconProfile,
  IconCalc,
} from "./Icons";

export type Tab = "feed" | "game" | "portfolio" | "calc" | "profile";

const IconGame = ({ size = 22 }: { size?: number }) => (
  <span style={{ fontSize: size, lineHeight: 1 }}>🎮</span>
);

const TABS: { id: Tab; icon: ComponentType<{ size?: number }>; label: string }[] = [
  { id: "feed", icon: IconFeed, label: "Лента" },
  { id: "game", icon: IconGame, label: "Игра" },
  { id: "portfolio", icon: IconPortfolio, label: "Без Б" },
  { id: "calc", icon: IconCalc, label: "Расчёт" },
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
