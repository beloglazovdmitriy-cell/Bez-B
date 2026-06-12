"""AI-слой «Без Б» — разбор портфеля через Claude API.

Ключ берётся из переменной окружения ANTHROPIC_API_KEY. Если ключа нет или SDK
не установлен — available()=False, и API вернёт мягкое 503 (фича просто скрыта),
а не упадёт. Модель по умолчанию — Haiku 4.5 (дёшево для частых разборов),
переопределяется через AI_MODEL.
"""
import os

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MODEL = os.getenv("AI_MODEL", "claude-haiku-4-5")
# для публичных постов берём модель посильнее (объём низкий — DCA раз в 2 недели)
POST_MODEL = os.getenv("AI_POST_MODEL", "claude-sonnet-4-6")

SYSTEM = (
    "Ты — аналитик проекта «Без Б — инвестиции без буллшита». "
    "Разбираешь инвестиционный портфель человеческим языком: структура, "
    "концентрация и риск, перекосы, что бросается в глаза, и пара идей/сценариев. "
    "Тон: коротко, по делу, дерзко, без воды и без обещаний доходности. "
    "ВАЖНО: это аналитика и наблюдение, а не сигналы и не призыв покупать/продавать. "
    "Не давай прямых указаний «купи X». Пиши по-русски, 150–220 слов, без markdown-"
    "заголовков (можно короткие абзацы и маркеры •). В конце одной строкой: "
    "«Не является индивидуальной инвестиционной рекомендацией.»"
)


def available() -> bool:
    """Готов ли AI: есть ключ и установлен SDK."""
    if not ANTHROPIC_API_KEY:
        return False
    try:
        import anthropic  # noqa: F401
        return True
    except ImportError:
        return False


def _format_portfolio(d: dict) -> str:
    L = [f"Портфель: {d.get('label', 'портфель')}",
         f"Баланс: {d.get('totalUsd', 0):,.0f}$ / {d.get('totalRub', 0):,.0f}₽".replace(",", " "),
         f"Доходность: {d.get('profitRubPct', 0):+.1f}% ₽ / {d.get('profitUsdPct', 0):+.1f}% $",
         f"Индекс Без Б: {d.get('index', 100):.1f} пт",
         f"Свободный кэш USDT: {d.get('cashUsdt', 0):,.0f}".replace(",", " "), "",
         "Позиции (тикер — доля — P/L — ср.цена→тек.цена):"]
    for p in d.get("positions", []):
        L.append(
            f"• {p['ticker']}: {p['weightPct']:.0f}% · {p['profitPct']:+.1f}% · "
            f"${p['avgPrice']:g}→${p['priceNow']:g}")
    if not d.get("positions"):
        L.append("• позиций нет (только кэш)")
    return "\n".join(L)


def _call(model: str, system: str, user: str, tools=None, max_tokens: int = 1200) -> str:
    """Один вызов Claude. Обрабатывает pause_turn (для серверных инструментов
    вроде web_search). Возвращает текст ответа."""
    import anthropic
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    messages = [{"role": "user", "content": user}]
    kw = {"tools": tools} if tools else {}
    resp = None
    for _ in range(4):
        resp = client.messages.create(
            model=model, max_tokens=max_tokens, system=system, messages=messages, **kw)
        if resp.stop_reason == "pause_turn":
            messages = [{"role": "user", "content": user},
                        {"role": "assistant", "content": resp.content}]
            continue
        break
    return "".join(b.text for b in (resp.content if resp else []) if b.type == "text").strip()


def analyze_portfolio(data: dict) -> str:
    """AI-разбор портфеля."""
    user = ("Разбери этот портфель:\n\n" + _format_portfolio(data) +
            "\n\nДай разбор: риск/концентрация, перекосы, что заметно, "
            "1–2 сценария «что если рынок дёрнется». Без сигналов.")
    return _call(MODEL, SYSTEM, user, max_tokens=1200)


SYSTEM_POST = (
    "Ты ведёшь Telegram-канал «Без Б — инвестиции без буллшита». Превращаешь "
    "сделку автора в короткий пост: что сделал, почему это может быть разумно "
    "(логика), какие риски и что говорит против, на что смотреть дальше. "
    "Тон: живо, дерзко, по делу, без воды и без обещаний доходности. Это "
    "наблюдение и разбор мышления, НЕ сигнал и не призыв повторять. Пиши по-русски, "
    "100–160 слов, можно эмодзи и короткие абзацы. В конце одной строкой: "
    "«Не ИИР. Слежу за портфелём открыто.»"
)


def analyze_trade(trade: dict) -> str:
    """Черновик поста в канал по сделке."""
    side = "Купил" if trade.get("side") == "buy" else "Продал"
    lines = [
        f"Сделка: {side} {trade['ticker']} на {trade.get('amountUsd', 0):,.0f}$ "
        f"по ${trade.get('price', 0):g} ({trade.get('qty', 0):g} шт.)".replace(",", " "),
        f"Доля {trade['ticker']} в портфеле сейчас: {trade.get('sharePct', 0):.0f}%",
    ]
    if trade.get("reason"):
        lines.append(f"Причина (от автора): {trade['reason']}")
    user = ("Напиши пост в канал по этой сделке:\n\n" + "\n".join(lines) +
            "\n\nДай логику, риски, что против, на что смотреть. Без сигналов.")
    return _call(POST_MODEL, SYSTEM_POST, user, max_tokens=900)


SYSTEM_SCEN = (
    "Ты — аналитик «Без Б». По составу портфеля строишь сценарии «что если рынок "
    "дёрнется». Дай ровно три сценария: 📉 медвежий, ➡️ нейтральный, 📈 бычий. "
    "Для каждого: что это значит для ЭТОГО портфеля (какие позиции под ударом / "
    "в плюсе) и на что смотреть. Тон: коротко, по делу, без воды и без обещаний. "
    "Это сценарный анализ, НЕ прогноз и НЕ сигнал. По-русски, до 220 слов. "
    "В конце строкой: «Не является индивидуальной инвестиционной рекомендацией.»"
)


def scenarios(data: dict) -> str:
    """3 сценария по портфелю."""
    user = ("Построй сценарии для портфеля:\n\n" + _format_portfolio(data) +
            "\n\nТри сценария (медвежий/нейтральный/бычий): что с этим портфелем "
            "и на что смотреть.")
    return _call(POST_MODEL, SYSTEM_SCEN, user, max_tokens=1300)


SYSTEM_DIGEST = (
    "Ты ведёшь канал «Без Б — инвестиции без буллшита». Пишешь дайджест «Рынок за "
    "60 секунд»: что происходит в крипте, в акциях США и в макро (ставки/инфляция), "
    "и что из этого важно для публичного портфеля Без Б. Используй веб-поиск для "
    "свежих фактов; ссылайся на конкретику без воды. Тон: коротко, дерзко, по делу, "
    "без обещаний доходности. Это обзор и аналитика, НЕ сигналы. По-русски, 120–200 "
    "слов, можно эмодзи и короткие блоки. В конце строкой: «Не ИИР.»"
)


def market_digest(context: str) -> str:
    """Дайджест рынка с веб-поиском. context — краткий состав портфеля Без Б."""
    user = ("Сделай свежий дайджест «Рынок за 60 секунд» на сегодня. "
            "Учитывай состав портфеля Без Б, чтобы отметить, что для него важно:\n\n"
            + context)
    tools = [{"type": "web_search_20260209", "name": "web_search"}]
    return _call(POST_MODEL, SYSTEM_DIGEST, user, tools=tools, max_tokens=1500)
