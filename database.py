import sqlite3
import hashlib
import os
from config import DATABASE_PATH


def get_conn():
    conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _hash_pw(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def init_db():
    conn = get_conn()
    c = conn.cursor()

    # ─── حساب‌های پنل ────────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ─── تنظیمات (per-user) ───────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            owner_id INTEGER NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            PRIMARY KEY (owner_id, key)
        )
    """)

    # ─── دشمن ─────────────────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS enemies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            username TEXT,
            name TEXT,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (owner_id, user_id)
        )
    """)

    # ─── دوست ─────────────────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS friends (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            username TEXT,
            name TEXT,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (owner_id, user_id)
        )
    """)

    # ─── سایلنت چت ────────────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS silent_chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id INTEGER NOT NULL,
            chat_id INTEGER NOT NULL,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (owner_id, chat_id)
        )
    """)

    # ─── سایلنت کاربر ─────────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS silent_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (owner_id, user_id)
        )
    """)

    # ─── پیام‌های ذخیره‌شده ────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS saved_messages (
            owner_id INTEGER NOT NULL,
            slot INTEGER NOT NULL,
            content TEXT,
            media_path TEXT,
            saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (owner_id, slot)
        )
    """)

    # ─── پیام‌های حذف‌شده ─────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS deleted_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id INTEGER NOT NULL,
            chat_id INTEGER,
            sender_id INTEGER,
            sender_name TEXT,
            message TEXT,
            media_type TEXT,
            deleted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ─── پیام‌های زمان‌بندی‌شده ───────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS scheduled_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id INTEGER NOT NULL,
            chat_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            send_at TIMESTAMP NOT NULL,
            sent INTEGER DEFAULT 0
        )
    """)

    conn.commit()
    conn.close()


# ─── مدیریت حساب ──────────────────────────────────────────────────────────────
def create_account(username: str, password: str):
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute(
            "INSERT INTO accounts (username, password_hash) VALUES (?, ?)",
            (username.strip(), _hash_pw(password)),
        )
        conn.commit()
        return c.lastrowid
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()


def verify_account(username: str, password: str):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "SELECT id FROM accounts WHERE username = ? AND password_hash = ?",
        (username.strip(), _hash_pw(password)),
    )
    row = c.fetchone()
    conn.close()
    return row["id"] if row else None


def get_account(owner_id: int):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, username, created_at FROM accounts WHERE id = ?", (owner_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_accounts():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, username, created_at FROM accounts ORDER BY created_at")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def account_exists():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) as cnt FROM accounts")
    row = c.fetchone()
    conn.close()
    return row["cnt"] > 0


# ─── تنظیمات ──────────────────────────────────────────────────────────────────
SETTING_DEFAULTS = {
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
    "channel_save_active": "0",
    "spam_count": "10",
    "spam_delay": "2",
    "spam_text": "",
    "session_data": "",
    "logged_in": "0",
}


def init_user_settings(owner_id: int):
    conn = get_conn()
    c = conn.cursor()
    for key, value in SETTING_DEFAULTS.items():
        c.execute(
            "INSERT OR IGNORE INTO settings (owner_id, key, value) VALUES (?, ?, ?)",
            (owner_id, key, value),
        )
    conn.commit()
    conn.close()


def get_setting(owner_id: int, key: str, default=None):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE owner_id = ? AND key = ?", (owner_id, key))
    row = c.fetchone()
    conn.close()
    if row:
        return row["value"]
    return SETTING_DEFAULTS.get(key, default)


def set_setting(owner_id: int, key: str, value):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO settings (owner_id, key, value) VALUES (?, ?, ?)",
        (owner_id, key, str(value)),
    )
    conn.commit()
    conn.close()


def toggle_setting(owner_id: int, key: str):
    current = get_setting(owner_id, key, "0")
    new_val = "0" if current == "1" else "1"
    set_setting(owner_id, key, new_val)
    return new_val == "1"


def get_all_logged_in_users():
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "SELECT owner_id FROM settings WHERE key = 'logged_in' AND value = '1'"
    )
    rows = [r["owner_id"] for r in c.fetchall()]
    conn.close()
    return rows


# ─── دشمن ─────────────────────────────────────────────────────────────────────
def add_enemy(owner_id: int, user_id: int, username=None, name=None):
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute(
            "INSERT OR REPLACE INTO enemies (owner_id, user_id, username, name) VALUES (?, ?, ?, ?)",
            (owner_id, user_id, username, name),
        )
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()


def remove_enemy(owner_id: int, user_id: int):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM enemies WHERE owner_id = ? AND user_id = ?", (owner_id, user_id))
    affected = c.rowcount
    conn.commit()
    conn.close()
    return affected > 0


def get_enemies(owner_id: int):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM enemies WHERE owner_id = ? ORDER BY added_at DESC", (owner_id,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def is_enemy(owner_id: int, user_id: int):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT 1 FROM enemies WHERE owner_id = ? AND user_id = ?", (owner_id, user_id))
    row = c.fetchone()
    conn.close()
    return row is not None


def clear_enemies(owner_id: int):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM enemies WHERE owner_id = ?", (owner_id,))
    conn.commit()
    conn.close()


# ─── دوست ─────────────────────────────────────────────────────────────────────
def add_friend(owner_id: int, user_id: int, username=None, name=None):
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute(
            "INSERT OR REPLACE INTO friends (owner_id, user_id, username, name) VALUES (?, ?, ?, ?)",
            (owner_id, user_id, username, name),
        )
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()


def remove_friend(owner_id: int, user_id: int):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM friends WHERE owner_id = ? AND user_id = ?", (owner_id, user_id))
    affected = c.rowcount
    conn.commit()
    conn.close()
    return affected > 0


def get_friends(owner_id: int):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM friends WHERE owner_id = ? ORDER BY added_at DESC", (owner_id,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def is_friend(owner_id: int, user_id: int):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT 1 FROM friends WHERE owner_id = ? AND user_id = ?", (owner_id, user_id))
    row = c.fetchone()
    conn.close()
    return row is not None


def clear_friends(owner_id: int):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM friends WHERE owner_id = ?", (owner_id,))
    conn.commit()
    conn.close()


# ─── سایلنت ───────────────────────────────────────────────────────────────────
def add_silent_chat(owner_id: int, chat_id: int):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO silent_chats (owner_id, chat_id) VALUES (?, ?)", (owner_id, chat_id))
    conn.commit()
    conn.close()


def remove_silent_chat(owner_id: int, chat_id: int):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM silent_chats WHERE owner_id = ? AND chat_id = ?", (owner_id, chat_id))
    conn.commit()
    conn.close()


def is_silent_chat(owner_id: int, chat_id: int):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT 1 FROM silent_chats WHERE owner_id = ? AND chat_id = ?", (owner_id, chat_id))
    row = c.fetchone()
    conn.close()
    return row is not None


def add_silent_user(owner_id: int, user_id: int):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO silent_users (owner_id, user_id) VALUES (?, ?)", (owner_id, user_id))
    conn.commit()
    conn.close()


def remove_silent_user(owner_id: int, user_id: int):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM silent_users WHERE owner_id = ? AND user_id = ?", (owner_id, user_id))
    conn.commit()
    conn.close()


def is_silent_user(owner_id: int, user_id: int):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT 1 FROM silent_users WHERE owner_id = ? AND user_id = ?", (owner_id, user_id))
    row = c.fetchone()
    conn.close()
    return row is not None


# ─── پیام‌های ذخیره‌شده ────────────────────────────────────────────────────────
def save_message_slot(owner_id: int, slot: int, content, media_path=None):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO saved_messages (owner_id, slot, content, media_path) VALUES (?, ?, ?, ?)",
        (owner_id, slot, content, media_path),
    )
    conn.commit()
    conn.close()


def get_message_slot(owner_id: int, slot: int):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM saved_messages WHERE owner_id = ? AND slot = ?", (owner_id, slot))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


# ─── پیام‌های حذف‌شده ─────────────────────────────────────────────────────────
def log_deleted_message(owner_id: int, chat_id, sender_id, sender_name, message, media_type=None):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO deleted_messages (owner_id, chat_id, sender_id, sender_name, message, media_type) VALUES (?, ?, ?, ?, ?, ?)",
        (owner_id, chat_id, sender_id, sender_name, message, media_type),
    )
    conn.commit()
    conn.close()


def get_deleted_messages(owner_id: int, limit=50):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "SELECT * FROM deleted_messages WHERE owner_id = ? ORDER BY deleted_at DESC LIMIT ?",
        (owner_id, limit),
    )
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


# ─── پیام‌های زمان‌بندی‌شده ───────────────────────────────────────────────────
def add_scheduled_message(owner_id: int, chat_id, message, send_at):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO scheduled_messages (owner_id, chat_id, message, send_at) VALUES (?, ?, ?, ?)",
        (owner_id, chat_id, message, send_at),
    )
    last_id = c.lastrowid
    conn.commit()
    conn.close()
    return last_id


def get_pending_scheduled(owner_id: int):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "SELECT * FROM scheduled_messages WHERE owner_id = ? AND sent = 0 AND send_at <= datetime('now') ORDER BY send_at",
        (owner_id,),
    )
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def mark_scheduled_sent(msg_id: int):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE scheduled_messages SET sent = 1 WHERE id = ?", (msg_id,))
    conn.commit()
    conn.close()
