"""Хранение данных портфеля в JSON-файле."""
import json
import os
import threading
from config import DATA_FILE, DEFAULT_FAVORITES

_lock = threading.Lock()

_DEFAULT = {
    "trades": [],    # лента операций: deposit / buy / sell / withdraw
    "history": [],   # снимки стоимости: {ts, value_usd, value_rub, invested_rub, index}
    "favorites": list(DEFAULT_FAVORITES),  # избранные тикеры (быстрые кнопки)
    "units": 0.0,    # «паи» для индекса Без Б (паевая стоимость = индекс)
}


def load():
    """Загрузить данные портфеля (с дефолтами, если файла нет)."""
    if not os.path.exists(DATA_FILE):
        return json.loads(json.dumps(_DEFAULT))
    # utf-8-sig корректно проглатывает BOM, если файл вдруг записан с меткой
    with open(DATA_FILE, "r", encoding="utf-8-sig") as f:
        data = json.load(f)
    # подстраховка на случай старого формата
    data.setdefault("trades", [])
    data.setdefault("history", [])
    data.setdefault("favorites", list(DEFAULT_FAVORITES))
    data.setdefault("units", 0.0)
    return data


def save(data):
    """Сохранить данные портфеля атомарно."""
    with _lock:
        tmp = DATA_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, DATA_FILE)


def next_trade_id(data):
    return max((t["id"] for t in data["trades"]), default=0) + 1
