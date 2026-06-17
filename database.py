# database.py - Bridge بین کد قدیم و جدید + دیتابیس موقت کش

import hashlib
import datetime
from typing import Optional, Dict, List, Any

# ─── ایمپورت از دیتابیس اصلی ──────────────────────────────────────────────────
from database_supabase import (
    create_account as supa_create_account,
    verify_account as supa_verify_account,
    get_account as supa_get_account,
    get_account_by_username as supa_get_account_by_username,
    get_account_by_tg_id as supa_get_account_by_tg_id,
    get_all_accounts as supa_get_all_accounts,
    account_exists as supa_account_exists,
    save_telegram_user_id as supa_save_telegram_user_id,
    get_telegram_id_by_owner as supa_get_telegram_id_by_owner,
    get_setting as supa_get_setting,
    set_setting as supa_set_setting,
    toggle_setting as supa_toggle_setting,
    get_all_logged_in_users as supa_get_all_logged_in_users,
    init_user_settings as supa_init_user_settings,
    get_token_balance as supa_get_token_balance,
    add_tokens as supa_add_tokens,
    deduct_tokens as supa_deduct_tokens,
    claim_daily_token as supa_claim_daily_token,
    get_token_stats as supa_get_token_stats,
    process_referral as supa_process_referral,
    get_referral_count as supa_get_referral_count,
    add_enemy as supa_add_enemy,
    remove_enemy as supa_remove_enemy,
    get_enemies as supa_get_enemies,
    is_enemy as supa_is_enemy,
    clear_enemies as supa_clear_enemies,
    add_friend as supa_add_friend,
    remove_friend as supa_remove_friend,
    get_friends as supa_get_friends,
    is_friend as supa_is_friend,
    clear_friends as supa_clear_friends,
    save_message_slot as supa_save_message_slot,
    get_message_slot as supa_get_message_slot,
    add_scheduled_message as supa_add_scheduled_message,
    get_pending_scheduled as supa_get_pending_scheduled,
    mark_scheduled_sent as supa_mark_scheduled_sent,
    log_deleted_message as supa_log_deleted_message,
    get_deleted_messages as supa_get_deleted_messages,
    SETTING_DEFAULTS,
    _hash_pw,
    get_db,
)

# ─── ایمپورت از دیتابیس کش ────────────────────────────────────────────────────
import db_cache as cache

# ─── توابع دیتابیس پایدار ──────────────────────────────────────────────────────
def create_account(username: str, password: str) -> Optional[int]:
    """ایجاد حساب کاربری جدید"""
    return supa_create_account(username, password)

def verify_account(username: str, password: str) -> Optional[int]:
    """تأیید ورود کاربر"""
    return supa_verify_account(username, password)

def get_account(owner_id: int) -> Optional[Dict]:
    """دریافت اطلاعات حساب کاربر"""
    return supa_get_account(owner_id)

def get_account_by_username(username: str) -> Optional[Dict]:
    """دریافت حساب با یوزرنیم"""
    return supa_get_account_by_username(username)

def get_account_by_tg_id(tg_id: int) -> Optional[Dict]:
    """دریافت حساب با آیدی تلگرام"""
    return supa_get_account_by_tg_id(tg_id)

def get_all_accounts() -> List[Dict]:
    """دریافت همه حساب‌ها"""
    return supa_get_all_accounts()

def account_exists() -> bool:
    """بررسی وجود حداقل یک حساب"""
    return supa_account_exists()

def save_telegram_user_id(owner_id: int, tg_user_id: int):
    """ذخیره آیدی تلگرام کاربر"""
    supa_save_telegram_user_id(owner_id, tg_user_id)

def get_telegram_id_by_owner(owner_id: int) -> Optional[int]:
    """دریافت آیدی تلگرام با owner_id"""
    return supa_get_telegram_id_by_owner(owner_id)

# ─── توابع تنظیمات ─────────────────────────────────────────────────────────────
def get_setting(owner_id: int, key: str, default=None) -> str:
    """دریافت تنظیمات (با کش)"""
    return supa_get_setting(owner_id, key, default)

def set_setting(owner_id: int, key: str, value):
    """تنظیم مقدار (با کش)"""
    supa_set_setting(owner_id, key, value)

