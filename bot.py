"""Telegram-бот портфеля «Без Б» — кнопочный интерфейс, модель с USDT-кэшем.

Денежная логика как в брокере:
  1) «💵 Пополнить» — заводишь рубли, покупаешь USDT по своему курсу (₽ за 1 USDT);
  2) «➕ Купить» — за USDT покупаешь активы по рынку (DCA);
  3) «➖ Продать» — актив обратно в USDT;
  4) «💸 Вывести» — выводишь USDT из портфеля.
Снизу всегда есть постоянная кнопка «☰ Меню».
"""
import asyncio
import logging
import os
from logging.handlers import RotatingFileHandler
from datetime import time as dtime, datetime, timedelta

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton, WebAppInfo,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, PreCheckoutQueryHandler, ContextTypes, filters,
)

import config
import portfolio
import charts
import benchmark
import ai
import storage
from quotes import get_price_usd, get_usd_rub, normalize_ticker

def _setup_logging():
    """Логи с ротацией. httpx/httpcore логируют URL запроса вместе с токеном бота
    на каждый getUpdates — приглушаем их до WARNING, иначе токен утекает в логи,
    а файл лога растёт без предела."""
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    root.addHandler(console)

    file_handler = RotatingFileHandler(
        os.path.join(os.path.dirname(__file__), "bot.log"),
        maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    # источники, которые шумят и/или светят токен в URL — только важное
    for noisy in ("httpx", "httpcore", "telegram.ext", "apscheduler"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


_setup_logging()
log = logging.getLogger("bezb")

DISCLAIMER = "_Не является индивидуальной инвестиционной рекомендацией._"

PRESET_CRYPTO = [("BTC", "₿ BTC/USDT"), ("ETH", "Ξ ETH/USDT")]
PRESET_STOCKS = ["SPY", "QQQ", "AAPL", "TSLA", "NVDA"]
PRESET_BUY_AMOUNTS = [50, 100, 250, 500, 1000]
PRESET_DEPO_RUB = [5000, 10000, 25000, 50000]
PRESET_WD_AMOUNTS = [100, 500, 1000]
PRESET_COPY_RUB = [10000, 30000, 50000, 100000]

# Готовые причины сделки (журнал решений)
REASONS = [
    "Плановая закупка (DCA)",
    "Докупка на просадке",
    "Ребаланс портфеля",
    "Долгосрочный тренд",
    "Свободный кэш",
    "Фиксация прибыли",
]

TICKER_HINT = (
    "*Популярные тикеры*\n\n"
    "₿ *Крипта:* BTC, ETH, SOL, BNB, XRP, TON, ADA, DOGE\n"
    "📈 *Акции США:* AAPL (Apple), MSFT (Microsoft), NVDA (Nvidia), "
    "TSLA (Tesla), GOOGL (Google), AMZN (Amazon), META\n"
    "🧺 *Фонды/ETF:* SPY (S&P 500), QQQ (Nasdaq-100), VOO, SCHD\n\n"
    "_Введи тикер (для крипты можно с /USDT — бот поймёт):_"
)


def _is_admin(uid):
    return uid == config.ADMIN_ID


def _fmt(x, suffix):
    return f"{x:,.2f} {suffix}".replace(",", " ")


def _display(ticker):
    for tk, label in PRESET_CRYPTO:
        if tk == ticker:
            return label
    return ticker


# ───────────────────────── Клавиатуры ─────────────────────────

def kb_reply() -> ReplyKeyboardMarkup:
    """Постоянная нижняя клавиатура."""
    return ReplyKeyboardMarkup(
        [[KeyboardButton("📊 Портфель"), KeyboardButton("☰ Меню")]],
        resize_keyboard=True, is_persistent=True,
    )


def kb_main(is_admin) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("📊 Портфель", callback_data="nav:portfolio"),
         InlineKeyboardButton("📈 Графики", callback_data="nav:chart")],
        [InlineKeyboardButton("💲 Цены", callback_data="price:menu"),
         InlineKeyboardButton("🏆 Сравнение", callback_data="cmp:show")],
        [InlineKeyboardButton("🎴 Поделиться результатом", callback_data="card:show")],
        [InlineKeyboardButton("📋 Повторить портфель", callback_data="copy:menu")],
    ]
    rows.append([InlineKeyboardButton("📔 Журнал сделок", callback_data="jrnl:show"),
                 InlineKeyboardButton("⭐ Избранное", callback_data="fav:menu")])
    if is_admin:
        rows += [
            [InlineKeyboardButton("➕ Купить", callback_data="buy:menu"),
             InlineKeyboardButton("➖ Продать", callback_data="sell:menu")],
            [InlineKeyboardButton("💵 Пополнить USDT", callback_data="depo:menu"),
             InlineKeyboardButton("💸 Вывести", callback_data="wd:menu")],
            [InlineKeyboardButton("🧾 Отмена операции", callback_data="ops:menu"),
             InlineKeyboardButton("📸 Снимок", callback_data="snap")],
        ]
    return InlineKeyboardMarkup(rows)


def kb_back() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Меню", callback_data="nav:main")]])


def _asset_rows(prefix):
    rows = [[InlineKeyboardButton(label, callback_data=f"{prefix}:{tk}")]
            for tk, label in PRESET_CRYPTO]
    for i in range(0, len(PRESET_STOCKS), 3):
        rows.append([InlineKeyboardButton(t, callback_data=f"{prefix}:{t}")
                     for t in PRESET_STOCKS[i:i + 3]])
    return rows


def kb_assets(prefix, custom_cb) -> InlineKeyboardMarkup:
    rows = []
    # избранное — быстрые кнопки сверху (по 3 в ряд), без дублей с пресетами
    preset_set = {tk for tk, _ in PRESET_CRYPTO} | set(PRESET_STOCKS)
    favs = [f for f in portfolio.get_favorites() if f not in preset_set]
    for i in range(0, len(favs), 3):
        rows.append([InlineKeyboardButton(f"⭐ {t}", callback_data=f"{prefix}:{t}")
                     for t in favs[i:i + 3]])
    rows += _asset_rows(prefix)
    rows.append([InlineKeyboardButton("✏️ Другой тикер", callback_data=custom_cb)])
    rows.append([InlineKeyboardButton("⬅️ Меню", callback_data="nav:main")])
    return InlineKeyboardMarkup(rows)


def _amount_kb(amounts, prefix, custom_cb, back_cb, extra=None, cur="$") -> InlineKeyboardMarkup:
    rows, row = [], []
    for a in amounts:
        label = f"{a} ₽" if cur == "₽" else f"${a}"
        row.append(InlineKeyboardButton(label, callback_data=f"{prefix}:{a}"))
        if len(row) == 3:
            rows.append(row); row = []
    if row:
        rows.append(row)
    if extra:
        rows.append(extra)
    rows.append([InlineKeyboardButton("✏️ Своя сумма", callback_data=custom_cb)])
    rows.append([InlineKeyboardButton("⬅️ Назад", callback_data=back_cb)])
    return InlineKeyboardMarkup(rows)


# ───────────────────────── Тексты ─────────────────────────

def _dot(x):
    return "🟢" if x > 0 else ("🔴" if x < 0 else "⚪")


