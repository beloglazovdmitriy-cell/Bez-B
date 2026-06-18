"""Настройки проекта. Читаются из переменных окружения или файла .env."""
import os
from dotenv import load_dotenv

load_dotenv()

# Токен бота от @BotFather (обязательно)
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# ID администратора (твой Telegram user id) — только он может менять портфель.
# Узнать свой id: напиши боту @userinfobot.
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# ID канала для автопубликации (например, @bez_b или -1001234567890).
# Можно оставить пустым на старте.
CHANNEL_ID = os.getenv("CHANNEL_ID", "")

# Публичные ссылки канала (для карточки результата и кнопки «Подписаться»).
CHANNEL_NAME = os.getenv("CHANNEL_NAME", "Без Б")
CHANNEL_URL = os.getenv("CHANNEL_URL", "https://t.me/BezBlogfin")

# Адрес Mini App — для кнопки «Открыть приложение» в боте.
MINIAPP_URL = os.getenv("MINIAPP_URL", "https://beloglazovdmitriy-cell.github.io/Bez-B/")

# Ссылка на бота — для CTA-кнопки под постами в канале (в каналах web_app-кнопки
# нельзя, только URL; ведём на бота, у него кнопка-меню открывает приложение).
BOT_USERNAME = os.getenv("BOT_USERNAME", "BezzBot_bot")
BOT_URL = os.getenv("BOT_URL", f"https://t.me/{BOT_USERNAME}")

# Криптовалюты — котируются через Binance ({SYMBOL}USDT), фолбэк yfinance.
CRYPTO_SYMBOLS = {
    "BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "TON", "AVAX", "DOT",
    "LINK", "UNI", "ONDO", "FIL", "ARKM", "LTC", "TRX", "MATIC", "NEAR",
    "ATOM", "APT", "ARB", "OP", "INJ", "SUI", "RNDR", "AAVE",
}

# Избранные активы по умолчанию (быстрые кнопки, чтобы не искать каждый раз).
DEFAULT_FAVORITES = ["SOL", "XRP", "LINK", "UNI", "DOT"]

# Ставка рублёвого вклада для бенчмарка «Вклад ₽» (годовых, доля). 0.18 = 18%.
DEPOSIT_RATE_RUB = 0.18

# Тикеры бенчмарков для сравнения: (тикер, отображаемое имя).
BENCHMARK_TICKERS = [("SPY", "S&P 500"), ("BTC", "Bitcoin"), ("GLD", "Золото")]

# ── Оплата премиума (Telegram Payments через провайдера, напр. Сбербанк) ──
# Provider token из @BotFather → Bot Settings → Payments. Пусто = оплата выключена.
PAYMENT_PROVIDER_TOKEN = os.getenv("PAYMENT_PROVIDER_TOKEN", "")
PREMIUM_PRICE_RUB = int(os.getenv("PREMIUM_PRICE_RUB", "990"))   # регулярная цена, ₽
PREMIUM_DAYS = int(os.getenv("PREMIUM_DAYS", "30"))             # длительность доступа
PREMIUM_TITLE = os.getenv("PREMIUM_TITLE", "Премиум «Без Б» на 30 дней")
# Early-bird: первым подписчикам — сниженная цена, закрепляется за ними навсегда.
PREMIUM_EARLYBIRD_RUB = int(os.getenv("PREMIUM_EARLYBIRD_RUB", "490"))
PREMIUM_EARLYBIRD_LIMIT = int(os.getenv("PREMIUM_EARLYBIRD_LIMIT", "100"))

# CloudPayments: Public ID (можно во фронт) и пароль для API (только сервер, для
# проверки подписи webhook). Пусто = провайдер выключен.
CLOUDPAYMENTS_PUBLIC_ID = os.getenv("CLOUDPAYMENTS_PUBLIC_ID", "")
CLOUDPAYMENTS_API_SECRET = os.getenv("CLOUDPAYMENTS_API_SECRET", "")

# Реферальная программа: сколько дней премиума получает пригласивший за друга.
REFERRAL_PREMIUM_DAYS = int(os.getenv("REFERRAL_PREMIUM_DAYS", "3"))

# ── Контент: недельная воронка-расписание ────────────────────────────────────
# Часы публикации черновиков (MSK). Утро — ценность/авторитет, вечер — вовлечение/продажа.
CONTENT_MORNING_HOUR = int(os.getenv("CONTENT_MORNING_HOUR", "9"))
CONTENT_EVENING_HOUR = int(os.getenv("CONTENT_EVENING_HOUR", "19"))
# Недельная воронка: weekday (0=Пн … 6=Вс) → (утренняя рубрика, вечерняя рубрика).
# Бот сам готовит эти черновики на ревью; ведёт к продаже подписки в воскресенье.
CONTENT_WEEK_PLAN = {
    0: ("news",      "poll_predict"),   # Пн  Новости · Прогноз недели
    1: ("edu",       "promo_ai"),       # Вт  Ликбез · Продажа: AI-разбор
    2: ("crowd",     "poll_decision"),  # Ср  Разбор толпы · Опрос
    3: ("bullshit",  "promo_speed"),    # Чт  Детектор Б · Продажа: скорость
    4: ("scenarios", "fun"),            # Пт  Сценарии · Развлекательный
    5: ("psych",     "poll_mood"),      # Сб  Психология · Опрос настроения
    6: ("personal",  "promo_results"),  # Вс  Личное · Итоги + оффер
}

# ── Бренд-знак в постах ──────────────────────────────────────────────────────
# Эмодзи-«дублёр» логотипа (видят ВСЕ подписчики без Premium). Логотип — монета с
# «Б», поэтому по умолчанию монета 🪙. Добавляется подписью к 2 «фирменным» постам
# в неделю (см. bot._BRAND_KINDS).
BRAND_MARK = os.getenv("BRAND_MARK", "🪙")
# Полная бренд-подпись, которой помечаем фирменные посты.
BRAND_SIGNATURE = os.getenv("BRAND_SIGNATURE", f"{BRAND_MARK} Без Б")
# ВАЖНО: кастом-эмодзи с настоящим логотипом в тексте поста НЕДОСТУПНЫ боту —
# Telegram вырезает custom_emoji-сущности из любых сообщений бота (проверено живьём
# 2026-06-18, и для пользовательского набора t.me/addemoji/BezB_logo, и для
# бот-набора). Показать настоящий логотип всем подписчикам можно только КАРТИНКОЙ
# (вложить brand/bezb_logo_300.png), либо постить от Premium-аккаунта (не бот). В
# тексте используем обычный знак BRAND_MARK (🪙).

# Файл с данными портфеля
DATA_FILE = os.path.join(os.path.dirname(__file__), "portfolio_data.json")
