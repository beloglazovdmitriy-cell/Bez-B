"""Ядро портфеля «Без Б» — модель с USDT как базовым активом (кэшем).

Логика как в брокерском приложении:
  1. Пополнение: заводишь рубли -> покупаешь USDT по своему курсу (₽ за 1 USDT).
     USDT попадает в «денежные средства» (кэш).
  2. Покупка: за USDT покупаешь активы (BTC, ETH, акции). Кэш USDT уменьшается,
     появляется позиция со своей средней ценой в USDT.
  3. Продажа: актив -> обратно в USDT (кэш растёт).
  4. Вывод: USDT уходит из портфеля (уменьшает кэш и вложенную сумму).

Две валюты:
  invested_rub  — сколько рублей реально вложено (через покупку USDT по своим курсам)
  value_rub     — текущая стоимость всего портфеля в рублях по текущему курсу ЦБ
Декомпозиция рублёвой прибыли (точная, аддитивная):
  asset_gain_rub = (value_usdt - net_deposited_usdt) * rate_now   # заработок на активах
  fx_gain_rub    = net_deposited_usdt * (rate_now - avg_deposit_rate)  # на курсе
"""
import time
from dataclasses import dataclass

import storage
from quotes import get_price_usd, get_usd_rub

INDEX_BASE = 100.0   # стартовое значение индекса Без Б (в пунктах)


@dataclass
class Position:
    ticker: str
    qty: float
    avg_price_usdt: float   # средняя цена покупки в USDT
    cost_usdt: float        # вложено в позицию, USDT
    cost_rub: float         # вложено в позицию, ₽ (по курсам на моменты покупок)
    price_now: float        # текущая цена, USDT(≈USD)
    rate_now: float         # текущий курс USD/RUB

    @property
    def value_usd(self):     # имя value_usd сохранено для совместимости с charts
        return self.qty * self.price_now

    @property
    def value_rub(self):
        return self.value_usd * self.rate_now

    @property
    def profit_usdt(self):
        return self.value_usd - self.cost_usdt

    @property
    def profit_pct(self):
        return (self.profit_usdt / self.cost_usdt * 100) if self.cost_usdt else 0.0

    @property
    def profit_rub(self):
        return self.value_rub - self.cost_rub

    @property
    def avg_rate_buy(self):
        return (self.cost_rub / self.cost_usdt) if self.cost_usdt else self.rate_now

    @property
    def asset_gain_rub(self):
        return (self.value_usd - self.cost_usdt) * self.rate_now

    @property
    def fx_gain_rub(self):
        return self.cost_usdt * (self.rate_now - self.avg_rate_buy)


# ───────────────────────── запись операций ─────────────────────────

def _append(data, tx):
    tx["id"] = storage.next_trade_id(data)
    tx["ts"] = int(time.time())
    data["trades"].append(tx)
    storage.save(data)
    return tx


def _value_now_usdt():
    """Текущая стоимость портфеля (до выполняемой операции). None при сбое."""
    try:
        return summary()["total_value_usdt"]
    except Exception:
        return None


def _units_inflow(data, usdt, value_before=None):
    """Завод средств/актива: добавляем паи по текущей паевой стоимости (NAV не меняется)."""
    units = data.get("units", 0.0)
    if units <= 0:
        data["units"] = float(usdt)          # первый завод: NAV=1 -> индекс=100
        return
    if value_before is None:
        value_before = _value_now_usdt()
    nav = (value_before / units) if (value_before and value_before > 0) else 1.0
    data["units"] = units + usdt / nav


def _units_outflow(data, usdt):
    """Вывод средств: убираем паи по текущей NAV (индекс не меняется в момент вывода)."""
    units = data.get("units", 0.0)
    if units <= 0:
        return
    value_before = _value_now_usdt()
    nav = (value_before / units) if (value_before and value_before > 0) else 1.0
    data["units"] = max(0.0, units - usdt / nav)


def add_deposit(usdt: float, rate_rub: float) -> dict:
    """Пополнить кэш: купить `usdt` USDT по курсу `rate_rub` ₽ за 1 USDT."""
    data = storage.load()
    _units_inflow(data, float(usdt))
    return _append(data, {"type": "deposit", "usdt": float(usdt), "rate_rub": float(rate_rub)})


def add_withdraw(usdt: float) -> dict:
    """Вывести `usdt` USDT из портфеля."""
    data = storage.load()
    _units_outflow(data, float(usdt))
    return _append(data, {"type": "withdraw", "usdt": float(usdt)})