def _summary_text(s) -> str:
    L = ["*📊 Портфель «Без Б»*", ""]

    # ── заметный итоговый блок наверху ──
    L += [
        "┏━━━━━━ ИТОГО ━━━━━━┓",
        f"💰 Баланс: *{_fmt(s['total_value_usdt'], '$')}*  /  *{_fmt(s['value_rub'], '₽')}*",
    ]
    if s["cost_usdt"] > 0:
        L += [
            f"{_dot(s['profit_usdt'])} Прибыль $: *{_fmt(s['profit_usdt'], '$')}* "
            f"(*{s['profit_usdt_pct']:+.1f}%*)",
            f"{_dot(s['profit_rub'])} Прибыль ₽: *{_fmt(s['profit_rub'], '₽')}* "
            f"(*{s['profit_rub_pct']:+.1f}%*)",
        ]
    L += ["┗━━━━━━━━━━━━━━━━━┛"]

    # ── накопленный реализованный доход (за всё время) ──
    if abs(s["realized_usdt"]) > 1e-6 or abs(s["realized_rub"]) > 1e-6:
        L.append(
            f"{_dot(s['realized_usdt'])} Реализовано за всё время: "
            f"*{_fmt(s['realized_usdt'], '$')}* / *{_fmt(s['realized_rub'], '₽')}*")
    L.append(f"📈 Индекс Без Б: *{s['index']:.1f}* пт ({s['index'] - 100:+.1f})")
    L.append("")

    # ── разбивка баланса ──
    L += [f"📦 Активы: {_fmt(s['positions_value_usdt'], 'USDT')}  |  "
          f"💵 Кэш: {_fmt(s['usdt_cash'], 'USDT')}"]

    if s["positions"]:
        L.append("")
        L.append("*Позиции (оценка в USDT):*")
        for p in s["positions"]:
            sign = "🟢" if p.profit_usdt > 0 else ("🔴" if p.profit_usdt < 0 else "⚪")
            L.append(
                f"{sign} *{_display(p.ticker)}* — {_fmt(p.value_usd, 'USDT')}\n"
                f"   {p.qty:.6g} шт. | ср. цена ${p.avg_price_usdt:,.2f} → тек. ${p.price_now:,.2f}\n"
                f"   {p.profit_pct:+.1f}% ({_fmt(p.profit_usdt, 'USDT')})"
            )

    if s["cost_usdt"] > 0:
        L += [
            "",
            f"📥 Вложено в позиции: {_fmt(s['cost_usdt'], 'USDT')} / "
            f"{_fmt(s['cost_rub'], '₽')}  (ср. курс {s['avg_deposit_rate']:.2f} ₽)",
            "_прибыль в рублях, в т.ч.:_",
            f"   • рост активов: {_fmt(s['asset_gain_rub'], '₽')}",
            f"   • курсовая разница: {_fmt(s['fx_gain_rub'], '₽')}",
        ]
    elif not s["positions"] and s["usdt_cash"] <= 1e-6:
        L.append("\n_Портфель пуст. Нажми «💵 Пополнить USDT», затем «➕ Купить»._")

    L += ["", f"💱 Курс ЦБ: 1$ = {s['rate_now']:.2f} ₽", "", DISCLAIMER]
    return "\n".join(L)


def _comparison_text(c) -> str:
    L = ["*🏆 Без Б против рынка*",
         f"_купил-и-держу, с {c['start']}_", "",
         f"📥 Вложено: {_fmt(c['invested_usd'], '$')} / {_fmt(c['invested_rub'], '₽')}", ""]
    for i, r in enumerate(c["results"]):
        medal = ["🥇", "🥈", "🥉"][i] if i < 3 else "▫️"
        marker = "👉 " if r.get("is_me") else ""
        ru = f"{r['ret_rub_pct']:+.1f}% ₽" if r["ret_rub_pct"] is not None else "—"
        us = f"{r['ret_usd_pct']:+.1f}% $" if r["ret_usd_pct"] is not None else "—"
        L.append(f"{medal} {marker}*{r['name']}*: {ru}  /  {us}")
    L += ["", "_Сравнение стратегий «купил и держу», без учёта продаж._", "", DISCLAIMER]
    return "\n".join(L)


def _copy_text(s, capital_rub) -> str:
    rate = s["rate_now"]
    total = s["positions_value_usdt"]
    cap_usd = capital_rub / rate
    L = ["*📋 Повтори портфель Без Б*",
         f"Твой капитал: {_fmt(capital_rub, '₽')}  (≈ {_fmt(cap_usd, '$')})", "",
         "_Распределение по текущей структуре:_", ""]
    for p in s["positions"]:
        w = p.value_usd / total
        amt_rub = capital_rub * w
        amt_usd = cap_usd * w
        qty = amt_usd / p.price_now if p.price_now else 0
        L.append(
            f"• *{_display(p.ticker)}* — {w * 100:.0f}%\n"
            f"   {_fmt(amt_rub, '₽')} (≈ {amt_usd:,.0f} $ · ~{qty:.4g} шт.)".replace(",", " "))
    L += ["", f"💱 Курс ЦБ: 1$ = {rate:.2f} ₽",
          "_Доли — на текущую дату; не ИИР, решение за тобой._", "", DISCLAIMER]
    return "\n".join(L)


async def _finalize_trade(q, context, txid, is_admin):
    """Завершить запись сделки: пост в канал + подтверждение."""
    posted = await _post_trade(context, txid)
    tx = portfolio.get_operation(txid)
    rsn = (tx or {}).get("reason")
    msg = "📔 Записано в журнал."
    if rsn:
        msg += f" Причина: _{rsn}_."
    msg += "\n📢 Опубликовано в канал." if posted else "\n_(канал не подключён — пост не отправлен)_"
    await q.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=kb_main(is_admin))


async def _post_trade(context, txid) -> bool:
    """Опубликовать сделку в канал. Возвращает True, если отправлено.

    Перед каналом — мгновенный пуш подписчикам (премиум-скорость, раньше канала).
    """
    tx = portfolio.get_operation(txid)
    if not tx:
        return False
    try:
        import asyncio
        import notify
        asyncio.create_task(asyncio.to_thread(notify.notify_trade, dict(tx)))
    except Exception:
        log.exception("subscriber push failed")
    if not config.CHANNEL_ID:
        return False
    s = portfolio.summary()
    ttype = tx.get("type") or tx.get("side")
    price = tx.get("price_usdt", tx.get("price_usd"))
    amount = tx.get("amount_usdt", tx["qty"] * price)
    icon = "📥" if ttype == "buy" else "📤"
    verb = "Купил" if ttype == "buy" else "Продал"
    share = _trade_share(s, tx["ticker"])
    text = (f"{icon} *Сделка — Без Б*\n"
            f"{verb} *{_display(tx['ticker'])}* на {amount:,.0f}$ по ${price:,.2f}").replace(",", " ")
    if share > 0:
        text += f"\nДоля в портфеле: {share:.0f}%"
    if tx.get("reason"):
        text += f"\nПричина: {tx['reason']}"
    text += f"\n\n📊 Слежу за портфелём открыто → {config.CHANNEL_NAME}"
    try:
        await context.bot.send_message(config.CHANNEL_ID, text, parse_mode=ParseMode.MARKDOWN)
        return True
    except Exception:
        log.exception("post trade failed")
        return False


def _journal_text() -> str:
    trades = [t for t in portfolio.get_operations()
              if (t.get("type") or t.get("side")) in ("buy", "sell")][:12]
    if not trades:
        return "*📔 Журнал сделок*\n\n_Сделок пока нет._"
    L = ["*📔 Журнал сделок*", "_последние сделки и причины_", ""]
    for t in trades:
        d = datetime.fromtimestamp(t["ts"]).strftime("%d.%m")
        ttype = t.get("type") or t.get("side")
        side = "🟢 Купил" if ttype == "buy" else "🔴 Продал"
        price = t.get("price_usdt", t.get("price_usd"))
        amount = t.get("amount_usdt", t["qty"] * price)
        L.append(f"{d} · {side} *{_display(t['ticker'])}* на {amount:,.0f}$ по ${price:,.2f}"
                 .replace(",", " "))
        if t.get("reason"):
            L.append(f"      _{t['reason']}_")
    L += ["", DISCLAIMER]
    return "\n".join(L)