def toggle_setting(owner_id: int, key: str) -> bool:
    """تغییر وضعیت یک تنظیمات"""
    return supa_toggle_setting(owner_id, key)

def get_all_logged_in_users() -> List[int]:
    """دریافت همه کاربران لاگین‌شده"""
    return supa_get_all_logged_in_users()

def init_user_settings(owner_id: int):
    """مقداردهی اولیه تنظیمات کاربر"""
    supa_init_user_settings(owner_id)

# ─── توابع توکن ────────────────────────────────────────────────────────────────
def get_token_balance(owner_id: int) -> int:
    """دریافت موجودی توکن"""
    return supa_get_token_balance(owner_id)

def add_tokens(owner_id: int, amount: int):
    """افزایش توکن"""
    supa_add_tokens(owner_id, amount)

def deduct_tokens(owner_id: int, amount: int) -> bool:
    """کاهش توکن"""
    return supa_deduct_tokens(owner_id, amount)

def claim_daily_token(owner_id: int):
    """دریافت هدیه روزانه"""
    return supa_claim_daily_token(owner_id)

def get_token_stats(owner_id: int) -> dict:
    """دریافت آمار توکن"""
    return supa_get_token_stats(owner_id)

def process_referral(referrer_owner_id: int, referred_tg_id: int) -> bool:
    """پردازش رفرال"""
    return supa_process_referral(referrer_owner_id, referred_tg_id)

def get_referral_count(owner_id: int) -> int:
    """دریافت تعداد رفرال‌ها"""
    return supa_get_referral_count(owner_id)

# ─── توابع دشمن ────────────────────────────────────────────────────────────────
def add_enemy(owner_id: int, user_id: int, username=None, name=None):
    """افزودن دشمن"""
    return supa_add_enemy(owner_id, user_id, username, name)

def remove_enemy(owner_id: int, user_id: int) -> bool:
    """حذف دشمن"""
    return supa_remove_enemy(owner_id, user_id)

def get_enemies(owner_id: int) -> List[Dict]:
    """دریافت لیست دشمن‌ها"""
    return supa_get_enemies(owner_id)

def is_enemy(owner_id: int, user_id: int) -> bool:
    """بررسی دشمن بودن کاربر"""
    return supa_is_enemy(owner_id, user_id)

def clear_enemies(owner_id: int):
    """پاک کردن لیست دشمن"""
    supa_clear_enemies(owner_id)

# ─── توابع دوست ────────────────────────────────────────────────────────────────
def add_friend(owner_id: int, user_id: int, username=None, name=None):
    """افزودن دوست"""
    return supa_add_friend(owner_id, user_id, username, name)

def remove_friend(owner_id: int, user_id: int) -> bool:
    """حذف دوست"""
    return supa_remove_friend(owner_id, user_id)

def get_friends(owner_id: int) -> List[Dict]:
    """دریافت لیست دوست‌ها"""
    return supa_get_friends(owner_id)

def is_friend(owner_id: int, user_id: int) -> bool:
    """بررسی دوست بودن کاربر"""
    return supa_is_friend(owner_id, user_id)

def clear_friends(owner_id: int):
    """پاک کردن لیست دوست"""
    supa_clear_friends(owner_id)

# ─── توابع پیام ────────────────────────────────────────────────────────────────
def save_message_slot(owner_id: int, slot: int, content, media_path=None):
    """ذخیره پیام در اسلات"""
    supa_save_message_slot(owner_id, slot, content, media_path)

def get_message_slot(owner_id: int, slot: int):
    """دریافت پیام از اسلات"""
    return supa_get_message_slot(owner_id, slot)

def add_scheduled_message(owner_id: int, chat_id, message, send_at):
    """افزودن پیام زمان‌بندی‌شده"""
    return supa_add_scheduled_message(owner_id, chat_id, message, send_at)

def get_pending_scheduled(owner_id: int):
    """دریافت پیام‌های زمان‌بندی‌شده در انتظار"""
    return supa_get_pending_scheduled(owner_id)

def mark_scheduled_sent(msg_id: int):
    """علامت‌گذاری پیام زمان‌بندی‌شده به عنوان ارسال‌شده"""
    supa_mark_scheduled_sent(msg_id)

