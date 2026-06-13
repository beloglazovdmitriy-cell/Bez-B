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
import os
from datetime import datetime
from urllib.parse import parse_qsl

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import config
import portfolio
import benchmark
import storage
import ai

app = FastAPI(title="Bez B API")

# В dev без initData считаем клиента владельцем (удобно тестировать в браузере).
# Перед публичным деплоем задать API_DEV_ADMIN=0 — тогда писать сможет только
# тот, чей валидный initData даёт id == ADMIN_ID.
_DEV_ADMIN = os.getenv("API_DEV_ADMIN", "1") == "1"

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
    """Проверить подпись Telegram initData (HMAC по токену). Вернуть user или None.

    Новые клиенты добавляют поле `signature` (для отдельной ed25519-проверки),
    которое не входит в HMAC data_check_string — поэтому пробуем оба варианта."""
    try:
        pairs = dict(parse_qsl(init_data))
        received_hash = pairs.pop("hash", None)
        if not received_hash:
            print("[auth] no hash; keys=", sorted(pairs), flush=True)
            return None
        secret = hmac.new(b"WebAppData", config.BOT_TOKEN.encode(), hashlib.sha256).digest()

        def _calc(d):
            check = "\n".join(f"{k}={d[k]}" for k in sorted(d))
            return hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()

        candidates = [pairs]
        if "signature" in pairs:
            no_sig = {k: v for k, v in pairs.items() if k != "signature"}
            candidates.append(no_sig)
        for d in candidates:
            if hmac.compare_digest(_calc(d), received_hash):
                return json.loads(pairs.get("user", "{}"))
        print("[auth] hash mismatch; keys=", sorted(pairs), flush=True)
        return None
    except Exception as e:
        print("[auth] error:", e, flush=True)
        return None


def _resolve_user(init_data: str | None) -> dict:
    """Кто перед нами. В dev без initData — владелец (если _DEV_ADMIN)."""
    if init_data:
        user = _verify_init_data(init_data)
        if user:
            uid = user.get("id")
            return {
                "id": uid,
                "name": user.get("first_name", "Гость"),
                "isAdmin": uid == config.ADMIN_ID,
                "isPremium": False,  # позже — из подписки
            }
    return {"id": config.ADMIN_ID if _DEV_ADMIN else None,
            "name": "Дмитрий", "isAdmin": _DEV_ADMIN, "isPremium": False}


def _ctx(p: str, init_data: str | None, write: bool = False) -> str:
    """Выбрать портфель по запросу и установить его как текущий в storage.

    p="bezb" — публичный (читать всем; писать только владельцу).
    p="me"   — личный портфель пользователя (нужна авторизация Telegram).
    Возвращает uid; кидает 401/403 при отсутствии прав."""
    user = _resolve_user(init_data)
    if p == "me":
        uid = user.get("id")
        if uid is None:
            raise HTTPException(status_code=401, detail="Откройте приложение через Telegram")
        target = f"u{uid}"
    else:  # bezb
        if write and not user["isAdmin"]:
            raise HTTPException(status_code=403,
                                detail="Портфель «Без Б» может менять только владелец")
        target = "bezb"
    storage.use_uid(target)
    return target


# ───────────────────────── эндпойнты ─────────────────────────

@app.get("/api/me")
def me(x_init_data: str | None = Header(default=None)):
    u = _resolve_user(x_init_data)
    u["isSubscribed"] = storage.is_subscriber(u.get("id"))
    return u


def _notify_bezb_trade(p: str, txid):
    """Фоном разослать пуш подписчикам о сделке публичного портфеля Без Б."""
    if p != "bezb":
        return
    try:
        tx = portfolio.get_operation(txid)  # uid ещё = bezb (контекст запроса)
    except Exception:
        tx = None
    if not tx:
        return
    import threading
    import notify
    threading.Thread(target=notify.notify_trade, args=(tx,), daemon=True).start()


