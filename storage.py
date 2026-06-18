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


# ──────────────── комментарии под постами ленты ────────────────

def _ensure_comments(conn):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS comments ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, post_id INTEGER NOT NULL, "
        "uid TEXT NOT NULL, name TEXT, text TEXT NOT NULL, ts INTEGER NOT NULL)")


def add_comment(post_id: int, uid: str, name: str, text: str) -> dict:
    now = int(time.time())
    with _lock:
        conn = _connect()
        try:
            _ensure_comments(conn)
            cur = conn.execute(
                "INSERT INTO comments (post_id, uid, name, text, ts) VALUES (?,?,?,?,?)",
                (post_id, uid, name, text, now))
            conn.commit()
            return {"id": cur.lastrowid, "postId": post_id, "uid": uid,
                    "name": name, "text": text, "ts": now}
        finally:
            conn.close()


def list_comments(post_id: int, limit: int = 200) -> list:
    with _lock:
        conn = _connect()
        try:
            _ensure_comments(conn)
            rows = conn.execute(
                "SELECT id, uid, name, text, ts FROM comments WHERE post_id=? "
                "ORDER BY id ASC LIMIT ?", (post_id, limit)).fetchall()
            return [{"id": r[0], "uid": r[1], "name": r[2] or "Аноним",
                     "text": r[3], "ts": r[4]} for r in rows]
        finally:
            conn.close()


def comment_counts(post_ids: list) -> dict:
    """{post_id: число комментариев} для списка постов."""
    if not post_ids:
        return {}
    with _lock:
        conn = _connect()
        try:
            _ensure_comments(conn)
            qm = ",".join("?" * len(post_ids))
            rows = conn.execute(
                f"SELECT post_id, COUNT(*) FROM comments "
                f"WHERE post_id IN ({qm}) GROUP BY post_id", post_ids).fetchall()
            return {r[0]: r[1] for r in rows}
        finally:
            conn.close()


def delete_comment(comment_id: int) -> None:
    with _lock:
        conn = _connect()
        try:
            _ensure_comments(conn)
            conn.execute("DELETE FROM comments WHERE id=?", (comment_id,))
            conn.commit()
        finally:
            conn.close()


# ──────────────── сезон фэнтези-портфелей ────────────────

def _ensure_fantasy(conn):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS fantasy_season ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, start_ts INTEGER, end_ts INTEGER, "
        "status TEXT, bezb_start REAL)")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS fantasy_players ("
        "uid TEXT PRIMARY KEY, name TEXT, joined_ts INTEGER)")


def _season_dict(r):
    if not r:
        return None
    return {"id": r[0], "startTs": r[1], "endTs": r[2], "status": r[3], "bezbStart": r[4]}


def fantasy_current_season() -> dict | None:
    now = int(time.time())
    with _lock:
        conn = _connect()
        try:
            _ensure_fantasy(conn)
            r = conn.execute(
                "SELECT id, start_ts, end_ts, status, bezb_start FROM fantasy_season "
                "WHERE status='active' AND end_ts > ? ORDER BY id DESC LIMIT 1",
                (now,)).fetchone()
            return _season_dict(r)
        finally:
            conn.close()


def fantasy_ensure_season(bezb_start: float, days: int = 30) -> dict:
    """Вернуть активный сезон; если нет — создать новый на days дней."""
    s = fantasy_current_season()
    if s:
        return s
    now = int(time.time())
    with _lock:
        conn = _connect()
        try:
            _ensure_fantasy(conn)
            conn.execute(
                "INSERT INTO fantasy_season (start_ts, end_ts, status, bezb_start) "
                "VALUES (?, ?, 'active', ?)", (now, now + days * 86400, float(bezb_start)))
            conn.commit()
        finally:
            conn.close()
    return fantasy_current_season()


def fantasy_add_player(uid: str, name: str) -> None:
    with _lock:
        conn = _connect()
        try:
            _ensure_fantasy(conn)
            conn.execute(
                "INSERT INTO fantasy_players (uid, name, joined_ts) VALUES (?,?,?) "
                "ON CONFLICT(uid) DO UPDATE SET name=excluded.name",
                (uid, name, int(time.time())))
            conn.commit()
        finally:
            conn.close()


def fantasy_is_player(uid: str) -> bool:
    with _lock:
        conn = _connect()
        try:
            _ensure_fantasy(conn)
            return bool(conn.execute(
                "SELECT 1 FROM fantasy_players WHERE uid=?", (uid,)).fetchone())
        finally:
            conn.close()


def fantasy_players() -> list:
    with _lock:
        conn = _connect()
        try:
            _ensure_fantasy(conn)
            rows = conn.execute(
                "SELECT uid, name FROM fantasy_players").fetchall()
            return [{"uid": r[0], "name": r[1] or "Аноним"} for r in rows]
        finally:
            conn.close()


