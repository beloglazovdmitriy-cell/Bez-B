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

from fastapi import FastAPI, File, Header, HTTPException, Request, UploadFile
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
            uname = (user.get("username") or "").lower()
            is_admin = uid == config.ADMIN_ID or storage.is_admin_username(uname)
            return {
                "id": uid,
                "name": user.get("first_name", "Гость"),
                "isAdmin": is_admin,
                "isPremium": is_admin or storage.is_premium(f"u{uid}"),
                "premiumUntil": storage.premium_until(f"u{uid}"),
            }
    return {"id": config.ADMIN_ID if _DEV_ADMIN else None,
            "name": "Дмитрий", "isAdmin": _DEV_ADMIN,
            "isPremium": _DEV_ADMIN, "premiumUntil": 0}


def _ctx(p: str, init_data: str | None, write: bool = False) -> str:
    """Выбрать портфель по запросу и установить его как текущий в storage.

    p="bezb" — публичный (читать всем; писать только владельцу).
    p="me"   — личный портфель пользователя (нужна авторизация Telegram).
    Возвращает uid; кидает 401/403 при отсутствии прав."""
    user = _resolve_user(init_data)
    if p in ("me", "fantasy"):
        uid = user.get("id")
        if uid is None:
            raise HTTPException(status_code=401, detail="Откройте приложение через Telegram")
        target = f"u{uid}" if p == "me" else f"f{uid}"
    else:  # bezb
        if write and not user["isAdmin"]:
            raise HTTPException(status_code=403,
                                detail="Портфель «Без Б» может менять только владелец")
        target = "bezb"
    storage.use_uid(target)
    return target


# ───────────────────────── эндпойнты ─────────────────────────

def _premium_price(uid) -> tuple[int, str]:
    """Цена премиума для пользователя: (рубли, тариф 'eb'|'reg').
    Early-bird (490 ₽) — для уже-early-bird и пока есть свободные слоты."""
    fid = f"u{uid}" if uid else ""
    if uid and storage.is_early_bird(fid):
        return config.PREMIUM_EARLYBIRD_RUB, "eb"
    if storage.early_bird_count() < config.PREMIUM_EARLYBIRD_LIMIT:
        return config.PREMIUM_EARLYBIRD_RUB, "eb"
    return config.PREMIUM_PRICE_RUB, "reg"


@app.get("/api/me")
def me(x_init_data: str | None = Header(default=None)):
    u = _resolve_user(x_init_data)
    uid = u.get("id")
    u["isSubscribed"] = storage.is_subscriber(uid)
    price, tier = _premium_price(uid)
    u["premiumPrice"] = price
    u["premiumEarlyBird"] = tier == "eb"
    u["earlyBirdLeft"] = max(0, config.PREMIUM_EARLYBIRD_LIMIT - storage.early_bird_count())
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
    """AI-разбор портфеля. Публичный Без Б — бесплатно (витрина); свой — премиум."""
    _ctx(p, x_init_data)
    if p == "me":
        _require_premium(x_init_data, "AI-разбор своего портфеля")
    _ai_or_503()
    try:
        text = ai.analyze_portfolio(_ai_portfolio_data(p))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI временно недоступен: {e}")
    return {"text": text}


@app.post("/api/scenarios")
def scenarios(p: str = "bezb", x_init_data: str | None = Header(default=None)):
    """AI-сценарии «что если рынок дёрнется». Свой портфель — премиум."""
    _ctx(p, x_init_data)
    if p == "me":
        _require_premium(x_init_data, "AI-сценарии по своему портфелю")
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
    cta: bool = True              # прикреплять ли кнопку-ссылку на бота
    chartKind: str | None = None  # если задано — приложить график рубрики


class TopicReq(BaseModel):
    topic: str


def _cta_kb():
    # прямой вход в мини-апп с меткой источника «channel» — чтобы считать
    # переходы из канала (приложение фиксирует start_param при открытии).
    url = f"https://t.me/{config.BOT_USERNAME}?startapp=src_channel"
    return {"inline_keyboard": [[{"text": "📈 Открыть Без Б", "url": url}]]}


def _channel_post(text: str, chart: bytes | None = None, cta: bool = True):
    """Опубликовать в канал. chart — фото (график/картинка); cta — кнопка на бота.

    Если есть фото и текст влезает в подпись (<=1024) — публикуем ОДНИМ постом
    (фото с подписью), иначе фото отдельно + текст. Кнопка-ссылка на бота
    добавляется по флагу cta.
    """
    import requests
    base = f"https://api.telegram.org/bot{config.BOT_TOKEN}"
    kb = _cta_kb() if cta else None
    if chart and len(text) <= 1024:
        r = requests.post(f"{base}/sendPhoto",
                          data={"chat_id": config.CHANNEL_ID, "caption": text,
                                **({"reply_markup": json.dumps(kb)} if kb else {})},
                          files={"photo": ("bezb.png", chart, "image/png")}, timeout=30)
        if not r.json().get("ok"):
            raise RuntimeError(r.text)
        return
    if chart:
        try:
            requests.post(f"{base}/sendPhoto", data={"chat_id": config.CHANNEL_ID},
                          files={"photo": ("bezb.png", chart, "image/png")}, timeout=30)
        except Exception:
            pass  # без графика не критично
    payload = {"chat_id": config.CHANNEL_ID, "text": text}
    if kb:
        payload["reply_markup"] = kb
    r = requests.post(f"{base}/sendMessage", json=payload, timeout=20)
    if not r.json().get("ok"):
        raise RuntimeError(r.text)


