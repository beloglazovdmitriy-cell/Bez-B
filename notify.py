"""Мгновенные пуши подписчикам о сделках публичного портфеля «Без Б».

Локомотив премиума — СКОРОСТЬ: подписчик узнаёт о сделке раньше канала.
Список подписчиков — storage.subscribers (пока включение свободное; после
подключения оплаты CryptoCloud станет гейтом по премиум-подписке).
"""
import config
import storage


def _kb():
    return {"inline_keyboard": [[{"text": "📈 Открыть Без Б", "url": config.BOT_URL}]]}


def _fmt_amount(v: float) -> str:
    return f"{v:,.0f}".replace(",", " ")


def _fmt_price(v: float) -> str:
    s = f"{v:,.4f}".replace(",", " ")
    return s.rstrip("0").rstrip(".") if "." in s else s


def trade_message(tx: dict) -> str:
    side = (tx.get("type") or tx.get("side") or "").lower()
    verb = {"buy": "купил", "sell": "продал", "asset_deposit": "завёл актив"}.get(side, "сделка")
    ticker = tx.get("ticker", "?")
    price = tx.get("price_usdt", tx.get("price_usd")) or 0
    amount = tx.get("amount_usdt") or (tx.get("qty", 0) * price)
    reason = tx.get("reason", "")
    head = f"🔔 Без Б только что {verb} {ticker}"
    if amount:
        head += f" на ${_fmt_amount(amount)}"
    lines = [head]
    if price:
        lines.append(f"Цена: ${_fmt_price(price)}")
    if reason:
        lines.append(f"Причина: {reason}")
    lines += ["", "Ты видишь это раньше канала — премиум-скорость."]
    return "\n".join(lines)


def notify_trade(tx: dict) -> int:
    """Разослать пуш о сделке всем подписчикам. Возвращает число доставленных.

    Синхронная (requests) — вызывать в отдельном потоке, чтобы не блокировать
    ответ API / event loop бота. Заблокировавших бота подписчиков вычищает.
    """
    if not tx or not config.BOT_TOKEN:
        return 0
    side = (tx.get("type") or tx.get("side") or "").lower()
    if side not in ("buy", "sell", "asset_deposit"):
        return 0
    # только активные премиум-подписчики (плюс владелец)
    subs = [u for u in storage.list_subscribers()
            if storage.is_premium(f"u{u}") or u == config.ADMIN_ID]
    if not subs:
        return 0
    import requests
    text = trade_message(tx)
    base = f"https://api.telegram.org/bot{config.BOT_TOKEN}"
    sent = 0
    for uid in subs:
        try:
            r = requests.post(f"{base}/sendMessage", json={
                "chat_id": uid, "text": text, "reply_markup": _kb()}, timeout=10)
            body = r.json()
            if body.get("ok"):
                sent += 1
            else:
                desc = (body.get("description") or "").lower()
                if any(w in desc for w in ("blocked", "deactivated", "chat not found")):
                    storage.remove_subscriber(uid)
        except Exception:
            pass
    return sent