async def _show_copy(q, capital_rub, is_admin):
    s = portfolio.summary()
    if not s["positions"] or s["positions_value_usdt"] <= 0:
        await q.edit_message_text("Портфель пуст — копировать нечего.", reply_markup=kb_back())
        return
    await q.edit_message_text(_copy_text(s, capital_rub), parse_mode=ParseMode.MARKDOWN,
                              reply_markup=kb_main(is_admin))


# ───────────────────────── Команды ─────────────────────────

WELCOME = (
    "👋 *Привет! Это «Без Б» — инвестиции без буллшита.*\n\n"
    "Я веду публичный портфель *для тебя* — чтобы показать на живом примере, что "
    "инвестировать *просто и по силам каждому*. Каждая покупка и продажа — открыто, "
    "с причиной, в реальном времени, без задним числом. Никаких «иксов» и обещаний "
    "золотых гор — только реальные сделки и честные результаты, в том числе ошибки.\n\n"
    "*Что внутри приложения:*\n"
    "📊 Портфель — состав, баланс и доходность в ₽ и $\n"
    "📈 Динамика — рост капитала и сравнение с рынком\n"
    "📔 Журнал — все сделки с причинами\n"
    "🧮 Расчёт — калькулятор: как создаётся капитал, если начать сейчас, "
    "а не «потом»\n"
    "📋 Повтори стратегию под свой капитал\n\n"
    "Жми «🚀 Открыть приложение» и заходи в канал — там разборы и контекст.\n\n"
    "_Это личный портфель автора и не является индивидуальной инвестиционной "
    "рекомендацией._"
)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    # реферальный диплинк: /start ref_<id>
    if context.args and context.args[0].startswith("ref_"):
        try:
            ref_id = int(context.args[0][4:])
            referee = f"u{update.effective_user.id}"
            referrer = f"u{ref_id}"
            if storage.add_referral(referee, referrer):
                until = storage.grant_premium(referrer, config.REFERRAL_PREMIUM_DAYS)
                cnt = storage.referral_count(referrer)
                when = datetime.fromtimestamp(until).strftime("%d.%m.%Y")
                try:
                    await context.bot.send_message(
                        ref_id,
                        f"🎉 По твоей ссылке пришёл друг! +{config.REFERRAL_PREMIUM_DAYS} дня "
                        f"премиума (до {when}). Всего друзей: {cnt}.")
                except Exception:
                    pass
        except Exception:
            log.exception("referral start failed")
    is_admin = _is_admin(update.effective_user.id)
    await update.message.reply_text(
        WELCOME, parse_mode=ParseMode.MARKDOWN, reply_markup=kb_reply())
    rows = [
        [InlineKeyboardButton("🚀 Открыть приложение",
                              web_app=WebAppInfo(url=config.MINIAPP_URL))],
        [InlineKeyboardButton("📢 Канал «Без Б»", url=config.CHANNEL_URL)],
    ]
    rows += kb_main(is_admin).inline_keyboard
    await update.message.reply_text(
        "Открой приложение или выбери раздел:", reply_markup=InlineKeyboardMarkup(rows))


async def cmd_portfolio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    s = portfolio.summary()
    await update.message.reply_text(_summary_text(s), parse_mode=ParseMode.MARKDOWN,
                                    reply_markup=kb_back())


# ───────────────────────── Действия ─────────────────────────

def _reason_kb(tx_id) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(r, callback_data=f"rsn:p:{tx_id}:{i}")]
            for i, r in enumerate(REASONS)]
    rows.append([InlineKeyboardButton("✍️ Своя причина", callback_data=f"rsn:c:{tx_id}")])
    rows.append([InlineKeyboardButton("⏭ Без причины", callback_data=f"rsn:s:{tx_id}")])
    return InlineKeyboardMarkup(rows)


def _trade_share(s, ticker):
    pv = s["positions_value_usdt"]
    if pv <= 0:
        return 0.0
    v = next((p.value_usd for p in s["positions"] if p.ticker == ticker), 0)
    return v / pv * 100


async def _after_trade(target, tx, is_admin):
    """После сделки: подтверждение + выбор причины (журнал и пост в канал)."""
    s = portfolio.summary()
    ttype = tx.get("type") or tx.get("side")
    price = tx.get("price_usdt", tx.get("price_usd"))
    amount = tx.get("amount_usdt", tx["qty"] * price)
    verb = "Куплено" if ttype == "buy" else "Продано"
    text = (f"✅ {verb}: *{_display(tx['ticker'])}* на {amount:,.0f}$ по ${price:,.2f}\n"
            f"Кэш: {_fmt(s['usdt_cash'], 'USDT')}\n\n"
            f"_Зачем эта сделка? — для журнала и поста в канал:_").replace(",", " ")
    await target.reply_text(text, parse_mode=ParseMode.MARKDOWN,
                            reply_markup=_reason_kb(tx["id"]))


async def _do_buy(target, ticker, amount, is_admin):
    tx = portfolio.market_buy(ticker, amount)
    await _after_trade(target, tx, is_admin)


async def _do_deposit(target, usdt, rate, is_admin):
    portfolio.add_deposit(usdt, rate)
    await target.reply_text(
        f"✅ Пополнено: *{usdt:,.0f} USDT* по {rate:.2f} ₽ = {_fmt(usdt * rate, '₽')}",
        parse_mode=ParseMode.MARKDOWN, reply_markup=kb_main(is_admin))


# ───────────────────────── Кнопки ─────────────────────────

