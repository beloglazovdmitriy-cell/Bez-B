import type { Summary } from "../mock";

// Лёгкий SVG-donut без сторонних библиотек (для прототипа).
// На Этапе 2 заменим на интерактивный график.
export default function CompositionDonut({ s }: { s: Summary }) {
  const slices = [
    ...s.positions.map((p) => ({ label: p.ticker, value: p.valueUsd, color: p.color })),
    { label: "USDT (кэш)", value: s.cashUsdt, color: "#5a6472" },
  ].filter((x) => x.value > 0);

  const total = slices.reduce((a, b) => a + b.value, 0);
  const R = 56, C = 2 * Math.PI * R;
  let offset = 0;

  return (
    <div className="card">
      <div className="donut-wrap">
        <svg className="donut" viewBox="0 0 132 132" width="132" height="132">
          <g transform="rotate(-90 66 66)">
            {slices.map((sl) => {
              const frac = sl.value / total;
              const dash = frac * C;
              const el = (
                <circle
                  key={sl.label}
                  cx="66" cy="66" r={R}
                  fill="none" stroke={sl.color} strokeWidth="18"
                  strokeDasharray={`${dash} ${C - dash}`}
                  strokeDashoffset={-offset}
                />
              );
              offset += dash;
              return el;
            })}
          </g>
          <text x="66" y="62" textAnchor="middle" fill="#d1d4dc" fontSize="15" fontWeight="700">
            ${total.toLocaleString("ru-RU", { maximumFractionDigits: 0 }).replace(/,/g, " ")}
          </text>
          <text x="66" y="80" textAnchor="middle" fill="#787b86" fontSize="10">
            всего
          </text>
        </svg>

        <div className="legend">
          {slices.map((sl) => (
            <div className="li" key={sl.label}>
              <span className="dot" style={{ background: sl.color }} />
              <span>{sl.label}</span>
              <span className="pct">{((sl.value / total) * 100).toFixed(0)}%</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
