"""AI-слой «Без Б» — разбор портфеля через Claude API.

Ключ берётся из переменной окружения ANTHROPIC_API_KEY. Если ключа нет или SDK
не установлен — available()=False, и API вернёт мягкое 503 (фича просто скрыта),
а не упадёт. Модель по умолчанию — Haiku 4.5 (дёшево для частых разборов),
переопределяется через AI_MODEL.
"""
import os

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
# можно указать совместимый прокси (напр. tokenator.top); пусто = офиц. Anthropic
BASE_URL = os.getenv("ANTHROPIC_BASE_URL", "")
MODEL = os.getenv("AI_MODEL", "claude-haiku-4-5")
# для публичных постов берём модель посильнее (объём низкий — DCA раз в 2 недели)
POST_MODEL = os.getenv("AI_POST_MODEL", "claude-sonnet-4-6")
# некоторые прокси/модели включают «рассуждение» через extra_body.reasoning
REASONING = os.getenv("AI_REASONING", "0") == "1"

# Общий голос «Без Б» (по образцу живых эконом-блогеров): разговорный, дерзкий,
# структурный, с воздухом. Добавляется ко всем промптам.
STYLE = (
    " ГОЛОС: пиши разговорно, дерзко и по-человечески — будто объясняешь толковому "
    "другу, но уверенно и со знанием дела. Эмодзи-акценты (🚀 💸 📈 ⚠️ 🔥 🤖) и короткие "
    "абзацы с переносами строк — воздух важнее сплошного текста. Дроби мысль на "
    "короткие пункты. Признавай неопределённость («я не знаю», «может пойти иначе») и "
    "давай рамку для размышления, а не указания. Без корп-жаргона, без воды, без "
    "обещаний доходности. НЕ используй markdown-звёздочки для жирного (не "
    "отрендерятся) — выделяй эмодзи и редким КАПСОМ."
)

POST_STYLE = (STYLE + " Начни с короткой цепляющей фразы/обращения к подписчикам, "
              "заверши тёплым вопросом или фразой к читателю.")

SYSTEM = (
    "Ты — аналитик проекта «Без Б — инвестиции без буллшита». "
    "Разбираешь инвестиционный портфель человеческим языком: структура, "
    "концентрация и риск, перекосы, что бросается в глаза, и пара идей/сценариев. "
    "ВАЖНО: это аналитика и наблюдение, а не сигналы и не призыв покупать/продавать. "
    "Не давай прямых указаний «купи X». Пиши по-русски, 150–220 слов. В конце одной "
    "строкой: «Не является индивидуальной инвестиционной рекомендацией.»"
) + STYLE


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


def _client():
    import anthropic
    kw = {"api_key": ANTHROPIC_API_KEY}
    if BASE_URL:
        kw["base_url"] = BASE_URL
    return anthropic.Anthropic(**kw)


def _call(model: str, system: str, user: str, tools=None, max_tokens: int = 1200) -> str:
    """Один вызов Claude (или совместимого прокси). Обрабатывает pause_turn для
    серверных инструментов вроде web_search. Возвращает текст ответа."""
    client = _client()
    messages = [{"role": "user", "content": user}]
    kw = {"tools": tools} if tools else {}
    if REASONING:
        kw["extra_body"] = {"reasoning": {"enabled": True}}
    resp = None
    for _ in range(4):
        resp = client.messages.create(
            model=model, max_tokens=max_tokens, system=system, messages=messages, **kw)
        if resp.stop_reason == "pause_turn":
            messages = [{"role": "user", "content": user},
                        {"role": "assistant", "content": resp.content}]
            continue
        break
    out = []
    for b in (resp.content if resp else []):
        if b.type == "text":
            out.append(b.text)
    return "".join(out).strip()


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
    "100–160 слов. В конце одной строкой: «Не ИИР. Слежу за портфелём открыто.»"
) + POST_STYLE


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
) + STYLE


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
    "слов. В конце строкой: «Не ИИР.»"
) + POST_STYLE


_CONTENT_TASKS = {
    "edu": "Напиши обучающий пост-ликбез: простым языком объясни одну идею про "
           "инвестиции или усреднение (DCA) — как работает и зачем, с понятным "
           "примером. Без сигналов.",
    "manifest": "Напиши короткий пост-манифест в духе «Без Б»: инвестиция — это вклад "
                "в любую сферу жизни (семья, время, здоровье, навыки), не только "
                "деньги. О дисциплине и регулярности как основе результата.",
    "bullshit": "Напиши пост рубрики «Детектор буллшита»: разбери типичный "
                "инфоцыганский приём (обещание иксов, «100% годовых без риска», "
                "платные сигналы, скрины Lamborghini) — почему это развод и как "
                "думать трезво.",
}