async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data, msg = q.data, q.message
    is_admin = _is_admin(q.from_user.id)

    try:
        if data == "nav:main":
            context.user_data.clear()
            await q.edit_message_text("Меню:", reply_markup=kb_main(is_admin))

        elif data == "nav:portfolio":
            s = portfolio.summary()
            await q.edit_message_text(_summary_text(s), parse_mode=ParseMode.MARKDOWN,
                                      reply_markup=kb_back())

        elif data == "nav:chart":
            await msg.chat.send_action("upload_photo")
            s = portfolio.summary()
            await msg.reply_photo(charts.composition_pie(portfolio.pie_slices(s)),
                                  caption="Состав портфеля")
            await msg.reply_photo(charts.growth_line(), caption="Динамика стоимости")
            await msg.reply_photo(charts.index_line(), caption="Индекс Без Б")
            await msg.reply_text("Меню:", reply_markup=kb_main(is_admin))

        # причина сделки (журнал + пост в канал)
        elif data.startswith("rsn:p:"):
            _require_admin(is_admin)
            parts = data.split(":")
            portfolio.set_reason(int(parts[2]), REASONS[int(parts[3])])
            await _finalize_trade(q, context, int(parts[2]), is_admin)
        elif data.startswith("rsn:c:"):
            _require_admin(is_admin)
            txid = int(data.split(":")[2])
            context.user_data["reason_tx"] = txid
            context.user_data["flow"] = "reason_text"
            await q.edit_message_text("Введи причину сделки одним сообщением:",
                                      reply_markup=kb_back())
        elif data.startswith("rsn:s:"):
            _require_admin(is_admin)
            await _finalize_trade(q, context, int(data.split(":")[2]), is_admin)

        # журнал сделок
        elif data == "jrnl:show":
            await q.edit_message_text(_journal_text(), parse_mode=ParseMode.MARKDOWN,
                                      reply_markup=kb_back())

        elif data == "copy:menu":
            s = portfolio.summary()
            if not s["positions"] or s["positions_value_usdt"] <= 0:
                await q.edit_message_text(
                    "Портфель пока пуст — копировать нечего. Загляни позже.",
                    reply_markup=kb_back())
                return
            await q.edit_message_text(
                "📋 *Повтори стратегию Без Б.*\nКакой у тебя капитал? Разложу его по "
                "текущей структуре портфеля.", parse_mode=ParseMode.MARKDOWN,
                reply_markup=_amount_kb(PRESET_COPY_RUB, "copy:amt", "copy:amtc", "nav:main", cur="₽"))
        elif data.startswith("copy:amt:"):
            await _show_copy(q, float(data.split(":", 2)[2]), is_admin)
        elif data == "copy:amtc":
            context.user_data["flow"] = "copy_amount"
            await q.edit_message_text("Введи сумму капитала в рублях (например, `100000`):",
                                      parse_mode=ParseMode.MARKDOWN, reply_markup=kb_back())

        elif data == "card:show":
            await msg.chat.send_action("upload_photo")
            s = portfolio.summary()
            card = charts.result_card(s, config.CHANNEL_NAME)
            caption = (
                f"📈 Мой публичный портфель в реальном времени\n"
                f"Доходность: {s['profit_rub_pct']:+.1f}% ₽ / {s['profit_usdt_pct']:+.1f}% $\n\n"
                f"Все сделки открыто → {config.CHANNEL_NAME}\n"
                f"_Перешли эту карточку друзьям 👆_"
            )
            await q.edit_message_reply_markup(reply_markup=None)
            await msg.reply_photo(
                card, caption=caption, parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📢 Подписаться на канал", url=config.CHANNEL_URL)],
                    [InlineKeyboardButton("⬅️ Меню", callback_data="nav:main")]]))
            return

        elif data == "cmp:show":
            await msg.chat.send_action("typing")
            cmp = benchmark.compare()
            if not cmp:
                await q.edit_message_text(
                    "Пока нет покупок для сравнения. Сначала «➕ Купить».",
                    reply_markup=kb_back())
                return
            await q.edit_message_reply_markup(reply_markup=None)
            await msg.reply_text(_comparison_text(cmp), parse_mode=ParseMode.MARKDOWN)
            await msg.reply_photo(charts.benchmark_bar(cmp["results"]))
            await msg.reply_text("Меню:", reply_markup=kb_main(is_admin))

        # цены
        elif data == "price:menu":
            await q.edit_message_text("Выбери актив для котировки:",
                                      reply_markup=kb_assets("price:t", "price:custom"))
        elif data.startswith("price:t:"):
            await _show_price(q, data.split(":", 2)[2])
        elif data == "price:custom":
            context.user_data["flow"] = "price_ticker"
            await q.edit_message_text(TICKER_HINT, parse_mode=ParseMode.MARKDOWN,
                                      reply_markup=kb_back())

        # покупка
        elif data == "buy:menu":
            _require_admin(is_admin)
            await q.edit_message_text("Что покупаем по рынку?",
                                      reply_markup=kb_assets("buy:a", "buy:custom"))
        elif data.startswith("buy:a:"):
            _require_admin(is_admin)
            ticker = data.split(":", 2)[2]
            context.user_data["buy_ticker"] = ticker
            await q.edit_message_text(
                f"Покупаем *{_display(ticker)}* по рынку.\nНа сколько USDT?",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=_amount_kb(PRESET_BUY_AMOUNTS, "buy:amt", "buy:amtc", "buy:menu"))
        elif data == "buy:custom":
            _require_admin(is_admin)
            context.user_data["flow"] = "buy_ticker"
            await q.edit_message_text(TICKER_HINT, parse_mode=ParseMode.MARKDOWN,
                                      reply_markup=kb_back())
        elif data.startswith("buy:amt:"):
            _require_admin(is_admin)
            ticker = context.user_data.get("buy_ticker")
            if not ticker:
                await q.edit_message_text("Сначала выбери актив.",
                    reply_markup=kb_assets("buy:a", "buy:custom")); return
            await msg.chat.send_action("typing")
            await q.edit_message_reply_markup(reply_markup=None)
            await _do_buy(msg, ticker, float(data.split(":", 2)[2]), is_admin)
        elif data == "buy:amtc":
            _require_admin(is_admin)
            context.user_data["flow"] = "buy_amount"
            await q.edit_message_text("Введи сумму покупки в USDT (например, `150`):",
                                      parse_mode=ParseMode.MARKDOWN, reply_markup=kb_back())

        # пополнение (калькулятор: рубли -> курс -> USDT -> подтверждение)
        elif data == "depo:menu":
            _require_admin(is_admin)
            await q.edit_message_text(
                "💵 *Пополнение.* Сколько рублей заводишь?", parse_mode=ParseMode.MARKDOWN,
                reply_markup=_amount_kb(PRESET_DEPO_RUB, "depo:rub", "depo:rubc", "nav:main", cur="₽"))
        elif data.startswith("depo:rub:"):
            _require_admin(is_admin)
            context.user_data["depo_rub"] = float(data.split(":", 2)[2])
            context.user_data["flow"] = "depo_rate"
            await _ask_rate(q)
        elif data == "depo:rubc":
            _require_admin(is_admin)
            context.user_data["flow"] = "depo_rub_amount"
            await q.edit_message_text("Введи сумму пополнения в рублях (например, `30000`):",
                                      parse_mode=ParseMode.MARKDOWN, reply_markup=kb_back())
        elif data == "depo:confirm":
            _require_admin(is_admin)
            rub = context.user_data.get("depo_rub")
            rate = context.user_data.get("depo_rate")
            context.user_data.clear()
            if not rub or not rate:
                await q.edit_message_text("Данные пополнения потерялись, начни заново.",
                                          reply_markup=kb_main(is_admin)); return
            usdt = rub / rate
            portfolio.add_deposit(usdt, rate)
            await q.edit_message_text(
                f"✅ Пополнено: {_fmt(rub, '₽')} ÷ {rate:.2f} = *{_fmt(usdt, 'USDT')}*",
                parse_mode=ParseMode.MARKDOWN, reply_markup=kb_main(is_admin))

        # вывод
        elif data == "wd:menu":
            _require_admin(is_admin)
            s = portfolio.summary()
            extra = [InlineKeyboardButton(f"Вывести всё ({s['usdt_cash']:,.0f})",
                                          callback_data="wd:all")]
            await q.edit_message_text(
                f"Вывод USDT. Доступно: *{_fmt(s['usdt_cash'], 'USDT')}*\nСколько вывести?",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=_amount_kb(PRESET_WD_AMOUNTS, "wd:amt", "wd:amtc", "nav:main", extra))
        elif data.startswith("wd:amt:"):
            _require_admin(is_admin)
            await _do_withdraw(q, float(data.split(":", 2)[2]), is_admin)
        elif data == "wd:all":
            _require_admin(is_admin)
            s = portfolio.summary()
            await _do_withdraw(q, max(0.0, s["usdt_cash"]), is_admin)
        elif data == "wd:amtc":
            _require_admin(is_admin)
            context.user_data["flow"] = "wd_amount"
            await q.edit_message_text("Введи сумму вывода в USDT:",
                                      reply_markup=kb_back())

        # продажа (полная или частичная)
        elif data == "sell:menu":
            _require_admin(is_admin)
            await _show_sell_menu(q)
        elif data.startswith("sell:p:"):
            _require_admin(is_admin)
            ticker = data.split(":", 2)[2]
            pos = next((p for p in portfolio.get_positions() if p.ticker == ticker), None)
            if not pos:
                await q.edit_message_text("Позиция не найдена.", reply_markup=kb_back()); return
            context.user_data["sell_ticker"] = ticker
            extra = [InlineKeyboardButton(f"Продать всё (${pos.value_usd:,.0f})",
                                          callback_data=f"sell:all:{ticker}")]
            await q.edit_message_text(
                f"Продаём *{_display(ticker)}* по рынку. В позиции ${pos.value_usd:,.0f}.\n"
                f"На сколько USDT продать?", parse_mode=ParseMode.MARKDOWN,
                reply_markup=_amount_kb(PRESET_BUY_AMOUNTS, f"sell:amt:{ticker}",
                                        f"sell:amtc:{ticker}", "sell:menu", extra))
        elif data.startswith("sell:amt:"):
            _require_admin(is_admin)
            _, _, ticker, amount = data.split(":", 3)
            await msg.chat.send_action("typing")
            await q.edit_message_reply_markup(reply_markup=None)
            await _do_sell(msg, ticker, float(amount), is_admin)
        elif data.startswith("sell:amtc:"):
            _require_admin(is_admin)
            context.user_data["sell_ticker"] = data.split(":", 2)[2]
            context.user_data["flow"] = "sell_amount"
            await q.edit_message_text("Введи сумму продажи в USDT:", reply_markup=kb_back())
        elif data.startswith("sell:all:"):
            _require_admin(is_admin)
            ticker = data.split(":", 2)[2]
            await msg.chat.send_action("typing")
            await q.edit_message_reply_markup(reply_markup=None)
            await _do_sell(msg, ticker, None, is_admin)

        elif data == "snap":
            _require_admin(is_admin)
            s = portfolio.record_snapshot()
            await q.edit_message_text(
                f"📸 Снимок: {_fmt(s['value_rub'], '₽')} ({s['profit_rub_pct']:+.1f}%)",
                reply_markup=kb_main(is_admin))

        # избранное
        elif data == "fav:menu":
            await _show_fav_menu(q, is_admin)
        elif data.startswith("fav:rm:"):
            _require_admin(is_admin)
            portfolio.remove_favorite(data.split(":", 2)[2])
            await _show_fav_menu(q, is_admin)
        elif data.startswith("fav:add:"):
            _require_admin(is_admin)
            tk = data.split(":", 2)[2]
            ok = portfolio.add_favorite(tk)
            await q.answer("Добавлено в избранное ⭐" if ok else "Уже в избранном")
        elif data == "fav:addnew":
            _require_admin(is_admin)
            context.user_data["flow"] = "fav_add"
            await q.edit_message_text(TICKER_HINT, parse_mode=ParseMode.MARKDOWN,
                                      reply_markup=kb_back())

        # операции: единый список с удалением любой (актив или USDT)
        elif data == "ops:menu":
            _require_admin(is_admin)
            await _show_ops_menu(q)
        elif data.startswith("ops:del:"):
            _require_admin(is_admin)
            tx = portfolio.delete_tx(int(data.split(":", 2)[2]))
            if tx:
                await q.answer("Удалено")
            await _show_ops_menu(q)

        else:
            await q.answer("Неизвестная кнопка")

    except PermissionError:
        await q.answer("⛔ Только владелец портфеля", show_alert=True)
    except Exception as e:
        log.exception("callback error: %s", data)
        await msg.reply_text(f"⚠️ Ошибка: {e}", reply_markup=kb_main(is_admin))