# ──────────────── квиз «Детектор буллшита» ────────────────

def _ensure_quiz(conn):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS quiz ("
        "uid TEXT PRIMARY KEY, score INTEGER, streak INTEGER, best INTEGER, answered TEXT)")


def quiz_get(uid: str) -> dict:
    with _lock:
        conn = _connect()
        try:
            _ensure_quiz(conn)
            r = conn.execute(
                "SELECT score, streak, best, answered FROM quiz WHERE uid=?", (uid,)).fetchone()
        finally:
            conn.close()
    if not r:
        return {"score": 0, "streak": 0, "best": 0, "answered": []}
    try:
        answered = json.loads(r[3]) if r[3] else []
    except Exception:
        answered = []
    return {"score": r[0], "streak": r[1], "best": r[2], "answered": answered}


def quiz_record(uid: str, qid: int, correct: bool) -> dict:
    st = quiz_get(uid)
    if qid not in st["answered"]:
        st["answered"].append(qid)
    st["score"] = st["score"] + (1 if correct else 0)
    st["streak"] = st["streak"] + 1 if correct else 0
    st["best"] = max(st["best"], st["streak"])
    with _lock:
        conn = _connect()
        try:
            _ensure_quiz(conn)
            conn.execute(
                "INSERT INTO quiz (uid, score, streak, best, answered) VALUES (?,?,?,?,?) "
                "ON CONFLICT(uid) DO UPDATE SET score=excluded.score, streak=excluded.streak, "
                "best=excluded.best, answered=excluded.answered",
                (uid, st["score"], st["streak"], st["best"], json.dumps(st["answered"])))
            conn.commit()
        finally:
            conn.close()
    return st


def quiz_reset_answered(uid: str) -> None:
    """Сбросить пройденные вопросы (счёт/рекорд сохраняются) — чтобы пройти заново."""
    st = quiz_get(uid)
    with _lock:
        conn = _connect()
        try:
            _ensure_quiz(conn)
            conn.execute(
                "INSERT INTO quiz (uid, score, streak, best, answered) VALUES (?,?,?,?,'[]') "
                "ON CONFLICT(uid) DO UPDATE SET answered='[]'",
                (uid, st["score"], st["streak"], st["best"]))
            conn.commit()
        finally:
            conn.close()


# ──────────────── квиз дня «Детектор буллшита» (1 карточка в сутки) ────────────────

def _ensure_quiz_daily(conn):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS quiz_daily ("
        "uid TEXT PRIMARY KEY, last_day INTEGER, last_choice INTEGER, "
        "last_correct INTEGER, streak INTEGER, best INTEGER, correct INTEGER, total INTEGER)")


def quiz_daily_get(uid: str) -> dict:
    with _lock:
        conn = _connect()
        try:
            _ensure_quiz_daily(conn)
            r = conn.execute(
                "SELECT last_day, last_choice, last_correct, streak, best, correct, total "
                "FROM quiz_daily WHERE uid=?", (uid,)).fetchone()
        finally:
            conn.close()
    if not r:
        return {"lastDay": 0, "lastChoice": None, "lastCorrect": None,
                "streak": 0, "best": 0, "correct": 0, "total": 0}
    return {"lastDay": r[0], "lastChoice": r[1],
            "lastCorrect": None if r[2] is None else bool(r[2]),
            "streak": r[3], "best": r[4], "correct": r[5], "total": r[6]}


def quiz_daily_answer(uid: str, day: int, choice_bs: bool, key_bs: bool) -> dict:
    """Зафиксировать ответ на карточку дня. Один ответ в сутки (повтор — no-op).
    Серия — по последовательным дням (вернулся и ответил)."""
    st = quiz_daily_get(uid)
    if st["lastDay"] == day:
        return st                       # уже отвечал сегодня — не двоим
    correct = (choice_bs == key_bs)
    st["streak"] = st["streak"] + 1 if st["lastDay"] == day - 1 else 1
    st["best"] = max(st["best"], st["streak"])
    st["correct"] += 1 if correct else 0
    st["total"] += 1
    st["lastDay"], st["lastChoice"], st["lastCorrect"] = day, int(choice_bs), correct
    with _lock:
        conn = _connect()
        try:
            _ensure_quiz_daily(conn)
            conn.execute(
                "INSERT INTO quiz_daily (uid, last_day, last_choice, last_correct, "
                "streak, best, correct, total) VALUES (?,?,?,?,?,?,?,?) "
                "ON CONFLICT(uid) DO UPDATE SET last_day=excluded.last_day, "
                "last_choice=excluded.last_choice, last_correct=excluded.last_correct, "
                "streak=excluded.streak, best=excluded.best, correct=excluded.correct, "
                "total=excluded.total",
                (uid, day, int(choice_bs), int(correct), st["streak"], st["best"],
                 st["correct"], st["total"]))
            conn.commit()
        finally:
            conn.close()
    return st


