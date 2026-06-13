"""Настроение рынка крипты для рубрики «🌡 Разбор толпы».

Источники (бесплатные, без ключа):
  • Индекс страха и жадности — alternative.me (/fng).
  • Funding rate и лонг/шорт толпы — Binance Futures (fapi).

Каждый источник обёрнут в свой try/except: если что-то недоступно
(напр. fapi гео-заблокирован, как было с Yahoo) — отдаём, что собралось.
Результат кэшируется на 10 минут, чтобы публикация/планировщик не дёргали
сеть лишний раз.
"""
import time
import requests

_FNG_URL = "https://api.alternative.me/fng/"
_FAPI = "https://fapi.binance.com"          # Futures: funding/long-short (гео-блок возможен)
_SPOT = "https://data-api.binance.vision/api/v3/ticker/24hr"  # spot 24ч (публ. зеркало, без гео-блока)
_TTL = 600  # сек

_cache = {"ts": 0.0, "data": None}

# перевод классификации alternative.me на русский
_RU = {
    "Extreme Fear": "Крайний страх", "Fear": "Страх", "Neutral": "Нейтрально",
    "Greed": "Жадность", "Extreme Greed": "Крайняя жадность",
}


def _fear_greed() -> dict:
    r = requests.get(_FNG_URL, params={"limit": 2, "format": "json"}, timeout=8)
    r.raise_for_status()
    d = r.json()["data"]
    cur, prev = d[0], (d[1] if len(d) > 1 else d[0])
    cls = cur.get("value_classification", "")
    return {"value": int(cur["value"]), "label": cls,
            "label_ru": _RU.get(cls, cls), "prev": int(prev["value"])}


def _funding(symbol: str) -> float:
    r = requests.get(f"{_FAPI}/fapi/v1/premiumIndex",
                     params={"symbol": symbol}, timeout=6)
    r.raise_for_status()
    return float(r.json()["lastFundingRate"])  # доля за 8 часов


def _spot_change(symbol: str) -> dict:
    r = requests.get(_SPOT, params={"symbol": symbol}, timeout=6)
    r.raise_for_status()
    d = r.json()
    return {"price": float(d["lastPrice"]), "pct24": float(d["priceChangePercent"])}


def _long_short(symbol: str) -> dict:
    r = requests.get(f"{_FAPI}/futures/data/globalLongShortAccountRatio",
                     params={"symbol": symbol, "period": "1h", "limit": 1}, timeout=6)
    r.raise_for_status()
    row = r.json()[0]
    return {"ratio": float(row["longShortRatio"]),
            "long": float(row["longAccount"]) * 100,
            "short": float(row["shortAccount"]) * 100}


def snapshot(force: bool = False) -> dict:
    """Собрать настроение рынка (с кэшем). Любой источник может быть None/пустым."""
    now = time.time()
    if not force and _cache["data"] and now - _cache["ts"] < _TTL:
        return _cache["data"]
    out = {"fng": None, "spot": {}, "funding": {}, "longshort": None}
    try:
        out["fng"] = _fear_greed()
    except Exception:
        pass
    for sym in ("BTCUSDT", "ETHUSDT"):
        try:
            out["spot"][sym] = _spot_change(sym)
        except Exception:
            pass
        try:
            out["funding"][sym] = _funding(sym)
        except Exception:
            pass
    try:
        out["longshort"] = _long_short("BTCUSDT")
    except Exception:
        pass
    _cache.update(ts=now, data=out)
    return out


def context() -> str:
    """Человекочитаемый контекст для AI-промпта рубрики «Разбор толпы»."""
    m = snapshot()
    L = []
    f = m.get("fng")
    if f:
        arrow = "↑" if f["value"] > f["prev"] else "↓" if f["value"] < f["prev"] else "→"
        L.append(f"Индекс страха и жадности: {f['value']}/100 — {f['label_ru']} "
                 f"(вчера {f['prev']} {arrow}).")
    spot = m.get("spot") or {}
    if spot:
        parts = [f"{sym.replace('USDT', '')} ${d['price']:,.0f} ({d['pct24']:+.1f}% за сутки)"
                 .replace(",", " ") for sym, d in spot.items()]
        L.append("Цены: " + "; ".join(parts) + ".")
    fund = m.get("funding") or {}
    if fund:
        parts = []
        for sym, rate in fund.items():
            ann = rate * 3 * 365 * 100  # ~годовых, %
            parts.append(f"{sym.replace('USDT', '')} {rate * 100:+.3f}%/8ч "
                         f"(~{ann:+.0f}% год.)")
        L.append("Funding фьючерсов (+ = перевес лонгов, толпа в плечах на лонг): "
                 + "; ".join(parts) + ".")
    ls = m.get("longshort")
    if ls:
        L.append(f"Лонг/шорт счетов BTC: {ls['ratio']:.2f} "
                 f"({ls['long']:.0f}% в лонге / {ls['short']:.0f}% в шорте).")
    return " ".join(L) if L else "Данные о настроении рынка временно недоступны."
