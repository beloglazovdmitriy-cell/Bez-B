"""Котировки активов и курс USD/RUB.

Крипта   -> Binance public API (быстро, без блокировок), фолбэк на yfinance.
Акции/ETF-> Finnhub (ключ FINNHUB_API_KEY, достижим с VPS), фолбэк на yfinance.
Курс USD/RUB -> официальный API ЦБ РФ (без ключа).

Надёжность: последняя удачная цена кэшируется в файл price_cache.json и
используется как запасной вариант, если живой запрос не прошёл, — чтобы
портфель никогда не падал из-за временного сбоя источника.
"""
import os
import json
import math
import time
from datetime import datetime
import requests
import yfinance as yf
from config import CRYPTO_SYMBOLS


def _isnum(x):
    """Число и не NaN (yfinance иногда отдаёт NaN, который проходит `if x`)."""
    try:
        return x is not None and not math.isnan(float(x))
    except (TypeError, ValueError):
        return False

_CBR_URL = "https://www.cbr-xml-daily.ru/daily_json.js"
_BINANCE_URL = "https://api.binance.com/api/v3/ticker/price"
_CACHE_FILE = os.path.join(os.path.dirname(__file__), "price_cache.json")
_CACHE_TTL = 60  # секунд для «живого» кэша в памяти

_price_cache = {}                      # ticker -> (ts, price)  — свежий кэш
_rate_cache = {"ts": 0, "value": None}