def _channel_poll(question: str, options: list):
    """Опубликовать нативный Telegram-опрос в канал (sendPoll)."""
    import requests
    base = f"https://api.telegram.org/bot{config.BOT_TOKEN}"
    opts = [{"text": str(o)[:90]} for o in options][:4]
    r = requests.post(f"{base}/sendPoll", json={
        "chat_id": config.CHANNEL_ID, "question": str(question)[:250],
        "options": opts, "is_anonymous": True}, timeout=20)
    body = r.json()
    if not body.get("ok"):
        # фолбэк для старых Bot API: options как массив строк
        r2 = requests.post(f"{base}/sendPoll", json={
            "chat_id": config.CHANNEL_ID, "question": str(question)[:250],
            "options": [str(o)[:90] for o in options][:4], "is_anonymous": True}, timeout=20)
        if not r2.json().get("ok"):
            raise RuntimeError(body.get("description") or r.text)


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
        # теханализ, сценарии и дайджест — TA-график «карта уровней» (BTC = прокси рынка)
        if kind in ("ta", "scenarios", "digest"):
            return charts.ta_chart("BTCUSDT", "1d")
        storage.use_uid("bezb")
        s = portfolio.summary()
        if kind in ("trade", "portfolio"):
            return charts.composition_pie(portfolio.pie_slices(s))
        return charts.index_line()
    except Exception:
        return None


def _require_owner(init_data):
    if not _resolve_user(init_data)["isAdmin"]:
        raise HTTPException(status_code=403, detail="Только владелец")


def _is_premium(init_data) -> bool:
    u = _resolve_user(init_data)
    return bool(u.get("isAdmin") or u.get("isPremium"))


def _require_premium(init_data, what: str = "Эта функция"):
    if not _is_premium(init_data):
        raise HTTPException(status_code=402, detail=f"{what} доступна в премиуме")


@app.post("/api/publish")
def publish(req: PublishReq, x_init_data: str | None = Header(default=None)):
    """Опубликовать текст в канал (только владелец)."""
    _require_owner(x_init_data)
    if not config.CHANNEL_ID:
        raise HTTPException(status_code=400, detail="Канал не подключён (задай CHANNEL_ID)")
    chart = _chart_for(req.chartKind) if req.chartKind else None
    try:
        _channel_post(req.text, chart, cta=req.cta)
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
        elif kind == "ta":
            text = ai.ta_bezb("BTCUSDT", "1d")
        elif kind in ("edu", "manifest", "bullshit", "psych", "case"):
            text = ai.content_post(kind)
        elif kind.startswith("promo_"):
            text = ai.convert_post(kind)
        elif kind.startswith("poll_"):
            import json as _json
            p = ai.poll(kind)
            return storage.add_draft("poll", _json.dumps(p, ensure_ascii=False))
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


# "bez" — фирменная реакция-логотип «Без Б» (рисуется монетой на фронте).
REACTIONS = ["bez", "🔥", "👍"]


def _reaction_uid(init_data: str | None) -> str:
    """Стабильный uid для реакций: telegram id или 'anon' (dev/вне Telegram)."""
    uid = _resolve_user(init_data).get("id")
    return f"u{uid}" if uid else "anon"


@app.get("/api/feed")
def feed(x_init_data: str | None = Header(default=None)):
    """Лента опубликованных постов с реакциями (публично)."""
    posts = storage.list_published()
    uid = _reaction_uid(x_init_data)
    ids = [p["id"] for p in posts]
    rmap = storage.reactions_for(ids, uid)
    cmap = storage.comment_counts(ids)
    for p in posts:
        r = rmap.get(p["id"], {"counts": {}, "mine": []})
        p["reactions"] = r["counts"]
        p["mine"] = r["mine"]
        p["comments"] = cmap.get(p["id"], 0)
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


@app.get("/api/feed/comments")
def feed_comments(post_id: int):
    """Комментарии под постом (публично читаемы)."""
    return storage.list_comments(post_id)


class CommentReq(BaseModel):
    post_id: int
    text: str


@app.post("/api/feed/comment")
def feed_comment(req: CommentReq, x_init_data: str | None = Header(default=None)):
    """Оставить комментарий. Нужна авторизация Telegram (аноним не пишет)."""
    u = _resolve_user(x_init_data)
    uid = u.get("id")
    if not uid:
        raise HTTPException(status_code=401, detail="Откройте приложение из Telegram, чтобы комментировать")
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Пустой комментарий")
    if len(text) > 600:
        raise HTTPException(status_code=400, detail="Слишком длинно (макс. 600 символов)")
    return storage.add_comment(req.post_id, f"u{uid}", u.get("name", "Гость"), text)


class CommentDelReq(BaseModel):
    id: int