def _summary_payload() -> dict:
    s = portfolio.summary()
    positions = [
        {
            "ticker": p.ticker,
            "qty": round(p.qty, 8),
            "valueUsd": round(p.value_usd, 2),
            "avgPrice": round(p.avg_price_usdt, 4),
            "priceNow": round(p.price_now, 4),
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


@app.get("/api/summary")
def summary(p: str = "bezb", x_init_data: str | None = Header(default=None)):
    _ctx(p, x_init_data)
    return _summary_payload()


# ──────────────── пишущие операции ────────────────
# p="bezb" — только владелец; p="me" — свой портфель (любой авторизованный)

class BuyReq(BaseModel):
    ticker: str
    amountUsdt: float
    reason: str | None = None


class SellReq(BaseModel):
    ticker: str
    amountUsdt: float | None = None  # None → продать всю позицию
    reason: str | None = None


class DepositReq(BaseModel):
    rub: float
    rate: float


class WithdrawReq(BaseModel):
    amountUsdt: float


class AssetDepositReq(BaseModel):
    ticker: str
    amountUsdt: float
    price: float | None = None      # цена входа; по умолчанию рыночная
    reason: str | None = None


def _ok():
    # фиксируем точку стоимости на каждой операции — чтобы график роста и индекс
    # наполнялись по ходу сделок (а не только недельными автоснимками)
    try:
        portfolio.record_snapshot()
    except Exception:
        pass
    return {"ok": True, "summary": _summary_payload()}


@app.post("/api/buy")
def api_buy(req: BuyReq, p: str = "bezb", x_init_data: str | None = Header(default=None)):
    _ctx(p, x_init_data, write=True)
    try:
        tx = portfolio.market_buy(req.ticker, req.amountUsdt)
        if req.reason:
            portfolio.set_reason(tx["id"], req.reason)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    _notify_bezb_trade(p, tx["id"])
    return _ok()


@app.post("/api/sell")
def api_sell(req: SellReq, p: str = "bezb", x_init_data: str | None = Header(default=None)):
    _ctx(p, x_init_data, write=True)
    try:
        tx = portfolio.market_sell(req.ticker, req.amountUsdt)
        if req.reason:
            portfolio.set_reason(tx["id"], req.reason)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    _notify_bezb_trade(p, tx["id"])
    return _ok()


@app.post("/api/deposit")
def api_deposit(req: DepositReq, p: str = "bezb", x_init_data: str | None = Header(default=None)):
    _ctx(p, x_init_data, write=True)
    if req.rate <= 0:
        raise HTTPException(status_code=400, detail="Курс должен быть > 0")
    portfolio.add_deposit(req.rub / req.rate, req.rate)
    return _ok()


@app.post("/api/withdraw")
def api_withdraw(req: WithdrawReq, p: str = "bezb", x_init_data: str | None = Header(default=None)):
    _ctx(p, x_init_data, write=True)
    portfolio.add_withdraw(req.amountUsdt)
    return _ok()


@app.post("/api/deposit_asset")
def api_deposit_asset(req: AssetDepositReq, p: str = "bezb", x_init_data: str | None = Header(default=None)):
    _ctx(p, x_init_data, write=True)
    try:
        tx = portfolio.add_asset_deposit(req.ticker, req.amountUsdt, req.price)
        if req.reason:
            portfolio.set_reason(tx["id"], req.reason)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    _notify_bezb_trade(p, tx["id"])
    return _ok()


@app.get("/api/history")
def history(p: str = "bezb", x_init_data: str | None = Header(default=None)):
    _ctx(p, x_init_data)
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
def journal(p: str = "bezb", x_init_data: str | None = Header(default=None)):
    _ctx(p, x_init_data)
    s = portfolio.summary()
    pv = s["positions_value_usdt"] or 1
    shares = {pos.ticker: pos.value_usd / pv * 100 for pos in s["positions"]}
    out = []
    for t in portfolio.get_operations():
        ttype = t.get("type") or t.get("side")
        date = datetime.fromtimestamp(t["ts"]).strftime("%d.%m")
        # ввод/вывод кэша = покупка/вывод USDT
        if ttype in ("deposit", "withdraw"):
            usdt = float(t.get("usdt", 0))
            rate = t.get("rate_rub")
            reason = t.get("reason", "")
            if not reason and ttype == "deposit" and rate:
                reason = f"по курсу {rate:.2f} ₽".replace(".", ",")
            out.append({
                "id": t["id"], "date": date,
                "side": ttype,                      # "deposit" | "withdraw"
                "ticker": "USDT",
                "qty": round(usdt, 2),
                "amountUsd": round(usdt),
                "price": 1.0,
                "sharePct": 0,
                "reason": reason,
            })
        elif ttype in ("buy", "sell", "asset_deposit"):
            price = t.get("price_usdt", t.get("price_usd"))
            amount = t.get("amount_usdt", t["qty"] * price)
            out.append({
                "id": t["id"], "date": date,
                "side": "sell" if ttype == "sell" else "buy",
                "ticker": t["ticker"],
                "qty": round(t["qty"], 8),
                "amountUsd": round(amount),
                "price": round(price, 6),
                "sharePct": round(shares.get(t["ticker"], 0)),
                "reason": t.get("reason", ""),
            })
        else:
            continue
        if len(out) >= 20:
            break
    return out


def _ai_portfolio_data(p: str) -> dict:
    """Компактные данные текущего портфеля (uid уже установлен) для AI."""
    s = portfolio.summary()
    pv = s["positions_value_usdt"] or 1
    return {
        "label": "публичный портфель «Без Б»" if p != "me" else "ваш портфель",
        "totalUsd": s["total_value_usdt"], "totalRub": s["value_rub"],
        "profitRubPct": s["profit_rub_pct"], "profitUsdPct": s["profit_usdt_pct"],
        "index": s["index"], "cashUsdt": s["usdt_cash"],
        "positions": [{
            "ticker": pos.ticker, "weightPct": pos.value_usd / pv * 100,
            "profitPct": pos.profit_pct, "avgPrice": round(pos.avg_price_usdt, 4),
            "priceNow": round(pos.price_now, 4),
        } for pos in s["positions"]],
    }


def _ai_or_503():
    if not ai.available():
        raise HTTPException(status_code=503,
                            detail="AI появится после подключения ключа Claude API")


@app.post("/api/analyze")
def analyze(p: str = "bezb", x_init_data: str | None = Header(default=None)):
    """AI-разбор выбранного портфеля."""
    _ctx(p, x_init_data)
    _ai_or_503()
    try:
        text = ai.analyze_portfolio(_ai_portfolio_data(p))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI временно недоступен: {e}")
    return {"text": text}


@app.post("/api/scenarios")
def scenarios(p: str = "bezb", x_init_data: str | None = Header(default=None)):
    """AI-сценарии «что если рынок дёрнется» по выбранному портфелю."""
    _ctx(p, x_init_data)
    _ai_or_503()
    try:
        text = ai.scenarios(_ai_portfolio_data(p))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI временно недоступен: {e}")
    return {"text": text}


@app.post("/api/digest")
def digest(x_init_data: str | None = Header(default=None)):
    """AI-дайджест рынка (веб-поиск) → черновик в канал. Только владелец."""
    if not _resolve_user(x_init_data)["isAdmin"]:
        raise HTTPException(status_code=403, detail="Только владелец")
    _ai_or_503()
    storage.use_uid("bezb")
    s = portfolio.summary()
    pv = s["positions_value_usdt"] or 1
    ctx = (f"Баланс {s['value_rub']:,.0f}₽, индекс Без Б {s['index']:.0f} пт. "
           "Позиции: " + (", ".join(f"{pos.ticker} {pos.value_usd / pv * 100:.0f}%"
                                    for pos in s["positions"]) or "только кэш")).replace(",", " ")
    try:
        text = ai.market_digest(ctx)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI временно недоступен: {e}")
    return {"text": text}


@app.post("/api/trade_comment")
def trade_comment(id: int, p: str = "bezb", x_init_data: str | None = Header(default=None)):
    """AI-черновик поста в канал по конкретной сделке (только владелец для Без Б)."""
    _ctx(p, x_init_data, write=True)
    if not ai.available():
        raise HTTPException(status_code=503,
                            detail="AI появится после подключения ключа Claude API")
    tx = portfolio.get_operation(id)
    ttype = (tx or {}).get("type") or (tx or {}).get("side")
    if not tx or ttype not in ("buy", "sell", "asset_deposit"):
        raise HTTPException(status_code=404, detail="Сделка не найдена")
    s = portfolio.summary()
    pv = s["positions_value_usdt"] or 1
    share = next((pos.value_usd / pv * 100 for pos in s["positions"] if pos.ticker == tx["ticker"]), 0)
    price = tx.get("price_usdt", tx.get("price_usd"))
    data = {
        "side": "sell" if ttype == "sell" else "buy",
        "ticker": tx["ticker"], "qty": tx["qty"],
        "amountUsd": tx.get("amount_usdt", tx["qty"] * price), "price": price,
        "sharePct": share, "reason": tx.get("reason", ""),
    }
    try:
        text = ai.analyze_trade(data)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI временно недоступен: {e}")
    return {"text": text}


class PublishReq(BaseModel):
    text: str


class TopicReq(BaseModel):
    topic: str


def _cta_kb():
    return {"inline_keyboard": [[{"text": "📈 Открыть Без Б", "url": config.BOT_URL}]]}


def _channel_post(text: str, chart: bytes | None = None):
    """Опубликовать в канал: опц. график (фото) + текст с CTA-кнопкой."""
    import requests
    base = f"https://api.telegram.org/bot{config.BOT_TOKEN}"
    if chart:
        try:
            requests.post(f"{base}/sendPhoto", data={"chat_id": config.CHANNEL_ID},
                          files={"photo": ("bezb.png", chart, "image/png")}, timeout=25)
        except Exception:
            pass  # без графика не критично
    r = requests.post(f"{base}/sendMessage", json={
        "chat_id": config.CHANNEL_ID, "text": text, "reply_markup": _cta_kb()}, timeout=20)
    if not r.json().get("ok"):
        raise RuntimeError(r.text)


def _chart_for(kind: str) -> bytes | None:
    """Подобрать график под рубрику (портфель Без Б)."""
    try:
        import charts
        if kind == "custom":
            return None
        if kind == "crowd":
            import market_mood
            f = market_mood.snapshot().get("fng")
            return charts.fear_greed_gauge(f["value"], f.get("label_ru", "")) if f else None
        storage.use_uid("bezb")
        s = portfolio.summary()
        if kind in ("scenarios", "trade", "portfolio"):
            return charts.composition_pie(portfolio.pie_slices(s))
        return charts.index_line()
    except Exception:
        return None


def _require_owner(init_data):
    if not _resolve_user(init_data)["isAdmin"]:
        raise HTTPException(status_code=403, detail="Только владелец")


@app.post("/api/publish")
def publish(req: PublishReq, x_init_data: str | None = Header(default=None)):
    """Опубликовать текст в канал (только владелец)."""
    _require_owner(x_init_data)
    if not config.CHANNEL_ID:
        raise HTTPException(status_code=400, detail="Канал не подключён (задай CHANNEL_ID)")
    try:
        _channel_post(req.text)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Не удалось опубликовать: {e}")
    return {"ok": True}


# ──────────── Контент-студия (очередь черновиков, только владелец) ────────────

def _bezb_digest_ctx() -> str:
    storage.use_uid("bezb")
    s = portfolio.summary()
    pv = s["positions_value_usdt"] or 1
    return (f"Баланс {s['value_rub']:,.0f}₽, индекс Без Б {s['index']:.0f} пт. Позиции: "
            + (", ".join(f"{p.ticker} {p.value_usd / pv * 100:.0f}%" for p in s["positions"])
               or "только кэш")).replace(",", " ")


@app.post("/api/content/generate")
def content_generate(kind: str, x_init_data: str | None = Header(default=None)):
    _require_owner(x_init_data)
    _ai_or_503()
    try:
        if kind == "digest":
            text = ai.market_digest(_bezb_digest_ctx())
        elif kind == "scenarios":
            storage.use_uid("bezb")
            text = ai.scenarios(_ai_portfolio_data("bezb"))
        elif kind == "crowd":
            import market_mood
            text = ai.crowd_post(market_mood.context())
        elif kind in ("edu", "manifest", "bullshit"):
            text = ai.content_post(kind)
        else:
            raise HTTPException(status_code=400, detail="неизвестная рубрика")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI временно недоступен: {e}")
    return storage.add_draft(kind, text)


@app.post("/api/content/custom")
def content_custom(req: TopicReq, x_init_data: str | None = Header(default=None)):
    """Создать черновик по своей теме/задаче (только владелец)."""
    _require_owner(x_init_data)
    _ai_or_503()
    topic = (req.topic or "").strip()
    if not topic:
        raise HTTPException(status_code=400, detail="Пустая тема")
    try:
        text = ai.custom_post(topic)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI временно недоступен: {e}")
    return storage.add_draft("custom", text)


REACTIONS = ["🔥", "👍", "🤔"]


def _reaction_uid(init_data: str | None) -> str:
    """Стабильный uid для реакций: telegram id или 'anon' (dev/вне Telegram)."""
    uid = _resolve_user(init_data).get("id")
    return f"u{uid}" if uid else "anon"


@app.get("/api/feed")
def feed(x_init_data: str | None = Header(default=None)):
    """Лента опубликованных постов с реакциями (публично)."""
    posts = storage.list_published()
    uid = _reaction_uid(x_init_data)
    rmap = storage.reactions_for([p["id"] for p in posts], uid)
    for p in posts:
        r = rmap.get(p["id"], {"counts": {}, "mine": []})
        p["reactions"] = r["counts"]
        p["mine"] = r["mine"]
    return posts


class ReactReq(BaseModel):
    post_id: int
    emoji: str


@app.post("/api/feed/react")
def feed_react(req: ReactReq, x_init_data: str | None = Header(default=None)):
    """Поставить/снять реакцию (любой пользователь Telegram)."""
    if req.emoji not in REACTIONS:
        raise HTTPException(status_code=400, detail="Недопустимая реакция")
    uid = _reaction_uid(x_init_data)
    storage.toggle_reaction(req.post_id, uid, req.emoji)
    r = storage.reactions_for([req.post_id], uid).get(
        req.post_id, {"counts": {}, "mine": []})
    return r


@app.get("/api/home")
def home():
    """Сводка «Главная»: гейдж страха/жадности + последний дайджест +
    что сделал Без Б сегодня. Публично, для домашнего блока Mini App."""
    # 1) Индекс страха и жадности
    mood = None
    try:
        import market_mood
        f = market_mood.snapshot().get("fng")
        if f:
            arrow = "up" if f["value"] > f["prev"] else "down" if f["value"] < f["prev"] else "flat"
            mood = {"value": f["value"], "label": f["label_ru"],
                    "prev": f["prev"], "trend": arrow}
    except Exception:
        pass
    # 2) «Рынок за 60 сек» — последний опубликованный дайджест из ленты
    digest = None
    try:
        for d in storage.list_published():
            if d.get("kind") == "digest":
                digest = {"id": d["id"], "ts": d["ts"], "text": d["text"]}
                break
    except Exception:
        pass
    # 3) Что сделал Без Б сегодня (последняя сделка публичного портфеля)
    today_trade = None
    try:
        storage.use_uid("bezb")
        ops = portfolio.get_operations()
        for t in ops:
            ttype = t.get("type") or t.get("side")
            if ttype not in ("buy", "sell", "asset_deposit"):
                continue
            price = t.get("price_usdt", t.get("price_usd")) or 0
            amount = t.get("amount_usdt", t["qty"] * price)
            d = datetime.fromtimestamp(t["ts"])
            today_trade = {
                "side": "sell" if ttype == "sell" else "buy",
                "ticker": t["ticker"],
                "amountUsd": round(amount),
                "date": d.strftime("%d.%m"),
                "isToday": d.date() == datetime.now().date(),
                "reason": t.get("reason", ""),
            }
            break
    except Exception:
        pass
    return {"mood": mood, "digest": digest, "bezbToday": today_trade}


@app.get("/api/sandbox/dca")
def sandbox_dca(ticker: str = "BTC", amount: float = 50, years: float = 2):
    """DCA-песочница: бэктест взносов по $amount каждые 2 недели (крипта). Публично."""
    if amount <= 0 or years <= 0:
        raise HTTPException(status_code=400, detail="Неверные параметры")
    try:
        import sandbox
        res = sandbox.simulate(ticker, amount, years)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Нет данных истории: {e}")
    if not res:
        raise HTTPException(status_code=404, detail=f"Нет истории по {ticker} (только крипта)")
    return res


@app.get("/api/dca")
def dca(x_init_data: str | None = Header(default=None)):
    """Состояние стрика дисциплины DCA пользователя."""
    uid = _resolve_user(x_init_data).get("id")
    if not uid:
        return {"streak": 0, "longest": 0, "total": 0, "lastTs": None,
                "canCheckIn": False, "nextInDays": 0, "atRisk": False, "anon": True}
    return storage.dca_get(f"u{uid}")


@app.post("/api/dca/checkin")
def dca_checkin(x_init_data: str | None = Header(default=None)):
    """Отметить DCA-взнос (наращивает серию). Нужна авторизация Telegram."""
    uid = _resolve_user(x_init_data).get("id")
    if not uid:
        raise HTTPException(status_code=401, detail="Откройте приложение из Telegram")
    return storage.dca_checkin(f"u{uid}")


@app.post("/api/subscribe")
def subscribe(x_init_data: str | None = Header(default=None)):
    """Подписаться на мгновенные пуши о сделках Без Б (нужна авторизация Telegram)."""
    uid = _resolve_user(x_init_data).get("id")
    if not uid:
        raise HTTPException(status_code=401, detail="Откройте приложение из Telegram")
    storage.add_subscriber(uid)
    return {"ok": True, "isSubscribed": True}


@app.post("/api/unsubscribe")
def unsubscribe(x_init_data: str | None = Header(default=None)):
    uid = _resolve_user(x_init_data).get("id")
    if not uid:
        raise HTTPException(status_code=401, detail="Откройте приложение из Telegram")
    storage.remove_subscriber(uid)
    return {"ok": True, "isSubscribed": False}


@app.get("/api/content/drafts")
def content_drafts(x_init_data: str | None = Header(default=None)):
    _require_owner(x_init_data)
    return storage.list_drafts()


@app.post("/api/content/publish")
def content_publish(id: int, x_init_data: str | None = Header(default=None)):
    _require_owner(x_init_data)
    if not config.CHANNEL_ID:
        raise HTTPException(status_code=400, detail="Канал не подключён")
    d = storage.get_draft(id)
    if not d:
        raise HTTPException(status_code=404, detail="Черновик не найден")
    try:
        _channel_post(d["text"], _chart_for(d["kind"]))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Не удалось опубликовать: {e}")
    storage.set_draft_status(id, "published")
    return {"ok": True}


@app.post("/api/content/update")
def content_update(id: int, req: PublishReq, x_init_data: str | None = Header(default=None)):
    """Сохранить отредактированный текст черновика (только владелец)."""
    _require_owner(x_init_data)
    if not storage.get_draft(id):
        raise HTTPException(status_code=404, detail="Черновик не найден")
    storage.update_draft(id, req.text)
    return {"ok": True}


@app.post("/api/content/delete")
def content_delete(id: int, x_init_data: str | None = Header(default=None)):
    _require_owner(x_init_data)
    storage.delete_draft(id)
    return {"ok": True}


@app.get("/api/compare")
def compare(p: str = "bezb", x_init_data: str | None = Header(default=None)):
    _ctx(p, x_init_data)
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