# ──────────────── реферальная программа ────────────────

def _ensure_referrals(conn):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS referrals ("
        "referee TEXT PRIMARY KEY, referrer TEXT, ts INTEGER)")


def add_referral(referee: str, referrer: str) -> bool:
    """Записать, что referee пришёл по ссылке referrer. True — если это новый
    реферал (referee ещё не приглашён и не сам себя)."""
    if not referee or not referrer or referee == referrer:
        return False
    with _lock:
        conn = _connect()
        try:
            _ensure_referrals(conn)
            ex = conn.execute("SELECT 1 FROM referrals WHERE referee=?", (referee,)).fetchone()
            if ex:
                return False
            conn.execute("INSERT INTO referrals (referee, referrer, ts) VALUES (?,?,?)",
                         (referee, referrer, int(time.time())))
            conn.commit()
            return True
        finally:
            conn.close()


def referral_count(uid: str) -> int:
    with _lock:
        conn = _connect()
        try:
            _ensure_referrals(conn)
            r = conn.execute("SELECT COUNT(*) FROM referrals WHERE referrer=?", (uid,)).fetchone()
            return r[0] if r else 0
        finally:
            conn.close()


# ──────────────── событие дня (игра) ────────────────

def _ensure_event(conn):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS event_choices ("
        "day INTEGER, uid TEXT, choice TEXT, ts INTEGER, PRIMARY KEY(day, uid))")


def event_my_choice(day: int, uid: str):
    with _lock:
        conn = _connect()
        try:
            _ensure_event(conn)
            r = conn.execute("SELECT choice FROM event_choices WHERE day=? AND uid=?",
                             (day, uid)).fetchone()
            return r[0] if r else None
        finally:
            conn.close()


def event_choose(day: int, uid: str, choice: str) -> bool:
    """Записать выбор (один раз в день, потом не меняется)."""
    with _lock:
        conn = _connect()
        try:
            _ensure_event(conn)
            ex = conn.execute("SELECT 1 FROM event_choices WHERE day=? AND uid=?",
                              (day, uid)).fetchone()
            if ex:
                return False
            conn.execute("INSERT INTO event_choices (day, uid, choice, ts) VALUES (?,?,?,?)",
                         (day, uid, choice, int(time.time())))
            conn.commit()
            return True
        finally:
            conn.close()


def event_crowd(day: int) -> dict:
    with _lock:
        conn = _connect()
        try:
            _ensure_event(conn)
            rows = conn.execute(
                "SELECT choice, COUNT(*) FROM event_choices WHERE day=? GROUP BY choice",
                (day,)).fetchall()
        finally:
            conn.close()
    return {ch: n for ch, n in rows}


def event_answered_count(uid: str) -> int:
    with _lock:
        conn = _connect()
        try:
            _ensure_event(conn)
            r = conn.execute("SELECT COUNT(*) FROM event_choices WHERE uid=?", (uid,)).fetchone()
            return r[0] if r else 0
        finally:
            conn.close()


# ──────────────── стрик входов (ежедневный визит) ────────────────

def _ensure_login(conn):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS login_streak ("
        "uid TEXT PRIMARY KEY, last_day INTEGER, streak INTEGER, best INTEGER)")


def streak_ping(uid: str) -> dict:
    """Отметить визит. Возвращает {streak, best, today}. day = номер дня (UTC)."""
    today = int(time.time()) // 86400
    with _lock:
        conn = _connect()
        try:
            _ensure_login(conn)
            r = conn.execute("SELECT last_day, streak, best FROM login_streak WHERE uid=?",
                             (uid,)).fetchone()
            if not r:
                streak, best, last = 1, 1, today
            else:
                last, streak, best = r
                if last == today:
                    pass
                elif last == today - 1:
                    streak += 1
                else:
                    streak = 1
                best = max(best, streak)
            conn.execute(
                "INSERT INTO login_streak (uid, last_day, streak, best) VALUES (?,?,?,?) "
                "ON CONFLICT(uid) DO UPDATE SET last_day=excluded.last_day, "
                "streak=excluded.streak, best=excluded.best",
                (uid, today, streak, best))
            conn.commit()
            return {"streak": streak, "best": best, "today": last == today}
        finally:
            conn.close()


def streak_get(uid: str) -> dict:
    today = int(time.time()) // 86400
    with _lock:
        conn = _connect()
        try:
            _ensure_login(conn)
            r = conn.execute("SELECT last_day, streak, best FROM login_streak WHERE uid=?",
                             (uid,)).fetchone()
        finally:
            conn.close()
    if not r:
        return {"streak": 0, "best": 0}
    last, streak, best = r
    # если пропущен день — текущий стрик уже не активен (обнулится при следующем визите)
    if last < today - 1:
        streak = 0
    return {"streak": streak, "best": best}


