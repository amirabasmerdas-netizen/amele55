import database_supabase as supa


# ══════════════════════════════════════════════════════════════════════════════
# Init
# ══════════════════════════════════════════════════════════════════════════════
def init_db():
    supa.init_db()


# ══════════════════════════════════════════════════════════════════════════════
# Accounts
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
# Balance
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
# Settings
# ══════════════════════════════════════════════════════════════════════════════
def init_settings(owner_id: int):
    return supa.init_settings(owner_id)


def get_setting(owner_id: int, key: str, default=None):
    return supa.get_setting(owner_id, key, default)


def set_setting(owner_id: int, key: str, value):
    return supa.set_setting(owner_id, key, value)


# ══════════════════════════════════════════════════════════════════════════════
# Sessions
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
# 🆕 دشمن
# ══════════════════════════════════════════════════════════════════════════════
def add_enemy(owner_id: int, user_id: int, username=None, name=None):
    return supa.add_enemy(owner_id, user_id, username, name)


def remove_enemy(owner_id: int, user_id: int):
    return supa.remove_enemy(owner_id, user_id)


def get_enemies(owner_id: int):
    return supa.get_enemies(owner_id)


def is_enemy(owner_id: int, user_id: int):
    return supa.is_enemy(owner_id, user_id)


def clear_enemies(owner_id: int):
    return supa.clear_enemies(owner_id)


# ══════════════════════════════════════════════════════════════════════════════
# 🆕 دوست
# ══════════════════════════════════════════════════════════════════════════════
def add_friend(owner_id: int, user_id: int, username=None, name=None):
    return supa.add_friend(owner_id, user_id, username, name)


def remove_friend(owner_id: int, user_id: int):
    return supa.remove_friend(owner_id, user_id)


def get_friends(owner_id: int):
    return supa.get_friends(owner_id)


def is_friend(owner_id: int, user_id: int):
    return supa.is_friend(owner_id, user_id)


def clear_friends(owner_id: int):
    return supa.clear_friends(owner_id)


# ══════════════════════════════════════════════════════════════════════════════
# 🆕 سایلنت
# ══════════════════════════════════════════════════════════════════════════════
def add_silent_chat(owner_id: int, chat_id: int):
    return supa.add_silent_chat(owner_id, chat_id)


def remove_silent_chat(owner_id: int, chat_id: int):
    return supa.remove_silent_chat(owner_id, chat_id)


def is_silent_chat(owner_id: int, chat_id: int):
    return supa.is_silent_chat(owner_id, chat_id)


def add_silent_user(owner_id: int, user_id: int):
    return supa.add_silent_user(owner_id, user_id)


def remove_silent_user(owner_id: int, user_id: int):
    return supa.remove_silent_user(owner_id, user_id)


def is_silent_user(owner_id: int, user_id: int):
    return supa.is_silent_user(owner_id, user_id)


# ══════════════════════════════════════════════════════════════════════════════
# 🆕 پیام‌های ذخیره‌شده
# ══════════════════════════════════════════════════════════════════════════════
def save_message_slot(owner_id: int, slot: int, content: str):
    return supa.save_message_slot(owner_id, slot, content)


def get_message_slot(owner_id: int, slot: int):
    return supa.get_message_slot(owner_id, slot)


# ══════════════════════════════════════════════════════════════════════════════
# 🆕 پیام‌های زمان‌بندی‌شده
# ══════════════════════════════════════════════════════════════════════════════
def add_scheduled_message(owner_id: int, chat_id: int, message: str, send_at: str):
    return supa.add_scheduled_message(owner_id, chat_id, message, send_at)


def get_pending_scheduled(owner_id: int):
    return supa.get_pending_scheduled(owner_id)


def mark_scheduled_sent(msg_id: int):
    return supa.mark_scheduled_sent(msg_id)
