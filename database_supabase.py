def init_db():
    conn = get_conn()
    try:
        c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # ─── جدول accounts (اگر قبلاً ساخته شده، ستون balance اضافه می‌شود) ───
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

        # ─── جدول friends ──────────────────────────────────────────────────
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

        # ─── جدول saved_messages ─────────────────────────────────────────
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

        # ─── جدول lotteries ───────────────────────────────────────────────
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

        # ─── جدول diamond_transactions ───────────────────────────────────
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

        # ─── Index‌ها ────────────────────────────────────────────────────
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
