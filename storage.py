"""Хранение данных портфеля.

Бэкенд — SQLite (файл portfolio.db). Весь документ портфеля хранится как один
JSON в одной строке таблицы kv. Так мы:
  • сохраняем прежний интерфейс load()/save(data)/next_trade_id(data) —
    остальной код (bot.py, portfolio.py, benchmark.py, charts.py) не меняется;
  • получаем безопасную одновременную работу двух процессов (бот + API):
    SQLite в режиме WAL разрешает читателей во время записи, а каждая запись
    атомарна. JSON-файл с tmp+replace такого не гарантировал.

При первом запуске данные автоматически переносятся из старого
portfolio_data.json (он остаётся как резервная копия).
"""
import json
import os
import sqlite3
import threading

from config import DATA_FILE, DEFAULT_FAVORITES

_DB_FILE = os.path.join(os.path.dirname(DATA_FILE), "portfolio.db")
_lock = threading.Lock()

_DEFAULT = {
    "trades": [],    # лента операций: deposit / buy / sell / withdraw
    "history": [],   # снимки стоимости: {ts, value_usd, value_rub, invested_rub, index}
    "favorites": list(DEFAULT_FAVORITES),  # избранные тикеры (быстрые кнопки)
    "units": 0.0,    # «паи» для индекса Без Б (паевая стоимость = индекс)
}


def _connect():
    conn = sqlite3.connect(_DB_FILE, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def _ensure(conn):
    """Создать таблицу и при первом запуске перенести данные из JSON."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS kv (id INTEGER PRIMARY KEY CHECK (id = 1), doc TEXT NOT NULL)")
    row = conn.execute("SELECT doc FROM kv WHERE id = 1").fetchone()
    if row is not None:
        return
    # миграция: берём старый portfolio_data.json, иначе дефолт
    data = json.loads(json.dumps(_DEFAULT))
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
        except Exception:
            pass
    conn.execute("INSERT INTO kv (id, doc) VALUES (1, ?)",
                 (json.dumps(data, ensure_ascii=False),))
    conn.commit()


def load():
    """Загрузить данные портфеля (с дефолтами по ключам)."""
    with _lock:
        conn = _connect()
        try:
            _ensure(conn)
            row = conn.execute("SELECT doc FROM kv WHERE id = 1").fetchone()
            data = json.loads(row[0])
        finally:
            conn.close()
    # подстраховка на случай старого/частичного документа
    data.setdefault("trades", [])
    data.setdefault("history", [])
    data.setdefault("favorites", list(DEFAULT_FAVORITES))
    data.setdefault("units", 0.0)
    return data


def save(data):
    """Сохранить данные портфеля (атомарно, одной записью)."""
    with _lock:
        conn = _connect()
        try:
            _ensure(conn)
            conn.execute(
                "INSERT INTO kv (id, doc) VALUES (1, ?) "
                "ON CONFLICT(id) DO UPDATE SET doc = excluded.doc",
                (json.dumps(data, ensure_ascii=False),))
            conn.commit()
        finally:
            conn.close()


def next_trade_id(data):
    return max((t["id"] for t in data["trades"]), default=0) + 1
