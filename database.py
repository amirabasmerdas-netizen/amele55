import psycopg2
import psycopg2.extras
import hashlib
import os
import datetime
from config import DATABASE_URL


def get_conn():
    """اتصال به Supabase PostgreSQL"""
    conn = psycopg2.connect(DATABASE_URL)
    return conn


def _hash_pw(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def init_db():
    conn = get_conn()
    c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # ─── حساب‌های پنل ────────────────────────────────────────────────────────
    c.execute("""CREATE TABLE IF NOT EXISTS accounts (
        id SERIAL PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        telegram_user_id BIGINT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    # ─── چنل‌های اجباری ──────────────────────────────────────────────────────
    c.execute("""CREATE TABLE IF NOT EXISTS forced_channels (
        id SERIAL PRIMARY KEY,
        username TEXT NOT NULL UNIQUE,
        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    # ─── تنظیمات (per-user) ───────────────────────────────────────────────────
    c.execute("""CREATE TABLE IF NOT EXISTS settings (
        owner_id BIGINT NOT NULL,
        key TEXT NOT NULL,
        value TEXT NOT NULL,
        PRIMARY KEY (owner_id, key)
    )""")

    # ── دشمن ─────────────────────────────────────────────────────────────────
    c.execute("""CREATE TABLE IF NOT EXISTS enemies (
        id SERIAL PRIMARY KEY,
        owner_id BIGINT NOT NULL,
        user_id BIGINT NOT NULL,
        username TEXT,
        name TEXT,
        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (owner_id, user_id)
    )""")

    # ─── دوست ─────────────────────────────────────────────────────────────────
    c.execute("""CREATE TABLE IF NOT EXISTS friends (
        id SERIAL PRIMARY KEY,
        owner_id BIGINT NOT NULL,
        user_id BIGINT NOT NULL,
        username TEXT,
        name TEXT,
        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (owner_id, user_id)
    )""")

    # ─── سایلنت چت ────────────────────────────────────────────────────────────
    c.execute("""CREATE TABLE IF NOT EXISTS silent_chats (
        id SERIAL PRIMARY KEY,
        owner_id BIGINT NOT NULL,
        chat_id BIGINT NOT NULL,
        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (owner_id, chat_id)
    )""")

    # ─── سایلنت کاربر ─────────────────────────────────────────────────────────
    c.execute("""CREATE TABLE IF NOT EXISTS silent_users (
        id SERIAL PRIMARY KEY,
        owner_id BIGINT NOT NULL,
        user_id BIGINT NOT NULL,
        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (owner_id, user_id)
    )""")

    # ─── پیام‌های ذخیره‌شده ────────────────────────────────────────────────────
    c.execute("""CREATE TABLE IF NOT EXISTS saved_messages (
        owner_id BIGINT NOT NULL,
        slot INTEGER NOT NULL,
        content TEXT,
        media_path TEXT,
        saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (owner_id, slot)
    )""")

    # ─── پیام‌های حذف‌شده ─────────────────────────────────────────────────────
    c.execute("""CREATE TABLE IF NOT EXISTS deleted_messages (
        id SERIAL PRIMARY KEY,
        owner_id BIGINT NOT NULL,
        chat_id BIGINT,
        sender_id BIGINT,
        sender_name TEXT,
        message TEXT,
        media_type TEXT,
        deleted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    # ── پیام‌های زمان‌بندی‌شده ───────────────────────────────────────────────
    c.execute("""CREATE TABLE IF NOT EXISTS scheduled_messages (
        id SERIAL PRIMARY KEY,
        owner_id BIGINT NOT NULL,
        chat_id BIGINT NOT NULL,
        message TEXT NOT NULL,
        send_at TIMESTAMP NOT NULL,
        sent INTEGER DEFAULT 0
    )""")

    # ─── الماس‌ها ─────────────────────────────────────────────────────────────
    c.execute("""CREATE TABLE IF NOT EXISTS tokens (
        owner_id BIGINT PRIMARY KEY,
        balance INTEGER DEFAULT 0,
        last_daily TEXT DEFAULT NULL,
        total_earned INTEGER DEFAULT 0
    )""")

    # ─── رفرال‌ها ──────────────────────────────────────────────────────────────
    c.execute("""CREATE TABLE IF NOT EXISTS referrals (
        id SERIAL PRIMARY KEY,
        referrer_owner_id BIGINT NOT NULL,
        referred_tg_id BIGINT NOT NULL UNIQUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    # ── چالش‌های جام جهانی ──────────────────────────────────────────────────
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

    # ─── قرعه‌کشی‌ها ─────────────────────────────────────────────────────────
    c.execute("""CREATE TABLE IF NOT EXISTS lotteries (
        id SERIAL PRIMARY KEY,
        chat_id BIGINT NOT NULL,
        creator_tg_id BIGINT NOT NULL,
        prize_amount INTEGER NOT NULL,
        end_time TIMESTAMP NOT NULL,
        winner_tg_id BIGINT DEFAULT NULL,
        status TEXT DEFAULT 'active',
        message_id BIGINT DEFAULT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS lottery_participants (
        id SERIAL PRIMARY KEY,
        lottery_id BIGINT NOT NULL,
        user_tg_id BIGINT NOT NULL,
        owner_id BIGINT NOT NULL,
        bet_amount INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (lottery_id, user_tg_id)
    )""")

    # ── تراکنش‌های الماس ────────────────────────────────────────────────────
    c.execute("""CREATE TABLE IF NOT EXISTS diamond_transactions (
        id SERIAL PRIMARY KEY,
        from_owner_id BIGINT NOT NULL,
        to_owner_id BIGINT NOT NULL,
        amount INTEGER NOT NULL,
        type TEXT NOT NULL,
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    conn.commit()
    conn.close()