def _require_admin(is_admin):
    if not is_admin:
        raise PermissionError()


async def _ask_rate(q):
    rate = get_usd_rub()
    usdt = q.message  # not used; just for context
    await q.edit_message_text(
        f"По какому курсу купил USDT? Введи ₽ за 1 USDT (например, `{rate:.2f}`).\n"
        f"_Текущий курс ЦБ: {rate:.2f} ₽._",
        parse_mode=ParseMode.MARKDOWN, reply_markup=kb_back())


async def _do_withdraw(q, amount, is_admin):
    portfolio.add_withdraw(amount)
    s = portfolio.summary()
    await q.edit_message_text(
        f"✅ Выведено: {_fmt(amount, 'USDT')}\nОстаток кэша: {_fmt(s['usdt_cash'], 'USDT')}",
        reply_markup=kb_main(is_admin))


async def _show_price(q, ticker):
    try:
        price, rate = get_price_usd(ticker), get_usd_rub()
    except Exception as e:
        await q.edit_message_text(f"Не удалось получить цену для *{ticker}*: {e}",
            parse_mode=ParseMode.MARKDOWN, reply_markup=kb_assets("price:t", "price:custom"))
        return
    await q.edit_message_text(
        f"*{_display(ticker)}*\n💵 ${price:,.2f}  (~{price * rate:,.2f} ₽)\n"
        f"💱 Курс ЦБ: 1$ = {rate:.2f} ₽", parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⭐ В избранное", callback_data=f"fav:add:{normalize_ticker(ticker)}"),
             InlineKeyboardButton("💲 Другая цена", callback_data="price:menu")],
            [InlineKeyboardButton("⬅️ Меню", callback_data="nav:main")]]))


async def _do_sell(target, ticker, amount, is_admin):
    tx = portfolio.market_sell(ticker, amount)
    await _after_trade(target, tx, is_admin)


async def _show_sell_menu(q):
    positions = portfolio.get_positions()
    if not positions:
        await q.edit_message_text("Нет открытых позиций для продажи.", reply_markup=kb_back())
        return
    rows = [[InlineKeyboardButton(
        f"{_display(p.ticker)} (${p.value_usd:,.0f})",
        callback_data=f"sell:p:{p.ticker}")] for p in positions]
    rows.append([InlineKeyboardButton("⬅️ Меню", callback_data="nav:main")])
    await q.edit_message_text("Что продаём? (можно частично)",
                              reply_markup=InlineKeyboardMarkup(rows))


async def _show_ops_menu(q):
    ops = portfolio.get_operations()
    if not ops:
        await q.edit_message_text("Операций пока нет.", reply_markup=kb_back()); return
    rows = []
    for t in ops[:20]:  # последние 20
        rows.append([InlineKeyboardButton(f"🗑 {_describe_tx(t)}",
                                          callback_data=f"ops:del:{t['id']}")])
    rows.append([InlineKeyboardButton("⬅️ Меню", callback_data="nav:main")])
    await q.edit_message_text(
        "*🧾 Отмена операции* — нажми, чтобы отменить любую "
        "(пополнение, покупку, продажу, вывод):",
        parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(rows))


async def _show_fav_menu(q, is_admin):
    favs = portfolio.get_favorites()
    lines = ["*⭐ Избранные активы* — текущие цены (USDT):"]
    rows = []
    if favs:
        for t in favs:
            try:
                price = get_price_usd(t, allow_stale=True)
                lines.append(f"• *{t}*: {price:,.2f} USDT")
            except Exception:
                lines.append(f"• *{t}*: цена недоступна")
        if is_admin:
            lines.append("\n_Убрать из избранного:_")
            for i in range(0, len(favs), 3):
                rows.append([InlineKeyboardButton(f"❌ {t}", callback_data=f"fav:rm:{t}")
                             for t in favs[i:i + 3]])
    else:
        lines.append("\n_Пока пусто._")
    if is_admin:
        rows.append([InlineKeyboardButton("➕ Добавить тикер", callback_data="fav:addnew")])
    rows.append([InlineKeyboardButton("⬅️ Меню", callback_data="nav:main")])
    await q.edit_message_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN,
                              reply_markup=InlineKeyboardMarkup(rows))