@app.post("/api/feed/comment/delete")
def feed_comment_delete(req: CommentDelReq, x_init_data: str | None = Header(default=None)):
    """Удалить комментарий — только владелец/админ (модерация)."""
    u = _resolve_user(x_init_data)
    if not u.get("isAdmin"):
        raise HTTPException(status_code=403, detail="Только владелец может удалять комментарии")
    storage.delete_comment(req.id)
    return {"ok": True}


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
    # Индекс Без Б — собственный композит (тяжёлый, но кэшируется внутри модуля)
    bezb_index = None
    try:
        import bezb_index as bi
        d = bi.compute()
        if d.get("value") is not None:
            bezb_index = d
    except Exception:
        pass
    return {"mood": mood, "digest": digest, "bezbToday": today_trade,
            "bezbIndex": bezb_index}


@app.get("/api/bezb-index")
def bezb_index_endpoint():
    """Полный Индекс Без Б с разбивкой по компонентам (публично)."""
    try:
        import bezb_index as bi
        return bi.compute()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Индекс недоступен: {e}")


@app.post("/api/appopen")
def app_open(src: str = "", x_init_data: str | None = Header(default=None)):
    """Зафиксировать открытие мини-аппа с меткой источника (start_param).
    Источник закрепляется за юзером (первый побеждает) — для статистики /sources."""
    uid = _resolve_user(x_init_data).get("id")
    if uid and src:
        tag = src[4:] if src.startswith("src_") else src
        tag = "".join(c for c in tag[:32] if c.isalnum() or c in "_-").lower()
        if tag:
            storage.source_track(f"u{uid}", tag)
    return {"ok": True}


@app.get("/api/underdog")
def underdog_endpoint(x_init_data: str | None = Header(default=None)):
    """«Нелюбимчик недели» — премиум. Free видит только тизер (locked)."""
    try:
        import underdog
        data = underdog.current(build_if_stale=True)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Недоступно: {e}")
    if not data or not data.get("ticker"):
        return {"locked": False, "ticker": None}
    if _is_premium(x_init_data):
        return {"locked": False, **data}
    # тизер для бесплатных: фича есть, актив и разбор скрыты
    return {"locked": True, "weekId": data.get("weekId"),
            "teaser": "🔎 Нелюбимчик недели готов — самый перепроданный актив по фильтрам "
                      "«Без Б» с честным разбором за и против. Открой в премиуме."}


class FeedbackReq(BaseModel):
    name: str = ""
    phone: str = ""
    message: str = ""
    consentPd: bool = False
    consentAds: bool = False


@app.post("/api/feedback")
def feedback(req: FeedbackReq):
    """Заявка с лендинга. Обязательно согласие на обработку ПД (152-ФЗ)."""
    if not req.consentPd:
        raise HTTPException(status_code=400,
                            detail="Нужно согласие на обработку персональных данных")
    phone = req.phone.strip()
    name = req.name.strip()
    if not phone or len(phone) < 6:
        raise HTTPException(status_code=400, detail="Укажите корректный номер телефона")
    fid = storage.add_feedback(name, phone, req.message.strip(),
                               req.consentPd, req.consentAds)
    # уведомить владельца в Telegram
    try:
        import requests
        if config.BOT_TOKEN and config.ADMIN_ID:
            ads = "да" if req.consentAds else "нет"
            text = (f"📨 Новая заявка с лендинга #{fid}\n"
                    f"Имя: {name or '—'}\nТелефон: {phone}\n"
                    f"Сообщение: {req.message.strip() or '—'}\n"
                    f"Согласие на рекламу: {ads}")
            requests.post(f"https://api.telegram.org/bot{config.BOT_TOKEN}/sendMessage",
                          json={"chat_id": config.ADMIN_ID, "text": text}, timeout=10)
    except Exception:
        pass
    return {"ok": True, "id": fid}


@app.get("/api/feedback")
def feedback_list(x_init_data: str | None = Header(default=None)):
    _require_owner(x_init_data)
    return storage.list_feedback()


class AdminGrantReq(BaseModel):
    username: str
    revoke: bool = False


@app.post("/api/admin/grant")
def admin_grant(req: AdminGrantReq, x_init_data: str | None = Header(default=None)):
    """Выдать/снять полный доступ пользователю по @username (только владелец)."""
    _require_owner(x_init_data)
    if req.revoke:
        storage.remove_admin_username(req.username)
    else:
        storage.add_admin_username(req.username)
    return {"ok": True, "admins": storage.list_admin_usernames()}


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


@app.get("/api/pay/config")
def pay_config(x_init_data: str | None = Header(default=None)):
    """Что и как платить: провайдер, цена/тариф, publicId для виджета CloudPayments."""
    uid = _resolve_user(x_init_data).get("id")
    price, tier = _premium_price(uid)
    if config.CLOUDPAYMENTS_PUBLIC_ID:
        provider = "cloudpayments"
    elif config.PAYMENT_PROVIDER_TOKEN:
        provider = "telegram"
    else:
        provider = "none"
    return {"provider": provider, "publicId": config.CLOUDPAYMENTS_PUBLIC_ID,
            "price": price, "tier": tier, "days": config.PREMIUM_DAYS,
            "title": config.PREMIUM_TITLE, "accountId": f"u{uid}" if uid else "",
            "invoiceId": f"premium:u{uid}:{tier}" if uid else ""}


