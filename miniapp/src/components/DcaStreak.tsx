import { useEffect, useState } from "react";
import { apiDca, apiDcaCheckin, type Dca } from "../data";

const BADGES = [
  { n: 1, ic: "🌱", label: "Старт" },
  { n: 3, ic: "💪", label: "Втянулся" },
  { n: 6, ic: "🔥", label: "3 месяца" },
  { n: 13, ic: "🏆", label: "Полгода" },
  { n: 26, ic: "👑", label: "Год" },
];

function plural(n: number, one: string, few: string, many: string): string {
  const m10 = n % 10, m100 = n % 100;
  if (m10 === 1 && m100 !== 11) return one;
  if (m10 >= 2 && m10 <= 4 && (m100 < 10 || m100 >= 20)) return few;
  return many;
}

function haptic(type: "light" | "success") {
  const h = (window as any).Telegram?.WebApp?.HapticFeedback;
  if (!h) return;
  if (type === "success") h.notificationOccurred?.("success");
  else h.impactOccurred?.("light");
}

export default function DcaStreak() {
  const [d, setD] = useState<Dca | null>(null);
  const [busy, setBusy] = useState(false);
  const [flash, setFlash] = useState("");

  useEffect(() => { apiDca().then(setD).catch(() => setD(null)); }, []);

  if (!d || d.anon) return null;

  async function checkIn() {
    if (busy || !d!.canCheckIn) return;
    setBusy(true);
    try {
      const r = await apiDcaCheckin();
      setD(r);
      if (r.result === "reset") setFlash("Серия прервалась — начинаем заново 🌱");
      else if (r.result === "started") setFlash("Первый взнос — серия пошла! 🔥");
      else setFlash(`+1 к серии — так держать! 🔥`);
      haptic("success");
      setTimeout(() => setFlash(""), 3500);
    } catch {
      /* молча */
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card dca">
      <div className="dca-top">
        <div className="dca-streak">
          <span className="dca-fire">🔥</span>
          <span className="dca-num">{d.streak}</span>
        </div>
        <div className="dca-meta">
          <div className="home-cap">Дисциплина DCA</div>
          <div className="dca-line">
            {d.streak > 0
              ? `${d.streak} ${plural(d.streak, "взнос", "взноса", "взносов")} подряд`
              : "Отмечай взнос раз в 2 недели"}
          </div>
          <div className="dca-sub">
            рекорд {d.longest} · всего {d.total}
          </div>
        </div>
      </div>

      <div className="dca-badges">
        {BADGES.map((b) => (
          <span key={b.n} className={"dca-badge" + (d.longest >= b.n ? " earned" : "")}
            title={b.label}>{b.ic}</span>
        ))}
      </div>

      {flash && <div className="dca-flash">{flash}</div>}

      {d.canCheckIn ? (
        <button className="cta dca-btn" onClick={checkIn} disabled={busy}>
          ✅ Я внёс взнос
        </button>
      ) : (
        <div className="dca-next">
          Следующий взнос через {d.nextInDays} {plural(d.nextInDays, "день", "дня", "дней")}
        </div>
      )}
    </div>
  );
}
