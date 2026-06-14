"""Технический анализ для контента: свечи Хейкен Аши + авто-уровни
поддержки/сопротивления. Данные — публичное зеркало Binance
(data-api.binance.vision, без гео-блока). Только крипта (тикер+USDT).

Используется для контент-графиков (charts.ta_chart) и AI-разбора уровней.
Философия «Без Б»: это КАРТА УРОВНЕЙ и сценарии, а не прямые сигналы.
"""
import time
import requests

_KLINES = "https://data-api.binance.vision/api/v3/klines"
_TTL = 600
_cache = {}


def _m(v: float) -> str:
    """Денежный формат с пробелами как разделителями тысяч."""
    return f"{v:,.0f}".replace(",", " ") if v >= 100 else f"{v:,.4f}".rstrip("0").rstrip(".")


def _klines(symbol: str, interval: str, limit: int):
    key = (symbol, interval, limit)
    now = time.time()
    c = _cache.get(key)
    if c and now - c[0] < _TTL:
        return c[1]
    r = requests.get(_KLINES, params={"symbol": symbol, "interval": interval,
                                      "limit": limit}, timeout=12)
    r.raise_for_status()
    rows = [{"t": int(k[0]), "o": float(k[1]), "h": float(k[2]),
             "l": float(k[3]), "c": float(k[4])} for k in r.json()]
    _cache[key] = (now, rows)
    return rows


def heikin_ashi(ohlc):
    ha = []
    prev = None
    for k in ohlc:
        close = (k["o"] + k["h"] + k["l"] + k["c"]) / 4
        open_ = (k["o"] + k["c"]) / 2 if prev is None else (prev["o"] + prev["c"]) / 2
        high = max(k["h"], open_, close)
        low = min(k["l"], open_, close)
        bar = {"t": k["t"], "o": open_, "h": high, "l": low, "c": close}
        ha.append(bar)
        prev = bar
    return ha


def support_resistance(ohlc, last, k=5, max_levels=6):
    """Авто-уровни: свинг-хаи/лоу (пивоты) → кластеризация → отбор значимых."""
    highs = [x["h"] for x in ohlc]
    lows = [x["l"] for x in ohlc]
    n = len(ohlc)
    piv = []
    for i in range(k, n - k):
        if highs[i] == max(highs[i - k:i + k + 1]):
            piv.append(highs[i])
        if lows[i] == min(lows[i - k:i + k + 1]):
            piv.append(lows[i])
    piv += [max(highs), min(lows)]
    piv.sort()
    clusters = []
    for p in piv:
        if clusters:
            cur = clusters[-1]["sum"] / clusters[-1]["n"]
            if abs(p - cur) / p <= 0.018:        # сливаем уровни в пределах ~1.8%
                clusters[-1]["sum"] += p
                clusters[-1]["n"] += 1
                continue
        clusters.append({"sum": p, "n": 1})
    levels = [{"value": c["sum"] / c["n"], "touches": c["n"]} for c in clusters]
    levels.sort(key=lambda L: (-L["touches"], abs(L["value"] - last)))
    levels = levels[:max_levels]
    for L in levels:
        L["kind"] = "resistance" if L["value"] >= last else "support"
    levels.sort(key=lambda L: L["value"])
    return levels


def analyze(symbol: str = "BTCUSDT", interval: str = "1d", limit: int = 180):
    ohlc = _klines(symbol, interval, limit)
    if not ohlc or len(ohlc) < 20:
        return None
    last = ohlc[-1]["c"]
    first = ohlc[0]["c"]
    levels = support_resistance(ohlc, last)
    sup = [L["value"] for L in levels if L["kind"] == "support"]
    res = [L["value"] for L in levels if L["kind"] == "resistance"]
    return {
        "symbol": symbol, "interval": interval, "last": last,
        "changePct": (last / first - 1) * 100 if first else 0,
        "ohlc": ohlc, "ha": heikin_ashi(ohlc), "levels": levels,
        "nearestSupport": max(sup) if sup else None,
        "nearestResistance": min(res) if res else None,
    }


def context(symbol: str = "BTCUSDT", interval: str = "1d") -> str:
    """Текстовый контекст уровней для AI-разбора."""
    a = analyze(symbol, interval)
    if not a:
        return ""
    base = symbol.replace("USDT", "")
    L = [f"{base}: цена ${_m(a['last'])} ({a['changePct']:+.1f}% за период, таймфрейм {interval})."]
    if a["nearestSupport"]:
        L.append(f"Ближайшая поддержка около ${_m(a['nearestSupport'])}.")
    if a["nearestResistance"]:
        L.append(f"Ближайшее сопротивление около ${_m(a['nearestResistance'])}.")
    levs = ", ".join(f"${_m(l['value'])}" for l in a["levels"])
    if levs:
        L.append(f"Ключевые уровни снизу вверх: {levs}.")
    return " ".join(L)