@app.post("/api/cloudpayments/pay")
async def cloudpayments_pay(request: Request,
                           content_hmac: str | None = Header(default=None, alias="Content-HMAC"),
                           x_content_hmac: str | None = Header(default=None, alias="X-Content-HMAC")):
    """Webhook CloudPayments (уведомление Pay). Проверяем подпись и выдаём премиум.
    Отвечаем {code:0} = принято. Источник истины об оплате — этот вызов."""
    raw = await request.body()
    secret = config.CLOUDPAYMENTS_API_SECRET
    if not secret:
        return {"code": 13}      # пока секрет не задан — выдачу не делаем (fail-closed)
    import base64
    digest = hmac.new(secret.encode(), raw, hashlib.sha256).digest()
    expected = base64.b64encode(digest).decode()
    got = content_hmac or x_content_hmac or ""
    if not hmac.compare_digest(expected, got):
        return {"code": 13}      # подпись неверна
    form = dict(parse_qsl(raw.decode("utf-8", "ignore")))
    account = form.get("AccountId", "")           # наш uid вида u<id>
    invoice = form.get("InvoiceId", "")           # premium:u<id>:<tier>
    tier = invoice.split(":")[2] if invoice.count(":") >= 2 else "reg"
    if account.startswith("u"):
        if tier == "eb":
            storage.add_early_bird(account)
        until = storage.grant_premium(account, config.PREMIUM_DAYS)
        try:
            chat_id = int(account.lstrip("u"))
            from datetime import datetime as _dt
            _tg_send(chat_id, f"✅ Премиум активирован до "
                     f"{_dt.fromtimestamp(until).strftime('%d.%m.%Y')}! Спасибо за поддержку «Без Б».")
            _tg_send(config.ADMIN_ID, f"💰 Оплата премиума (CloudPayments): {account}, тариф {tier}.")
        except Exception:
            pass
    return {"code": 0}


@app.post("/api/cloudpayments/order")
def cloudpayments_order(x_init_data: str | None = Header(default=None)):
    """Создать платёжную ссылку CloudPayments (hosted-страница) и вернуть {url}.
    Открывается во ВНЕШНЕМ браузере (tg.openLink) — там 3DS банка работает, в отличие
    от виджета внутри Telegram WebView, где форма ввода кода виснет. Оплата подтверждается
    Pay-webhook (/api/cloudpayments/pay) — он остаётся источником истины о выдаче премиума."""
    uid = _resolve_user(x_init_data).get("id")
    if not uid:
        raise HTTPException(status_code=401, detail="Откройте приложение из Telegram")
    if not (config.CLOUDPAYMENTS_PUBLIC_ID and config.CLOUDPAYMENTS_API_SECRET):
        raise HTTPException(status_code=503, detail="Оплата скоро будет подключена")
    import requests
    price_rub, tier = _premium_price(uid)
    title = config.PREMIUM_TITLE + (" · early-bird" if tier == "eb" else "")
    body = {
        "Amount": price_rub,
        "Currency": "RUB",
        "Description": title,
        "AccountId": f"u{uid}",
        "InvoiceId": f"premium:u{uid}:{tier}",
        "JsonData": {"premiumDays": config.PREMIUM_DAYS, "tier": tier},
    }
    try:
        r = requests.post(
            "https://api.cloudpayments.ru/orders/create",
            json=body,
            auth=(config.CLOUDPAYMENTS_PUBLIC_ID, config.CLOUDPAYMENTS_API_SECRET),
            timeout=15)
        data = r.json()
    except Exception:
        raise HTTPException(status_code=502, detail="Платёжный сервис недоступен, попробуйте позже")
    if not data.get("Success") or not data.get("Model", {}).get("Url"):
        msg = data.get("Message") or "Не удалось создать ссылку на оплату"
        raise HTTPException(status_code=502, detail=msg)
    return {"url": data["Model"]["Url"]}


@app.post("/api/pay/invoice")
def pay_invoice(x_init_data: str | None = Header(default=None)):
    """Создать ссылку на оплату премиума (Telegram-инвойс через провайдера).
    Возвращает {link} для tg.openInvoice. 503 — если оплата не подключена."""
    uid = _resolve_user(x_init_data).get("id")
    if not uid:
        raise HTTPException(status_code=401, detail="Откройте приложение из Telegram")
    if not config.PAYMENT_PROVIDER_TOKEN:
        raise HTTPException(status_code=503, detail="Оплата скоро будет подключена")
    import requests
    price_rub, tier = _premium_price(uid)
    amount = price_rub * 100  # в копейках
    title = config.PREMIUM_TITLE + (" · early-bird" if tier == "eb" else "")
    body = {
        "title": title,
        "description": "Премиум-доступ «Без Б»: расширенные AI-функции и приоритет.",
        "payload": f"premium:u{uid}:{tier}",
        "provider_token": config.PAYMENT_PROVIDER_TOKEN,
        "currency": "RUB",
        "prices": [{"label": title, "amount": amount}],
    }
    r = requests.post(
        f"https://api.telegram.org/bot{config.BOT_TOKEN}/createInvoiceLink",
        json=body, timeout=15)
    data = r.json()
    if not data.get("ok"):
        raise HTTPException(status_code=502, detail="Не удалось создать счёт")
    return {"link": data["result"]}


