"""Индекс Без Б — собственный композитный индикатор «режима и перегрева» рынка.

Шкала 0–100, ориентация: ВЫШЕ = эйфория/перегрев (риск коррекции выше),
НИЖЕ = страх/перепроданность (исторически лучше risk/reward). Это НЕ предсказание
точной цены и НЕ сигнал — это карта: где мы на цикле и насколько «натянута пружина».

Складываем 3 группы (каждый компонент нормируем в 0–100 в одной ориентации):
  1. Настроение/позиционирование: страх-жадность, funding, лонг/шорт, открытый интерес.
  2. Тренд/импульс: цена BTC к средним (50/200), RSI, широта рынка.
  3. Риск/структура: просадка от хая, волатильность, доминация BTC.

Каждый источник в своём try/except: если что-то недоступно, компонент выпадает и
веса перенормируются по доступным. Результат кэшируется (тяжёлый — много свечей).
"""
import time
from datetime import datetime, timedelta

import requests

import market_mood
import quotes

_TTL = 900  # 15 мин
_cache = {"ts": 0.0, "data": None}
_FAPI = "https://fapi.binance.com"
_CG_GLOBAL = "https://api.coingecko.com/api/v3/global"

# монеты для «широты рынка» (доля выше своей 50-дн средней)
_BREADTH = ["ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "AVAX", "LINK", "DOT", "TRX", "TON", "LTC"]


def _clip(x, lo=0.0, hi=100.0):
    return max(lo, min(hi, x))


def _scale(x, lo, hi):
    """Линейно перевести x из [lo,hi] в [0,100] с обрезкой."""
    if hi == lo:
        return 50.0
    return _clip((x - lo) / (hi - lo) * 100.0)


def _closes(base: str, days: int) -> list:
    """Список цен закрытия за последние ~days дней (по возрастанию даты)."""
    start = (datetime.utcnow() - timedelta(days=days)).date().isoformat()
    hist = quotes.get_daily_history(base, start)   # {date: close}, с кэшем Binance
    return [hist[d] for d in sorted(hist)]


def _sma(vals: list, n: int):
    if len(vals) < n:
        return None
    return sum(vals[-n:]) / n


def _rsi(vals: list, n: int = 14):
    if len(vals) < n + 1:
        return None
    gains, losses = 0.0, 0.0
    for i in range(-n, 0):
        ch = vals[i] - vals[i - 1]
        if ch >= 0:
            gains += ch
        else:
            losses -= ch
    if losses == 0:
        return 100.0
    rs = (gains / n) / (losses / n)
    return 100.0 - 100.0 / (1.0 + rs)


def _open_interest_change() -> float | None:
    """Изменение открытого интереса BTC за ~7 дней, %."""
    r = requests.get(f"{_FAPI}/futures/data/openInterestHist",
                     params={"symbol": "BTCUSDT", "period": "1d", "limit": 8}, timeout=6)
    r.raise_for_status()
    rows = r.json()
    if len(rows) < 2:
        return None
    first = float(rows[0]["sumOpenInterest"])
    last = float(rows[-1]["sumOpenInterest"])
    if first == 0:
        return None
    return (last / first - 1.0) * 100.0


def _btc_dominance() -> float | None:
    r = requests.get(_CG_GLOBAL, timeout=8)
    r.raise_for_status()
    return float(r.json()["data"]["market_cap_percentage"]["btc"])


def _realized_vol(closes: list) -> float | None:
    """Годовая реализованная волатильность по 30 дн дневных доходностей."""
    if len(closes) < 31:
        return None
    rets = [closes[i] / closes[i - 1] - 1.0 for i in range(-30, 0)]
    mean = sum(rets) / len(rets)
    var = sum((x - mean) ** 2 for x in rets) / len(rets)
    return (var ** 0.5) * (365 ** 0.5)


# ───────────────────────── сборка индекса ─────────────────────────

def compute(force: bool = False) -> dict:
    now = time.time()
    if not force and _cache["data"] and now - _cache["ts"] < _TTL:
        return _cache["data"]

    comps = []   # {key,label,score,detail,weight}
    mood = market_mood.snapshot()

    def add(key, label, score, detail, weight):
        if score is not None:
            comps.append({"key": key, "label": label,
                          "score": round(_clip(score)), "detail": detail, "weight": weight})

    # ── Группа 1: настроение/позиционирование ──
    fng = mood.get("fng")
    if fng:
        add("fng", "Страх/жадность", fng["value"],
            f"{fng['value']}/100 · {fng['label_ru']}", 0.18)

    fund = mood.get("funding") or {}
    fvals = [fund[s] for s in ("BTCUSDT", "ETHUSDT") if s in fund]
    if fvals:
        favg = sum(fvals) / len(fvals)
        add("funding", "Плечо (funding)", _scale(favg, -0.0003, 0.0006),
            f"{favg * 100:+.3f}%/8ч", 0.12)

    ls = mood.get("longshort")
    if ls:
        add("longshort", "Лонг/шорт толпы", _scale(ls["ratio"], 0.7, 2.0),
            f"{ls['long']:.0f}% в лонге", 0.08)

    try:
        oi = _open_interest_change()
        add("oi", "Открытый интерес", _scale(oi, -15, 25),
            f"{oi:+.0f}% за 7д", 0.07)
    except Exception:
        pass

    # ── Группа 2: тренд/импульс ──
    btc = _closes("BTC", 230)
    price = None
    if mood.get("spot", {}).get("BTCUSDT"):
        price = mood["spot"]["BTCUSDT"]["price"]
    elif btc:
        price = btc[-1]

    if btc and price:
        sma50, sma200 = _sma(btc, 50), _sma(btc, 200)
        parts = []
        if sma50:
            parts.append(_scale(price / sma50, 0.90, 1.15))
        if sma200:
            parts.append(_scale(price / sma200, 0.80, 1.40))
        if parts:
            above = []
            if sma50:
                above.append("50д" if price >= sma50 else "под 50д")
            if sma200:
                above.append("200д" if price >= sma200 else "под 200д")
            add("trend", "Тренд BTC к средним", sum(parts) / len(parts),
                "выше " + "/".join(a for a in above), 0.20)

        rsi = _rsi(btc, 14)
        if rsi is not None:
            add("rsi", "Импульс (RSI)", rsi, f"RSI {rsi:.0f}", 0.10)

        # просадка от 90-дневного максимума
        hi90 = max(btc[-90:]) if len(btc) >= 90 else max(btc)
        dist = (price / hi90 - 1.0) * 100.0
        add("drawdown", "Близость к максимуму", _scale(dist, -40, 0),
            ("у хая" if dist > -3 else f"{dist:.0f}% от хая"), 0.06)

        vol = _realized_vol(btc)
        if vol is not None:
            add("vol", "Волатильность", 100 - _scale(vol, 0.30, 1.20),
                f"~{vol * 100:.0f}% год.", 0.04)

    # широта рынка: доля монет выше своей 50-дн средней
    try:
        above, total = 0, 0
        for c in _BREADTH:
            cl = _closes(c, 70)
            s = _sma(cl, 50)
            if cl and s:
                total += 1
                if cl[-1] >= s:
                    above += 1
        if total:
            frac = above / total
            add("breadth", "Широта рынка", frac * 100,
                f"{above}/{total} монет выше 50д", 0.10)
    except Exception:
        pass

    # ── Группа 3: доминация BTC (инверсно: высокая = risk-off = ниже) ──
    try:
        dom = _btc_dominance()
        add("dominance", "Доминация BTC", 100 - _scale(dom, 0.40, 0.65) if dom <= 1
            else 100 - _scale(dom, 40, 65), f"{dom if dom > 1 else dom * 100:.0f}%", 0.05)
    except Exception:
        pass

    # ── свёртка ──
    if not comps:
        data = {"value": None, "label": "нет данных", "zone": "na", "components": []}
        _cache.update(ts=now, data=data)
        return data

    wsum = sum(c["weight"] for c in comps)
    value = round(sum(c["score"] * c["weight"] for c in comps) / wsum)
    data = {"value": value, "label": _label(value), "zone": _zone(value),
            "components": [{"label": c["label"], "score": c["score"], "detail": c["detail"]}
                          for c in sorted(comps, key=lambda x: -x["weight"])]}
    _cache.update(ts=now, data=data)
    return data


def _zone(v: int) -> str:
    if v < 20:
        return "extreme_fear"
    if v < 40:
        return "fear"
    if v < 55:
        return "neutral"
    if v < 75:
        return "greed"
    return "extreme_greed"


def _label(v: int) -> str:
    return {"extreme_fear": "Крайний страх", "fear": "Страх", "neutral": "Нейтрально",
            "greed": "Жадность", "extreme_greed": "Крайняя жадность"}[_zone(v)]


def context() -> str:
    """Текст для AI/постов: значение индекса + главные драйверы."""
    d = compute()
    if d["value"] is None:
        return "Индекс Без Б временно недоступен."
    top = "; ".join(f"{c['label']} {c['score']}/100 ({c['detail']})"
                    for c in d["components"][:5])
    return (f"Индекс Без Б = {d['value']}/100 — {d['label']} "
            f"(0 = страх/перепроданность, 100 = эйфория/перегрев). Главные факторы: {top}.")
