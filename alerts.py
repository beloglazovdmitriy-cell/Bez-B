"""Умные предупреждения о рынке (премиум-фича «AI-алерты»).

Раз в несколько часов джоба бота зовёт check(): по данным настроения рынка
(market_mood) ищет «события» — перегрев/паника, перекос плечей, резкое движение.
Сработавшие пуши уходят только премиум-подписчикам (notify.notify_alert).

Антиспам: один тип алерта не повторяется чаще, чем раз в _COOLDOWN (состояние —
в storage.meta). Это НЕ сигналы на вход/выход, а предупреждения о риске и психологии.
"""
import time

import market_mood
import storage

# не повторять один тип алерта чаще, чем раз в ~20 часов (≈ не больше 1/сутки на тип)
_COOLDOWN = int(__import__("os").getenv("ALERT_COOLDOWN_HOURS", "20")) * 3600


def _fired_recently(key: str, now: float) -> bool:
    raw = storage.meta_get(f"alert:{key}")
    try:
        return raw is not None and now - float(raw) < _COOLDOWN
    except (TypeError, ValueError):
        return False


def mark(key: str) -> None:
    """Зафиксировать, что алерт отправлен (запускает кулдаун)."""
    storage.meta_set(f"alert:{key}", time.time())


def _fmt_usd(v: float) -> str:
    return f"${v:,.0f}".replace(",", " ")


def check() -> list:
    """Список сработавших алертов с учётом кулдауна.

    Каждый: {key, title, context, fallback}. context — для AI-промпта,
    fallback — готовый текст, если AI недоступен.
    """
    now = time.time()
    m = market_mood.snapshot(force=True)
    out = []

    def add(key, title, context, fallback):
        if not _fired_recently(key, now):
            out.append({"key": key, "title": title, "context": context, "fallback": fallback})

    # ── Индекс страха и жадности: эйфория / паника ──
    fng = m.get("fng")
    if fng:
        v = fng["value"]
        if v >= 80:
            add("fng_greed", "🥵 Крайняя жадность на рынке",
                f"Индекс страха и жадности крипторынка = {v}/100 ({fng['label_ru']}). Толпа в эйфории.",
                f"🥵 Индекс страха и жадности = {v}/100 — крайняя жадность.\n\n"
                "Когда толпа в эйфории, риск коррекции выше обычного. Это не повод "
                "паниковать или запрыгивать на хаях — повод проверить свою дисциплину "
                "и не поддаваться FOMO.\n\nНе сигнал, а наблюдение. Не ИИР.")
        elif v <= 20:
            add("fng_fear", "🧊 Крайний страх на рынке",
                f"Индекс страха и жадности крипторынка = {v}/100 ({fng['label_ru']}). Толпа в панике.",
                f"🧊 Индекс страха и жадности = {v}/100 — крайний страх.\n\n"
                "Толпа в панике. Исторически такие моменты были ближе к возможностям, "
                "чем к концу света — но без резких движений и геройства. Действуй по плану.\n\n"
                "Не сигнал, а наблюдение. Не ИИР.")

    # ── Funding фьючерсов BTC: перегрев плечей ──
    fund = (m.get("funding") or {}).get("BTCUSDT")
    if fund is not None:
        if fund >= 0.0005:
            add("funding_long", "⚠️ Перегрев лонгов BTC",
                f"Funding BTC = {fund * 100:+.3f}%/8ч — сильный перевес плечевых лонгов.",
                f"⚠️ Funding по BTC {fund * 100:+.3f}%/8ч — толпа набрала плечо в лонг.\n\n"
                "Так бывает на перегреве: даже небольшое движение вниз может вызвать "
                "каскад ликвидаций и резкую просадку. Осторожнее с плечами.\n\n"
                "Не сигнал, а наблюдение. Не ИИР.")
        elif fund <= -0.0003:
            add("funding_short", "⚠️ Перевес шортов BTC",
                f"Funding BTC = {fund * 100:+.3f}%/8ч — заметный перевес шортов.",
                f"⚠️ Funding по BTC {fund * 100:+.3f}%/8ч — толпа в шортах.\n\n"
                "Резкий вынос вверх может выбить шортистов (short squeeze) и ускорить рост. "
                "Рынок на эмоциях в обе стороны.\n\nНе сигнал, а наблюдение. Не ИИР.")

    # ── Индекс Без Б в крайней зоне (флагманский алерт) ──
    try:
        import bezb_index
        bi = bezb_index.compute()
        v = bi.get("value")
        if v is not None and v >= 80:
            add("bezb_index_hot", "🥵 Индекс Без Б — зона перегрева",
                bezb_index.context(),
                f"🥵 Индекс Без Б = {v}/100 — {bi['label']}.\n\n"
                "Сразу несколько факторов указывают на перегрев рынка. Когда так "
                "сходится, риск коррекции выше обычного. Не геройствуй на хаях — держи план.\n\n"
                "Это карта режима, а не сигнал. Не ИИР.")
        elif v is not None and v <= 20:
            add("bezb_index_cold", "🧊 Индекс Без Б — зона страха",
                bezb_index.context(),
                f"🧊 Индекс Без Б = {v}/100 — {bi['label']}.\n\n"
                "Рынок в страхе и перепродан по нескольким факторам. Исторически такие "
                "зоны были ближе к возможностям, чем к концу света — но без резких движений.\n\n"
                "Это карта режима, а не сигнал. Не ИИР.")
    except Exception:
        pass

    # ── Резкое движение BTC за сутки ──
    spot = (m.get("spot") or {}).get("BTCUSDT")
    if spot:
        pct = spot.get("pct24", 0)
        if abs(pct) >= 7:
            price = spot.get("price", 0)
            emoji = "🚀" if pct > 0 else "🔻"
            direction = "вверх" if pct > 0 else "вниз"
            add("btc_move", f"{emoji} Резкое движение BTC за сутки",
                f"BTC {pct:+.1f}% за 24ч, цена {_fmt_usd(price)}.",
                f"{emoji} BTC {pct:+.1f}% за сутки ({_fmt_usd(price)}).\n\n"
                f"Сильное движение {direction} — рынок на эмоциях. Не дёргайся вслед за "
                "толпой и не отыгрывай уже случившееся. Держись своего плана.\n\n"
                "Не сигнал, а наблюдение. Не ИИР.")

    return out