def _tg_send(chat_id, text: str) -> None:
    """Отправить личное сообщение пользователю/владельцу в Telegram (best-effort)."""
    try:
        import requests
        if config.BOT_TOKEN and chat_id:
            requests.post(
                f"https://api.telegram.org/bot{config.BOT_TOKEN}/sendMessage",
                json={"chat_id": chat_id, "text": text}, timeout=10)
    except Exception:
        pass


# ──────────────── онбординг (5 уроков) ────────────────

@app.get("/api/onboarding")
def onboarding(x_init_data: str | None = Header(default=None)):
    uid = _resolve_user(x_init_data).get("id")
    if not uid:
        return {"done": 0, "total": 5, "canRead": False, "finished": False,
                "nextInHours": 0, "anon": True}
    return storage.onboarding_get(f"u{uid}")


@app.post("/api/onboarding/read")
def onboarding_read(x_init_data: str | None = Header(default=None)):
    uid = _resolve_user(x_init_data).get("id")
    if not uid:
        raise HTTPException(status_code=401, detail="Откройте приложение из Telegram")
    return storage.onboarding_read(f"u{uid}")


# ──────────────── Q&A (вопрос-ответ) ────────────────

class QaAskReq(BaseModel):
    question: str


class QaAnswerReq(BaseModel):
    id: int
    text: str


_QA_LIMIT_FREE = 1
_QA_LIMIT_PREMIUM = 10


@app.post("/api/qa/ask")
def qa_ask(req: QaAskReq, x_init_data: str | None = Header(default=None)):
    """Вопрос подписчика. AI отвечает сразу; владелец может ответить лично позже."""
    u = _resolve_user(x_init_data)
    uid = u.get("id")
    if not uid:
        raise HTTPException(status_code=401, detail="Откройте приложение из Telegram")
    q = (req.question or "").strip()
    if len(q) < 5:
        raise HTTPException(status_code=400, detail="Сформулируй вопрос подробнее")
    limit = _QA_LIMIT_PREMIUM if (u.get("isAdmin") or u.get("isPremium")) else _QA_LIMIT_FREE
    if storage.qa_count_today(f"u{uid}") >= limit:
        msg = ("Лимит вопросов на сегодня исчерпан. В премиуме — до 10 вопросов в день."
               if limit == _QA_LIMIT_FREE else "Лимит вопросов на сегодня исчерпан.")
        raise HTTPException(status_code=429, detail=msg)
    # AI-ответ (если доступен)
    answer, by = None, None
    if ai.available():
        try:
            _, ctx = ai._bezb_ai_data()
            answer = ai.answer_qa(q, ctx)
            by = "ai"
        except Exception:
            answer = None
    qid = storage.add_qa(f"u{uid}", u.get("name", ""), q, answer, by)
    # уведомить владельца
    note = (f"❓ Вопрос #{qid} от {u.get('name', 'юзера')}:\n{q}")
    if answer:
        note += f"\n\n🤖 AI ответил. Можешь дополнить личным ответом в разделе «Вопросы»."
    else:
        note += "\n\nAI не ответил — ждёт твоего ответа в разделе «Вопросы»."
    _tg_send(config.ADMIN_ID, note)
    return {"id": qid, "question": q, "answer": answer, "answeredBy": by}


@app.get("/api/qa/mine")
def qa_mine(x_init_data: str | None = Header(default=None)):
    uid = _resolve_user(x_init_data).get("id")
    if not uid:
        return []
    return storage.list_qa_mine(f"u{uid}")


@app.get("/api/qa/all")
def qa_all(x_init_data: str | None = Header(default=None)):
    _require_owner(x_init_data)
    return storage.list_qa_all()


@app.post("/api/qa/answer")
def qa_answer(req: QaAnswerReq, x_init_data: str | None = Header(default=None)):
    """Личный ответ владельца на вопрос — пушится пользователю в Telegram."""
    _require_owner(x_init_data)
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Пустой ответ")
    target_uid = storage.set_qa_answer(req.id, text, "owner")
    if not target_uid:
        raise HTTPException(status_code=404, detail="Вопрос не найден")
    # target_uid вида "u<id>" → достаём числовой id
    try:
        chat_id = int(str(target_uid).lstrip("u"))
        _tg_send(chat_id, f"💬 Ответ на твой вопрос в «Без Б»:\n\n{text}")
    except Exception:
        pass
    return {"ok": True}


# ──────────────── сезон фэнтези-портфелей ────────────────

FANTASY_START = 10000.0


def _uid_value(uid: str) -> float:
    storage.use_uid(uid)
    try:
        return portfolio.summary()["total_value_usdt"]
    except Exception:
        return 0.0


