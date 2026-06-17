import sqlite3
import threading
import datetime
from config import RENDER_DB_PATH


_lock = threading.Lock()


def get_conn():
    conn = sqlite3.connect(RENDER_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    try:
        c = conn.cursor()
        
        # Lotteries
        c.execute("""CREATE TABLE IF NOT EXISTS lotteries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT NOT NULL,
            creator_id INTEGER NOT NULL,
            prize INTEGER NOT NULL,
            entry_fee INTEGER DEFAULT 1,
            end_time TIMESTAMP NOT NULL,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        
        # Lottery Participants
        c.execute("""CREATE TABLE IF NOT EXISTS lottery_participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lottery_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            amount INTEGER NOT NULL,
            UNIQUE(lottery_id, user_id)
        )""")
        
        # Challenges
        c.execute("""CREATE TABLE IF NOT EXISTS challenges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team1 TEXT NOT NULL,
            team2 TEXT NOT NULL,
            match_time TEXT NOT NULL,
            bet_amount INTEGER NOT NULL,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        
        # Challenge Bets
        c.execute("""CREATE TABLE IF NOT EXISTS challenge_bets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            challenge_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            team_choice TEXT NOT NULL,
            amount INTEGER NOT NULL,
            result TEXT DEFAULT 'pending',
            UNIQUE(challenge_id, user_id)
        )""")
        
        # Transactions
        c.execute("""CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_id INTEGER,
            to_id INTEGER,
            amount INTEGER NOT NULL,
            type TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        
        # Indexes
        c.execute("CREATE INDEX IF NOT EXISTS idx_lot_status ON lotteries(status)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_chal_status ON challenges(status)")
        
        conn.commit()
        print("✅ Render DB (SQLite) آماده شد")
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# Lotteries
# ══════════════════════════════════════════════════════════════════════════════
def create_lottery(chat_id: str, creator_id: int, prize: int, entry_fee: int = 1, duration_min: int = 120):
    end_time = datetime.datetime.now() + datetime.timedelta(minutes=duration_min)
    
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("""INSERT INTO lotteries (chat_id, creator_id, prize, entry_fee, end_time)
                     VALUES (?, ?, ?, ?, ?)""",
                  (chat_id, creator_id, prize, entry_fee, end_time.isoformat()))
        lottery_id = c.lastrowid
        conn.commit()
        return lottery_id
    finally:
        conn.close()


def join_lottery(lottery_id: int, user_id: int, amount: int) -> bool:
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("INSERT INTO lottery_participants (lottery_id, user_id, amount) VALUES (?, ?, ?)",
                  (lottery_id, user_id, amount))
        conn.commit()
        return True
    except:
        return False
    finally:
        conn.close()


def get_lottery_participants(lottery_id: int):
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("SELECT user_id, amount FROM lottery_participants WHERE lottery_id = ?", (lottery_id,))
        return [dict(row) for row in c.fetchall()]
    finally:
        conn.close()


def finish_lottery(lottery_id: int):
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("UPDATE lotteries SET status = 'finished' WHERE id = ?", (lottery_id,))
        conn.commit()
    finally:
        conn.close()


def get_active_lotteries():
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("SELECT * FROM lotteries WHERE status = 'active'")
        return [dict(row) for row in c.fetchall()]
    finally:
        conn.close()


def get_expired_lotteries():
    now = datetime.datetime.now().isoformat()
    
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("SELECT * FROM lotteries WHERE status = 'active' AND end_time <= ?", (now,))
        return [dict(row) for row in c.fetchall()]
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# Challenges
# ═════════════════════════════════════════════════════════════════════════════
def create_challenge(team1: str, team2: str, match_time: str, bet_amount: int):
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("""INSERT INTO challenges (team1, team2, match_time, bet_amount)
                     VALUES (?, ?, ?, ?)""",
                  (team1, team2, match_time, bet_amount))
        challenge_id = c.lastrowid
        conn.commit()
        return challenge_id
    finally:
        conn.close()


def place_bet(challenge_id: int, user_id: int, team: str, amount: int) -> bool:
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("""INSERT INTO challenge_bets (challenge_id, user_id, team_choice, amount)
                     VALUES (?, ?, ?, ?)""",
                  (challenge_id, user_id, team, amount))
        conn.commit()
        return True
    except:
        return False
    finally:
        conn.close()


def get_challenge_bets(challenge_id: int):
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("SELECT user_id, team_choice, amount FROM challenge_bets WHERE challenge_id = ?", 
                  (challenge_id,))
        return [dict(row) for row in c.fetchall()]
    finally:
        conn.close()


def settle_challenge(challenge_id: int, winner_team: str):
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("UPDATE challenges SET status = 'finished' WHERE id = ?", (challenge_id,))
        c.execute("""UPDATE challenge_bets SET result = 
                     CASE WHEN team_choice = ? THEN 'won' ELSE 'lost' END
                     WHERE challenge_id = ?""",
                  (winner_team, challenge_id))
        conn.commit()
    finally:
        conn.close()


def get_active_challenges():
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("SELECT * FROM challenges WHERE status = 'active'")
        return [dict(row) for row in c.fetchall()]
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# Transactions
# ══════════════════════════════════════════════════════════════════════════════
def log_transaction(from_id: int, to_id: int, amount: int, type_: str):
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("INSERT INTO transactions (from_id, to_id, amount, type) VALUES (?, ?, ?, ?)",
                  (from_id, to_id, amount, type_))
        conn.commit()
    finally:
        conn.close()
