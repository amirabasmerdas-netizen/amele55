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
list_cache = FastCache(ttl=180)


# ══════════════════════════════════════════════════════════════════════════════
# Init DB - با ALTER TABLE برای ستون‌های جدید
# ══════════════════════════════════════════════════════════════════════════════
def init_db():
    conn = get_conn()
    try:
        c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # ─── جدول accounts ──────────────────────────────────────────────────
        c.execute("""CREATE TABLE IF NOT EXISTS accounts (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            telegram_user_id BIGINT UNIQUE,
            balance INTEGER DEFAULT 10,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")

        # ✅ اضافه کردن ستون balance اگر جدول قبلاً وجود داشت
        try:
            c.execute("""ALTER TABLE accounts 
                         ADD COLUMN IF NOT EXISTS balance INTEGER DEFAULT 10""")
            conn.commit()
        except Exception:
            conn.rollback()

        # ─── جدول settings ──────────────────────────────────────────────────
        c.execute("""CREATE TABLE IF NOT EXISTS settings (
            owner_id BIGINT NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            PRIMARY KEY (owner_id, key)
        )""")

        # ─── جدول sessions ──────────────────────────────────────────────────
        c.execute("""CREATE TABLE IF NOT EXISTS sessions (
            owner_id BIGINT PRIMARY KEY,
            session_data TEXT NOT NULL,
            phone TEXT,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")

        # ─── جدول enemies ──────────────────────────────────────────────────
        c.execute("""CREATE TABLE IF NOT EXISTS enemies (
            id SERIAL PRIMARY KEY,
            owner_id BIGINT NOT NULL,
            user_id BIGINT NOT NULL,
            username TEXT,
            name TEXT,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (owner_id, user_id)
        )""")

        # ── جدول friends ──────────────────────────────────────────────────
        c.execute("""CREATE TABLE IF NOT EXISTS friends (
            id SERIAL PRIMARY KEY,
            owner_id BIGINT NOT NULL,
            user_id BIGINT NOT NULL,
            username TEXT,
            name TEXT,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (owner_id, user_id)
        )""")

        # ─── جدول silent_chats ────────────────────────────────────────────
        c.execute("""CREATE TABLE IF NOT EXISTS silent_chats (
            id SERIAL PRIMARY KEY,
            owner_id BIGINT NOT NULL,
            chat_id BIGINT NOT NULL,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (owner_id, chat_id)
        )""")

        # ─── جدول silent_users ────────────────────────────────────────────
        c.execute("""CREATE TABLE IF NOT EXISTS silent_users (
            id SERIAL PRIMARY KEY,
            owner_id BIGINT NOT NULL,
            user_id BIGINT NOT NULL,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (owner_id, user_id)
        )""")

        # ── جدول saved_messages ─────────────────────────────────────────
        c.execute("""CREATE TABLE IF NOT EXISTS saved_messages (
            owner_id BIGINT NOT NULL,
            slot INTEGER NOT NULL,
            content TEXT,
            saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (owner_id, slot)
        )""")

        # ─── جدول scheduled_messages ──────────────────────────────────────
        c.execute("""CREATE TABLE IF NOT EXISTS scheduled_messages (
            id SERIAL PRIMARY KEY,
            owner_id BIGINT NOT NULL,
            chat_id BIGINT NOT NULL,
            message TEXT NOT NULL,
            send_at TIMESTAMP NOT NULL,
            sent INTEGER DEFAULT 0
        )""")

        # ─── جدول forced_channels ─────────────────────────────────────────
        c.execute("""CREATE TABLE IF NOT EXISTS forced_channels (
            id SERIAL PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")

        # ── جدول lotteries ───────────────────────────────────────────────
        c.execute("""CREATE TABLE IF NOT EXISTS lotteries (
            id SERIAL PRIMARY KEY,
            chat_id BIGINT NOT NULL,
            creator_tg_id BIGINT NOT NULL,
            prize_amount INTEGER NOT NULL,
            entry_fee INTEGER DEFAULT 1,
            end_time TIMESTAMP NOT NULL,
            winner_tg_id BIGINT DEFAULT NULL,
            status TEXT DEFAULT 'active',
            message_id BIGINT DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")

        # ─── جدول lottery_participants ───────────────────────────────────
        c.execute("""CREATE TABLE IF NOT EXISTS lottery_participants (
            id SERIAL PRIMARY KEY,
            lottery_id BIGINT NOT NULL,
            user_tg_id BIGINT NOT NULL,
            owner_id BIGINT NOT NULL,
            bet_amount INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (lottery_id, user_tg_id)
        )""")

        # ─── جدول world_cup_challenges ───────────────────────────────────
        c.execute("""CREATE TABLE IF NOT EXISTS world_cup_challenges (
            id SERIAL PRIMARY KEY,
            team1 TEXT NOT NULL,
            team2 TEXT NOT NULL,
            match_time TEXT NOT NULL,
            bet_amount INTEGER NOT NULL,
            winner_team TEXT DEFAULT NULL,
            status TEXT DEFAULT 'active',
            message_id BIGINT DEFAULT NULL,
            chat_id BIGINT DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")

        # ─── جدول world_cup_bets ─────────────────────────────────────────
        c.execute("""CREATE TABLE IF NOT EXISTS world_cup_bets (
            id SERIAL PRIMARY KEY,
            challenge_id BIGINT NOT NULL,
            user_tg_id BIGINT NOT NULL,
            owner_id BIGINT NOT NULL,
            team_choice TEXT NOT NULL,
            bet_amount INTEGER NOT NULL,
            result TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (challenge_id, user_tg_id)
        )""")

        # ─── جدول diamond_transactions ──────────────────────────────────
        c.execute("""CREATE TABLE IF NOT EXISTS diamond_transactions (
            id SERIAL PRIMARY KEY,
            from_owner_id BIGINT NOT NULL,
            to_owner_id BIGINT NOT NULL,
            amount INTEGER NOT NULL,
            type TEXT NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")

        # ── جدول referrals ──────────────────────────────────────────────
        c.execute("""CREATE TABLE IF NOT EXISTS referrals (
            id SERIAL PRIMARY KEY,
            referrer_owner_id BIGINT NOT NULL,
            referred_tg_id BIGINT NOT NULL UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")

        # ── Index‌ها ────────────────────────────────────────────────────
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_acc_tg ON accounts(telegram_user_id)",
            "CREATE INDEX IF NOT EXISTS idx_acc_user ON accounts(username)",
            "CREATE INDEX IF NOT EXISTS idx_set_owner ON settings(owner_id)",
            "CREATE INDEX IF NOT EXISTS idx_sess_active ON sessions(is_active)",
            "CREATE INDEX IF NOT EXISTS idx_enemies_owner ON enemies(owner_id)",
            "CREATE INDEX IF NOT EXISTS idx_friends_owner ON friends(owner_id)",
            "CREATE INDEX IF NOT EXISTS idx_silent_chats ON silent_chats(owner_id, chat_id)",
            "CREATE INDEX IF NOT EXISTS idx_silent_users ON silent_users(owner_id, user_id)",
            "CREATE INDEX IF NOT EXISTS idx_scheduled_pending ON scheduled_messages(owner_id, sent, send_at)",
            "CREATE INDEX IF NOT EXISTS idx_lot_status ON lotteries(status)",
            "CREATE INDEX IF NOT EXISTS idx_wc_status ON world_cup_challenges(status)",
            "CREATE INDEX IF NOT EXISTS idx_referrals_ref ON referrals(referrer_owner_id)",
        ]
        
        for idx_sql in indexes:
            try:
                c.execute(idx_sql)
            except Exception:
                pass

        conn.commit()
        print("✅ Supabase آماده شد")
    except Exception as e:
        print(f"❌ خطا در init_db: {e}")
        conn.rollback()
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
        return False, f" خطا: {e}"
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
    "logged_in": "0", "session_data": "",
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
# Enemies
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
# Friends
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
# Silent
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
# Saved Messages
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
# Scheduled Messages
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


# ══════════════════════════════════════════════════════════════════════════════
# Forced Channels
# ═════════════════════════════════════════════════════════════════════════════
def get_forced_channels():
    conn = get_conn()
    try:
        c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        c.execute("SELECT username FROM forced_channels ORDER BY added_at DESC")
        return [r["username"] for r in c.fetchall()]
    finally:
        release_conn(conn)


def add_forced_channel(username: str) -> bool:
    if not username.startswith("@"):
        username = "@" + username
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("INSERT INTO forced_channels (username) VALUES (%s)", (username,))
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        release_conn(conn)


def remove_forced_channel(username: str) -> bool:
    if not username.startswith("@"):
        username = "@" + username
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("DELETE FROM forced_channels WHERE username = %s", (username,))
        affected = c.rowcount
        conn.commit()
        return affected > 0
    finally:
        release_conn(conn)


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


# ══════════════════════════════════════════════════════════════════════════════
# Lotteries
# ══════════════════════════════════════════════════════════════════════════════
def create_lottery(chat_id: int, creator_tg_id: int, prize_amount: int, duration_minutes: int, entry_fee: int = 1):
    import datetime
    conn = get_conn()
    try:
        c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        end_time = datetime.datetime.now() + datetime.timedelta(minutes=duration_minutes)
        c.execute("""INSERT INTO lotteries (chat_id, creator_tg_id, prize_amount, entry_fee, end_time, status)
                     VALUES (%s, %s, %s, %s, %s, 'active') RETURNING id""",
                  (chat_id, creator_tg_id, prize_amount, entry_fee, end_time.isoformat()))
        lottery_id = c.fetchone()["id"]
        conn.commit()
        return lottery_id
    finally:
        release_conn(conn)


def update_lottery_message(lottery_id: int, message_id: int):
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("UPDATE lotteries SET message_id = %s WHERE id = %s", (message_id, lottery_id))
        conn.commit()
    finally:
        release_conn(conn)


def get_active_lotteries():
    conn = get_conn()
    try:
        c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        c.execute("SELECT * FROM lotteries WHERE status = 'active' ORDER BY created_at DESC")
        return [dict(r) for r in c.fetchall()]
    finally:
        release_conn(conn)


def get_lottery(lottery_id: int):
    conn = get_conn()
    try:
        c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        c.execute("SELECT * FROM lotteries WHERE id = %s", (lottery_id,))
        row = c.fetchone()
        return dict(row) if row else None
    finally:
        release_conn(conn)


def join_lottery(lottery_id: int, user_tg_id: int, owner_id: int, entry_fee: int = None) -> tuple:
    conn = get_conn()
    try:
        c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        if entry_fee is None:
            c.execute("SELECT entry_fee FROM lotteries WHERE id = %s AND status = 'active'", (lottery_id,))
            lottery_row = c.fetchone()
            if not lottery_row:
                return False, "❌ قرعه‌کشی فعال نیست یا یافت نشد."
            entry_fee = lottery_row["entry_fee"]
        
        c.execute("SELECT balance FROM accounts WHERE id = %s", (owner_id,))
        row = c.fetchone()
        if not row or row["balance"] < entry_fee:
            return False, f"❌ موجودی کافی ندارید. موجودی: {row['balance'] if row else 0} الماس | هزینه: {entry_fee} الماس"
        
        c.execute("SELECT 1 FROM lottery_participants WHERE lottery_id = %s AND user_tg_id = %s",
                  (lottery_id, user_tg_id))
        if c.fetchone():
            return False, "❌ شما قبلاً در این قرعه‌کشی شرکت کرده‌اید."
        
        c_upd = conn.cursor()
        c_upd.execute("UPDATE accounts SET balance = balance - %s WHERE id = %s", (entry_fee, owner_id))
        c_upd.execute("""INSERT INTO lottery_participants (lottery_id, user_tg_id, owner_id, bet_amount)
                         VALUES (%s, %s, %s, %s)""",
                      (lottery_id, user_tg_id, owner_id, entry_fee))
        
        conn.commit()
        balance_cache.invalidate(f"balance:{owner_id}")
        return True, f"✅ با {entry_fee} الماس در قرعه‌کشی شرکت کردید."
    except Exception as e:
        return False, f"❌ خطا: {str(e)}"
    finally:
        release_conn(conn)


def get_lottery_participants(lottery_id: int):
    conn = get_conn()
    try:
        c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        c.execute("SELECT * FROM lottery_participants WHERE lottery_id = %s", (lottery_id,))
        return [dict(r) for r in c.fetchall()]
    finally:
        release_conn(conn)


def finish_lottery(lottery_id: int, winner_tg_id: int, winner_owner_id: int):
    conn = get_conn()
    try:
        c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        c.execute("SELECT * FROM lottery_participants WHERE lottery_id = %s", (lottery_id,))
        participants = c.fetchall()
        
        total_prize = sum(p["bet_amount"] for p in participants)
        
        c_upd = conn.cursor()
        c_upd.execute("UPDATE accounts SET balance = balance + %s WHERE id = %s",
                      (total_prize, winner_owner_id))
        c_upd.execute("UPDATE lotteries SET winner_tg_id = %s, status = 'finished' WHERE id = %s",
                      (winner_tg_id, lottery_id))
        
        conn.commit()
        balance_cache.invalidate(f"balance:{winner_owner_id}")
        return True, total_prize
    except Exception as e:
        return False, str(e)
    finally:
        release_conn(conn)


# ══════════════════════════════════════════════════════════════════════════════
# World Cup Challenges
# ══════════════════════════════════════════════════════════════════════════════
def create_world_cup_challenge(team1: str, team2: str, match_time: str, bet_amount: int):
    conn = get_conn()
    try:
        c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        c.execute("""INSERT INTO world_cup_challenges (team1, team2, match_time, bet_amount, status)
                     VALUES (%s, %s, %s, %s, 'active') RETURNING id""",
                  (team1, team2, match_time, bet_amount))
        challenge_id = c.fetchone()["id"]
        conn.commit()
        return challenge_id
    finally:
        release_conn(conn)


def update_challenge_message(challenge_id: int, message_id: int, chat_id: int):
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("UPDATE world_cup_challenges SET message_id = %s, chat_id = %s WHERE id = %s",
                  (message_id, chat_id, challenge_id))
        conn.commit()
    finally:
        release_conn(conn)


def get_active_challenges():
    conn = get_conn()
    try:
        c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        c.execute("SELECT * FROM world_cup_challenges WHERE status = 'active' ORDER BY created_at DESC")
        return [dict(r) for r in c.fetchall()]
    finally:
        release_conn(conn)


def get_challenge(challenge_id: int):
    conn = get_conn()
    try:
        c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        c.execute("SELECT * FROM world_cup_challenges WHERE id = %s", (challenge_id,))
        row = c.fetchone()
        return dict(row) if row else None
    finally:
        release_conn(conn)


def place_bet(challenge_id: int, user_tg_id: int, owner_id: int, team_choice: str, bet_amount: int) -> tuple:
    conn = get_conn()
    try:
        c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        c.execute("SELECT balance FROM accounts WHERE id = %s", (owner_id,))
        row = c.fetchone()
        if not row or row["balance"] < bet_amount:
            return False, f"❌ موجودی کافی ندارید. موجودی: {row['balance'] if row else 0} الماس"
        
        c.execute("SELECT 1 FROM world_cup_bets WHERE challenge_id = %s AND user_tg_id = %s",
                  (challenge_id, user_tg_id))
        if c.fetchone():
            return False, "❌ شما قبلاً در این چالش شرکت کرده‌اید."
        
        c_upd = conn.cursor()
        c_upd.execute("UPDATE accounts SET balance = balance - %s WHERE id = %s", (bet_amount, owner_id))
        c_upd.execute("""INSERT INTO world_cup_bets (challenge_id, user_tg_id, owner_id, team_choice, bet_amount)
                         VALUES (%s, %s, %s, %s, %s)""",
                      (challenge_id, user_tg_id, owner_id, team_choice, bet_amount))
        
        conn.commit()
        balance_cache.invalidate(f"balance:{owner_id}")
        return True, f"✅ شرط {bet_amount} الماس روی {team_choice} ثبت شد."
    except Exception as e:
        return False, f" خطا: {str(e)}"
    finally:
        release_conn(conn)


def get_challenge_bets(challenge_id: int):
    conn = get_conn()
    try:
        c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        c.execute("SELECT * FROM world_cup_bets WHERE challenge_id = %s", (challenge_id,))
        return [dict(r) for r in c.fetchall()]
    finally:
        release_conn(conn)


def set_challenge_winner(challenge_id: int, winner_team: str):
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("UPDATE world_cup_challenges SET winner_team = %s, status = 'finished' WHERE id = %s",
                  (winner_team, challenge_id))
        conn.commit()
    finally:
        release_conn(conn)


def settle_challenge_bets(challenge_id: int):
    challenge = get_challenge(challenge_id)
    if not challenge or not challenge["winner_team"]:
        return False, "❌ چالش یافت نشد یا برنده مشخص نشده."
    
    bets = get_challenge_bets(challenge_id)
    results = []
    
    conn = get_conn()
    try:
        c = conn.cursor()
        for bet in bets:
            if bet["team_choice"] == challenge["winner_team"]:
                winnings = bet["bet_amount"] * 2
                c.execute("UPDATE accounts SET balance = balance + %s WHERE id = %s",
                          (winnings, bet["owner_id"]))
                c.execute("UPDATE world_cup_bets SET result = 'won' WHERE id = %s", (bet["id"],))
                results.append({"user_tg_id": bet["user_tg_id"], "owner_id": bet["owner_id"],
                                "result": "won", "amount": winnings})
            else:
                c.execute("UPDATE world_cup_bets SET result = 'lost' WHERE id = %s", (bet["id"],))
                results.append({"user_tg_id": bet["user_tg_id"], "owner_id": bet["owner_id"],
                                "result": "lost", "amount": bet["bet_amount"]})
        
        conn.commit()
        for r in results:
            balance_cache.invalidate(f"balance:{r['owner_id']}")
        return True, results
    except Exception as e:
        return False, str(e)
    finally:
        release_conn(conn)


# ══════════════════════════════════════════════════════════════════════════════
# Referrals
# ══════════════════════════════════════════════════════════════════════════════
def process_referral(referrer_owner_id: int, referred_tg_id: int) -> bool:
    from config import REFERRAL_TOKENS
    conn = get_conn()
    try:
        c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        c.execute("SELECT 1 FROM referrals WHERE referred_tg_id = %s", (referred_tg_id,))
        if c.fetchone():
            return False
        c.execute("SELECT 1 FROM accounts WHERE id = %s", (referrer_owner_id,))
        if not c.fetchone():
            return False
        
        c_ins = conn.cursor()
        c_ins.execute("INSERT INTO referrals (referrer_owner_id, referred_tg_id) VALUES (%s, %s)",
                      (referrer_owner_id, referred_tg_id))
        c_ins.execute("UPDATE accounts SET balance = balance + %s WHERE id = %s",
                      (REFERRAL_TOKENS, referrer_owner_id))
        conn.commit()
        balance_cache.invalidate(f"balance:{referrer_owner_id}")
        return True
    except Exception:
        return False
    finally:
        release_conn(conn)


def get_referral_count(owner_id: int) -> int:
    conn = get_conn()
    try:
        c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        c.execute("SELECT COUNT(*) as cnt FROM referrals WHERE referrer_owner_id = %s", (owner_id,))
        row = c.fetchone()
        return row["cnt"] if row else 0
    finally:
        release_conn(conn)


# ══════════════════════════════════════════════════════════════════════════════
# Token Stats (برای سازگاری با کد قدیمی)
# ══════════════════════════════════════════════════════════════════════════════
def get_token_balance(owner_id: int) -> int:
    return get_balance(owner_id)


def add_tokens(owner_id: int, amount: int):
    add_balance(owner_id, amount)


def deduct_tokens(owner_id: int, amount: int) -> bool:
    return deduct_balance(owner_id, amount)


def get_token_stats(owner_id: int) -> dict:
    balance = get_balance(owner_id)
    return {
        "balance": balance,
        "last_daily": get_setting(owner_id, "last_daily", "0"),
        "total_earned": balance,
        "can_claim_daily": True,
    }


def claim_daily_token(owner_id: int):
    from config import DAILY_GIFT
    last = get_setting(owner_id, "last_daily", "0")
    now = int(_time.time())
    
    if now - int(last) > 86400:
        add_balance(owner_id, DAILY_GIFT)
        set_setting(owner_id, "last_daily", str(now))
        return True, f"🎁 {DAILY_GIFT} الماس روزانه دریافت کردید!"
    else:
        remaining = 86400 - (now - int(last))
        hours = remaining // 3600
        return False, f"⏰ {hours} ساعت دیگر می‌توانید هدیه دریافت کنید"


def transfer_diamonds(from_owner_id: int, to_owner_id: int, amount: int) -> tuple:
    return transfer_balance(from_owner_id, to_owner_id, amount)
