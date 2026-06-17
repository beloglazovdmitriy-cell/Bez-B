"""«Нелюбимчик недели» — самый перепроданный/нелюбимый рынком актив по прозрачным
механическим фильтрам (премиум-фича).

ЧЕСТНО: это НЕ «недооценён → вырастет» и НЕ сигнал. Это «по нашим фильтрам сильнее
всех просел и сейчас не в фаворе» + разбор за/против. Чтобы не ловить «падающий нож»,
в скоре тяжело весит признак стабилизации (упал И нащупал дно/разворот), а не просто
«упал сильнее всех».

Скор 0–100 (выше = более «нелюбимый, но с признаками жизни»):
  • просадка от годового максимума (вес 0.30)
  • перепроданность RSI (0.20)
  • признаки стабилизации/разворота за 7д на фоне падения за 30д (0.25)
  • насколько ниже 200-дневной средней (0.15)
  • негативный funding — толпа ставит против (0.10)
"""
import json
import time
from datetime import datetime

import market_mood
import storage
from bezb_index import _closes, _sma, _rsi, _scale, _clip

# корзина ликвидных, устоявшихся монет (без мусора и стейблов)
_UNIVERSE = ["BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "AVAX", "LINK",
             "DOT", "TRX", "TON", "LTC", "ATOM", "NEAR", "UNI", "AAVE", "FIL"]

_TTL = 6 * 3600
_cache = {"ts": 0.0, "data": None}
_META_KEY = "underdog:current"


def _week_id(dt: datetime | None = None) -> str:
    dt = dt or datetime.now()
    y, w, _ = dt.isocalendar()
    return f"{y}-W{w:02d}"


def _funding(base: str):
    try:
        return market_mood._funding(f"{base}USDT")
    except Exception:
        return None


def _score_coin(base: str) -> dict | None:
    closes = _closes(base, 380)
    if len(closes) < 60:
        return None
    price = closes[-1]
    hi = max(closes[-365:]) if len(closes) >= 365 else max(closes)
    dd = (price / hi - 1.0) * 100.0                      # просадка от хая, %
    rsi = _rsi(closes, 14)
    sma200 = _sma(closes, 200)
    p7 = closes[-8] if len(closes) >= 8 else closes[0]
    p30 = closes[-31] if len(closes) >= 31 else closes[0]
    ret7 = (price / p7 - 1.0) * 100.0
    ret30 = (price / p30 - 1.0) * 100.0
    fund = _funding(base)

    parts, wsum = 0.0, 0.0

    def add(score, w):
        nonlocal parts, wsum
        if score is not None:
            parts += _clip(score) * w
            wsum += w

    add(_scale(-dd, 10, 70), 0.30)                       # глубже просадка → выше
    if rsi is not None:
        add(100 - rsi, 0.20)                             # перепродан → выше
    # стабилизация: падал за 30д, но за 7д уже не падает / разворот
    if ret30 < 0:
        add(_scale(ret7, -8, 8), 0.25)                   # 7д вверх на фоне минуса 30д
    else:
        add(20, 0.25)                                    # уже растёт 30д — не «нелюбимчик»
    if sma200:
        add(_scale((sma200 / price - 1.0) * 100, -10, 40), 0.15)
    if fund is not None:
        add(_scale(-fund, -0.0002, 0.0005), 0.10)        # негативный funding → выше

    if wsum == 0:
        return None
    score = round(parts / wsum)
    return {"ticker": base, "score": score, "price": price,
            "dd": round(dd), "rsi": round(rsi) if rsi is not None else None,
            "ret7": round(ret7, 1), "ret30": round(ret30, 1),
            "belowSma200": bool(sma200 and price < sma200)}


def _ranking() -> list:
    out = []
    for base in _UNIVERSE:
        try:
            r = _score_coin(base)
            if r:
                out.append(r)
        except Exception:
            pass
    return sorted(out, key=lambda x: -x["score"])


def _context(top: dict) -> str:
    bits = [f"{top['ticker']}: просадка {top['dd']}% от годового максимума"]
    if top.get("rsi") is not None:
        bits.append(f"RSI {top['rsi']} (перепроданность)")
    bits.append(f"за 7д {top['ret7']:+.1f}%, за 30д {top['ret30']:+.1f}%")
    if top.get("belowSma200"):
        bits.append("ниже 200-дневной средней")
    return "; ".join(bits) + "."


def build(with_ai: bool = True) -> dict:
    """Посчитать ранжирование, выбрать нелюбимчика недели, сделать AI-разбор, сохранить."""
    rank = _ranking()
    if not rank:
        return {"weekId": _week_id(), "ticker": None, "top3": [], "analysis": ""}
    top = rank[0]
    analysis = ""
    if with_ai:
        try:
            import ai
            if ai.available():
                analysis = ai.underdog_analysis(top["ticker"], _context(top))
        except Exception:
            pass
    data = {"weekId": _week_id(), "ticker": top["ticker"], "score": top["score"],
            "label": top["ticker"], "stats": top, "analysis": analysis,
            "top3": rank[:3], "ts": int(time.time())}
    storage.meta_set(_META_KEY, json.dumps(data, ensure_ascii=False))
    _cache.update(ts=time.time(), data=data)
    return data


def current(build_if_stale: bool = True) -> dict | None:
    """Текущий нелюбимчик недели из хранилища; пересобрать, если неделя сменилась."""
    raw = storage.meta_get(_META_KEY)
    data = None
    if raw:
        try:
            data = json.loads(raw)
        except Exception:
            data = None
    if data and data.get("weekId") == _week_id() and data.get("ticker"):
        return data
    if build_if_stale:
        return build(with_ai=True)
    return data