# последняя удачная цена (переживает перезапуски)
def _load_last_good():
    try:
        with open(_CACHE_FILE, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception:
        return {}

_last_good = _load_last_good()


def _save_last_good():
    try:
        tmp = _CACHE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(_last_good, f)
        os.replace(tmp, _CACHE_FILE)
    except Exception:
        pass


def normalize_ticker(ticker: str) -> str:
    return ticker.strip().upper().replace("/USDT", "").replace("-USD", "").replace("USDT", "")


def is_crypto(ticker: str) -> bool:
    return normalize_ticker(ticker) in CRYPTO_SYMBOLS


def get_usd_rub() -> float:
    """Текущий курс доллара к рублю по данным ЦБ РФ."""
    now = time.time()
    if _rate_cache["value"] is not None and now - _rate_cache["ts"] < _CACHE_TTL:
        return _rate_cache["value"]
    try:
        resp = requests.get(_CBR_URL, timeout=10)
        resp.raise_for_status()
        rate = float(resp.json()["Valute"]["USD"]["Value"])
        _rate_cache.update(ts=now, value=rate)
        _last_good["__USDRUB__"] = rate
        _save_last_good()
        return rate
    except Exception:
        if "__USDRUB__" in _last_good:
            return _last_good["__USDRUB__"]
        raise


def _fetch_binance(base: str):
    resp = requests.get(_BINANCE_URL, params={"symbol": f"{base}USDT"}, timeout=8)
    resp.raise_for_status()
    return float(resp.json()["price"])


# Акции/ETF США — Finnhub (достижим с VPS, в отличие от Yahoo). Ключ из .env;
# без ключа источник пропускается и работает прежний путь (yfinance/кэш).
_FINNHUB_KEY = os.getenv("FINNHUB_API_KEY", "")
_FINNHUB_URL = "https://finnhub.io/api/v1/quote"


def _fetch_finnhub(symbol: str) -> float:
    if not _FINNHUB_KEY:
        raise ValueError("нет ключа Finnhub")
    r = requests.get(_FINNHUB_URL,
                     params={"symbol": symbol, "token": _FINNHUB_KEY}, timeout=8)
    r.raise_for_status()
    c = r.json().get("c")          # current price; 0 при неизвестном тикере
    if _isnum(c) and float(c) > 0:
        return float(c)
    raise ValueError("finnhub: нет цены")


# Yahoo (yfinance) недоступен с части серверов и висит по 30с. Жёсткий короткий
# таймаут через curl_cffi-сессию, чтобы не блокировать ответы — акции тогда берутся
# из кэша последних известных цен, а не из 30-секундного зависания.
_YF_TIMEOUT = float(os.getenv("YF_TIMEOUT", "7"))
# на серверах, где Yahoo заблокирован (запросы висят 30с), ставим YF_DISABLE=1 —
# тогда обращений к Yahoo нет вовсе: акции берутся из кэша последних цен мгновенно.
_YF_DISABLE = os.getenv("YF_DISABLE", "0") == "1"
try:
    from curl_cffi import requests as _cffi
    _yf_session = _cffi.Session(impersonate="chrome", timeout=_YF_TIMEOUT)
except Exception:
    _yf_session = None


def _ticker(symbol: str):
    try:
        return yf.Ticker(symbol, session=_yf_session) if _yf_session else yf.Ticker(symbol)
    except TypeError:
        return yf.Ticker(symbol)


def _fetch_yfinance(symbol: str):
    if _YF_DISABLE:
        raise ValueError("yfinance отключён на этом хосте")
    yt = _ticker(symbol)
    try:
        p = yt.fast_info.get("last_price")
        if _isnum(p):
            return float(p)
    except Exception:
        pass
    hist = yt.history(period="5d")
    if not hist.empty:
        # берём последнюю НЕ-NaN цену закрытия (текущий день может быть незакрыт)
        closes = [c for c in hist["Close"].tolist() if _isnum(c)]
        if closes:
            return float(closes[-1])
    raise ValueError("нет данных")


def _fetch_live(ticker: str) -> float:
    base = normalize_ticker(ticker)
    if base in CRYPTO_SYMBOLS:
        try:
            return _fetch_binance(base)
        except Exception:
            return _fetch_yfinance(f"{base}-USD")   # фолбэк
    # тикер не в списке известной крипты — это может быть как акция США, так и
    # криптовалюта, которой просто нет в CRYPTO_SYMBOLS (напр. TWT). Поэтому:
    # сначала акции (Finnhub), затем Binance как крипта, затем yfinance.
    if _FINNHUB_KEY:
        try:
            return _fetch_finnhub(base)
        except Exception:
            pass
    try:
        return _fetch_binance(base)        # вдруг это коин с Binance ({BASE}USDT)
    except Exception:
        pass
    return _fetch_yfinance(base)


def get_price_usd(ticker: str, allow_stale: bool = False) -> float:
    """Текущая цена актива в USD(≈USDT).

    allow_stale=True -> при сбое источника вернуть последнюю известную цену
    вместо исключения (для отображения портфеля)."""
    base = normalize_ticker(ticker)
    now = time.time()
    cached = _price_cache.get(base)
    if cached and now - cached[0] < _CACHE_TTL:
        return cached[1]

    try:
        price = _fetch_live(ticker)
        _price_cache[base] = (now, price)
        _last_good[base] = price
        _save_last_good()
        return price
    except Exception:
        if allow_stale and base in _last_good:
            return _last_good[base]
        raise ValueError(f"Не удалось получить цену для тикера '{ticker}'")


# ───────────────────────── исторические цены (для сравнения) ─────────────────────────

_BINANCE_KLINES = "https://api.binance.com/api/v3/klines"
_hist_cache = {}   # (base, start_iso) -> {date_iso: close}


def get_daily_history(ticker: str, start_iso: str) -> dict:
    """Дневные цены закрытия с даты start_iso: {YYYY-MM-DD: close}. {} при сбое."""
    base = normalize_ticker(ticker)
    key = (base, start_iso)
    if key in _hist_cache:
        return _hist_cache[key]
    out = {}
    if base in CRYPTO_SYMBOLS:
        try:
            out = _binance_history(base, start_iso)
        except Exception:
            out = {}
        if not out:                           # фолбэк на yfinance для крипты
            try:
                out = _yf_history(f"{base}-USD", start_iso)
            except Exception:
                out = {}
    else:
        try:
            out = _yf_history(base, start_iso)
        except Exception:
            out = {}
    _hist_cache[key] = out
    return out


def _binance_history(base: str, start_iso: str) -> dict:
    start_ms = int(datetime.fromisoformat(start_iso).timestamp() * 1000)
    resp = requests.get(_BINANCE_KLINES, params={
        "symbol": f"{base}USDT", "interval": "1d",
        "startTime": start_ms, "limit": 1000}, timeout=12)
    resp.raise_for_status()
    out = {}
    for k in resp.json():
        d = datetime.utcfromtimestamp(k[0] / 1000).date().isoformat()
        out[d] = float(k[4])   # цена закрытия
    return out


def _yf_history(symbol: str, start_iso: str) -> dict:
    if _YF_DISABLE:
        return {}
    hist = _ticker(symbol).history(start=start_iso)
    out = {}
    for idx, row in hist.iterrows():
        c = row["Close"]
        if _isnum(c):
            out[idx.date().isoformat()] = float(c)   # пропускаем NaN-бары
    return out


def price_on_date(hist: dict, date_iso: str):
    """Цена на дату (или ближайшую предыдущую, если в эту день нет торгов)."""
    if not hist:
        return None
    if date_iso in hist:
        return hist[date_iso]
    earlier = [d for d in hist if d <= date_iso]
    if earlier:
        return hist[max(earlier)]
    return hist[min(hist)]   # дата раньше начала истории — берём самую раннюю