def _fantasy_status(uid):
    bezb_val = _uid_value("bezb")
    season = storage.fantasy_ensure_season(bezb_val)
    players = storage.fantasy_players()
    vals = sorted(((p["uid"], _uid_value(p["uid"])) for p in players), key=lambda x: -x[1])
    joined = my_value = rank = ret = None
    joined = False
    if uid:
        fid = f"f{uid}"
        joined = storage.fantasy_is_player(fid)
        if joined:
            my_value = _uid_value(fid)
            ret = (my_value / FANTASY_START - 1) * 100
            rank = next((i + 1 for i, (u, _) in enumerate(vals) if u == fid), None)
    bezb_start = season.get("bezbStart") or 0
    bezb_ret = (_uid_value("bezb") / bezb_start - 1) * 100 if bezb_start > 0 else 0.0
    return {
        "season": {"startTs": season["startTs"], "endTs": season["endTs"]},
        "joined": joined, "startCapital": FANTASY_START,
        "value": round(my_value, 2) if my_value is not None else None,
        "returnPct": round(ret, 1) if ret is not None else None,
        "rank": rank, "players": len(players),
        "bezbReturnPct": round(bezb_ret, 1),
    }


@app.get("/api/fantasy")
def fantasy(x_init_data: str | None = Header(default=None)):
    return _fantasy_status(_resolve_user(x_init_data).get("id"))


@app.post("/api/fantasy/join")
def fantasy_join(x_init_data: str | None = Header(default=None)):
    u = _resolve_user(x_init_data)
    uid = u.get("id")
    if not uid:
        raise HTTPException(status_code=401, detail="Откройте приложение из Telegram")
    fid = f"f{uid}"
    storage.fantasy_ensure_season(_uid_value("bezb"))
    if not storage.fantasy_is_player(fid):
        storage.use_uid(fid)
        if portfolio.summary()["total_value_usdt"] <= 0:
            portfolio.add_deposit(FANTASY_START, 1.0)   # виртуальный капитал
        storage.fantasy_add_player(fid, u.get("name", ""))
    return _fantasy_status(uid)


_LEVELS = [
    (0, "Новичок"), (60, "Ученик"), (160, "Дисциплинированный"),
    (320, "Расчётливый"), (560, "Хладнокровный"), (900, "Стратег"),
    (1400, "Мастер"), (2100, "Гуру без Б"),
]


def _player_level(uid) -> dict:
    """XP/уровень/титул из всех активностей (агрегат, без отдельной записи XP)."""
    if not uid:
        return {"xp": 0, "level": 1, "title": _LEVELS[0][1], "curXp": 0,
                "nextXp": _LEVELS[1][0], "anon": True}
    u = f"u{uid}"
    dca = storage.dca_get(u)
    quiz = storage.quiz_get(u)
    pred = storage.pred_my_stats(u)
    onb = storage.onboarding_get(u)
    # сделки в учебном портфеле
    storage.use_uid(f"f{uid}")
    try:
        ftrades = sum(1 for t in portfolio.get_operations()
                      if (t.get("type") or t.get("side")) in ("buy", "sell"))
    except Exception:
        ftrades = 0
    events = storage.event_answered_count(u)
    login = storage.streak_get(u)
    refs = storage.referral_count(u)
    xp = (dca.get("total", 0) * 15 + quiz.get("score", 0) * 10
          + pred.get("points", 0) * 20 + onb.get("done", 0) * 25 + ftrades * 10
          + events * 8 + login.get("best", 0) * 5 + refs * 40)
    lvl = 1
    title = _LEVELS[0][1]
    cur_thr = 0
    nxt = None
    for i, (thr, name) in enumerate(_LEVELS):
        if xp >= thr:
            lvl, title, cur_thr = i + 1, name, thr
            nxt = _LEVELS[i + 1][0] if i + 1 < len(_LEVELS) else None
    return {"xp": xp, "level": lvl, "title": title, "curXp": cur_thr, "nextXp": nxt}


@app.get("/api/profile/level")
def profile_level(x_init_data: str | None = Header(default=None)):
    return _player_level(_resolve_user(x_init_data).get("id"))


@app.get("/api/referral")
def referral(x_init_data: str | None = Header(default=None)):
    uid = _resolve_user(x_init_data).get("id")
    link = f"https://t.me/{config.BOT_USERNAME}?start=ref_{uid}" if uid else ""
    return {"link": link, "count": storage.referral_count(f"u{uid}") if uid else 0,
            "days": config.REFERRAL_PREMIUM_DAYS}


@app.get("/api/profile/badges")
def profile_badges(x_init_data: str | None = Header(default=None)):
    uid = _resolve_user(x_init_data).get("id")
    if not uid:
        return []
    u = f"u{uid}"
    dca = storage.dca_get(u)
    quiz = storage.quiz_get(u)
    pred = storage.pred_my_stats(u)
    onb = storage.onboarding_get(u)
    login = storage.streak_get(u)
    refs = storage.referral_count(u)
    storage.use_uid(f"f{uid}")
    try:
        ftrades = sum(1 for t in portfolio.get_operations()
                      if (t.get("type") or t.get("side")) in ("buy", "sell"))
    except Exception:
        ftrades = 0
    B = [
        ("🎓", "Курс пройден", onb.get("done", 0) >= 5),
        ("🔥", "DCA 3 подряд", dca.get("best", 0) >= 3),
        ("🏅", "DCA полгода", dca.get("best", 0) >= 13),
        ("🚩", "Детектор буллшита", quiz.get("best", 0) >= 12),
        ("🔮", "Аналитик", pred.get("points", 0) >= 3),
        ("🎮", "Инвестор (10 сделок)", ftrades >= 10),
        ("📅", "7 дней входов", login.get("best", 0) >= 7),
        ("👥", "Амбассадор (3 друга)", refs >= 3),
    ]
    return [{"icon": ic, "label": lb, "earned": bool(e)} for ic, lb, e in B]


