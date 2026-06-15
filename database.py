import sqlite3
import json
from config import DB_PATH


def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS friends (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            added_at TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS enemies (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            added_at TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS deleted_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            sender_id INTEGER,
            sender_name TEXT,
            message_text TEXT,
            media_path TEXT,
            deleted_at TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS saved_messages (
            slot INTEGER PRIMARY KEY,
            content TEXT,
            saved_at TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS scheduled_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            message TEXT,
            send_at TEXT,
            sent INTEGER DEFAULT 0
        )
    """)

    defaults = {
        "bot_active": "true",
        "secretary_active": "false",
        "anti_delete_active": "false",
        "pv_lock_active": "false",
        "anti_link_active": "false",
        "auto_seen_active": "false",
        "auto_react_active": "false",
        "secretary_text": "در حال حاضر در دسترس نیستم. پیام بگذارید.",
        "auto_react_emoji": "👍",
        "spam_delay": "2",
    }
    for key, value in defaults.items():
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, value))

    conn.commit()
    conn.close()


def get_setting(key: str) -> str:
    conn = get_conn()
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else ""


def set_setting(key: str, value: str):
    conn = get_conn()
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()


def is_active() -> bool:
    return get_setting("bot_active") == "true"


def add_friend(user_id: int, username: str = ""):
    from datetime import datetime
    import pytz
    tz = pytz.timezone("Asia/Tehran")
    now = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO friends (user_id, username, added_at) VALUES (?, ?, ?)",
        (user_id, username, now)
    )
    conn.commit()
    conn.close()


def remove_friend(user_id: int):
    conn = get_conn()
    conn.execute("DELETE FROM friends WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def is_friend(user_id: int) -> bool:
    conn = get_conn()
    row = conn.execute("SELECT 1 FROM friends WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return row is not None


def get_friends():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM friends").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_enemy(user_id: int, username: str = ""):
    from datetime import datetime
    import pytz
    tz = pytz.timezone("Asia/Tehran")
    now = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO enemies (user_id, username, added_at) VALUES (?, ?, ?)",
        (user_id, username, now)
    )
    conn.commit()
    conn.close()


def remove_enemy(user_id: int):
    conn = get_conn()
    conn.execute("DELETE FROM enemies WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def is_enemy(user_id: int) -> bool:
    conn = get_conn()
    row = conn.execute("SELECT 1 FROM enemies WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return row is not None


def get_enemies():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM enemies").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_deleted_message(chat_id, sender_id, sender_name, message_text, media_path=""):
    from datetime import datetime
    import pytz
    tz = pytz.timezone("Asia/Tehran")
    now = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
    conn = get_conn()
    conn.execute(
        "INSERT INTO deleted_messages (chat_id, sender_id, sender_name, message_text, media_path, deleted_at) VALUES (?,?,?,?,?,?)",
        (chat_id, sender_id, sender_name, message_text, media_path, now)
    )
    conn.commit()
    conn.close()


def get_deleted_messages(limit=20):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM deleted_messages ORDER BY deleted_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_slot(slot: int, content: str):
    from datetime import datetime
    import pytz
    tz = pytz.timezone("Asia/Tehran")
    now = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO saved_messages (slot, content, saved_at) VALUES (?, ?, ?)",
        (slot, content, now)
    )
    conn.commit()
    conn.close()


def get_slot(slot: int) -> str:
    conn = get_conn()
    row = conn.execute("SELECT content FROM saved_messages WHERE slot = ?", (slot,)).fetchone()
    conn.close()
    return row["content"] if row else ""


def all_slots():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM saved_messages ORDER BY slot").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_scheduled(chat_id: int, message: str, send_at: str):
    conn = get_conn()
    conn.execute(
        "INSERT INTO scheduled_messages (chat_id, message, send_at) VALUES (?, ?, ?)",
        (chat_id, message, send_at)
    )
    conn.commit()
    conn.close()


def get_pending_scheduled(now_str: str):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM scheduled_messages WHERE sent = 0 AND send_at <= ?", (now_str,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mark_scheduled_sent(msg_id: int):
    conn = get_conn()
    conn.execute("UPDATE scheduled_messages SET sent = 1 WHERE id = ?", (msg_id,))
    conn.commit()
    conn.close()


def get_all_settings() -> dict:
    conn = get_conn()
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    conn.close()
    return {r["key"]: r["value"] for r in rows}