def streak_users_to_remind(min_streak: int = 2) -> list:
    """uid пользователей с активным стриком, кто сегодня ещё не заходил."""
    today = int(time.time()) // 86400
    with _lock:
        conn = _connect()
        try:
            _ensure_login(conn)
            rows = conn.execute(
                "SELECT uid, streak FROM login_streak WHERE last_day=? AND streak>=?",
                (today - 1, min_streak)).fetchall()
            return [r[0] for r in rows]
        finally:
            conn.close()


# ──────────────── игра «Прогноз недели» ────────────────

def _ensure_pred(conn):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS pred_rounds ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, target REAL, "
        "start_ts INTEGER, close_ts INTEGER, status TEXT, result TEXT, close_price REAL)")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS pred_votes ("
        "round_id INTEGER, uid TEXT, name TEXT, choice TEXT, ts INTEGER, "
        "PRIMARY KEY(round_id, uid))")


def pred_create(symbol: str, target: float, days: int = 7) -> dict:
    now = int(time.time())
    with _lock:
        conn = _connect()
        try:
            _ensure_pred(conn)
            cur = conn.execute(
                "INSERT INTO pred_rounds (symbol, target, start_ts, close_ts, status) "
                "VALUES (?, ?, ?, ?, 'open')",
                (symbol, float(target), now, now + days * 86400))
            conn.commit()
            rid = cur.lastrowid
        finally:
            conn.close()
    return pred_get(rid)


def _round_row(conn, rid):
    return conn.execute(
        "SELECT id, symbol, target, start_ts, close_ts, status, result, close_price "
        "FROM pred_rounds WHERE id=?", (rid,)).fetchone()


def _round_dict(r):
    if not r:
        return None
    return {"id": r[0], "symbol": r[1], "target": r[2], "startTs": r[3],
            "closeTs": r[4], "status": r[5], "result": r[6], "closePrice": r[7]}


def pred_get(rid: int) -> dict:
    with _lock:
        conn = _connect()
        try:
            _ensure_pred(conn)
            return _round_dict(_round_row(conn, rid))
        finally:
            conn.close()


def pred_current() -> dict | None:
    with _lock:
        conn = _connect()
        try:
            _ensure_pred(conn)
            r = conn.execute(
                "SELECT id, symbol, target, start_ts, close_ts, status, result, close_price "
                "FROM pred_rounds WHERE status='open' ORDER BY id DESC LIMIT 1").fetchone()
            return _round_dict(r)
        finally:
            conn.close()


def pred_last_closed() -> dict | None:
    with _lock:
        conn = _connect()
        try:
            _ensure_pred(conn)
            r = conn.execute(
                "SELECT id, symbol, target, start_ts, close_ts, status, result, close_price "
                "FROM pred_rounds WHERE status='closed' ORDER BY id DESC LIMIT 1").fetchone()
            return _round_dict(r)
        finally:
            conn.close()


def pred_vote(round_id: int, uid: str, name: str, choice: str) -> bool:
    if choice not in ("up", "down"):
        return False
    now = int(time.time())
    with _lock:
        conn = _connect()
        try:
            _ensure_pred(conn)
            r = _round_row(conn, round_id)
            if not r or r[5] != "open" or now > r[4]:
                return False
            conn.execute(
                "INSERT INTO pred_votes (round_id, uid, name, choice, ts) VALUES (?,?,?,?,?) "
                "ON CONFLICT(round_id, uid) DO UPDATE SET choice=excluded.choice, ts=excluded.ts",
                (round_id, uid, name, choice, now))
            conn.commit()
            return True
        finally:
            conn.close()


def pred_my_vote(round_id: int, uid: str):
    with _lock:
        conn = _connect()
        try:
            _ensure_pred(conn)
            r = conn.execute("SELECT choice FROM pred_votes WHERE round_id=? AND uid=?",
                             (round_id, uid)).fetchone()
            return r[0] if r else None
        finally:
            conn.close()


def pred_crowd(round_id: int) -> dict:
    with _lock:
        conn = _connect()
        try:
            _ensure_pred(conn)
            rows = conn.execute(
                "SELECT choice, COUNT(*) FROM pred_votes WHERE round_id=? GROUP BY choice",
                (round_id,)).fetchall()
        finally:
            conn.close()
    d = {"up": 0, "down": 0}
    for ch, n in rows:
        d[ch] = n
    d["total"] = d["up"] + d["down"]
    return d


