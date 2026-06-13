"""Хранение портфелей (мультипользовательское).

Бэкенд — SQLite. Каждый портфель — отдельная строка таблицы portfolios(uid, doc),
где doc — весь документ портфеля в JSON. uid:
  • "bezb"          — публичный портфель «Без Б» (его ведёт владелец, бот);
  • "u<telegram_id>" — личный портфель пользователя.

Текущий uid берётся из contextvar (use_uid). По умолчанию — "bezb", поэтому бот
и любой код без явного контекста работают с публичным портфелем. API ставит uid
на каждый запрос по выбранному пользователем портфелю.

Интерфейс load()/save(data)/next_trade_id(data) прежний — остальной код
(portfolio.py, benchmark.py, charts.py, bot.py) не меняется.
"""
import contextvars
import json
import os
import sqlite3
import threading
import time

from config import DATA_FILE, DEFAULT_FAVORITES

_DB_FILE = os.path.join(os.path.dirname(DATA_FILE), "portfolio.db")
_lock = threading.Lock()
_uid_var = contextvars.ContextVar("bezb_uid", default="bezb")

_DEFAULT = {
    "trades": [],
    "history": [],
    "favorites": list(DEFAULT_FAVORITES),
    "units": 0.0,
}


def use_uid(uid: str):
    """Установить текущий портфель для последующих load()/save()."""
    _uid_var.set(uid)


def current_uid() -> str:
    return _uid_var.get()


