"""AI-слой «Без Б» — разбор портфеля через Claude API.

Ключ берётся из переменной окружения ANTHROPIC_API_KEY. Если ключа нет или SDK
не установлен — available()=False, и API вернёт мягкое 503 (фича просто скрыта),
а не упадёт. Модель по умолчанию — Haiku 4.5 (дёшево для частых разборов),
переопределяется через AI_MODEL.
"""
import os

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MODEL = os.getenv("AI_MODEL", "claude-haiku-4-5")

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


def analyze_portfolio(data: dict) -> str:
    """Сделать AI-разбор портфеля. Бросает исключение при ошибке вызова."""
    import anthropic
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    user = ("Разбери этот портфель:\n\n" + _format_portfolio(data) +
            "\n\nДай разбор: риск/концентрация, перекосы, что заметно, "
            "1–2 сценария «что если рынок дёрнется». Без сигналов.")
    resp = client.messages.create(
        model=MODEL,
        max_tokens=1200,
        system=SYSTEM,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(b.text for b in resp.content if b.type == "text").strip()
