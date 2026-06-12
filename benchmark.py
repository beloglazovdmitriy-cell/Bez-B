"""Сравнение портфеля «Без Б» с бенчмарками по принципу «купил и держу».

Для каждой покупки берём вложенную сумму в USDT и дату, и считаем, во что бы
она превратилась сейчас:
  • в моём активе (фактически)        — Портфель Без Б
  • в S&P 500 / Bitcoin / Золоте      — по исторической цене на дату покупки
  • в долларе (просто держал USDT)    — рост только за счёт курса в рублях
  • на рублёвом вкладе                — по ставке DEPOSIT_RATE_RUB

Результат — в двух валютах (USD и ₽), т.к. это ключевая фишка проекта.
Продажи в этом сравнении не учитываются — это сопоставление стратегий, а не
текущий P&L.
"""
import time
from datetime import datetime

import storage
from config import DEPOSIT_RATE_RUB, BENCHMARK_TICKERS
from quotes import get_price_usd, get_usd_rub, get_daily_history, price_on_date


def _buys():
    """Все покупки с суммой в USDT, курсом и датой."""
    out = []
    for t in storage.load()["trades"]:
        if (t.get("type") or t.get("side")) in ("buy", "asset_deposit"):
            price = t.get("price_usdt", t.get("price_usd"))
            if not price:
                continue
            out.append({
                "ticker": t["ticker"],
                "buy_price": price,
                "amount": t["qty"] * price,        # вложено USDT
                "rate": t.get("rate_rub"),
                "ts": t["ts"],
            })
    return out


def _safe_now(ticker):
    try:
        return get_price_usd(ticker, allow_stale=True)
    except Exception:
        return None


def _result(name, invested_usd, value_usd, invested_rub, value_rub):
    return {
        "name": name,
        "value_usd": value_usd,
        "value_rub": value_rub,
        "ret_usd_pct": (value_usd / invested_usd - 1) * 100 if (value_usd is not None and invested_usd) else None,
        "ret_rub_pct": (value_rub / invested_rub - 1) * 100 if invested_rub else None,
    }


def compare():
    """Главная функция. Возвращает словарь с результатами или None, если покупок нет."""
    buys = _buys()
    if not buys:
        return None

    rate_now = get_usd_rub()
    invested_usd = sum(b["amount"] for b in buys)
    invested_rub = sum(b["amount"] * (b["rate"] or rate_now) for b in buys)
    start_iso = datetime.utcfromtimestamp(min(b["ts"] for b in buys)).date().isoformat()

    results = []

    # 1) Портфель Без Б — фактические активы, купил-и-держу
    now_cache = {}
    val_usd = 0.0
    ok = True
    for b in buys:
        p = now_cache.get(b["ticker"])
        if p is None:
            p = _safe_now(b["ticker"])
            now_cache[b["ticker"]] = p
        if not p:
            ok = False
            break
        val_usd += (b["amount"] / b["buy_price"]) * p   # qty * текущая цена
    if ok:
        results.append({**_result("Портфель Без Б", invested_usd, val_usd,
                                   invested_rub, val_usd * rate_now), "is_me": True})

    # 2) Рыночные бенчмарки по исторической цене на дату покупки
    for tk, name in BENCHMARK_TICKERS:
        hist = get_daily_history(tk, start_iso)
        now = _safe_now(tk)
        if not hist or not now:
            continue
        v = 0.0
        for b in buys:
            d = datetime.utcfromtimestamp(b["ts"]).date().isoformat()
            pon = price_on_date(hist, d)
            if pon:
                v += b["amount"] / pon * now
        results.append(_result(name, invested_usd, v, invested_rub, v * rate_now))

    # 3) Доллар (просто держал USDT) — в USD 0%, в рублях растёт на курсе
    results.append(_result("Доллар (кэш)", invested_usd, invested_usd,
                           invested_rub, invested_usd * rate_now))

    # 4) Рублёвый вклад
    val_rub = 0.0
    for b in buys:
        years = max(0.0, (time.time() - b["ts"]) / (365.25 * 86400))
        val_rub += b["amount"] * (b["rate"] or rate_now) * ((1 + DEPOSIT_RATE_RUB) ** years)
    results.append({**_result(f"Вклад ₽ ({int(DEPOSIT_RATE_RUB*100)}%)",
                              invested_usd, None, invested_rub, val_rub)})

    # сортировка по рублёвой доходности (метрика аудитории)
    results.sort(key=lambda r: (r["ret_rub_pct"] is not None, r["ret_rub_pct"] or -1e9),
                 reverse=True)

    return {
        "results": results,
        "invested_usd": invested_usd,
        "invested_rub": invested_rub,
        "start": start_iso,
        "rate_now": rate_now,
    }