def _describe_tx(t):
    ttype = t.get("type") or t.get("side")
    if ttype == "deposit":
        return f"пополнение {t['usdt']:.0f} USDT по {t['rate_rub']:.2f} ₽"
    if ttype == "withdraw":
        return f"вывод {t['usdt']:.0f} USDT"
    if ttype in ("buy", "sell", "asset_deposit"):
        price = t.get("price_usdt", t.get("price_usd"))
        verb = {"buy": "покупка", "sell": "продажа",
                "asset_deposit": "завод актива"}[ttype]
        return f"{verb} {_display(t['ticker'])}: {t['qty']:.6g} шт. по ${price:,.2f}"
    return "операция"


# ───────────────────────── Ввод текста ─────────────────────────

def _clean_ticker(text):
    return text.strip().upper().replace("/USDT", "").replace("USDT", "")


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    is_admin = _is_admin(update.effective_user.id)

    # нижняя постоянная клавиатура
    if text in ("☰ Меню", "Меню"):
        context.user_data.clear()
        await update.message.reply_text("Меню:", reply_markup=kb_main(is_admin)); return
    if text == "📊 Портфель":
        await cmd_portfolio(update, context); return

    flow = context.user_data.get("flow")
    if not flow:
        return

    if flow == "price_ticker":
        context.user_data.pop("flow", None)
        ticker = _clean_ticker(text)
        try:
            price, rate = get_price_usd(ticker), get_usd_rub()
        except Exception as e:
            await update.message.reply_text(f"Не нашёл {ticker}: {e}",
                reply_markup=kb_assets("price:t", "price:custom")); return
        await update.message.reply_text(
            f"*{ticker}*: ${price:,.2f}  (~{price * rate:,.2f} ₽)\n💱 1$ = {rate:.2f} ₽",
            parse_mode=ParseMode.MARKDOWN, reply_markup=kb_main(is_admin))

    elif flow == "buy_ticker":
        if not is_admin:
            return
        ticker = _clean_ticker(text)
        try:
            get_price_usd(ticker)
        except Exception as e:
            await update.message.reply_text(f"Тикер {ticker} не найден ({e}). Попробуй другой:",
                                            reply_markup=kb_back()); return
        context.user_data["buy_ticker"] = ticker
        context.user_data.pop("flow", None)
        await update.message.reply_text(
            f"Тикер *{ticker}* принят. На сколько USDT покупаем?", parse_mode=ParseMode.MARKDOWN,
            reply_markup=_amount_kb(PRESET_BUY_AMOUNTS, "buy:amt", "buy:amtc", "buy:menu"))

    elif flow == "buy_amount":
        if not is_admin:
            return
        amount = _parse_amount(text)
        if amount is None:
            await update.message.reply_text("Нужна положительная сумма, например 150"); return
        ticker = context.user_data.get("buy_ticker")
        context.user_data.pop("flow", None)
        if not ticker:
            await update.message.reply_text("Сначала выбери актив.",
                reply_markup=kb_assets("buy:a", "buy:custom")); return
        await update.message.chat.send_action("typing")
        await _do_buy(update.message, ticker, amount, is_admin)

    elif flow == "depo_rub_amount":
        if not is_admin:
            return
        rub = _parse_amount(text)
        if rub is None:
            await update.message.reply_text("Нужна сумма в рублях, например 30000"); return
        context.user_data["depo_rub"] = rub
        context.user_data["flow"] = "depo_rate"
        rate = get_usd_rub()
        await update.message.reply_text(
            f"По какому курсу покупаешь USDT? Введи ₽ за 1 USDT (текущий ЦБ: {rate:.2f}).")

    elif flow == "depo_rate":
        if not is_admin:
            return
        rate = _parse_amount(text)
        if rate is None:
            await update.message.reply_text("Нужен курс, например 95.5"); return
        rub = context.user_data.get("depo_rub")
        if not rub:
            context.user_data.clear()
            await update.message.reply_text("Сначала укажи сумму пополнения.",
                                            reply_markup=kb_main(is_admin)); return
        context.user_data["depo_rate"] = rate
        context.user_data.pop("flow", None)
        usdt = rub / rate
        await update.message.reply_text(
            f"🧮 *Расчёт пополнения:*\n{_fmt(rub, '₽')} ÷ {rate:.2f} ₽ = *{_fmt(usdt, 'USDT')}*\n\n"
            f"Подтверждаешь?", parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Подтвердить", callback_data="depo:confirm")],
                [InlineKeyboardButton("⬅️ Отмена", callback_data="nav:main")]]))

    elif flow == "sell_amount":
        if not is_admin:
            return
        amount = _parse_amount(text)
        if amount is None:
            await update.message.reply_text("Нужна положительная сумма USDT"); return
        ticker = context.user_data.get("sell_ticker")
        context.user_data.pop("flow", None)
        if not ticker:
            await update.message.reply_text("Сначала выбери позицию.", reply_markup=kb_back()); return
        await update.message.chat.send_action("typing")
        await _do_sell(update.message, ticker, amount, is_admin)

    elif flow == "reason_text":
        if not is_admin:
            return
        txid = context.user_data.pop("reason_tx", None)
        context.user_data.pop("flow", None)
        if txid:
            portfolio.set_reason(txid, text)
            posted = await _post_trade(context, txid)
            extra = "📢 Опубликовано в канал." if posted else "_(канал не подключён)_"
            await update.message.reply_text(f"📔 Причина записана. {extra}",
                                            parse_mode=ParseMode.MARKDOWN,
                                            reply_markup=kb_main(is_admin))
        else:
            await update.message.reply_text("Сделка не найдена.", reply_markup=kb_main(is_admin))

    elif flow == "copy_amount":
        context.user_data.pop("flow", None)
        capital = _parse_amount(text)
        if capital is None:
            await update.message.reply_text("Нужна сумма в рублях, например 100000"); return
        s = portfolio.summary()
        if not s["positions"] or s["positions_value_usdt"] <= 0:
            await update.message.reply_text("Портфель пуст — копировать нечего.",
                                            reply_markup=kb_main(is_admin)); return
        await update.message.reply_text(_copy_text(s, capital), parse_mode=ParseMode.MARKDOWN,
                                        reply_markup=kb_main(is_admin))

    elif flow == "fav_add":
        if not is_admin:
            return
        context.user_data.pop("flow", None)
        ticker = _clean_ticker(text)
        try:
            get_price_usd(ticker)
        except Exception as e:
            await update.message.reply_text(f"Тикер {ticker} не найден ({e}). Попробуй другой.",
                                            reply_markup=kb_back()); return
        ok = portfolio.add_favorite(ticker)
        await update.message.reply_text(
            f"{'⭐ Добавлено' if ok else 'Уже было'} в избранном: *{ticker}*",
            parse_mode=ParseMode.MARKDOWN, reply_markup=kb_main(is_admin))

    elif flow == "wd_amount":
        if not is_admin:
            return
        amount = _parse_amount(text)
        if amount is None:
            await update.message.reply_text("Нужна положительная сумма USDT"); return
        context.user_data.pop("flow", None)
        portfolio.add_withdraw(amount)
        s = portfolio.summary()
        await update.message.reply_text(
            f"✅ Выведено: {_fmt(amount, 'USDT')}\nОстаток кэша: {_fmt(s['usdt_cash'], 'USDT')}",
            reply_markup=kb_main(is_admin))


def _parse_amount(text):
    try:
        v = float(text.replace(",", ".").replace("$", "").replace("₽", "").strip())
        return v if v > 0 else None
    except ValueError:
        return None