def pred_resolve(round_id: int, close_price: float) -> dict | None:
    with _lock:
        conn = _connect()
        try:
            _ensure_pred(conn)
            r = _round_row(conn, round_id)
            if not r or r[5] == "closed":
                return _round_dict(r)
            result = "up" if close_price >= r[2] else "down"
            conn.execute(
                "UPDATE pred_rounds SET status='closed', result=?, close_price=? WHERE id=?",
                (result, float(close_price), round_id))
            conn.commit()
            return _round_dict(_round_row(conn, round_id))
        finally:
            conn.close()


def pred_leaderboard(limit: int = 20) -> list:
    with _lock:
        conn = _connect()
        try:
            _ensure_pred(conn)
            rows = conn.execute(
                "SELECT v.uid, MAX(v.name), "
                "SUM(CASE WHEN v.choice=r.result THEN 1 ELSE 0 END), COUNT(*) "
                "FROM pred_votes v JOIN pred_rounds r ON v.round_id=r.id "
                "WHERE r.status='closed' AND r.result IS NOT NULL "
                "GROUP BY v.uid ORDER BY 3 DESC, 4 DESC LIMIT ?", (limit,)).fetchall()
        finally:
            conn.close()
    return [{"uid": x[0], "name": x[1] or "Аноним", "points": x[2], "total": x[3]}
            for x in rows]


def pred_my_stats(uid: str) -> dict:
    with _lock:
        conn = _connect()
        try:
            _ensure_pred(conn)
            r = conn.execute(
                "SELECT SUM(CASE WHEN v.choice=r.result THEN 1 ELSE 0 END), COUNT(*) "
                "FROM pred_votes v JOIN pred_rounds r ON v.round_id=r.id "
                "WHERE r.status='closed' AND r.result IS NOT NULL AND v.uid=?",
                (uid,)).fetchone()
        finally:
            conn.close()
    pts = r[0] or 0 if r else 0
    tot = r[1] or 0 if r else 0
    return {"points": pts, "total": tot}


# ──────────────── своя история цен (ежедневный снимок) ────────────────

def _ensure_price_history(conn):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS price_history ("
        "ticker TEXT, date TEXT, close REAL, PRIMARY KEY(ticker, date))")


def save_price(ticker: str, date: str, close: float) -> None:
    tk = (ticker or "").strip().upper()
    if not tk or close is None:
        return
    with _lock:
        conn = _connect()
        try:
            _ensure_price_history(conn)
            conn.execute(
                "INSERT INTO price_history (ticker, date, close) VALUES (?, ?, ?) "
                "ON CONFLICT(ticker, date) DO UPDATE SET close=excluded.close",
                (tk, date, float(close)))
            conn.commit()
        finally:
            conn.close()


def get_price_history(ticker: str, since: str | None = None) -> dict:
    """Своя дневная история: {YYYY-MM-DD: close} для тикера."""
    tk = (ticker or "").strip().upper()
    with _lock:
        conn = _connect()
        try:
            _ensure_price_history(conn)
            if since:
                rows = conn.execute(
                    "SELECT date, close FROM price_history WHERE ticker=? AND date>=? "
                    "ORDER BY date", (tk, since)).fetchall()
            else:
                rows = conn.execute(
                    "SELECT date, close FROM price_history WHERE ticker=? ORDER BY date",
                    (tk,)).fetchall()
            return {r[0]: r[1] for r in rows}
        finally:
            conn.close()


def all_held_tickers() -> list:
    """Уникальные тикеры из сделок всех портфелей — для снимка цен."""
    with _lock:
        conn = _connect()
        try:
            rows = conn.execute("SELECT doc FROM portfolios").fetchall()
        finally:
            conn.close()
    seen = set()
    for (doc,) in rows:
        try:
            d = json.loads(doc)
        except Exception:
            continue
        for t in d.get("trades", []):
            tk = (t.get("ticker") or "").strip().upper()
            if tk:
                seen.add(tk)
    return sorted(seen)


# ──────────────── премиум-подписка (оплата) ────────────────

def _ensure_premium(conn):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS premium (uid TEXT PRIMARY KEY, until_ts INTEGER)")


def grant_premium(uid: str, days: int) -> int:
    """Выдать/продлить премиум. Продление считается от max(сейчас, текущий конец).
    Возвращает новый until_ts."""
    now = int(time.time())
    with _lock:
        conn = _connect()
        try:
            _ensure_premium(conn)
            row = conn.execute("SELECT until_ts FROM premium WHERE uid=?", (uid,)).fetchone()
            base = max(now, row[0]) if row and row[0] else now
            until = base + days * 86400
            conn.execute(
                "INSERT INTO premium (uid, until_ts) VALUES (?, ?) "
                "ON CONFLICT(uid) DO UPDATE SET until_ts=excluded.until_ts", (uid, until))
            conn.commit()
            return until
        finally:
            conn.close()