def market_buy(ticker: str, amount_usdt: float) -> dict:
    """Купить актив «по рынку» на `amount_usdt`. Если кэша USDT не хватает,
    недостающее считается заводом актива извне (перевод с биржи) — кэш не уходит
    в минус. Сохраняем курс на момент сделки для рублёвого учёта внешней части."""
    ticker = ticker.strip().upper()
    price = get_price_usd(ticker)
    qty = amount_usdt / price
    rate = get_usd_rub()
    # учёт паёв: нехватка кэша = завод актива извне (инфлоу по текущей NAV)
    try:
        sb = summary()
        cash_before, val_before = sb["usdt_cash"], sb["total_value_usdt"]
    except Exception:
        cash_before = val_before = None
    data = storage.load()
    if cash_before is not None:
        external = max(0.0, qty * price - max(cash_before, 0.0))
        if external > 1e-9:
            _units_inflow(data, external, val_before)
    tx = _append(data, {"type": "buy", "ticker": ticker, "qty": qty,
                        "price_usdt": price, "rate_rub": rate})
    tx["amount_usdt"] = amount_usdt
    return tx


def market_sell(ticker: str, amount_usdt=None) -> dict:
    """Продать «по рынку». amount_usdt=None -> продать всю позицию."""
    ticker = ticker.strip().upper()
    price = get_price_usd(ticker)
    if amount_usdt is None:
        pos = next((p for p in get_positions() if p.ticker == ticker), None)
        if not pos:
            raise ValueError(f"Нет открытой позиции по {ticker}")
        qty = pos.qty
    else:
        qty = amount_usdt / price
    rate = get_usd_rub()
    data = storage.load()
    tx = _append(data, {"type": "sell", "ticker": ticker, "qty": qty,
                        "price_usdt": price, "rate_rub": rate})
    tx["amount_usdt"] = amount_usdt if amount_usdt is not None else qty * price
    return tx


# ───────────────────────── расчёт состояния ─────────────────────────

def _replay(trades, rate_now):
    """Проиграть все операции по порядку. Прибыль считается по ОТКРЫТЫМ позициям
    (как в брокерском приложении), поэтому пустой портфель = строго ноль.
    У каждой позиции своя база в USDT и в рублях (по курсам на моменты покупок)."""
    usdt_cash = 0.0
    realized_usdt = 0.0   # накопленный реализованный доход, USDT
    realized_rub = 0.0    # то же в рублях (по курсу на момент продажи)
    book = {}   # ticker -> {qty, cost_usdt, cost_rub}

    for t in sorted(trades, key=lambda x: x["ts"]):
        ttype = t.get("type") or t.get("side")
        if ttype == "deposit":
            usdt_cash += t["usdt"]
        elif ttype == "withdraw":
            usdt_cash -= min(t["usdt"], usdt_cash)   # кэш не уходит в минус
        elif ttype == "buy":
            price = t.get("price_usdt", t.get("price_usd"))
            rate_buy = t.get("rate_rub", rate_now)
            cost = t["qty"] * price
            # списываем из кэша только что есть; нехватка = завод актива извне
            usdt_cash -= min(cost, max(usdt_cash, 0.0))
            b = book.setdefault(t["ticker"], {"qty": 0.0, "cost_usdt": 0.0, "cost_rub": 0.0})
            b["qty"] += t["qty"]
            b["cost_usdt"] += cost
            b["cost_rub"] += cost * rate_buy
        elif ttype == "sell":
            price = t.get("price_usdt", t.get("price_usd"))
            rate_sell = t.get("rate_rub", rate_now)
            b = book.get(t["ticker"])
            if not b or b["qty"] <= 0:
                continue
            sell_qty = min(t["qty"], b["qty"])
            frac = sell_qty / b["qty"]
            sold_cost_usdt = b["cost_usdt"] * frac
            sold_cost_rub = b["cost_rub"] * frac
            proceeds = sell_qty * price
            # фиксируем реализованный доход
            realized_usdt += proceeds - sold_cost_usdt
            realized_rub += proceeds * rate_sell - sold_cost_rub
            b["cost_usdt"] -= sold_cost_usdt           # уменьшаем базу пропорционально
            b["cost_rub"] -= sold_cost_rub
            b["qty"] -= sell_qty
            usdt_cash += proceeds                       # выручка в кэш

    book = {tk: b for tk, b in book.items() if b["qty"] > 1e-9}
    return usdt_cash, book, realized_usdt, realized_rub


def _safe_price(ticker, fallback):
    """Цена с устойчивостью к сбою источника: живая -> последняя известная ->
    средняя цена покупки. Портфель из-за котировки никогда не падает."""
    try:
        return get_price_usd(ticker, allow_stale=True)
    except Exception:
        return fallback


def _build_positions(book, rate_now):
    positions = []
    for ticker, b in book.items():
        avg = b["cost_usdt"] / b["qty"]
        positions.append(Position(
            ticker=ticker, qty=b["qty"], avg_price_usdt=avg,
            cost_usdt=b["cost_usdt"], cost_rub=b["cost_rub"],
            price_now=_safe_price(ticker, avg), rate_now=rate_now,
        ))
    positions.sort(key=lambda p: p.value_usd, reverse=True)
    return positions


