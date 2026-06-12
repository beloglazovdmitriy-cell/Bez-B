import { useState } from "react";
import type { HistoryPoint, BenchRow } from "../data";

const W = 320, H = 150, PAD = 6;

function buildPath(values: number[], min: number, max: number) {
  const span = max - min || 1;
  const stepX = (W - PAD * 2) / (values.length - 1);
  return values.map((v, i) => {
    const x = PAD + i * stepX;
    const y = H - PAD - ((v - min) / span) * (H - PAD * 2);
    return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
}

function area(values: number[], min: number, max: number) {
  const span = max - min || 1;
  const stepX = (W - PAD * 2) / (values.length - 1);
  const top = values.map((v, i) => {
    const x = PAD + i * stepX;
    const y = H - PAD - ((v - min) / span) * (H - PAD * 2);
    return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
  return `${top} L${(W - PAD).toFixed(1)},${H - PAD} L${PAD},${H - PAD} Z`;
}

const PERIODS = ["1М", "3М", "6М", "Всё"];

export default function ChartScreen({
  history,
  bench,
}: {
  history: HistoryPoint[];
  bench: BenchRow[];
}) {
  const [period, setPeriod] = useState("Всё");
  const h = history;

  // нужно минимум 2 точки, иначе график не построить
  if (h.length < 2) {
    return (
      <div className="content">
        <div className="card stub-card">
          График наполняется снимками портфеля.<br />
          Нужно ещё немного истории — загляни позже.
        </div>
      </div>
    );
  }

  const values = h.map((p) => p.value);
  const invested = h.map((p) => p.invested);
  const idx = h.map((p) => p.index);

  const allMin = Math.min(...values, ...invested);
  const allMax = Math.max(...values, ...invested);
  const idxMin = Math.min(...idx, 100);
  const idxMax = Math.max(...idx, 100);

  const last = h[h.length - 1];
  const grew = last.value >= last.invested;
  const maxBench = Math.max(...bench.map((b) => Math.abs(b.retRubPct)), 1);

  return (
    <div className="content">
      {/* периоды */}
      <div className="periods">
        {PERIODS.map((p) => (
          <button
            key={p}
            className={`period ${period === p ? "active" : ""}`}
            onClick={() => setPeriod(p)}
          >
            {p}
          </button>
        ))}
      </div>

      {/* стоимость vs вложено */}
      <div className="card">
        <div className="chart-head">
          <span className="section-title" style={{ margin: 0 }}>Стоимость портфеля, ₽</span>
          <span className={grew ? "pos" : "neg"} style={{ fontWeight: 700 }}>
            {last.value.toLocaleString("ru-RU").replace(/,/g, " ")} ₽
          </span>
        </div>
        <svg viewBox={`0 0 ${W} ${H}`} className="svg-chart">
          <path d={area(values, allMin, allMax)} fill="url(#g1)" />
          <path d={buildPath(invested, allMin, allMax)} fill="none" stroke="#787b86" strokeWidth="1.5" strokeDasharray="4 3" />
          <path d={buildPath(values, allMin, allMax)} fill="none" stroke="#26a69a" strokeWidth="2.5" />
          <defs>
            <linearGradient id="g1" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#26a69a" stopOpacity="0.25" />
              <stop offset="100%" stopColor="#26a69a" stopOpacity="0" />
            </linearGradient>
          </defs>
        </svg>
        <div className="legend-inline">
          <span><i className="ln accent" /> Стоимость</span>
          <span><i className="ln dashed" /> Вложено</span>
        </div>
      </div>

      {/* индекс Без Б */}
      <div className="card">
        <div className="chart-head">
          <span className="section-title" style={{ margin: 0 }}>Индекс Без Б</span>
          <span className="pos" style={{ fontWeight: 700 }}>{last.index.toFixed(1)} пт</span>
        </div>
        <svg viewBox={`0 0 ${W} ${H}`} className="svg-chart">
          <path d={area(idx, idxMin, idxMax)} fill="url(#g2)" />
          <path d={buildPath(idx, idxMin, idxMax)} fill="none" stroke="#26a69a" strokeWidth="2.5" />
          <defs>
            <linearGradient id="g2" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#26a69a" stopOpacity="0.25" />
              <stop offset="100%" stopColor="#26a69a" stopOpacity="0" />
            </linearGradient>
          </defs>
        </svg>
      </div>

      {/* без Б против рынка */}
      <div className="card">
        <div className="section-title" style={{ marginTop: 0, marginBottom: 10 }}>
          Без Б против рынка · доходность ₽
        </div>
        <div className="bars">
          {bench.map((b) => (
            <div className="bar-row" key={b.name}>
              <span className="bar-name">{b.name}</span>
              <div className="bar-track">
                <div
                  className="bar-fill"
                  style={{
                    width: `${(Math.abs(b.retRubPct) / maxBench) * 100}%`,
                    background: b.isMe ? "#26a69a" : b.retRubPct >= 0 ? "#4a8f87" : "#ef5350",
                  }}
                />
              </div>
              <span className={`bar-val ${b.retRubPct >= 0 ? "pos" : "neg"}`}>
                {b.retRubPct >= 0 ? "+" : ""}{b.retRubPct.toFixed(1)}%
              </span>
            </div>
          ))}
        </div>
      </div>

      <div className="disclaimer">Сравнение стратегий «купил и держу».</div>
    </div>
  );
}
