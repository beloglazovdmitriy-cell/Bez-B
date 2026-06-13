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
CHANNEL_NAME = os.getenv("CHANNEL_NAME", "@BezBlogfin")
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

# Файл с данными портфеля
DATA_FILE = os.path.join(os.path.dirname(__file__), "portfolio_data.json")