# ───────────────────────── Публикация / расписание ─────────────────────────

async def _publish_to_channel(context):
    if not config.CHANNEL_ID:
        return
    s = portfolio.summary()
    await context.bot.send_message(config.CHANNEL_ID, _summary_text(s),
                                   parse_mode=ParseMode.MARKDOWN)
    await context.bot.send_photo(config.CHANNEL_ID, charts.composition_pie(portfolio.pie_slices(s)))
    await context.bot.send_photo(config.CHANNEL_ID, charts.growth_line())


async def job_weekly(context: ContextTypes.DEFAULT_TYPE):
    try:
        s = portfolio.record_snapshot()
        log.info("weekly snapshot: %.2f RUB (%.1f%%)", s["value_rub"], s["profit_rub_pct"])
    except Exception:
        log.exception("weekly snapshot failed"); return
    try:
        await _publish_to_channel(context)
    except Exception:
        log.exception("weekly publish failed")


# ───────────── Планировщик контента (черновики на ревью) ─────────────
# Бот по расписанию рубрик сам готовит AI-черновик и кладёт в очередь
# «Контент-студии», затем шлёт владельцу пинг «готово». Авто-публикации НЕТ —
# владелец проверяет и публикует вручную (draft-on-review).
# Час утренних/дневных джоб настраивается через env (время сервера).
_MORNING_HOUR = int(os.getenv("CONTENT_MORNING_HOUR", "9"))    # будни — дайджест
_MIDDAY_HOUR = int(os.getenv("CONTENT_MIDDAY_HOUR", "10"))     # рубрика дня
_SAT_HOUR = int(os.getenv("CONTENT_SAT_HOUR", "11"))          # суббота — манифест
_PRICE_SNAPSHOT_HOUR = int(os.getenv("PRICE_SNAPSHOT_HOUR", "23"))  # снимок цен (после US-закрытия, MSK)
_PREDICT_HOUR = int(os.getenv("PREDICT_HOUR", "10"))               # прогноз недели — Пн
_REMIND_HOUR = int(os.getenv("REMIND_HOUR", "19"))                 # вечернее напоминание
_UNDERDOG_HOUR = int(os.getenv("UNDERDOG_HOUR", "11"))             # «Нелюбимчик недели» — Пн
_ALERT_INTERVAL_HOURS = int(os.getenv("ALERT_INTERVAL_HOURS", "3"))  # как часто проверять рынок на алерты
_ALERT_QUIET_FROM = int(os.getenv("ALERT_QUIET_FROM", "23"))         # тихие часы: не пушить с 23:00
_ALERT_QUIET_TO = int(os.getenv("ALERT_QUIET_TO", "8"))              # ...до 08:00 (MSK)


async def job_daily_reminder(context: ContextTypes.DEFAULT_TYPE):
    """Вечером напомнить тем, у кого активный стрик, но сегодня ещё не заходили —
    чтобы не потеряли серию и прошли «событие дня»."""
    uids = storage.streak_users_to_remind(min_streak=2)
    if not uids:
        return
    kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton("🔥 Открыть Без Б", url=config.BOT_URL)]])
    sent = 0
    for u in uids:
        try:
            chat_id = int(str(u).lstrip("u"))
            await context.bot.send_message(
                chat_id,
                "🔥 Не потеряй серию! Загляни в «Без Б» — тебя ждёт событие дня "
                "и разбор от наставника.", reply_markup=kb)
            sent += 1
        except Exception:
            pass
    log.info("Напоминания о стрике: отправлено %d/%d", sent, len(uids))


async def job_predict_weekly(context: ContextTypes.DEFAULT_TYPE):
    """Понедельник: закрыть прошлый прогноз по цене, открыть новый, анонс в канал."""
    if datetime.now().weekday() != 0:        # 0 = понедельник
        return
    import quotes
    closed = None
    cur = storage.pred_current()
    if cur:
        try:
            price = await asyncio.to_thread(quotes.get_price_usd, cur["symbol"], True)
            closed = storage.pred_resolve(cur["id"], float(price))
        except Exception:
            log.exception("predict resolve failed")
    new = None
    try:
        price = await asyncio.to_thread(quotes.get_price_usd, "BTC", True)
        new = storage.pred_create("BTC", float(price), 7)
    except Exception:
        log.exception("predict create failed")
    if config.CHANNEL_ID and (closed or new):
        parts = []
        if closed and closed.get("result"):
            res = "ВЫШЕ ⬆️" if closed["result"] == "up" else "НИЖЕ ⬇️"
            parts.append(
                f"📊 Итоги прогноза: BTC закрылся ${closed['closePrice']:,.0f} — "
                f"правы те, кто ставил {res} уровня ${closed['target']:,.0f}."
                .replace(",", " "))
        if new:
            parts.append(
                f"🔮 Новый прогноз недели: BTC будет ВЫШЕ или НИЖЕ "
                f"${new['target']:,.0f} к воскресенью? Голосуй в приложении 📲"
                .replace(",", " "))
        try:
            await context.bot.send_message(
                config.CHANNEL_ID, "\n\n".join(parts),
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("📲 Голосовать в Без Б", url=config.BOT_URL)]]))
        except Exception:
            log.exception("predict announce failed")


async def job_price_snapshot(context: ContextTypes.DEFAULT_TYPE):
    """Раз в день сохранить цену закрытия по всем тикерам портфелей —
    копим собственную историю цен (вперёд)."""
    import quotes
    today = datetime.now().date().isoformat()
    tickers = storage.all_held_tickers()
    saved = 0
    for tk in tickers:
        try:
            price = await asyncio.to_thread(quotes.get_price_usd, tk, True)
            if price:
                storage.save_price(tk, today, price)
                saved += 1
        except Exception:
            pass
    log.info("Снимок цен: сохранено %d/%d тикеров за %s", saved, len(tickers), today)

_KIND_LABEL = {
    "digest": "📰 Дайджест", "scenarios": "🔮 Сценарии", "edu": "📚 Ликбез",
    "manifest": "🧭 Манифест", "bullshit": "🚩 Детектор буллшита",
    "crowd": "🌡 Разбор толпы",
}


async def _make_draft(context: ContextTypes.DEFAULT_TYPE, kind: str):
    """Сгенерировать черновик рубрики (в потоке, чтобы не блокировать loop) и
    положить в очередь Без Б. Пингануть владельца."""
    if not ai.available():
        log.warning("планировщик: AI недоступен, пропускаю %s", kind)
        return
    try:
        storage.use_uid("bezb")
        if kind == "digest":
            text = await asyncio.to_thread(ai.digest_bezb)
        elif kind == "scenarios":
            text = await asyncio.to_thread(ai.scenarios_bezb)
        elif kind == "crowd":
            text = await asyncio.to_thread(ai.crowd_bezb)
        else:
            text = await asyncio.to_thread(ai.content_post, kind)
        storage.use_uid("bezb")
        d = storage.add_draft(kind, text)
        log.info("планировщик: черновик %s готов (id=%s)", kind, d)
        if config.ADMIN_ID:
            await context.bot.send_message(
                config.ADMIN_ID,
                f"🗂 Готов черновик «{_KIND_LABEL.get(kind, kind)}».\n"
                "Открой приложение → Профиль → Контент-студия, проверь и опубликуй.")
    except Exception:
        log.exception("планировщик: не удалось подготовить черновик %s", kind)


async def job_content_morning(context: ContextTypes.DEFAULT_TYPE):
    """Будни (Пн–Пт): дайджест «Рынок за 60 секунд»."""
    if datetime.now().weekday() <= 4:
        await _make_draft(context, "digest")