def _today_num() -> int:
    import time as _t
    return int(_t.time()) // 86400


@app.get("/api/event/today")
def event_today(x_init_data: str | None = Header(default=None)):
    """Событие дня + мой выбор + расклад. Без ключа ответов до выбора."""
    import event_data
    uid = _resolve_user(x_init_data).get("id")
    day = _today_num()
    ev = event_data.event_for_day(day)
    my = storage.event_my_choice(day, f"u{uid}") if uid else None
    crowd = storage.event_crowd(day)
    out_choices = [{"key": c["key"], "label": c["label"]} for c in ev["choices"]]
    res = {"id": ev["id"], "title": ev["title"], "text": ev["text"],
           "choices": out_choices, "myChoice": my, "crowd": crowd, "total": sum(crowd.values())}
    if my:  # после ответа отдаём разбор выбранного
        ch = next((c for c in ev["choices"] if c["key"] == my), None)
        res["takeaway"] = ch["takeaway"] if ch else ""
    return res


class EventChooseReq(BaseModel):
    choice: str


@app.post("/api/event/choose")
def event_choose(req: EventChooseReq, x_init_data: str | None = Header(default=None)):
    import event_data
    uid = _resolve_user(x_init_data).get("id")
    if not uid:
        raise HTTPException(status_code=401, detail="Откройте приложение из Telegram")
    day = _today_num()
    ev = event_data.event_for_day(day)
    ch = next((c for c in ev["choices"] if c["key"] == req.choice), None)
    if not ch:
        raise HTTPException(status_code=400, detail="Нет такого варианта")
    storage.event_choose(day, f"u{uid}", req.choice)   # если уже выбрано — не меняем
    my = storage.event_my_choice(day, f"u{uid}")
    mych = next((c for c in ev["choices"] if c["key"] == my), ch)
    crowd = storage.event_crowd(day)
    return {"myChoice": my, "takeaway": mych["takeaway"], "crowd": crowd,
            "total": sum(crowd.values())}


@app.post("/api/streak/ping")
def streak_ping(x_init_data: str | None = Header(default=None)):
    """Отметить визит (вызывается при открытии приложения)."""
    uid = _resolve_user(x_init_data).get("id")
    if not uid:
        return {"streak": 0, "best": 0, "today": False}
    return storage.streak_ping(f"u{uid}")


@app.post("/api/fantasy/mentor")
def fantasy_mentor(x_init_data: str | None = Header(default=None)):
    """AI-наставник разбирает учебный портфель игрока."""
    uid = _resolve_user(x_init_data).get("id")
    if not uid:
        raise HTTPException(status_code=401, detail="Откройте приложение из Telegram")
    _ai_or_503()
    storage.use_uid(f"f{uid}")
    s = portfolio.summary()
    if s["total_value_usdt"] <= 0:
        raise HTTPException(status_code=400, detail="Сначала вступи в игру и собери портфель")
    data = _ai_portfolio_data("me")
    data["label"] = "учебный портфель игрока"
    # последние решения
    lines = []
    for t in portfolio.get_operations()[:6]:
        tt = t.get("type") or t.get("side")
        if tt not in ("buy", "sell"):
            continue
        price = t.get("price_usdt", t.get("price_usd")) or 0
        amount = t.get("amount_usdt", t["qty"] * price)
        lines.append(f"{'Купил' if tt == 'buy' else 'Продал'} {t['ticker']} на ${round(amount)}")
    try:
        text = ai.mentor(data, "\n".join(lines))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Наставник недоступен: {e}")
    return {"text": text}


@app.get("/api/fantasy/leaderboard")
def fantasy_leaderboard():
    out = []
    for p in storage.fantasy_players():
        v = _uid_value(p["uid"])
        out.append({"name": p["name"], "value": round(v),
                    "returnPct": round((v / FANTASY_START - 1) * 100, 1)})
    out.sort(key=lambda x: -x["value"])
    return out[:20]


# ──────────────── квиз «Детектор буллшита» ────────────────

class QuizAnswerReq(BaseModel):
    qid: int
    bs: bool          # ответ игрока: True = «это буллшит»


@app.get("/api/quiz/next")
def quiz_next(x_init_data: str | None = Header(default=None)):
    """Следующая неотвеченная карточка (без ключа) + статистика игрока."""
    import quiz_data
    uid = _resolve_user(x_init_data).get("id")
    st = storage.quiz_get(f"u{uid}") if uid else {"score": 0, "streak": 0, "best": 0, "answered": []}
    answered = set(st["answered"])
    nxt = next((q for q in quiz_data.QUESTIONS if q["id"] not in answered), None)
    total = len(quiz_data.QUESTIONS)
    if not nxt:
        return {"done": True, "stats": st, "total": total, "answeredCount": len(answered)}
    return {"done": False, "question": {"id": nxt["id"], "text": nxt["text"]},
            "stats": st, "total": total, "answeredCount": len(answered)}


