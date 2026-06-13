import sqlite3
import json
from config import DATABASE_PATH


def get_conn():
    conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
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
        CREATE TABLE IF NOT EXISTS enemies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            username TEXT,
            name TEXT,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS friends (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            username TEXT,
            name TEXT,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS silent_chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER UNIQUE NOT NULL,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS silent_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS saved_messages (
            slot INTEGER PRIMARY KEY,
            content TEXT,
            media_path TEXT,
            saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS deleted_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            sender_id INTEGER,
            sender_name TEXT,
            message TEXT,
            media_type TEXT,
            deleted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS scheduled_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            send_at TIMESTAMP NOT NULL,
            sent INTEGER DEFAULT 0
        )
    """)

    defaults = {
        "self_bot_active": "0",
        "secretary_active": "0",
        "anti_delete_active": "0",
        "anti_link_active": "0",
        "auto_seen_active": "0",
        "auto_reaction_active": "0",
        "private_lock_active": "0",
        "enemy_reply_active": "0",
        "auto_save_media": "0",
        "clock_name_active": "0",
        "clock_bio_active": "0",
        "selected_font": "0",
        "secretary_message": "در حال حاضر در دسترس نیستم، بعداً پیام بگذارید.",
        "auto_reaction_emoji": "❤️",
        "typing_style": "0",
        "spam_active": "0",
        "spam_count": "10",
        "spam_delay": "2",
        "spam_text": "",
        "session_data": "",
        "logged_in": "0",
    }

    for key, value in defaults.items():
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, value))

    conn.commit()
    conn.close()


def get_setting(key, default=None):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = c.fetchone()
    conn.close()
    return row["value"] if row else default


def set_setting(key, value):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()


def toggle_setting(key):
    current = get_setting(key, "0")
    new_val = "0" if current == "1" else "1"
    set_setting(key, new_val)
    return new_val == "1"


def add_enemy(user_id, username=None, name=None):
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute(
            "INSERT OR REPLACE INTO enemies (user_id, username, name) VALUES (?, ?, ?)",
            (user_id, username, name),
        )
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()


def remove_enemy(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM enemies WHERE user_id = ?", (user_id,))
    affected = c.rowcount
    conn.commit()
    conn.close()
    return affected > 0


def get_enemies():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM enemies ORDER BY added_at DESC")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def is_enemy(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT 1 FROM enemies WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row is not None


def clear_enemies():
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM enemies")
    conn.commit()
    conn.close()


def add_friend(user_id, username=None, name=None):
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute(
            "INSERT OR REPLACE INTO friends (user_id, username, name) VALUES (?, ?, ?)",
            (user_id, username, name),
        )
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()


def remove_friend(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM friends WHERE user_id = ?", (user_id,))
    affected = c.rowcount
    conn.commit()
    conn.close()
    return affected > 0


def get_friends():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM friends ORDER BY added_at DESC")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def is_friend(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT 1 FROM friends WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row is not None


def clear_friends():
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM friends")
    conn.commit()
    conn.close()


def add_silent_chat(chat_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO silent_chats (chat_id) VALUES (?)", (chat_id,))
    conn.commit()
    conn.close()


def remove_silent_chat(chat_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM silent_chats WHERE chat_id = ?", (chat_id,))
    conn.commit()
    conn.close()


def is_silent_chat(chat_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT 1 FROM silent_chats WHERE chat_id = ?", (chat_id,))
    row = c.fetchone()
    conn.close()
    return row is not None


def add_silent_user(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO silent_users (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()


def remove_silent_user(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM silent_users WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def is_silent_user(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT 1 FROM silent_users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row is not None


def save_message_slot(slot, content, media_path=None):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO saved_messages (slot, content, media_path) VALUES (?, ?, ?)",
        (slot, content, media_path),
    )
    conn.commit()
    conn.close()


def get_message_slot(slot):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM saved_messages WHERE slot = ?", (slot,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def log_deleted_message(chat_id, sender_id, sender_name, message, media_type=None):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO deleted_messages (chat_id, sender_id, sender_name, message, media_type) VALUES (?, ?, ?, ?, ?)",
        (chat_id, sender_id, sender_name, message, media_type),
    )
    conn.commit()
    conn.close()


def get_deleted_messages(limit=50):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM deleted_messages ORDER BY deleted_at DESC LIMIT ?", (limit,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def add_scheduled_message(chat_id, message, send_at):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO scheduled_messages (chat_id, message, send_at) VALUES (?, ?, ?)",
        (chat_id, message, send_at),
    )
    last_id = c.lastrowid
    conn.commit()
    conn.close()
    return last_id


def get_pending_scheduled():
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "SELECT * FROM scheduled_messages WHERE sent = 0 AND send_at <= datetime('now') ORDER BY send_at"
    )
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def mark_scheduled_sent(msg_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE scheduled_messages SET sent = 1 WHERE id = ?", (msg_id,))
    conn.commit()
    conn.close()