def premium_until(uid: str) -> int:
    if not uid:
        return 0
    with _lock:
        conn = _connect()
        try:
            _ensure_premium(conn)
            row = conn.execute("SELECT until_ts FROM premium WHERE uid=?", (uid,)).fetchone()
            return row[0] if row and row[0] else 0
        finally:
            conn.close()


def is_premium(uid: str) -> bool:
    return premium_until(uid) > int(time.time())


def _ensure_earlybird(conn):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS early_bird (uid TEXT PRIMARY KEY, ts INTEGER)")


def add_early_bird(uid: str) -> None:
    with _lock:
        conn = _connect()
        try:
            _ensure_earlybird(conn)
            conn.execute("INSERT OR IGNORE INTO early_bird (uid, ts) VALUES (?, ?)",
                         (uid, int(time.time())))
            conn.commit()
        finally:
            conn.close()


def is_early_bird(uid: str) -> bool:
    if not uid:
        return False
    with _lock:
        conn = _connect()
        try:
            _ensure_earlybird(conn)
            return bool(conn.execute(
                "SELECT 1 FROM early_bird WHERE uid=?", (uid,)).fetchone())
        finally:
            conn.close()


def early_bird_count() -> int:
    with _lock:
        conn = _connect()
        try:
            _ensure_earlybird(conn)
            r = conn.execute("SELECT COUNT(*) FROM early_bird").fetchone()
            return r[0] if r else 0
        finally:
            conn.close()


# ──────────────── онбординг (5 уроков, по одному в день) ────────────────

_ONBOARDING_TOTAL = 5
_ONBOARDING_GAP = 20 * 3600   # следующий урок не раньше, чем через ~сутки


def _ensure_onboarding(conn):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS onboarding ("
        "uid TEXT PRIMARY KEY, done INTEGER, last_ts INTEGER)")


def onboarding_get(uid: str) -> dict:
    with _lock:
        conn = _connect()
        try:
            _ensure_onboarding(conn)
            row = conn.execute(
                "SELECT done, last_ts FROM onboarding WHERE uid=?", (uid,)).fetchone()
        finally:
            conn.close()
    now = int(time.time())
    done, last_ts = (row[0], row[1]) if row else (0, 0)
    finished = done >= _ONBOARDING_TOTAL
    can = (not finished) and (done == 0 or now - last_ts >= _ONBOARDING_GAP)
    next_in = 0
    if not can and not finished:
        next_in = int((_ONBOARDING_GAP - (now - last_ts)) // 3600) + 1
    return {"done": done, "total": _ONBOARDING_TOTAL, "canRead": can,
            "finished": finished, "nextInHours": max(0, next_in)}


def onboarding_read(uid: str) -> dict:
    now = int(time.time())
    with _lock:
        conn = _connect()
        try:
            _ensure_onboarding(conn)
            row = conn.execute(
                "SELECT done, last_ts FROM onboarding WHERE uid=?", (uid,)).fetchone()
            done, last_ts = (row[0], row[1]) if row else (0, 0)
            ok = done < _ONBOARDING_TOTAL and (done == 0 or now - last_ts >= _ONBOARDING_GAP)
            if ok:
                done += 1
                conn.execute(
                    "INSERT INTO onboarding (uid, done, last_ts) VALUES (?, ?, ?) "
                    "ON CONFLICT(uid) DO UPDATE SET done=excluded.done, last_ts=excluded.last_ts",
                    (uid, done, now))
                conn.commit()
        finally:
            conn.close()
    st = onboarding_get(uid)
    st["ok"] = ok
    return st


# ──────────────── Q&A (вопрос-ответ) ────────────────

def _ensure_qa(conn):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS qa ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER, uid TEXT, name TEXT, "
        "question TEXT, answer TEXT, answered_by TEXT)")


def qa_count_today(uid: str) -> int:
    since = int(time.time()) - 86400
    with _lock:
        conn = _connect()
        try:
            _ensure_qa(conn)
            r = conn.execute("SELECT COUNT(*) FROM qa WHERE uid=? AND ts>=?",
                             (uid, since)).fetchone()
            return r[0] if r else 0
        finally:
            conn.close()


