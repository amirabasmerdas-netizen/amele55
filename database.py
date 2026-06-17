import database_supabase as supa
import database_render as render


# ══════════════════════════════════════════════════════════════════════════════
# Init
# ══════════════════════════════════════════════════════════════════════════════
def init_db():
    supa.init_db()
    render.init_db()


# ══════════════════════════════════════════════════════════════════════════════
# Accounts (Supabase)
# ══════════════════════════════════════════════════════════════════════════════
def create_account(username: str, password: str):
    return supa.create_account(username, password)


def verify_account(username: str, password: str):
    return supa.verify_account(username, password)


def get_account(owner_id: int):
    return supa.get_account(owner_id)


def get_account_by_tg_id(tg_id: int):
    return supa.get_account_by_tg_id(tg_id)


def get_account_by_username(username: str):
    return supa.get_account_by_username(username)


def save_telegram_user_id(owner_id: int, tg_user_id: int):
    return supa.save_telegram_user_id(owner_id, tg_user_id)


def get_all_accounts():
    return supa.get_all_accounts()


# ══════════════════════════════════════════════════════════════════════════════
# Balance (Supabase)
# ══════════════════════════════════════════════════════════════════════════════
def get_balance(owner_id: int):
    return supa.get_balance(owner_id)


def add_balance(owner_id: int, amount: int):
    return supa.add_balance(owner_id, amount)


def deduct_balance(owner_id: int, amount: int):
    return supa.deduct_balance(owner_id, amount)


def transfer_balance(from_id: int, to_id: int, amount: int):
    return supa.transfer_balance(from_id, to_id, amount)


# ══════════════════════════════════════════════════════════════════════════════
# Settings (Supabase)
# ══════════════════════════════════════════════════════════════════════════════
def init_settings(owner_id: int):
    return supa.init_settings(owner_id)


def get_setting(owner_id: int, key: str, default=None):
    return supa.get_setting(owner_id, key, default)


def set_setting(owner_id: int, key: str, value):
    return supa.set_setting(owner_id, key, value)


# ══════════════════════════════════════════════════════════════════════════════
# Sessions (Supabase)
# ══════════════════════════════════════════════════════════════════════════════
def save_session(owner_id: int, session_data: str, phone: str = None):
    return supa.save_session(owner_id, session_data, phone)


def get_session(owner_id: int):
    return supa.get_session(owner_id)


def delete_session(owner_id: int):
    return supa.delete_session(owner_id)


def get_all_active_sessions():
    return supa.get_all_active_sessions()


def is_session_active(owner_id: int):
    return supa.is_session_active(owner_id)


# ══════════════════════════════════════════════════════════════════════════════
# Lotteries (Render - Fast)
# ══════════════════════════════════════════════════════════════════════════════
def create_lottery(chat_id: str, creator_id: int, prize: int, entry_fee: int = 1, duration_min: int = 120):
    return render.create_lottery(chat_id, creator_id, prize, entry_fee, duration_min)


def join_lottery(lottery_id: int, user_id: int, amount: int):
    return render.join_lottery(lottery_id, user_id, amount)


def get_lottery_participants(lottery_id: int):
    return render.get_lottery_participants(lottery_id)


def finish_lottery(lottery_id: int):
    return render.finish_lottery(lottery_id)


def get_active_lotteries():
    return render.get_active_lotteries()


def get_expired_lotteries():
    return render.get_expired_lotteries()


# ══════════════════════════════════════════════════════════════════════════════
# Challenges (Render - Fast)
# ══════════════════════════════════════════════════════════════════════════════
def create_challenge(team1: str, team2: str, match_time: str, bet_amount: int):
    return render.create_challenge(team1, team2, match_time, bet_amount)


def place_bet(challenge_id: int, user_id: int, team: str, amount: int):
    return render.place_bet(challenge_id, user_id, team, amount)


def get_challenge_bets(challenge_id: int):
    return render.get_challenge_bets(challenge_id)


def settle_challenge(challenge_id: int, winner_team: str):
    return render.settle_challenge(challenge_id, winner_team)


def get_active_challenges():
    return render.get_active_challenges()


# ══════════════════════════════════════════════════════════════════════════════
# Transactions (Render - Fast)
# ══════════════════════════════════════════════════════════════════════════════
def log_transaction(from_id: int, to_id: int, amount: int, type_: str):
    return render.log_transaction(from_id, to_id, amount, type_)