def get_positions():
    """Список открытых позиций (без кэша USDT) с рыночной оценкой."""
    data = storage.load()
    rate_now = get_usd_rub()
    usdt_cash, book, _, _ = _replay(data["trades"], rate_now)
    return _build_positions(book, rate_now)


def summary():
    """Сводка по портфелю. Прибыль — по открытым позициям; кэш отдельно."""
    data = storage.load()
    rate_now = get_usd_rub()
    usdt_cash, book, realized_usdt, realized_rub = _replay(data["trades"], rate_now)
    positions = _build_positions(book, rate_now)

    positions_value = sum(p.value_usd for p in positions)
    cost_usdt = sum(p.cost_usdt for p in positions)
    cost_rub = sum(p.cost_rub for p in positions)
    profit_usdt = sum(p.profit_usdt for p in positions)
    profit_rub = sum(p.profit_rub for p in positions)
    asset_gain_rub = sum(p.asset_gain_rub for p in positions)
    fx_gain_rub = sum(p.fx_gain_rub for p in positions)
    total_value_usdt = usdt_cash + positions_value
    units = data.get("units", 0.0)
    index = (INDEX_BASE * total_value_usdt / units) if units > 0 else INDEX_BASE

    return {
        "positions": positions,
        "usdt_cash": usdt_cash,
        "rate_now": rate_now,
        "units": units,
        "index": index,
        "positions_value_usdt": positions_value,
        "cost_usdt": cost_usdt,
        "cost_rub": cost_rub,
        "avg_deposit_rate": (cost_rub / cost_usdt) if cost_usdt else rate_now,
        "total_value_usdt": total_value_usdt,
        "value_rub": total_value_usdt * rate_now,
        "profit_usdt": profit_usdt,
        "profit_usdt_pct": (profit_usdt / cost_usdt * 100) if cost_usdt else 0.0,
        "profit_rub": profit_rub,
        "profit_rub_pct": (profit_rub / cost_rub * 100) if cost_rub else 0.0,
        "asset_gain_rub": asset_gain_rub,
        "fx_gain_rub": fx_gain_rub,
        "realized_usdt": realized_usdt,
        "realized_rub": realized_rub,
    }


def pie_slices(s):
    """Доли для круговой диаграммы: позиции + кэш USDT. Список (label, value)."""
    slices = [(p.ticker, p.value_usd) for p in s["positions"]]
    if s["usdt_cash"] > 1e-9:
        slices.append(("USDT (кэш)", s["usdt_cash"]))
    return slices


def get_operations():
    """Все операции (новые сверху) для экрана управления/удаления."""
    data = storage.load()
    return sorted(data["trades"], key=lambda x: x["ts"], reverse=True)


def get_operation(tx_id: int):
    data = storage.load()
    return next((t for t in data["trades"] if t["id"] == tx_id), None)


def set_reason(tx_id: int, reason: str):
    """Записать причину к сделке (журнал решений)."""
    data = storage.load()
    for t in data["trades"]:
        if t["id"] == tx_id:
            t["reason"] = reason
            storage.save(data)
            return t
    return None


def delete_tx(tx_id: int):
    """Удалить любую операцию по id (пополнение/покупка/продажа/вывод).
    Возвращает удалённую операцию или None."""
    data = storage.load()
    target = next((t for t in data["trades"] if t["id"] == tx_id), None)
    if target is None:
        return None
    data["trades"] = [t for t in data["trades"] if t["id"] != tx_id]
    storage.save(data)
    return target


# ───────────────────────── избранное ─────────────────────────

def get_favorites():
    return storage.load().get("favorites", [])


def add_favorite(ticker: str) -> bool:
    ticker = ticker.strip().upper()
    data = storage.load()
    favs = data.setdefault("favorites", [])
    if ticker in favs:
        return False
    favs.append(ticker)
    storage.save(data)
    return True


def remove_favorite(ticker: str) -> bool:
    ticker = ticker.strip().upper()
    data = storage.load()
    favs = data.setdefault("favorites", [])
    if ticker not in favs:
        return False
    favs.remove(ticker)
    storage.save(data)
    return True


def record_snapshot():
    """Записать текущую стоимость портфеля в историю (для графика роста)."""
    s = summary()
    data = storage.load()
    data["history"].append({
        "ts": int(time.time()),
        "value_usd": round(s["total_value_usdt"], 2),
        "value_rub": round(s["value_rub"], 2),
        "invested_rub": round(s["cost_rub"], 2),
        "index": round(s["index"], 2),
    })
    storage.save(data)
    return s
