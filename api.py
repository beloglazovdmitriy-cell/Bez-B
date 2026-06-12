"""HTTP API для Mini App «Без Б».

Тонкая обёртка над существующей бизнес-логикой (portfolio / quotes / benchmark).
Отдаёт данные в форме, которую ждёт фронт (см. miniapp/src/data.ts), поэтому
экраны подключаются без переделки.

Запуск (из папки проекта):
    .\.venv\Scripts\python.exe -m uvicorn api:app --port 8000 --reload

Авторизация: проверка Telegram initData (HMAC по токену бота). В dev включается
только если фронт прислал заголовок X-Init-Data; иначе работаем как «гость-владелец»
для удобства отладки в браузере.
"""
import hashlib
import hmac
import json
from datetime import datetime
from urllib.parse import parse_qsl

from fastapi import FastAPI, Header
from fastapi.middleware.cors import CORSMiddleware

import config
import portfolio
import benchmark

app = FastAPI(title="Bez B API")

# В dev фронт живёт на :5173, API на :8000 — разрешаем CORS.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Цвета активов для donut (совпадают с фронтом). Прочее — из палитры по кругу.
_COLORS = {
    "BTC": "#f7931a", "ETH": "#627eea", "TSLA": "#e82127", "NVDA": "#76b900",
    "GDX": "#d4af37", "SOL": "#14f195", "BNB": "#f3ba2f", "XRP": "#23292f",
    "SPY": "#2e7d32", "QQQ": "#5c6bc0", "AAPL": "#a2aaad",
}
_PALETTE = ["#26a69a", "#42a5f5", "#ab47bc", "#ff7043", "#26c6da", "#9ccc65"]


def _color(ticker: str, i: int) -> str:
    return _COLORS.get(ticker, _PALETTE[i % len(_PALETTE)])


# ───────────────────────── авторизация ─────────────────────────

def _verify_init_data(init_data: str) -> dict | None:
    """Проверить подпись Telegram initData. Вернуть данные пользователя или None."""
    try:
        pairs = dict(parse_qsl(init_data, strict_parsing=True))
        received_hash = pairs.pop("hash", None)
        if not received_hash:
            return None
        check = "\n".join(f"{k}={pairs[k]}" for k in sorted(pairs))
        secret = hmac.new(b"WebAppData", config.BOT_TOKEN.encode(), hashlib.sha256).digest()
        calc = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(calc, received_hash):
            return None
        return json.loads(pairs.get("user", "{}"))
    except Exception:
        return None


def _resolve_user(init_data: str | None) -> dict:
    """Кто перед нами. В dev без initData — считаем владельцем (для отладки)."""
    if init_data:
        user = _verify_init_data(init_data)
        if user:
            uid = user.get("id")
            return {
                "name": user.get("first_name", "Гость"),
                "isAdmin": uid == config.ADMIN_ID,
                "isPremium": False,  # позже — из подписки
            }
    return {"name": "Дмитрий", "isAdmin": True, "isPremium": False}


# ───────────────────────── эндпойнты ─────────────────────────

@app.get("/api/me")
def me(x_init_data: str | None = Header(default=None)):
    return _resolve_user(x_init_data)


@app.get("/api/summary")
def summary():
    s = portfolio.summary()
    positions = [
        {
            "ticker": p.ticker,
            "valueUsd": round(p.value_usd, 2),
            "avgPrice": round(p.avg_price_usdt, 2),
            "priceNow": round(p.price_now, 2),
            "profitPct": round(p.profit_pct, 1),
            "color": _color(p.ticker, i),
        }
        for i, p in enumerate(s["positions"])
    ]
    return {
        "totalUsd": round(s["total_value_usdt"], 2),
        "totalRub": round(s["value_rub"], 2),
        "profitUsdPct": round(s["profit_usdt_pct"], 1),
        "profitRubPct": round(s["profit_rub_pct"], 1),
        "index": round(s["index"], 1),
        "cashUsdt": round(s["usdt_cash"], 2),
        "positions": positions,
    }


@app.get("/api/history")
def history():
    import storage
    out = []
    for h in storage.load().get("history", []):
        out.append({
            "date": datetime.fromtimestamp(h["ts"]).strftime("%d.%m"),
            "value": round(h.get("value_rub", 0)),
            "invested": round(h.get("invested_rub", 0)),
            "index": round(h.get("index", 100), 1),
        })
    return out


@app.get("/api/journal")
def journal():
    s = portfolio.summary()
    pv = s["positions_value_usdt"] or 1
    shares = {p.ticker: p.value_usd / pv * 100 for p in s["positions"]}
    out = []
    for t in portfolio.get_operations():
        ttype = t.get("type") or t.get("side")
        if ttype not in ("buy", "sell"):
            continue
        price = t.get("price_usdt", t.get("price_usd"))
        amount = t.get("amount_usdt", t["qty"] * price)
        out.append({
            "date": datetime.fromtimestamp(t["ts"]).strftime("%d.%m"),
            "side": ttype,
            "ticker": t["ticker"],
            "amountUsd": round(amount),
            "price": round(price, 2),
            "sharePct": round(shares.get(t["ticker"], 0)),
            "reason": t.get("reason", ""),
        })
        if len(out) >= 20:
            break
    return out


@app.get("/api/compare")
def compare():
    c = benchmark.compare()
    if not c:
        return []
    return [
        {
            "name": r["name"],
            "retRubPct": round(r["ret_rub_pct"], 1) if r["ret_rub_pct"] is not None else 0.0,
            "isMe": bool(r.get("is_me")),
        }
        for r in c["results"]
    ]