def add_qa(uid: str, name: str, question: str, answer, answered_by) -> int:
    with _lock:
        conn = _connect()
        try:
            _ensure_qa(conn)
            cur = conn.execute(
                "INSERT INTO qa (ts, uid, name, question, answer, answered_by) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (int(time.time()), uid, name, question, answer, answered_by))
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()


def set_qa_answer(qid: int, answer: str, answered_by: str = "owner"):
    with _lock:
        conn = _connect()
        try:
            _ensure_qa(conn)
            row = conn.execute("SELECT uid FROM qa WHERE id=?", (qid,)).fetchone()
            if not row:
                return None
            conn.execute("UPDATE qa SET answer=?, answered_by=? WHERE id=?",
                         (answer, answered_by, qid))
            conn.commit()
            return row[0]
        finally:
            conn.close()


def _qa_rows_to_list(rows):
    return [{"id": r[0], "ts": r[1], "uid": r[2], "name": r[3], "question": r[4],
             "answer": r[5], "answeredBy": r[6]} for r in rows]


def list_qa_mine(uid: str, limit: int = 30) -> list:
    with _lock:
        conn = _connect()
        try:
            _ensure_qa(conn)
            rows = conn.execute(
                "SELECT id, ts, uid, name, question, answer, answered_by FROM qa "
                "WHERE uid=? ORDER BY id DESC LIMIT ?", (uid, limit)).fetchall()
            return _qa_rows_to_list(rows)
        finally:
            conn.close()


def list_qa_all(limit: int = 100) -> list:
    with _lock:
        conn = _connect()
        try:
            _ensure_qa(conn)
            rows = conn.execute(
                "SELECT id, ts, uid, name, question, answer, answered_by FROM qa "
                "ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
            return _qa_rows_to_list(rows)
        finally:
            conn.close()


# ──────────────── обратная связь (лендинг) ────────────────

def _ensure_feedback(conn):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS feedback ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER, name TEXT, phone TEXT, "
        "message TEXT, consent_pd INTEGER, consent_ads INTEGER)")


def add_feedback(name: str, phone: str, message: str,
                 consent_pd: bool, consent_ads: bool) -> int:
    with _lock:
        conn = _connect()
        try:
            _ensure_feedback(conn)
            cur = conn.execute(
                "INSERT INTO feedback (ts, name, phone, message, consent_pd, consent_ads) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (int(time.time()), name, phone, message,
                 1 if consent_pd else 0, 1 if consent_ads else 0))
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()


