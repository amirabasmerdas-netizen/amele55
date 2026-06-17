import sqlite3
import datetime
from config import CACHE_DB_PATH

# ─── اتصال به دیتابیس کش ──────────────────────────────────────────────────────
_conn = None

def get_conn():
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(CACHE_DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("PRAGMA synchronous=NORMAL")
        _conn.execute("PRAGMA cache_size=10000")
        _init_tables()
    return _conn

def _init_tables():
    conn = get_conn()
    c = conn.cursor()
    
    # ─── چنل‌های اجباری ──────────────────────────────────────────────────────
    c.execute("""CREATE TABLE IF NOT EXISTS forced_channels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    
    # ─── سایلنت ──────────────────────────────────────────────────────────────
    c.execute("""CREATE TABLE IF NOT EXISTS silent_chats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_id INTEGER NOT NULL,
        chat_id INTEGER NOT NULL,
        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (owner_id, chat_id)
    )""")
    
    c.execute("""CREATE TABLE IF NOT EXISTS silent_users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (owner_id, user_id)
    )""")
    
    # ─── شاخص‌ها ──────────────────────────────────────────────────────────────
    c.execute("CREATE INDEX IF NOT EXISTS idx_silent_chats_owner ON silent_chats(owner_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_silent_users_owner ON silent_users(owner_id)")
    
    conn.commit()

# ─── چنل‌های اجباری ──────────────────────────────────────────────────────────
def get_forced_channels():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT username FROM forced_channels ORDER BY added_at DESC")
    return [r["username"] for r in c.fetchall()]

def add_forced_channel(username: str) -> bool:
    if not username.startswith("@"):
        username = "@" + username
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("INSERT INTO forced_channels (username) VALUES (?)", (username,))
        conn.commit()
        return True
    except Exception:
        return False

def remove_forced_channel(username: str) -> bool:
    if not username.startswith("@"):
        username = "@" + username
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM forced_channels WHERE username = ?", (username,))
    conn.commit()
    return c.rowcount > 0

def check_user_membership(bot, user_id: int) -> tuple:
    channels = get_forced_channels()
    if not channels:
        return True, []
    missing = []
    for ch in channels:
        try:
            member = bot.get_chat_member(ch, user_id)
            if member.status not in ['member', 'administrator', 'creator']:
                missing.append(ch)
        except Exception:
            missing.append(ch)
    return len(missing) == 0, missing

# ─── سایلنت ───────────────────────────────────────────────────────────────────
def add_silent_chat(owner_id: int, chat_id: int):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO silent_chats (owner_id, chat_id) VALUES (?, ?)", 
              (owner_id, chat_id))
    conn.commit()

def remove_silent_chat(owner_id: int, chat_id: int):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM silent_chats WHERE owner_id = ? AND chat_id = ?", 
              (owner_id, chat_id))
    conn.commit()

def is_silent_chat(owner_id: int, chat_id: int) -> bool:
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT 1 FROM silent_chats WHERE owner_id = ? AND chat_id = ?", 
              (owner_id, chat_id))
    return c.fetchone() is not None

def add_silent_user(owner_id: int, user_id: int):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO silent_users (owner_id, user_id) VALUES (?, ?)", 
              (owner_id, user_id))
    conn.commit()

def remove_silent_user(owner_id: int, user_id: int):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM silent_users WHERE owner_id = ? AND user_id = ?", 
              (owner_id, user_id))
    conn.commit()

def is_silent_user(owner_id: int, user_id: int) -> bool:
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT 1 FROM silent_users WHERE owner_id = ? AND user_id = ?", 
              (owner_id, user_id))
    return c.fetchone() is not None