def log_deleted_message(owner_id: int, chat_id, sender_id, sender_name, message, media_type=None):
    """ثبت پیام حذف‌شده"""
    supa_log_deleted_message(owner_id, chat_id, sender_id, sender_name, message, media_type)

def get_deleted_messages(owner_id: int, limit=50):
    """دریافت پیام‌های حذف‌شده"""
    return supa_get_deleted_messages(owner_id, limit)

# ─── توابع دیتابیس کش (موقت) ──────────────────────────────────────────────────
def get_forced_channels():
    """دریافت لیست چنل‌های اجباری (از کش)"""
    return cache.get_forced_channels()

def add_forced_channel(username: str) -> bool:
    """افزودن چنل اجباری (به کش)"""
    return cache.add_forced_channel(username)

def remove_forced_channel(username: str) -> bool:
    """حذف چنل اجباری (از کش)"""
    return cache.remove_forced_channel(username)

def check_user_membership(bot, user_id: int) -> tuple:
    """بررسی عضویت کاربر در چنل‌های اجباری (با کش)"""
    return cache.check_user_membership(bot, user_id)

def add_silent_chat(owner_id: int, chat_id: int):
    """افزودن چت سایلنت (به کش)"""
    cache.add_silent_chat(owner_id, chat_id)

def remove_silent_chat(owner_id: int, chat_id: int):
    """حذف چت سایلنت (از کش)"""
    cache.remove_silent_chat(owner_id, chat_id)

def is_silent_chat(owner_id: int, chat_id: int) -> bool:
    """بررسی سایلنت بودن چت (با کش)"""
    return cache.is_silent_chat(owner_id, chat_id)

def add_silent_user(owner_id: int, user_id: int):
    """افزودن کاربر سایلنت (به کش)"""
    cache.add_silent_user(owner_id, user_id)

def remove_silent_user(owner_id: int, user_id: int):
    """حذف کاربر سایلنت (از کش)"""
    cache.remove_silent_user(owner_id, user_id)

def is_silent_user(owner_id: int, user_id: int) -> bool:
    """بررسی سایلنت بودن کاربر (با کش)"""
    return cache.is_silent_user(owner_id, user_id)

# ─── توابع کمکی ────────────────────────────────────────────────────────────────
def hash_password(password: str) -> str:
    """هش کردن رمز عبور"""
    return _hash_pw(password)

def get_db_connection():
    """دریافت اتصال به دیتابیس اصلی (برای موارد خاص)"""
    return get_db()

# ─── صادرات همه توابع ─────────────────────────────────────────────────────────
__all__ = [
    # حساب‌ها
    'create_account', 'verify_account', 'get_account',
    'get_account_by_username', 'get_account_by_tg_id',
    'get_all_accounts', 'account_exists', 'save_telegram_user_id',
    'get_telegram_id_by_owner',
    
    # تنظیمات
    'get_setting', 'set_setting', 'toggle_setting',
    'get_all_logged_in_users', 'init_user_settings',
    'SETTING_DEFAULTS',
    
    # توکن
    'get_token_balance', 'add_tokens', 'deduct_tokens',
    'claim_daily_token', 'get_token_stats',
    'process_referral', 'get_referral_count',
    
    # دشمن
    'add_enemy', 'remove_enemy', 'get_enemies',
    'is_enemy', 'clear_enemies',
    
    # دوست
    'add_friend', 'remove_friend', 'get_friends',
    'is_friend', 'clear_friends',
    
    # پیام
    'save_message_slot', 'get_message_slot',
    'add_scheduled_message', 'get_pending_scheduled',
    'mark_scheduled_sent',
    'log_deleted_message', 'get_deleted_messages',
    
    # دیتابیس کش (چنل‌های اجباری و سایلنت)
    'get_forced_channels', 'add_forced_channel',
    'remove_forced_channel', 'check_user_membership',
    'add_silent_chat', 'remove_silent_chat', 'is_silent_chat',
    'add_silent_user', 'remove_silent_user', 'is_silent_user',
    
    # کمکی
    'hash_password', 'get_db_connection',
]