@app.post("/api/quiz/answer")
def quiz_answer(req: QuizAnswerReq, x_init_data: str | None = Header(default=None)):
    """Проверить ответ (ключ на сервере), вернуть разбор и обновлённый счёт."""
    import quiz_data
    uid = _resolve_user(x_init_data).get("id")
    if not uid:
        raise HTTPException(status_code=401, detail="Откройте приложение из Telegram")
    q = quiz_data.get(req.qid)
    if not q:
        raise HTTPException(status_code=404, detail="Вопрос не найден")
    correct = (req.bs == q["bs"])
    st = storage.quiz_record(f"u{uid}", req.qid, correct)
    return {"correct": correct, "bs": q["bs"], "explain": q["explain"], "stats": st}


@app.post("/api/quiz/reset")
def quiz_reset(x_init_data: str | None = Header(default=None)):
    uid = _resolve_user(x_init_data).get("id")
    if not uid:
        raise HTTPException(status_code=401, detail="Откройте приложение из Telegram")
    storage.quiz_reset_answered(f"u{uid}")
    return {"ok": True}


# ──────────────── игра «Прогноз недели» ────────────────

class PredictVoteReq(BaseModel):
    choice: str          # "up" | "down"


class PredictCreateReq(BaseModel):
    symbol: str = "BTC"
    target: float | None = None
    days: int = 7


@app.get("/api/predict")
def predict(x_init_data: str | None = Header(default=None)):
    """Текущий раунд прогноза + мой голос + расклад толпы + итог прошлого + мои очки."""
    u = _resolve_user(x_init_data)
    uid = u.get("id")
    cur = storage.pred_current()
    my_vote = storage.pred_my_vote(cur["id"], f"u{uid}") if (cur and uid) else None
    crowd = storage.pred_crowd(cur["id"]) if cur else {"up": 0, "down": 0, "total": 0}
    me = storage.pred_my_stats(f"u{uid}") if uid else {"points": 0, "total": 0}
    return {"round": cur, "myVote": my_vote, "crowd": crowd,
            "last": storage.pred_last_closed(), "me": me}


@app.post("/api/predict/vote")
def predict_vote(req: PredictVoteReq, x_init_data: str | None = Header(default=None)):
    u = _resolve_user(x_init_data)
    uid = u.get("id")
    if not uid:
        raise HTTPException(status_code=401, detail="Откройте приложение из Telegram")
    cur = storage.pred_current()
    if not cur:
        raise HTTPException(status_code=400, detail="Сейчас нет активного прогноза")
    if not storage.pred_vote(cur["id"], f"u{uid}", u.get("name", ""), req.choice):
        raise HTTPException(status_code=400, detail="Голос не принят (раунд закрыт?)")
    return {"ok": True, "myVote": req.choice, "crowd": storage.pred_crowd(cur["id"])}


@app.get("/api/predict/leaderboard")
def predict_leaderboard():
    return storage.pred_leaderboard()


@app.post("/api/predict/create")
def predict_create(req: PredictCreateReq, x_init_data: str | None = Header(default=None)):
    _require_owner(x_init_data)
    sym = req.symbol.strip().upper()
    target = req.target
    if not target:
        from quotes import get_price_usd
        target = get_price_usd(sym, True)
    return storage.pred_create(sym, float(target), req.days)


@app.post("/api/predict/resolve")
def predict_resolve(x_init_data: str | None = Header(default=None)):
    """Закрыть текущий раунд по текущей цене (вручную, владелец)."""
    _require_owner(x_init_data)
    cur = storage.pred_current()
    if not cur:
        raise HTTPException(status_code=400, detail="Нет открытого раунда")
    from quotes import get_price_usd
    price = get_price_usd(cur["symbol"], True)
    return storage.pred_resolve(cur["id"], float(price))


@app.post("/api/subscribe")
def subscribe(x_init_data: str | None = Header(default=None)):
    """Подписаться на мгновенные пуши о сделках Без Б — премиум-функция."""
    uid = _resolve_user(x_init_data).get("id")
    if not uid:
        raise HTTPException(status_code=401, detail="Откройте приложение из Telegram")
    _require_premium(x_init_data, "Мгновенные пуши о сделках")
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
async def content_publish(id: int, cta: bool = True, chart: bool = True,
                          image: UploadFile | None = File(default=None),
                          x_init_data: str | None = Header(default=None)):
    """Опубликовать черновик. cta — кнопка на бота; chart — приложить график
    рубрики; image — своя картинка (имеет приоритет над графиком)."""
    _require_owner(x_init_data)
    if not config.CHANNEL_ID:
        raise HTTPException(status_code=400, detail="Канал не подключён")
    d = storage.get_draft(id)
    if not d:
        raise HTTPException(status_code=404, detail="Черновик не найден")
    # опрос — публикуем как нативный Telegram-опрос
    if d["kind"] == "poll":
        import json as _json
        try:
            p = _json.loads(d["text"])
            _channel_poll(p["question"], p["options"])
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Не удалось опубликовать опрос: {e}")
        storage.set_draft_status(id, "published")
        return {"ok": True}
    photo = None
    if image is not None:
        photo = await image.read()
    elif chart:
        photo = _chart_for(d["kind"]) or _chart_for("portfolio")
    try:
        _channel_post(d["text"], photo, cta=cta)
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
