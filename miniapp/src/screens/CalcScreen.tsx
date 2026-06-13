import { useState } from "react";
import SandboxDca from "../components/SandboxDca";

const W = 320, H = 160, PAD = 8;
const fmt = (n: number) =>
  Math.round(n).toLocaleString("ru-RU").replace(/,/g, " ");

// будущая стоимость: p0 единоразово + pmt ежемесячно, r — мес. ставка, m — месяцев
function fv(m: number, p0: number, pmt: number, r: number) {
  if (m <= 0) return p0;
  if (r === 0) return p0 + pmt * m;
  const g = Math.pow(1 + r, m);
  return p0 * g + pmt * ((g - 1) / r);
}

function path(values: number[], max: number, close = false) {
  const stepX = (W - PAD * 2) / (values.length - 1);
  const pts = values.map((v, i) => {
    const x = PAD + i * stepX;
    const y = H - PAD - (v / (max || 1)) * (H - PAD * 2);
    return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
  if (!close) return pts;
  return `${pts} L${(W - PAD).toFixed(1)},${H - PAD} L${PAD},${H - PAD} Z`;
}

const MONTHLY = [10000, 20000, 30000, 50000];
const RETURN = [10, 20, 30, 50];
const YEARS = [5, 10, 20, 30];
const DELAY = [0, 1, 2, 5];

export default function CalcScreen() {
  const [mode, setMode] = useState<"calc" | "dca">("calc");
  const [start, setStart] = useState("0");
  const [monthly, setMonthly] = useState("20000");
  const [annual, setAnnual] = useState("20");
  const [years, setYears] = useState("10");
  const [delay, setDelay] = useState("2");

  const p0 = Number(start) || 0;
  const pmt = Number(monthly) || 0;
  const r = (Number(annual) || 0) / 100 / 12;
  const Y = Math.max(1, Math.min(50, Number(years) || 1));
  const D = Math.min(Y, Number(delay) || 0);

  // годовые точки для графика
  const withC: number[] = [], noC: number[] = [], delayed: number[] = [];
  for (let y = 0; y <= Y; y++) {
    withC.push(fv(y * 12, p0, pmt, r));
    noC.push(fv(y * 12, p0, 0, r));
    delayed.push(y <= D ? 0 : fv((y - D) * 12, p0, pmt, r));
  }
  const fWith = withC[Y], fNo = noC[Y], fDelay = delayed[Y];
  const invested = p0 + pmt * Y * 12;
  const max = Math.max(fWith, fNo, fDelay, 1);
  const delayCost = fWith - fDelay;

  return (
    <div className="content">
      <div className="seg">
        <button className={`seg-btn ${mode === "calc" ? "on" : ""}`}
          onClick={() => setMode("calc")}>Калькулятор</button>
        <button className={`seg-btn ${mode === "dca" ? "on" : ""}`}
          onClick={() => setMode("dca")}>Песочница DCA</button>
      </div>

      {mode === "dca" ? <SandboxDca /> : (<>
      <div className="section-title" style={{ marginTop: 4 }}>
        Калькулятор капитала · сложный процент
      </div>

      {/* входные данные */}
      <div className="card calc-inputs">
        <Row label="Начальный капитал, ₽">
          <input className="inp" inputMode="decimal" value={start}
            onChange={(e) => setStart(e.target.value)} />
        </Row>
        <Row label="Пополнение в месяц, ₽">
          <input className="inp" inputMode="decimal" value={monthly}
            onChange={(e) => setMonthly(e.target.value)} />
          <Chips items={MONTHLY} val={monthly} set={setMonthly} />
        </Row>
        <Row label="Доходность, % годовых">
          <input className="inp" inputMode="decimal" value={annual}
            onChange={(e) => setAnnual(e.target.value)} />
          <Chips items={RETURN} val={annual} set={setAnnual} />
        </Row>
        <Row label="Срок, лет">
          <Chips items={YEARS} val={years} set={setYears} />
        </Row>
        <Row label="Отложить старт на, лет">
          <Chips items={DELAY} val={delay} set={setDelay} />
        </Row>
      </div>

      {/* график */}
      <div className="card">
        <svg viewBox={`0 0 ${W} ${H}`} className="svg-chart">
          <path d={path(withC, max, true)} fill="url(#cg)" />
          <path d={path(withC, max)} fill="none" stroke="#26a69a" strokeWidth="2.5" />
          <path d={path(delayed, max)} fill="none" stroke="#f7931a" strokeWidth="2" strokeDasharray="5 3" />
          <path d={path(noC, max)} fill="none" stroke="#ef5350" strokeWidth="2" />
          <defs>
            <linearGradient id="cg" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#26a69a" stopOpacity="0.22" />
              <stop offset="100%" stopColor="#26a69a" stopOpacity="0" />
            </linearGradient>
          </defs>
        </svg>
        <div className="legend-inline">
          <span><i className="ln accent" /> С пополнением</span>
          <span><i className="ln" style={{ borderTopColor: "#f7931a", borderTopStyle: "dashed" }} /> Если отложить</span>
          <span><i className="ln" style={{ borderTopColor: "#ef5350" }} /> Без пополнения</span>
        </div>
      </div>

      {/* итоги */}
      <div className="calc-results">
        <Result tone="accent" title="С пополнением" value={fWith}
          note={`вложено ${fmt(invested)} ₽ · прирост ${fmt(fWith - invested)} ₽`} />
        <Result tone="red" title="Без пополнения" value={fNo}
          note={p0 === 0 ? "стартового капитала нет → ноль" : `только начальные ${fmt(p0)} ₽`} />
      </div>

      {/* инсайт */}
      <div className="card insight">
        {p0 === 0 && pmt === 0 ? (
          <>Пока ты ничего не откладываешь — капитала не будет. Его создаёт только регулярное действие.</>
        ) : (
          <>
            Промедление <b>{D} {D === 1 ? "год" : D < 5 ? "года" : "лет"}</b> стоит{" "}
            <b className="neg">−{fmt(delayCost)} ₽</b> к финалу.<br />
            Капитал создаётся, когда ты <b className="pos">начинаешь</b>, а не когда «начну позже».
          </>
        )}
      </div>

      <div className="disclaimer">
        Расчёт при постоянной доходности; реальные рынки колеблются. Не ИИР.
      </div>
      </>)}
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="calc-row">
      <div className="field-label">{label}</div>
      {children}
    </div>
  );
}

function Chips({ items, val, set }: { items: number[]; val: string; set: (v: string) => void }) {
  return (
    <div className="chips">
      {items.map((it) => (
        <button key={it} className={`chip ${val === String(it) ? "on" : ""}`}
          onClick={() => set(String(it))}>
          {it.toLocaleString("ru-RU").replace(/,/g, " ")}
        </button>
      ))}
    </div>
  );
}

function Result({ tone, title, value, note }: { tone: string; title: string; value: number; note: string }) {
  return (
    <div className={`result ${tone}`}>
      <div className="result-title">{title}</div>
      <div className="result-value">{fmt(value)} ₽</div>
      <div className="result-note">{note}</div>
    </div>
  );
}