def _bezb_ai_data():
    """Данные публичного портфеля Без Б для AI (uid bezb). (data, ctx)."""
    import storage
    import portfolio
    storage.use_uid("bezb")
    s = portfolio.summary()
    pv = s["positions_value_usdt"] or 1
    data = {
        "label": "публичный портфель «Без Б»",
        "totalUsd": s["total_value_usdt"], "totalRub": s["value_rub"],
        "profitRubPct": s["profit_rub_pct"], "profitUsdPct": s["profit_usdt_pct"],
        "index": s["index"], "cashUsdt": s["usdt_cash"],
        "positions": [{
            "ticker": p.ticker, "weightPct": p.value_usd / pv * 100,
            "profitPct": p.profit_pct, "avgPrice": round(p.avg_price_usdt, 4),
            "priceNow": round(p.price_now, 4),
        } for p in s["positions"]],
    }
    ctx = (f"Баланс {s['value_rub']:,.0f}₽, индекс Без Б {s['index']:.0f} пт. Позиции: "
           + (", ".join(f"{p.ticker} {p.value_usd / pv * 100:.0f}%" for p in s["positions"])
              or "только кэш")).replace(",", " ")
    return data, ctx


def digest_bezb() -> str:
    _, ctx = _bezb_ai_data()
    return market_digest(ctx)


def scenarios_bezb() -> str:
    data, _ = _bezb_ai_data()
    return scenarios(data)


SYSTEM_CROWD = (
    "Ты ведёшь канал «Без Б — инвестиции без буллшита». Рубрика «🌡 Разбор толпы»: "
    "по данным настроения крипторынка (индекс страха/жадности, funding фьючерсов, "
    "лонг/шорт толпы) объясняешь, что сейчас творится с НАСТРОЕНИЕМ людей — где "
    "FOMO и жадность, где паника и страх, есть ли перегрев или риск коррекции, и "
    "КАК к этому относиться спокойно. Это про психологию и дисциплину (когда толпа "
    "в эйфории — осторожнее; когда в страхе — без паники), НЕ сигнал на вход/выход. "
    "Не давай прямых указаний купить/продать. По-русски, 120–180 слов. В конце "
    "строкой: «Не ИИР. Это про психологию рынка, а не сигнал.»"
) + POST_STYLE


def crowd_post(mood_ctx: str) -> str:
    """Пост рубрики «Разбор толпы» по данным настроения рынка."""
    user = ("Разбери настроение толпы по этим данным:\n\n" + mood_ctx +
            "\n\nОбъясни простым языком: страх или жадность сейчас, есть ли "
            "перегрев / риск коррекции, и как к этому относиться без паники и FOMO.")
    return _call(POST_MODEL, SYSTEM_CROWD, user, max_tokens=1100)


def crowd_bezb() -> str:
    import market_mood
    return crowd_post(market_mood.context())


def content_post(kind: str) -> str:
    """Сгенерировать пост рубрики (edu/manifest/bullshit) — без данных портфеля."""
    task = _CONTENT_TASKS.get(kind)
    if not task:
        raise ValueError(f"неизвестная рубрика: {kind}")
    base = ("Ты ведёшь Telegram-канал «Без Б — инвестиции без буллшита». "
            "Это образование и аналитика, НЕ сигналы и не ИИР.")
    return _call(POST_MODEL, base + POST_STYLE,
                 task + " 120–180 слов. В конце строкой: «Не ИИР.»", max_tokens=1100)


def market_digest(context: str) -> str:
    """Дайджест рынка. Пробуем с веб-поиском; если прокси/модель его не
    поддерживает — собираем по знаниям модели (без выдуманной свежей конкретики)."""
    user = ("Сделай дайджест «Рынок за 60 секунд». "
            "Учитывай состав портфеля Без Б, отметь что для него важно:\n\n" + context)
    tools = [{"type": "web_search_20260209", "name": "web_search"}]
    try:
        return _call(POST_MODEL, SYSTEM_DIGEST, user, tools=tools, max_tokens=1500)
    except Exception:
        sys2 = (SYSTEM_DIGEST + " Веб-поиск недоступен: опирайся на общие знания, "
                "не выдумывай конкретные свежие цифры и даты.")
        return _call(POST_MODEL, sys2, user, max_tokens=1500)