def list_feedback(limit: int = 100) -> list:
    with _lock:
        conn = _connect()
        try:
            _ensure_feedback(conn)
            rows = conn.execute(
                "SELECT id, ts, name, phone, message, consent_pd, consent_ads "
                "FROM feedback ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
            return [{"id": r[0], "ts": r[1], "name": r[2], "phone": r[3],
                     "message": r[4], "consentPd": bool(r[5]), "consentAds": bool(r[6])}
                    for r in rows]
        finally:
            conn.close()


# ──────────────── доп. администраторы (по @username) ────────────────
# Полный доступ в приложении (как у владельца): редактировать публичный
# портфель, контент-студия, публикация. По нику, т.к. id узнаём только когда
# юзер откроет Mini App. НЕ даёт доступа к коду/серверу.

def _ensure_admins(conn):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS extra_admins (username TEXT PRIMARY KEY, ts INTEGER)")


def add_admin_username(username) -> None:
    u = (username or "").lstrip("@").lower()
    if not u:
        return
    with _lock:
        conn = _connect()
        try:
            _ensure_admins(conn)
            conn.execute("INSERT OR IGNORE INTO extra_admins (username, ts) VALUES (?, ?)",
                         (u, int(time.time())))
            conn.commit()
        finally:
            conn.close()


def remove_admin_username(username) -> None:
    u = (username or "").lstrip("@").lower()
    with _lock:
        conn = _connect()
        try:
            _ensure_admins(conn)
            conn.execute("DELETE FROM extra_admins WHERE username=?", (u,))
            conn.commit()
        finally:
            conn.close()


def is_admin_username(username) -> bool:
    u = (username or "").lstrip("@").lower()
    if not u:
        return False
    with _lock:
        conn = _connect()
        try:
            _ensure_admins(conn)
            return bool(conn.execute(
                "SELECT 1 FROM extra_admins WHERE username=?", (u,)).fetchone())
        finally:
            conn.close()


def list_admin_usernames() -> list:
    with _lock:
        conn = _connect()
        try:
            _ensure_admins(conn)
            return [r[0] for r in conn.execute(
                "SELECT username FROM extra_admins").fetchall()]
        finally:
            conn.close()


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


# ──────────────── стрик дисциплины DCA (геймификация привычки) ────────────────
# Привычка: вносить DCA-взнос раз в 2 недели. Отметка «внёс» наращивает серию.
# Слишком рано (<10 дн) — не засчитываем; пропуск (>21 дн) — серия сбрасывается.

_DCA_EARLY = 10 * 86400      # раньше нельзя отметить следующий взнос
_DCA_GRACE = 21 * 86400      # позже = пропуск, серия начинается заново


def _ensure_dca(conn):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS dca ("
        "uid TEXT PRIMARY KEY, last_ts INTEGER, streak INTEGER, "
        "longest INTEGER, total INTEGER)")


def dca_get(uid: str) -> dict:
    with _lock:
        conn = _connect()
        try:
            _ensure_dca(conn)
            row = conn.execute(
                "SELECT last_ts, streak, longest, total FROM dca WHERE uid=?",
                (uid,)).fetchone()
        finally:
            conn.close()
    now = int(time.time())
    if not row:
        return {"streak": 0, "longest": 0, "total": 0, "lastTs": None,
                "canCheckIn": True, "nextInDays": 0, "atRisk": False}
    last_ts, streak, longest, total = row
    elapsed = now - (last_ts or 0)
    can = elapsed >= _DCA_EARLY
    next_in = 0 if can else int((_DCA_EARLY - elapsed) // 86400) + 1
    return {"streak": streak, "longest": longest, "total": total,
            "lastTs": last_ts, "canCheckIn": can, "nextInDays": next_in,
            "atRisk": elapsed > _DCA_GRACE}


def dca_checkin(uid: str) -> dict:
    """Отметить взнос. result: started | on_time | reset | early."""
    now = int(time.time())
    with _lock:
        conn = _connect()
        try:
            _ensure_dca(conn)
            row = conn.execute(
                "SELECT last_ts, streak, longest, total FROM dca WHERE uid=?",
                (uid,)).fetchone()
            if not row:
                streak, longest, total, result = 1, 1, 1, "started"
            else:
                last_ts, streak, longest, total = row
                elapsed = now - (last_ts or 0)
                if elapsed < _DCA_EARLY:
                    result = "early"
                else:
                    if elapsed > _DCA_GRACE:
                        streak, result = 1, "reset"
                    else:
                        streak, result = streak + 1, "on_time"
                    total += 1
                    longest = max(longest, streak)
            if result != "early":
                conn.execute(
                    "INSERT INTO dca (uid, last_ts, streak, longest, total) "
                    "VALUES (?,?,?,?,?) ON CONFLICT(uid) DO UPDATE SET "
                    "last_ts=excluded.last_ts, streak=excluded.streak, "
                    "longest=excluded.longest, total=excluded.total",
                    (uid, now, streak, longest, total))
                conn.commit()
        finally:
            conn.close()
    st = dca_get(uid)
    st["result"] = result
    st["ok"] = result != "early"
    return st


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


# ──────────────── универсальное хранилище состояния (key→value) ────────────────
# Для служебных флагов: антиспам-кулдаун AI-алертов и т.п. Значение — строка.

def _ensure_meta(conn):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT)")


def meta_get(key: str, default=None):
    with _lock:
        conn = _connect()
        try:
            _ensure_meta(conn)
            row = conn.execute("SELECT v FROM meta WHERE k=?", (key,)).fetchone()
            return row[0] if row else default
        finally:
            conn.close()


def meta_set(key: str, value) -> None:
    with _lock:
        conn = _connect()
        try:
            _ensure_meta(conn)
            conn.execute(
                "INSERT INTO meta (k, v) VALUES (?, ?) "
                "ON CONFLICT(k) DO UPDATE SET v=excluded.v",
                (key, str(value)))
            conn.commit()
        finally:
            conn.close()


# ──────────────── учёт источников трафика (?start=src_<метка>) ────────────────
# Откуда пришёл юзер: каждое рекламное/взаимопиар-размещение — своя метка.
# За юзером закрепляется ПЕРВЫЙ источник (INSERT OR IGNORE).

def _ensure_sources(conn):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS source_hits ("
        "uid TEXT PRIMARY KEY, src TEXT NOT NULL, ts INTEGER NOT NULL)")


def source_track(uid: str, src: str) -> None:
    with _lock:
        conn = _connect()
        try:
            _ensure_sources(conn)
            conn.execute(
                "INSERT OR IGNORE INTO source_hits (uid, src, ts) VALUES (?, ?, ?)",
                (uid, src, int(time.time())))
            conn.commit()
        finally:
            conn.close()


def source_stats() -> list:
    """[{src, total, premium}] по источникам, по убыванию total."""
    now = int(time.time())
    with _lock:
        conn = _connect()
        try:
            _ensure_sources(conn)
            conn.execute(
                "CREATE TABLE IF NOT EXISTS premium (uid TEXT PRIMARY KEY, until_ts INTEGER)")
            rows = conn.execute(
                "SELECT sh.src, COUNT(*), "
                "SUM(CASE WHEN p.until_ts > ? THEN 1 ELSE 0 END) "
                "FROM source_hits sh LEFT JOIN premium p ON p.uid = sh.uid "
                "GROUP BY sh.src ORDER BY COUNT(*) DESC", (now,)).fetchall()
            return [{"src": r[0], "total": r[1], "premium": r[2] or 0} for r in rows]
        finally:
            conn.close()
