import { useEffect, useState } from "react";
import { apiSandboxDca, type SandboxResult } from "../data";

const W = 320, H = 160, PAD = 8;
const fmt = (n: number) => Math.round(n).toLocaleString("ru-RU").replace(/,/g, " ");

const TICKERS = ["BTC", "ETH", "SOL", "BNB", "TON"];
const AMOUNTS = [25, 50, 100];
const YEARS = [1, 2, 3];

function path(values: number[], max: number, close = false) {
  if (values.length < 2) return "";
  const stepX = (W - PAD * 2) / (values.length - 1);
  const pts = values.map((v, i) => {
    const x = PAD + i * stepX;
    const y = H - PAD - (v / (max || 1)) * (H - PAD * 2);
    return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
  if (!close) return pts;
  return `${pts} L${(W - PAD).toFixed(1)},${H - PAD} L${PAD},${H - PAD} Z`;
}

export default function SandboxDca() {
  const [ticker, setTicker] = useState("BTC");
  const [amount, setAmount] = useState(50);
  const [years, setYears] = useState(2);
  const [res, setRes] = useState<SandboxResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  useEffect(() => {
    let alive = true;
    setLoading(true); setErr("");
    apiSandboxDca(ticker, amount, years)
      .then((r) => { if (alive) setRes(r); })
      .catch((e) => { if (alive) { setErr((e as Error).message); setRes(null); } })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [ticker, amount, years]);

  const value = res?.value ?? 0;
  const invested = res?.invested ?? 0;
  const profit = value - invested;
  const up = profit >= 0;
  const valLine = res ? res.points.map((p) => p.value) : [];
  const invLine = res ? res.points.map((p) => p.invested) : [];
  const max = Math.max(value, invested, ...valLine, 1);

  return (
    <>
      <div className="section-title" style={{ marginTop: 4 }}>
        Песочница DCA · что было бы на истории
      </div>

      <div className="card calc-inputs">
        <div className="calc-row">
          <div className="field-label">Актив</div>
          <div className="chips">
            {TICKERS.map((t) => (
              <button key={t} className={`chip ${ticker === t ? "on" : ""}`}
                onClick={() => setTicker(t)}>{t}</button>
            ))}
          </div>
        </div>
        <div className="calc-row">
          <div className="field-label">Взнос каждые 2 недели, $</div>
          <div className="chips">
            {AMOUNTS.map((a) => (
              <button key={a} className={`chip ${amount === a ? "on" : ""}`}
                onClick={() => setAmount(a)}>${a}</button>
            ))}
          </div>
        </div>
        <div className="calc-row">
          <div className="field-label">Срок, лет</div>
          <div className="chips">
            {YEARS.map((y) => (
              <button key={y} className={`chip ${years === y ? "on" : ""}`}
                onClick={() => setYears(y)}>{y}</button>
            ))}
          </div>
        </div>
      </div>

      {loading ? (
        <div className="muted-note">Считаю по истории {ticker}…</div>
      ) : err ? (
        <div className="card stub-card">{err}</div>
      ) : res ? (
        <>
          <div className="card">
            <svg viewBox={`0 0 ${W} ${H}`} className="svg-chart">
              <path d={path(valLine, max, true)} fill="url(#sg)" />
              <path d={path(valLine, max)} fill="none"
                stroke={up ? "#26a69a" : "#ef5350"} strokeWidth="2.5" />
              <path d={path(invLine, max)} fill="none" stroke="#787b86"
                strokeWidth="2" strokeDasharray="5 3" />
              <defs>
                <linearGradient id="sg" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={up ? "#26a69a" : "#ef5350"} stopOpacity="0.22" />
                  <stop offset="100%" stopColor={up ? "#26a69a" : "#ef5350"} stopOpacity="0" />
                </linearGradient>
              </defs>
            </svg>
            <div className="legend-inline">
              <span><i className="ln accent" /> Стоимость</span>
              <span><i className="ln" style={{ borderTopColor: "#787b86", borderTopStyle: "dashed" }} /> Вложено</span>
            </div>
          </div>

          <div className="calc-results">
            <div className="result accent">
              <div className="result-title">Стоимость сейчас</div>
              <div className="result-value">${fmt(value)}</div>
              <div className="result-note">вложено ${fmt(invested)}</div>
            </div>
            <div className={`result ${up ? "accent" : "red"}`}>
              <div className="result-title">Результат</div>
              <div className="result-value">{up ? "+" : "−"}${fmt(Math.abs(profit))}</div>
              <div className="result-note">{up ? "+" : ""}{res.profitPct}% за {years} {years === 1 ? "год" : "года"}</div>
            </div>
          </div>

          <div className="card sand-compare">
            <div className="sc-row">
              <span>DCA — по ${amount} каждые 2 недели</span>
              <b className={up ? "pos" : "neg"}>{up ? "+" : ""}{res.profitPct}%</b>
            </div>
            <div className="sc-row">
              <span>Если вложить всё сразу в начале</span>
              <b className={res.lumpProfitPct >= 0 ? "pos" : "neg"}>
                {res.lumpProfitPct >= 0 ? "+" : ""}{res.lumpProfitPct}%
              </b>
            </div>
            <div className="sc-row muted">
              <span>Средняя цена входа</span>
              <b>${fmt(res.avgPrice)}</b>
            </div>
          </div>

          <div className="card insight">
            {(() => {
              const dcaBetter = res.profitPct >= res.lumpProfitPct;
              const grew = res.priceChangePct >= 0;
              if (dcaBetter) {
                return (<>
                  Здесь DCA сработал <b className="pos">лучше</b>, чем вложить всё сразу{" "}
                  ({res.profitPct >= 0 ? "+" : ""}{res.profitPct}% против{" "}
                  {res.lumpProfitPct >= 0 ? "+" : ""}{res.lumpProfitPct}%): регулярные покупки
                  усреднили вход на просадках. Это сила DCA на падающем и боковом рынке.
                </>);
              }
              return (<>
                Здесь вложить всё в начале было бы <b className="neg">выгоднее</b>{" "}
                ({res.lumpProfitPct >= 0 ? "+" : ""}{res.lumpProfitPct}% против{" "}
                {res.profitPct >= 0 ? "+" : ""}{res.profitPct}%): {grew ? "цена росла" : "рынок дёргался"},
                и поздние покупки подняли средний вход. DCA — это не про максимум доходности,
                а про <b className="pos">дисциплину</b> и защиту от плохого тайминга.
              </>);
            })()}
          </div>
        </>
      ) : null}

      <div className="disclaimer">
        Бэктест на реальных недельных ценах Binance. Прошлое не гарантирует будущее. Не ИИР.
      </div>
    </>
  );
}
