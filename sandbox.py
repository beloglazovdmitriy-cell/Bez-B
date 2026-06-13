"""DCA-песочница: бэктест «сколько было бы, если вкладывать по $X каждые 2 недели».

История цен — недельные свечи Binance (публичное зеркало data-api.binance.vision,
без гео-блока). Только крипта (тикер+USDT). Результат кэшируется на час.
"""
import time
from datetime import datetime, timezone

import requests

_KLINES = "https://data-api.binance.vision/api/v3/klines"
_TTL = 3600
_cache = {}


def _weekly_closes(symbol: str, weeks: int):
    """Список (ts_ms, close) от старых к новым, недельные свечи."""
    key = (symbol, weeks)
    now = time.time()
    c = _cache.get(key)
    if c and now - c[0] < _TTL:
        return c[1]
    r = requests.get(_KLINES, params={"symbol": symbol, "interval": "1w",
                                      "limit": weeks}, timeout=12)
    r.raise_for_status()
    rows = [(int(k[0]), float(k[4])) for k in r.json()]
    _cache[key] = (now, rows)
    return rows


def simulate(ticker: str, amount: float, years: float, every: int = 2) -> dict | None:
    """Бэктест DCA. every — раз в сколько недель вносим взнос (по умолч. 2)."""
    symbol = ticker.strip().upper() + "USDT"
    weeks = max(8, min(312, int(years * 52) + 1))   # до 6 лет
    try:
        closes = _weekly_closes(symbol, weeks)
    except Exception:
        return None                                  # нет пары на Binance (напр. акция)
    if not closes or len(closes) < 4:
        return None
    units = 0.0
    invested = 0.0
    points = []
    for i, (ts, price) in enumerate(closes):
        if price <= 0:
            continue
        if i % every == 0:
            units += amount / price
            invested += amount
        value = units * price
        points.append({
            "date": datetime.fromtimestamp(ts / 1000, timezone.utc).strftime("%m.%y"),
            "invested": round(invested),
            "value": round(value),
        })
    # прорежаем точки до ~52 для графика
    if len(points) > 52:
        step = len(points) / 52
        points = [points[int(i * step)] for i in range(52)] + [points[-1]]
    last_price = closes[-1][1]
    first_price = closes[0][1]
    value = units * last_price
    # бенчмарк DCA: вложить ту же сумму единоразово в начале периода
    lump_units = invested / first_price if first_price else 0.0
    lump_value = lump_units * last_price
    avg_price = invested / units if units else 0.0
    return {
        "ticker": ticker.strip().upper(),
        "amount": amount,
        "everyWeeks": every,
        "weeks": len(closes),
        "invested": round(invested),
        "value": round(value),
        "units": units,
        "profitPct": round((value / invested - 1) * 100, 1) if invested else 0.0,
        "avgPrice": round(avg_price, 2),
        "lumpValue": round(lump_value),
        "lumpProfitPct": round((lump_value / invested - 1) * 100, 1) if invested else 0.0,
        "firstPrice": first_price,
        "lastPrice": last_price,
        "priceChangePct": round((last_price / first_price - 1) * 100, 1) if first_price else 0.0,
        "points": points,
    }
