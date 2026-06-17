import psycopg2
import psycopg2.extras
import psycopg2.pool
import hashlib
import threading
import time as _time
from config import DATABASE_URL


# ══════════════════════════════════════════════════════════════════════════════
# 🚀 Connection Pooling
# ══════════════════════════════════════════════════════════════════════════════
_connection_pool = None
_pool_lock = threading.Lock()


def _get_pool():
    global _connection_pool
    if _connection_pool is None:
        with _pool_lock:
            if _connection_pool is None:
                try:
                    _connection_pool = psycopg2.pool.ThreadedConnectionPool(
                        minconn=5,
                        maxconn=20,
                        dsn=DATABASE_URL,
                        connect_timeout=3,
                    )
                    print("✅ Supabase pool ایجاد شد")
                except Exception as e:
                    print(f"❌ خطا: {e}")
                    raise
    return _connection_pool


def get_conn():
    try:
        return _get_pool().getconn()
    except:
        return psycopg2.connect(DATABASE_URL, connect_timeout=3)


def release_conn(conn):
    try:
        _get_pool().putconn(conn)
    except:
        try:
            conn.close()
        except:
            pass


def _hash_pw(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


# ══════════════════════════════════════════════════════════════════════════════
# 🚀 Cache System
# ══════════════════════════════════════════════════════════════════════════════
class FastCache:
    def __init__(self, ttl=300):
        self._cache = {}
        self._timestamps = {}
        self._ttl = ttl
        self._lock = threading.Lock()
    
    def get(self, key, default=None):
        with self._lock:
            if key in self._cache:
                if _time.time() - self._timestamps[key] < self._ttl:
                    return self._cache[key]
                else:
                    del self._cache[key]
                    del self._timestamps[key]
        return default
    
    def set(self, key, value):
        with self._lock:
            self._cache[key] = value
            self._timestamps[key] = _time.time()
    
    def invalidate(self, key):
        with self._lock:
            self._cache.pop(key, None)
            self._timestamps.pop(key, None)


account_cache = FastCache(ttl=600)
balance_cache = FastCache(ttl=60)
session_cache = FastCache(ttl=3600)
list_cache = FastCache(ttl=180)  # برای دشمن و دوست


# ══════════════════════════════════════════════════════════════════════════════
# Init DB
# ══════════════════════════════════════════════════════════════════════════════
def init_db():
    conn = get_conn()
    try:
        c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Accounts
        c.execute("""CREATE TABLE IF NOT EXISTS accounts (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            telegram_user_id BIGINT UNIQUE,
            balance INTEGER DEFAULT 10,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")

        # Settings
        c.execute("""CREATE TABLE IF NOT EXISTS settings (
            owner_id BIGINT NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            PRIMARY KEY (owner_id, key)
        )""")

        # Sessions
        c.execute("""CREATE TABLE IF NOT EXISTS sessions (
            owner_id BIGINT PRIMARY KEY,
            session_data TEXT NOT NULL,
            phone TEXT,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")

        # ═══════════════════════════════════════════════════════════════════
        # 🆕 جداول جدید: دشمن، دوست، سایلنت، پیام ذخیره، زمان‌بندی
        # ═══════════════════════════════════════════════════════════════════
        
        # Enemies
        c.execute("""CREATE TABLE IF NOT EXISTS enemies (
            id SERIAL PRIMARY KEY,
            owner_id BIGINT NOT NULL,
            user_id BIGINT NOT NULL,
            username TEXT,
            name TEXT,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (owner_id, user_id)
        )""")

        # Friends
        c.execute("""CREATE TABLE IF NOT EXISTS friends (
            id SERIAL PRIMARY KEY,
            owner_id BIGINT NOT NULL,
            user_id BIGINT NOT NULL,
            username TEXT,
            name TEXT,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (owner_id, user_id)
        )""")

        # Silent Chats
        c.execute("""CREATE TABLE IF NOT EXISTS silent_chats (
            id SERIAL PRIMARY KEY,
            owner_id BIGINT NOT NULL,
            chat_id BIGINT NOT NULL,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (owner_id, chat_id)
        )""")

        # Silent Users
        c.execute("""CREATE TABLE IF NOT EXISTS silent_users (
            id SERIAL PRIMARY KEY,
            owner_id BIGINT NOT NULL,
            user_id BIGINT NOT NULL,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (owner_id, user_id)
        )""")

        # Saved Messages
        c.execute("""CREATE TABLE IF NOT EXISTS saved_messages (
            owner_id BIGINT NOT NULL,
            slot INTEGER NOT NULL,
            content TEXT,
            saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (owner_id, slot)
        )""")

        # Scheduled Messages
        c.execute("""CREATE TABLE IF NOT EXISTS scheduled_messages (
            id SERIAL PRIMARY KEY,
            owner_id BIGINT NOT NULL,
            chat_id BIGINT NOT NULL,
            message TEXT NOT NULL,
            send_at TIMESTAMP NOT NULL,
            sent INTEGER DEFAULT 0
        )""")

        # Indexes
        c.execute("CREATE INDEX IF NOT EXISTS idx_acc_tg ON accounts(telegram_user_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_acc_user ON accounts(username)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_set_owner ON settings(owner_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_sess_active ON sessions(is_active)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_enemies_owner ON enemies(owner_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_friends_owner ON friends(owner_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_silent_chats ON silent_chats(owner_id, chat_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_silent_users ON silent_users(owner_id, user_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_scheduled_pending ON scheduled_messages(owner_id, sent, send_at)")

        conn.commit()
        print("✅ Supabase آماده شد")
    finally:
        release_conn(conn)


# ══════════════════════════════════════════════════════════════════════════════
# Accounts
# ══════════════════════════════════════════════════════════════════════════════
def create_account(username: str, password: str):
    conn = get_conn()
    try:
        c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        c.execute(
            "INSERT INTO accounts (username, password_hash) VALUES (%s, %s) RETURNING id",
            (username.strip(), _hash_pw(password)),
        )
        new_id = c.fetchone()["id"]
        conn.commit()
        return new_id
    except:
        return None
    finally:
        release_conn(conn)


def verify_account(username: str, password: str):
    cache_key = f"verify:{username}:{_hash_pw(password)}"
    cached = account_cache.get(cache_key)
    if cached:
        return cached
    
    conn = get_conn()
    try:
        c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        c.execute("SELECT id FROM accounts WHERE username = %s AND password_hash = %s",
                  (username.strip(), _hash_pw(password)))
        row = c.fetchone()
        result = row["id"] if row else None
        if result:
            account_cache.set(cache_key, result)
        return result
    finally:
        release_conn(conn)


def get_account(owner_id: int):
    cache_key = f"account:{owner_id}"
    cached = account_cache.get(cache_key)
    if cached:
        return cached
    
    conn = get_conn()
    try:
        c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        c.execute("SELECT id, username, telegram_user_id, balance FROM accounts WHERE id = %s", (owner_id,))
        row = c.fetchone()
        result = dict(row) if row else None
        if result:
            account_cache.set(cache_key, result)
        return result
    finally:
        release_conn(conn)


def get_account_by_tg_id(tg_id: int):
    cache_key = f"account_tg:{tg_id}"
    cached = account_cache.get(cache_key)
    if cached:
        return cached
    
    conn = get_conn()
    try:
        c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        c.execute("SELECT id, username, balance FROM accounts WHERE telegram_user_id = %s", (tg_id,))
        row = c.fetchone()
        result = dict(row) if row else None
        if result:
            account_cache.set(cache_key, result)
        return result
    finally:
        release_conn(conn)


def get_account_by_username(username: str):
    conn = get_conn()
    try:
        c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        c.execute("SELECT id, username, balance FROM accounts WHERE username = %s", (username.strip(),))
        row = c.fetchone()
        return dict(row) if row else None
    finally:
        release_conn(conn)


def save_telegram_user_id(owner_id: int, tg_user_id: int):
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("UPDATE accounts SET telegram_user_id = %s WHERE id = %s", (tg_user_id, owner_id))
        conn.commit()
        account_cache.invalidate(f"account:{owner_id}")
    finally:
        release_conn(conn)


def get_all_accounts():
    conn = get_conn()
    try:
        c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        c.execute("SELECT id, username, balance, created_at FROM accounts ORDER BY created_at DESC")
        return [dict(r) for r in c.fetchall()]
    finally:
        release_conn(conn)


# ══════════════════════════════════════════════════════════════════════════════
# Balance
# ══════════════════════════════════════════════════════════════════════════════
def get_balance(owner_id: int) -> int:
    cache_key = f"balance:{owner_id}"
    cached = balance_cache.get(cache_key)
    if cached is not None:
        return cached
    
    conn = get_conn()
    try:
        c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        c.execute("SELECT balance FROM accounts WHERE id = %s", (owner_id,))
        row = c.fetchone()
        result = row["balance"] if row else 0
        balance_cache.set(cache_key, result)
        return result
    finally:
        release_conn(conn)


def add_balance(owner_id: int, amount: int):
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("UPDATE accounts SET balance = balance + %s WHERE id = %s", (amount, owner_id))
        conn.commit()
        balance_cache.invalidate(f"balance:{owner_id}")
    finally:
        release_conn(conn)


def deduct_balance(owner_id: int, amount: int) -> bool:
    conn = get_conn()
    try:
        c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        c.execute("SELECT balance FROM accounts WHERE id = %s", (owner_id,))
        row = c.fetchone()
        if not row or row["balance"] < amount:
            return False
        c2 = conn.cursor()
        c2.execute("UPDATE accounts SET balance = balance - %s WHERE id = %s", (amount, owner_id))
        conn.commit()
        balance_cache.invalidate(f"balance:{owner_id}")
        return True
    finally:
        release_conn(conn)


def transfer_balance(from_id: int, to_id: int, amount: int) -> tuple:
    if amount <= 0:
        return False, "❌ مقدار نامعتبر"
    
    conn = get_conn()
    try:
        c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        c.execute("SELECT balance FROM accounts WHERE id = %s", (from_id,))
        row = c.fetchone()
        if not row or row["balance"] < amount:
            return False, "❌ موجودی کافی نیست"
        
        c2 = conn.cursor()
        c2.execute("UPDATE accounts SET balance = balance - %s WHERE id = %s", (amount, from_id))
        c2.execute("UPDATE accounts SET balance = balance + %s WHERE id = %s", (amount, to_id))
        conn.commit()
        
        balance_cache.invalidate(f"balance:{from_id}")
        balance_cache.invalidate(f"balance:{to_id}")
        return True, f"✅ {amount} الماس انتقال یافت"
    except Exception as e:
        return False, f"❌ خطا: {e}"
    finally:
        release_conn(conn)


# ══════════════════════════════════════════════════════════════════════════════
# Settings
# ══════════════════════════════════════════════════════════════════════════════
SETTING_DEFAULTS = {
    "self_active": "0", "secretary": "0", "anti_delete": "0",
    "anti_link": "0", "auto_seen": "0", "auto_reaction": "0",
    "private_lock": "0", "save_media": "0", "clock_name": "0",
    "clock_bio": "0", "font": "0", "secretary_msg": "در دسترس نیستم",
    "reaction_emoji": "❤️", "last_daily": "0",
    "enemy_reply": "0", "friend_reply": "0",
}


def init_settings(owner_id: int):
    conn = get_conn()
    try:
        c = conn.cursor()
        for key, value in SETTING_DEFAULTS.items():
            c.execute(
                "INSERT INTO settings (owner_id, key, value) VALUES (%s, %s, %s) ON CONFLICT (owner_id, key) DO NOTHING",
                (owner_id, key, value),
            )
        conn.commit()
    finally:
        release_conn(conn)


def get_setting(owner_id: int, key: str, default=None):
    conn = get_conn()
    try:
        c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        c.execute("SELECT value FROM settings WHERE owner_id = %s AND key = %s", (owner_id, key))
        row = c.fetchone()
        return row["value"] if row else SETTING_DEFAULTS.get(key, default)
    finally:
        release_conn(conn)


def set_setting(owner_id: int, key: str, value):
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("""INSERT INTO settings (owner_id, key, value) VALUES (%s, %s, %s)
                     ON CONFLICT (owner_id, key) DO UPDATE SET value = EXCLUDED.value""",
                  (owner_id, key, str(value)))
        conn.commit()
    finally:
        release_conn(conn)


# ══════════════════════════════════════════════════════════════════════════════
# Sessions
# ══════════════════════════════════════════════════════════════════════════════
def save_session(owner_id: int, session_data: str, phone: str = None):
    cache_key = f"session:{owner_id}"
    
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("""INSERT INTO sessions (owner_id, session_data, phone, is_active, updated_at)
                     VALUES (%s, %s, %s, TRUE, CURRENT_TIMESTAMP)
                     ON CONFLICT (owner_id) 
                     DO UPDATE SET session_data = EXCLUDED.session_data, 
                                   phone = EXCLUDED.phone,
                                   is_active = TRUE,
                                   updated_at = CURRENT_TIMESTAMP""",
                  (owner_id, session_data, phone))
        conn.commit()
        session_cache.set(cache_key, session_data)
        return True
    except Exception as e:
        print(f"❌ خطا در ذخیره سشن: {e}")
        return False
    finally:
        release_conn(conn)


def get_session(owner_id: int) -> str:
    cache_key = f"session:{owner_id}"
    
    cached = session_cache.get(cache_key)
    if cached:
        return cached
    
    conn = get_conn()
    try:
        c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        c.execute("SELECT session_data FROM sessions WHERE owner_id = %s AND is_active = TRUE", (owner_id,))
        row = c.fetchone()
        
        if row:
            session_data = row["session_data"]
            session_cache.set(cache_key, session_data)
            return session_data
        return None
    finally:
        release_conn(conn)


def delete_session(owner_id: int):
    cache_key = f"session:{owner_id}"
    
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("UPDATE sessions SET is_active = FALSE WHERE owner_id = %s", (owner_id,))
        conn.commit()
        session_cache.invalidate(cache_key)
        return True
    except Exception as e:
        print(f"❌ خطا در حذف سشن: {e}")
        return False
    finally:
        release_conn(conn)


def get_all_active_sessions():
    conn = get_conn()
    try:
        c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        c.execute("""SELECT s.owner_id, s.session_data, s.phone, a.username
                     FROM sessions s
                     JOIN accounts a ON s.owner_id = a.id
                     WHERE s.is_active = TRUE
                     ORDER BY s.updated_at DESC""")
        return [dict(r) for r in c.fetchall()]
    finally:
        release_conn(conn)


def is_session_active(owner_id: int) -> bool:
    cache_key = f"session:{owner_id}"
    
    cached = session_cache.get(cache_key)
    if cached:
        return True
    
    conn = get_conn()
    try:
        c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        c.execute("SELECT 1 FROM sessions WHERE owner_id = %s AND is_active = TRUE", (owner_id,))
        return c.fetchone() is not None
    finally:
        release_conn(conn)


# ══════════════════════════════════════════════════════════════════════════════
# 🆕 دشمن
# ══════════════════════════════════════════════════════════════════════════════
def add_enemy(owner_id: int, user_id: int, username=None, name=None):
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("""INSERT INTO enemies (owner_id, user_id, username, name) VALUES (%s, %s, %s, %s)
                     ON CONFLICT (owner_id, user_id) DO UPDATE SET username=EXCLUDED.username, name=EXCLUDED.name""",
                  (owner_id, user_id, username, name))
        conn.commit()
        list_cache.invalidate(f"enemies:{owner_id}")
        return True
    except Exception:
        return False
    finally:
        release_conn(conn)


def remove_enemy(owner_id: int, user_id: int):
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("DELETE FROM enemies WHERE owner_id = %s AND user_id = %s", (owner_id, user_id))
        affected = c.rowcount
        conn.commit()
        if affected > 0:
            list_cache.invalidate(f"enemies:{owner_id}")
        return affected > 0
    finally:
        release_conn(conn)


def get_enemies(owner_id: int):
    cache_key = f"enemies:{owner_id}"
    cached = list_cache.get(cache_key)
    if cached is not None:
        return cached
    
    conn = get_conn()
    try:
        c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        c.execute("SELECT * FROM enemies WHERE owner_id = %s ORDER BY added_at DESC", (owner_id,))
        rows = [dict(r) for r in c.fetchall()]
        list_cache.set(cache_key, rows)
        return rows
    finally:
        release_conn(conn)


def is_enemy(owner_id: int, user_id: int):
    enemies = get_enemies(owner_id)
    return any(e["user_id"] == user_id for e in enemies)


def clear_enemies(owner_id: int):
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("DELETE FROM enemies WHERE owner_id = %s", (owner_id,))
        conn.commit()
        list_cache.invalidate(f"enemies:{owner_id}")
    finally:
        release_conn(conn)


# ══════════════════════════════════════════════════════════════════════════════
# 🆕 دوست
# ══════════════════════════════════════════════════════════════════════════════
def add_friend(owner_id: int, user_id: int, username=None, name=None):
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("""INSERT INTO friends (owner_id, user_id, username, name) VALUES (%s, %s, %s, %s)
                     ON CONFLICT (owner_id, user_id) DO UPDATE SET username=EXCLUDED.username, name=EXCLUDED.name""",
                  (owner_id, user_id, username, name))
        conn.commit()
        list_cache.invalidate(f"friends:{owner_id}")
        return True
    except Exception:
        return False
    finally:
        release_conn(conn)


def remove_friend(owner_id: int, user_id: int):
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("DELETE FROM friends WHERE owner_id = %s AND user_id = %s", (owner_id, user_id))
        affected = c.rowcount
        conn.commit()
        if affected > 0:
            list_cache.invalidate(f"friends:{owner_id}")
        return affected > 0
    finally:
        release_conn(conn)


def get_friends(owner_id: int):
    cache_key = f"friends:{owner_id}"
    cached = list_cache.get(cache_key)
    if cached is not None:
        return cached
    
    conn = get_conn()
    try:
        c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        c.execute("SELECT * FROM friends WHERE owner_id = %s ORDER BY added_at DESC", (owner_id,))
        rows = [dict(r) for r in c.fetchall()]
        list_cache.set(cache_key, rows)
        return rows
    finally:
        release_conn(conn)


def is_friend(owner_id: int, user_id: int):
    friends = get_friends(owner_id)
    return any(f["user_id"] == user_id for f in friends)


def clear_friends(owner_id: int):
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("DELETE FROM friends WHERE owner_id = %s", (owner_id,))
        conn.commit()
        list_cache.invalidate(f"friends:{owner_id}")
    finally:
        release_conn(conn)


# ══════════════════════════════════════════════════════════════════════════════
# 🆕 سایلنت
# ══════════════════════════════════════════════════════════════════════════════
def add_silent_chat(owner_id: int, chat_id: int):
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("INSERT INTO silent_chats (owner_id, chat_id) VALUES (%s, %s) ON CONFLICT (owner_id, chat_id) DO NOTHING",
                  (owner_id, chat_id))
        conn.commit()
    finally:
        release_conn(conn)


def remove_silent_chat(owner_id: int, chat_id: int):
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("DELETE FROM silent_chats WHERE owner_id = %s AND chat_id = %s", (owner_id, chat_id))
        conn.commit()
    finally:
        release_conn(conn)


def is_silent_chat(owner_id: int, chat_id: int):
    conn = get_conn()
    try:
        c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        c.execute("SELECT 1 FROM silent_chats WHERE owner_id = %s AND chat_id = %s", (owner_id, chat_id))
        return c.fetchone() is not None
    finally:
        release_conn(conn)


def add_silent_user(owner_id: int, user_id: int):
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("INSERT INTO silent_users (owner_id, user_id) VALUES (%s, %s) ON CONFLICT (owner_id, user_id) DO NOTHING",
                  (owner_id, user_id))
        conn.commit()
    finally:
        release_conn(conn)


def remove_silent_user(owner_id: int, user_id: int):
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("DELETE FROM silent_users WHERE owner_id = %s AND user_id = %s", (owner_id, user_id))
        conn.commit()
    finally:
        release_conn(conn)


def is_silent_user(owner_id: int, user_id: int):
    conn = get_conn()
    try:
        c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        c.execute("SELECT 1 FROM silent_users WHERE owner_id = %s AND user_id = %s", (owner_id, user_id))
        return c.fetchone() is not None
    finally:
        release_conn(conn)


# ══════════════════════════════════════════════════════════════════════════════
# 🆕 پیام‌های ذخیره‌شده
# ══════════════════════════════════════════════════════════════════════════════
def save_message_slot(owner_id: int, slot: int, content: str):
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("""INSERT INTO saved_messages (owner_id, slot, content) VALUES (%s, %s, %s)
                     ON CONFLICT (owner_id, slot) DO UPDATE SET content=EXCLUDED.content""",
                  (owner_id, slot, content))
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        release_conn(conn)


def get_message_slot(owner_id: int, slot: int):
    conn = get_conn()
    try:
        c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        c.execute("SELECT * FROM saved_messages WHERE owner_id = %s AND slot = %s", (owner_id, slot))
        row = c.fetchone()
        return dict(row) if row else None
    finally:
        release_conn(conn)


# ══════════════════════════════════════════════════════════════════════════════
# 🆕 پیام‌های زمان‌بندی‌شده
# ══════════════════════════════════════════════════════════════════════════════
def add_scheduled_message(owner_id: int, chat_id: int, message: str, send_at: str):
    conn = get_conn()
    try:
        c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        c.execute("""INSERT INTO scheduled_messages (owner_id, chat_id, message, send_at)
                     VALUES (%s, %s, %s, %s) RETURNING id""",
                  (owner_id, chat_id, message, send_at))
        last_id = c.fetchone()["id"]
        conn.commit()
        return last_id
    finally:
        release_conn(conn)


def get_pending_scheduled(owner_id: int):
    conn = get_conn()
    try:
        c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        c.execute("""SELECT * FROM scheduled_messages 
                     WHERE owner_id = %s AND sent = 0 AND send_at <= CURRENT_TIMESTAMP 
                     ORDER BY send_at""", (owner_id,))
        return [dict(r) for r in c.fetchall()]
    finally:
        release_conn(conn)


def mark_scheduled_sent(msg_id: int):
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("UPDATE scheduled_messages SET sent = 1 WHERE id = %s", (msg_id,))
        conn.commit()
    finally:
        release_conn(conn)