def _connect():
    conn = sqlite3.connect(_DB_FILE, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def _ensure(conn):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS portfolios (uid TEXT PRIMARY KEY, doc TEXT NOT NULL)")
    # миграция со старой одно-портфельной схемы kv(id=1) -> portfolios['bezb']
    try:
        old = conn.execute("SELECT doc FROM kv WHERE id = 1").fetchone()
        if old:
            has = conn.execute("SELECT 1 FROM portfolios WHERE uid = 'bezb'").fetchone()
            if not has:
                conn.execute("INSERT INTO portfolios (uid, doc) VALUES ('bezb', ?)", (old[0],))
                conn.commit()
    except sqlite3.OperationalError:
        pass  # старой таблицы kv нет — ок


def load():
    """Загрузить документ текущего портфеля (uid из contextvar)."""
    uid = _uid_var.get()
    with _lock:
        conn = _connect()
        try:
            _ensure(conn)
            row = conn.execute("SELECT doc FROM portfolios WHERE uid = ?", (uid,)).fetchone()
            data = json.loads(row[0]) if row else json.loads(json.dumps(_DEFAULT))
        finally:
            conn.close()
    data.setdefault("trades", [])
    data.setdefault("history", [])
    data.setdefault("favorites", list(DEFAULT_FAVORITES))
    data.setdefault("units", 0.0)
    return data


def save(data):
    """Сохранить документ текущего портфеля (атомарно)."""
    uid = _uid_var.get()
    with _lock:
        conn = _connect()
        try:
            _ensure(conn)
            conn.execute(
                "INSERT INTO portfolios (uid, doc) VALUES (?, ?) "
                "ON CONFLICT(uid) DO UPDATE SET doc = excluded.doc",
                (uid, json.dumps(data, ensure_ascii=False)))
            conn.commit()
        finally:
            conn.close()


def next_trade_id(data):
    return max((t["id"] for t in data["trades"]), default=0) + 1


# ───────────────────────── очередь черновиков контента ─────────────────────────

def _ensure_drafts(conn):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS drafts (id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "ts INTEGER NOT NULL, kind TEXT NOT NULL, text TEXT NOT NULL, "
        "status TEXT NOT NULL DEFAULT 'draft')")


def _draft_row(r):
    return {"id": r[0], "ts": r[1], "kind": r[2], "text": r[3], "status": r[4]}


def add_draft(kind: str, text: str) -> dict:
    with _lock:
        conn = _connect()
        try:
            _ensure_drafts(conn)
            cur = conn.execute(
                "INSERT INTO drafts (ts, kind, text, status) VALUES (?, ?, ?, 'draft')",
                (int(time.time()), kind, text))
            conn.commit()
            return {"id": cur.lastrowid, "ts": int(time.time()),
                    "kind": kind, "text": text, "status": "draft"}
        finally:
            conn.close()


def list_drafts(limit: int = 30) -> list:
    with _lock:
        conn = _connect()
        try:
            _ensure_drafts(conn)
            rows = conn.execute(
                "SELECT id, ts, kind, text, status FROM drafts WHERE status='draft' "
                "ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
            return [_draft_row(r) for r in rows]
        finally:
            conn.close()


# ───────────────────────── реакции в ленте ─────────────────────────

def _ensure_reactions(conn):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS reactions ("
        "post_id INTEGER NOT NULL, uid TEXT NOT NULL, emoji TEXT NOT NULL, "
        "PRIMARY KEY (post_id, uid, emoji))")


def toggle_reaction(post_id: int, uid: str, emoji: str) -> bool:
    """Поставить/снять реакцию пользователя. True — поставлена, False — снята."""
    with _lock:
        conn = _connect()
        try:
            _ensure_reactions(conn)
            ex = conn.execute(
                "SELECT 1 FROM reactions WHERE post_id=? AND uid=? AND emoji=?",
                (post_id, uid, emoji)).fetchone()
            if ex:
                conn.execute("DELETE FROM reactions WHERE post_id=? AND uid=? AND emoji=?",
                             (post_id, uid, emoji))
                res = False
            else:
                conn.execute("INSERT INTO reactions (post_id, uid, emoji) VALUES (?, ?, ?)",
                             (post_id, uid, emoji))
                res = True
            conn.commit()
            return res
        finally:
            conn.close()


def reactions_for(post_ids: list, uid: str) -> dict:
    """{post_id: {"counts": {emoji: n}, "mine": [emoji]}} для списка постов."""
    if not post_ids:
        return {}
    with _lock:
        conn = _connect()
        try:
            _ensure_reactions(conn)
            qm = ",".join("?" * len(post_ids))
            counts = conn.execute(
                f"SELECT post_id, emoji, COUNT(*) FROM reactions "
                f"WHERE post_id IN ({qm}) GROUP BY post_id, emoji", post_ids).fetchall()
            mine = conn.execute(
                f"SELECT post_id, emoji FROM reactions WHERE uid=? AND post_id IN ({qm})",
                [uid] + list(post_ids)).fetchall()
        finally:
            conn.close()
    out = {}
    for pid, emoji, n in counts:
        out.setdefault(pid, {"counts": {}, "mine": []})["counts"][emoji] = n
    for pid, emoji in mine:
        out.setdefault(pid, {"counts": {}, "mine": []})["mine"].append(emoji)
    return out


# ──────────────── подписчики на пуши о сделках Без Б ────────────────
# Глобальная таблица (не привязана к портфелю): кто получает мгновенные
# уведомления о сделках публичного портфеля. Пока включение свободное;
# после подключения оплаты — гейт по премиум-подписке.

def _ensure_subscribers(conn):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS subscribers ("
        "uid INTEGER PRIMARY KEY, ts INTEGER NOT NULL)")


def add_subscriber(uid: int) -> None:
    with _lock:
        conn = _connect()
        try:
            _ensure_subscribers(conn)
            conn.execute("INSERT OR IGNORE INTO subscribers (uid, ts) VALUES (?, ?)",
                         (int(uid), int(time.time())))
            conn.commit()
        finally:
            conn.close()


def remove_subscriber(uid: int) -> None:
    with _lock:
        conn = _connect()
        try:
            _ensure_subscribers(conn)
            conn.execute("DELETE FROM subscribers WHERE uid=?", (int(uid),))
            conn.commit()
        finally:
            conn.close()


def is_subscriber(uid) -> bool:
    if not uid:
        return False
    with _lock:
        conn = _connect()
        try:
            _ensure_subscribers(conn)
            row = conn.execute("SELECT 1 FROM subscribers WHERE uid=?", (int(uid),)).fetchone()
            return bool(row)
        finally:
            conn.close()


def list_subscribers() -> list:
    with _lock:
        conn = _connect()
        try:
            _ensure_subscribers(conn)
            rows = conn.execute("SELECT uid FROM subscribers").fetchall()
            return [r[0] for r in rows]
        finally:
            conn.close()


def list_published(limit: int = 50) -> list:
    """Опубликованные посты — для ленты в Mini App (публично, без гейта)."""
    with _lock:
        conn = _connect()
        try:
            _ensure_drafts(conn)
            rows = conn.execute(
                "SELECT id, ts, kind, text, status FROM drafts WHERE status='published' "
                "ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
            return [_draft_row(r) for r in rows]
        finally:
            conn.close()


def get_draft(draft_id: int) -> dict | None:
    with _lock:
        conn = _connect()
        try:
            _ensure_drafts(conn)
            r = conn.execute(
                "SELECT id, ts, kind, text, status FROM drafts WHERE id=?",
                (draft_id,)).fetchone()
            return _draft_row(r) if r else None
        finally:
            conn.close()


def set_draft_status(draft_id: int, status: str):
    with _lock:
        conn = _connect()
        try:
            _ensure_drafts(conn)
            conn.execute("UPDATE drafts SET status=? WHERE id=?", (status, draft_id))
            conn.commit()
        finally:
            conn.close()


def update_draft(draft_id: int, text: str):
    with _lock:
        conn = _connect()
        try:
            _ensure_drafts(conn)
            conn.execute("UPDATE drafts SET text=? WHERE id=?", (text, draft_id))
            conn.commit()
        finally:
            conn.close()


def delete_draft(draft_id: int):
    with _lock:
        conn = _connect()
        try:
            _ensure_drafts(conn)
            conn.execute("DELETE FROM drafts WHERE id=?", (draft_id,))
            conn.commit()
        finally:
            conn.close()