async def job_content_midday(context: ContextTypes.DEFAULT_TYPE):
    """Рубрика дня: Вт ликбез, Ср разбор толпы, Чт детектор буллшита, Пт сценарии."""
    kind = {1: "edu", 2: "crowd", 3: "bullshit", 4: "scenarios"}.get(
        datetime.now().weekday())
    if kind:
        await _make_draft(context, kind)


async def job_content_saturday(context: ContextTypes.DEFAULT_TYPE):
    """Суббота через неделю (чётная ISO-неделя): манифест."""
    now = datetime.now()
    if now.weekday() == 5 and now.isocalendar().week % 2 == 0:
        await _make_draft(context, "manifest")


async def job_alerts(context: ContextTypes.DEFAULT_TYPE):
    """Умные предупреждения о рынке (премиум). Проверяет пороги перегрева/паники/
    резкого движения и шлёт пуш премиум-подписчикам. Антиспам — кулдаун в alerts."""
    # тихие часы: не будим людей ночью (события поймаем утром на следующем прогоне)
    hour = datetime.now().hour
    quiet = (_ALERT_QUIET_FROM <= hour or hour < _ALERT_QUIET_TO) if _ALERT_QUIET_FROM > _ALERT_QUIET_TO \
        else (_ALERT_QUIET_FROM <= hour < _ALERT_QUIET_TO)
    if quiet:
        return
    try:
        import alerts
        import ai
        import notify
    except Exception:
        log.exception("job_alerts import failed")
        return
    try:
        triggered = await asyncio.to_thread(alerts.check)
    except Exception:
        log.exception("alerts.check failed")
        return
    for a in triggered:
        text = a["fallback"]
        if ai.available():
            try:
                ai_text = await asyncio.to_thread(ai.alert_post, a["context"], a["title"])
                if ai_text and ai_text.strip():
                    text = f"{a['title']}\n\n{ai_text.strip()}"
            except Exception:
                log.exception("alert ai_post failed")
        try:
            sent = await asyncio.to_thread(notify.notify_alert, text)
        except Exception:
            log.exception("notify_alert failed")
            continue
        alerts.mark(a["key"])     # запускаем кулдаун только после отправки
        try:
            await context.bot.send_message(
                config.ADMIN_ID,
                f"⚠️ AI-алерт разослан ({a['key']}, премиум-доставок: {sent}).\n\n{text}")
        except Exception:
            pass


async def job_underdog_weekly(context: ContextTypes.DEFAULT_TYPE):
    """Понедельник: пересобрать «Нелюбимчика недели» и пингануть премиум-подписчиков."""
    if datetime.now().weekday() != 0:      # только понедельник
        return
    try:
        import underdog
        import notify
        data = await asyncio.to_thread(underdog.build, True)
        if data.get("ticker"):
            text = (f"🔎 Нелюбимчик недели обновлён: {data['ticker']}.\n\n"
                    "Самый перепроданный актив по фильтрам «Без Б» + честный разбор за и против. "
                    "Открой в приложении.")
            await asyncio.to_thread(notify.notify_alert, text)
    except Exception:
        log.exception("job_underdog_weekly failed")


def _seconds_until_next_sunday_18():
    now = datetime.now()
    target = now.replace(hour=18, minute=0, second=0, microsecond=0)
    days_ahead = (6 - now.weekday()) % 7  # 6 = воскресенье
    target += timedelta(days=days_ahead)
    if target <= now:
        target += timedelta(days=7)
    return (target - now).total_seconds()


# ───────────────────────── Запуск ─────────────────────────

async def on_pre_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтвердить заказ перед оплатой (нужно ответить за 10 сек)."""
    try:
        await update.pre_checkout_query.answer(ok=True)
    except Exception:
        log.exception("pre_checkout failed")


async def on_successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Платёж прошёл — выдать премиум по payload «premium:u<id>»."""
    sp = update.message.successful_payment
    payload = sp.invoice_payload or ""
    parts = payload.split(":")            # premium:u<id>:<tier>
    uid = parts[1] if len(parts) > 1 else f"u{update.effective_user.id}"
    tier = parts[2] if len(parts) > 2 else "reg"
    if tier == "eb":
        storage.add_early_bird(uid)       # закрепить early-bird за юзером навсегда
    until = storage.grant_premium(uid, config.PREMIUM_DAYS)
    when = datetime.fromtimestamp(until).strftime("%d.%m.%Y")
    await update.message.reply_text(
        f"✅ Премиум активирован до {when}! Спасибо, что поддерживаешь «Без Б».")
    try:
        await context.bot.send_message(
            config.ADMIN_ID,
            f"💰 Оплата премиума: {update.effective_user.first_name} ({uid}), до {when}.")
    except Exception:
        pass


def main():
    if not config.BOT_TOKEN:
        raise SystemExit("Не задан BOT_TOKEN. Создай файл .env (см. README).")

    # щедрые таймауты — соединение с Telegram у части провайдеров РФ медленное/нестабильное
    app = (
        Application.builder()
        .token(config.BOT_TOKEN)
        .connect_timeout(30).read_timeout(30).write_timeout(30).pool_timeout(30)
        .get_updates_connect_timeout(30).get_updates_read_timeout(40)
        .build()
    )
    app.add_handler(CommandHandler(["start", "help", "menu"], cmd_start))
    app.add_handler(CommandHandler(["portfolio", "p"], cmd_portfolio))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(PreCheckoutQueryHandler(on_pre_checkout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, on_successful_payment))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    if app.job_queue:
        jq = app.job_queue
        jq.run_repeating(
            job_weekly, interval=timedelta(days=7),
            first=_seconds_until_next_sunday_18())
        # контент-конвейер: авто-черновики на ревью по расписанию рубрик
        jq.run_daily(job_content_morning, time=dtime(hour=_MORNING_HOUR))
        jq.run_daily(job_content_midday, time=dtime(hour=_MIDDAY_HOUR))
        jq.run_daily(job_content_saturday, time=dtime(hour=_SAT_HOUR))
        jq.run_daily(job_price_snapshot, time=dtime(hour=_PRICE_SNAPSHOT_HOUR, minute=50))
        jq.run_daily(job_predict_weekly, time=dtime(hour=_PREDICT_HOUR))
        jq.run_daily(job_daily_reminder, time=dtime(hour=_REMIND_HOUR))
        # умные предупреждения о рынке (премиум) — проверка каждые N часов
        jq.run_repeating(job_alerts,
                         interval=timedelta(hours=_ALERT_INTERVAL_HOURS), first=120)
        # «Нелюбимчик недели» (премиум) — Пн утром
        jq.run_daily(job_underdog_weekly, time=dtime(hour=_UNDERDOG_HOUR))
        log.info("Снимок: Вс 18:00. Черновики: будни %02d:00 дайджест, "
                 "%02d:00 рубрика дня, Сб %02d:00 манифест.",
                 _MORNING_HOUR, _MIDDAY_HOUR, _SAT_HOUR)
    else:
        log.warning("JobQueue недоступна — автоснимок и черновики отключены.")

    log.info("Бот запущен. Ctrl+C для остановки.")
    # bootstrap_retries=-1 — бесконечно повторять старт при сетевых сбоях (не падать)
    # drop_pending_updates=True — на старте сбрасываем накопившийся бэклог апдейтов,
    # иначе после простоя бот спотыкается о старые нажатия («Query is too old»).
    app.run_polling(allowed_updates=Update.ALL_TYPES, bootstrap_retries=-1,
                    drop_pending_updates=True)


if __name__ == "__main__":
    main()
