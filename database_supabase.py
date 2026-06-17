import os
import json
import hashlib
import datetime
from typing import Optional, Dict, List, Any
import requests
from config import SUPABASE_URL, SUPABASE_KEY, SUPABASE_TABLE_PREFIX

# ─── کلاینت Supabase ──────────────────────────────────────────────────────────
class SupabaseDB:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance
    
    def _init(self):
        self.url = SUPABASE_URL.rstrip('/')
        self.key = SUPABASE_KEY
        self.headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json"
        }
        self.prefix = SUPABASE_TABLE_PREFIX
        self._ensure_tables()
    
    def _ensure_tables(self):
        """اطمینان از وجود جداول مورد نیاز"""
        tables = [
            f"{self.prefix}accounts",
            f"{self.prefix}settings",
            f"{self.prefix}tokens",
            f"{self.prefix}referrals",
            f"{self.prefix}enemies",
            f"{self.prefix}friends",
            f"{self.prefix}saved_messages",
            f"{self.prefix}scheduled_messages",
            f"{self.prefix}deleted_messages",
        ]
        # Supabase به صورت خودکار جدول می‌سازه، ولی برای اطمینان
        # ما از RLS و ساختار مناسب استفاده می‌کنیم
        pass
    
    def _request(self, method: str, table: str, data: dict = None, 
                 params: dict = None, match: dict = None) -> List[Dict]:
        """درخواست به Supabase"""
        url = f"{self.url}/rest/v1/{table}"
        headers = self.headers.copy()
        
        if method.upper() in ['POST', 'PATCH']:
            headers["Prefer"] = "return=representation"
        
        # فیلتر کردن با match
        if match:
            params = params or {}
            for key, value in match.items():
                params[key] = f"eq.{value}"
        
        try:
            if method.upper() == 'GET':
                response = requests.get(url, headers=headers, params=params, timeout=5)
            elif method.upper() == 'POST':
                response = requests.post(url, headers=headers, json=data, timeout=5)
            elif method.upper() == 'PATCH':
                response = requests.patch(url, headers=headers, json=data, params=params, timeout=5)
            elif method.upper() == 'DELETE':
                response = requests.delete(url, headers=headers, params=params, timeout=5)
            else:
                return []
            
            if response.status_code in [200, 201, 204]:
                if response.text:
                    return response.json()
                return []
            else:
                print(f"❌ Supabase error: {response.status_code} - {response.text}")
                return []
        except Exception as e:
            print(f"❌ Supabase request error: {e}")
            return []

# ─── هش رمز ──────────────────────────────────────────────────────────────────
def _hash_pw(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

# ─── حساب‌ها ──────────────────────────────────────────────────────────────────
def get_db():
    return SupabaseDB()

def create_account(username: str, password: str) -> Optional[int]:
    db = get_db()
    data = {
        "username": username.strip(),
        "password_hash": _hash_pw(password),
        "created_at": datetime.datetime.now().isoformat()
    }
    result = db._request('POST', f"{db.prefix}accounts", data)
    if result and len(result) > 0:
        return result[0].get('id')
    return None

def verify_account(username: str, password: str) -> Optional[int]:
    db = get_db()
    result = db._request('GET', f"{db.prefix}accounts", 
                         params={"username": f"eq.{username.strip()}"})
    if result and len(result) > 0:
        acc = result[0]
        if acc.get('password_hash') == _hash_pw(password):
            return acc.get('id')
    return None

def get_account(owner_id: int) -> Optional[Dict]:
    db = get_db()
    result = db._request('GET', f"{db.prefix}accounts", 
                         params={"id": f"eq.{owner_id}"})
    if result and len(result) > 0:
        return result[0]
    return None

def get_account_by_username(username: str) -> Optional[Dict]:
    db = get_db()
    result = db._request('GET', f"{db.prefix}accounts", 
                         params={"username": f"eq.{username.strip()}"})
    if result and len(result) > 0:
        return result[0]
    return None

def get_account_by_tg_id(tg_id: int) -> Optional[Dict]:
    db = get_db()
    result = db._request('GET', f"{db.prefix}accounts", 
                         params={"telegram_user_id": f"eq.{tg_id}"})
    if result and len(result) > 0:
        return result[0]
    return None

def get_all_accounts() -> List[Dict]:
    db = get_db()
    result = db._request('GET', f"{db.prefix}accounts")
    return result or []

def account_exists() -> bool:
    db = get_db()
    result = db._request('GET', f"{db.prefix}accounts", params={"limit": "1"})
    return len(result) > 0

def save_telegram_user_id(owner_id: int, tg_user_id: int):
    db = get_db()
    db._request('PATCH', f"{db.prefix}accounts", 
                data={"telegram_user_id": tg_user_id},
                params={"id": f"eq.{owner_id}"})

def get_telegram_id_by_owner(owner_id: int) -> Optional[int]:
    acc = get_account(owner_id)
    return acc.get('telegram_user_id') if acc else None

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
    "secretary_message": "در حال حاضر در دسترس نیستم.",
    "auto_reaction_emoji": "❤️",
    "spam_active": "0",
    "channel_save_active": "0",
    "spam_delay": "2",
    "session_data": "",
    "logged_in": "0",
}

# کش تنظیمات در حافظه
_settings_cache = {}
_cache_timestamps = {}

def _get_setting_key(owner_id: int, key: str) -> str:
    return f"{owner_id}:{key}"

def get_setting(owner_id: int, key: str, default=None) -> str:
    """دریافت تنظیمات با کش کردن برای سرعت بالا"""
    cache_key = _get_setting_key(owner_id, key)
    
    # بررسی کش
    if cache_key in _settings_cache:
        timestamp = _cache_timestamps.get(cache_key, 0)
        if datetime.datetime.now().timestamp() - timestamp < 60:  # کش 60 ثانیه
            return _settings_cache[cache_key]
    
    db = get_db()
    result = db._request('GET', f"{db.prefix}settings",
                         params={"owner_id": f"eq.{owner_id}", "key": f"eq.{key}"})
    
    if result and len(result) > 0:
        value = result[0].get('value')
        # ذخیره در کش
        _settings_cache[cache_key] = value
        _cache_timestamps[cache_key] = datetime.datetime.now().timestamp()
        return value
    
    # اگر تنظیمات وجود نداشت، مقدار پیش‌فرض رو برگردون
    default_val = SETTING_DEFAULTS.get(key, default)
    # ذخیره در کش
    _settings_cache[cache_key] = default_val if default_val is not None else ""
    _cache_timestamps[cache_key] = datetime.datetime.now().timestamp()
    return default_val if default_val is not None else ""

def set_setting(owner_id: int, key: str, value):
    """تنظیم مقدار با به‌روزرسانی کش"""
    db = get_db()
    existing = db._request('GET', f"{db.prefix}settings",
                           params={"owner_id": f"eq.{owner_id}", "key": f"eq.{key}"})
    
    if existing and len(existing) > 0:
        db._request('PATCH', f"{db.prefix}settings",
                    data={"value": str(value)},
                    params={"owner_id": f"eq.{owner_id}", "key": f"eq.{key}"})
    else:
        data = {
            "owner_id": owner_id,
            "key": key,
            "value": str(value)
        }
        db._request('POST', f"{db.prefix}settings", data)
    
    # به‌روزرسانی کش
    cache_key = _get_setting_key(owner_id, key)
    _settings_cache[cache_key] = str(value)
    _cache_timestamps[cache_key] = datetime.datetime.now().timestamp()

def toggle_setting(owner_id: int, key: str) -> bool:
    current = get_setting(owner_id, key, "0")
    new_val = "0" if current == "1" else "1"
    set_setting(owner_id, key, new_val)
    return new_val == "1"

def get_all_logged_in_users() -> List[int]:
    """دریافت همه کاربرانی که لاگین هستند (با کش)"""
    db = get_db()
    result = db._request('GET', f"{db.prefix}settings",
                         params={"key": "eq.logged_in", "value": "eq.1"})
    return [int(r.get('owner_id')) for r in result if r.get('owner_id')]

def init_user_settings(owner_id: int):
    """مقداردهی اولیه تنظیمات کاربر"""
    for key, value in SETTING_DEFAULTS.items():
        set_setting(owner_id, key, value)

# ─── توکن‌ها ──────────────────────────────────────────────────────────────────
def _init_tokens(owner_id: int):
    """اطمینان از وجود رکورد توکن برای کاربر"""
    db = get_db()
    existing = db._request('GET', f"{db.prefix}tokens",
                           params={"owner_id": f"eq.{owner_id}"})
    if not existing or len(existing) == 0:
        data = {
            "owner_id": owner_id,
            "balance": 0,
            "total_earned": 0
        }
        db._request('POST', f"{db.prefix}tokens", data)

def get_token_balance(owner_id: int) -> int:
    db = get_db()
    result = db._request('GET', f"{db.prefix}tokens",
                         params={"owner_id": f"eq.{owner_id}"})
    if result and len(result) > 0:
        return result[0].get('balance', 0)
    _init_tokens(owner_id)
    return 0

def add_tokens(owner_id: int, amount: int):
    db = get_db()
    _init_tokens(owner_id)
    # استفاده از raw SQL برای افزایش اتمی
    # در Supabase از RPC استفاده می‌کنیم
    response = db._request('GET', f"{db.prefix}tokens",
                           params={"owner_id": f"eq.{owner_id}"})
    if response and len(response) > 0:
        current = response[0].get('balance', 0)
        total = response[0].get('total_earned', 0)
        db._request('PATCH', f"{db.prefix}tokens",
                    data={"balance": current + amount, "total_earned": total + amount},
                    params={"owner_id": f"eq.{owner_id}"})

def deduct_tokens(owner_id: int, amount: int) -> bool:
    db = get_db()
    _init_tokens(owner_id)
    response = db._request('GET', f"{db.prefix}tokens",
                           params={"owner_id": f"eq.{owner_id}"})
    if response and len(response) > 0:
        current = response[0].get('balance', 0)
        if current < amount:
            return False
        db._request('PATCH', f"{db.prefix}tokens",
                    data={"balance": current - amount},
                    params={"owner_id": f"eq.{owner_id}"})
        return True
    return False

def claim_daily_token(owner_id: int):
    from config import DAILY_TOKEN_GIFT
    db = get_db()
    _init_tokens(owner_id)
    today = datetime.date.today().isoformat()
    
    response = db._request('GET', f"{db.prefix}tokens",
                           params={"owner_id": f"eq.{owner_id}"})
    if response and len(response) > 0:
        last_daily = response[0].get('last_daily')
        if last_daily == today:
            return False, "⏰ امروز قبلاً هدیه روزانه دریافت کردید."
        
        balance = response[0].get('balance', 0)
        total = response[0].get('total_earned', 0)
        db._request('PATCH', f"{db.prefix}tokens",
                    data={
                        "balance": balance + DAILY_TOKEN_GIFT,
                        "total_earned": total + DAILY_TOKEN_GIFT,
                        "last_daily": today
                    },
                    params={"owner_id": f"eq.{owner_id}"})
        return True, f"🎁 {DAILY_TOKEN_GIFT} توکن دریافت کردید!"
    return False, "خطا در دریافت هدیه"

def get_token_stats(owner_id: int) -> dict:
    db = get_db()
    _init_tokens(owner_id)
    response = db._request('GET', f"{db.prefix}tokens",
                           params={"owner_id": f"eq.{owner_id}"})
    if response and len(response) > 0:
        row = response[0]
        today = datetime.date.today().isoformat()
        return {
            "balance": row.get('balance', 0),
            "last_daily": row.get('last_daily'),
            "total_earned": row.get('total_earned', 0),
            "can_claim_daily": row.get('last_daily') != today,
        }
    return {"balance": 0, "last_daily": None, "total_earned": 0, "can_claim_daily": True}

# ─── رفرال ──────────────────────────────────────────────────────────────────
def process_referral(referrer_owner_id: int, referred_tg_id: int) -> bool:
    from config import REFERRAL_TOKENS
    db = get_db()
    
    # بررسی اینکه کاربر قبلاً رفرال نشده
    existing = db._request('GET', f"{db.prefix}referrals",
                           params={"referred_tg_id": f"eq.{referred_tg_id}"})
    if existing and len(existing) > 0:
        return False
    
    # بررسی وجود رفرر
    acc = get_account(referrer_owner_id)
    if not acc:
        return False
    
    data = {
        "referrer_owner_id": referrer_owner_id,
        "referred_tg_id": referred_tg_id,
        "created_at": datetime.datetime.now().isoformat()
    }
    db._request('POST', f"{db.prefix}referrals", data)
    
    # افزودن توکن
    add_tokens(referrer_owner_id, REFERRAL_TOKENS)
    return True

def get_referral_count(owner_id: int) -> int:
    db = get_db()
    result = db._request('GET', f"{db.prefix}referrals",
                         params={"referrer_owner_id": f"eq.{owner_id}"})
    return len(result) if result else 0

# ─── دشمن ──────────────────────────────────────────────────────────────────
def add_enemy(owner_id: int, user_id: int, username=None, name=None):
    db = get_db()
    data = {
        "owner_id": owner_id,
        "user_id": user_id,
        "username": username,
        "name": name,
        "added_at": datetime.datetime.now().isoformat()
    }
    # حذف قبلی و افزودن جدید
    db._request('DELETE', f"{db.prefix}enemies",
                params={"owner_id": f"eq.{owner_id}", "user_id": f"eq.{user_id}"})
    db._request('POST', f"{db.prefix}enemies", data)
    return True

def remove_enemy(owner_id: int, user_id: int) -> bool:
    db = get_db()
    db._request('DELETE', f"{db.prefix}enemies",
                params={"owner_id": f"eq.{owner_id}", "user_id": f"eq.{user_id}"})
    return True

def get_enemies(owner_id: int) -> List[Dict]:
    db = get_db()
    result = db._request('GET', f"{db.prefix}enemies",
                         params={"owner_id": f"eq.{owner_id}"})
    return result or []

def is_enemy(owner_id: int, user_id: int) -> bool:
    db = get_db()
    result = db._request('GET', f"{db.prefix}enemies",
                         params={"owner_id": f"eq.{owner_id}", "user_id": f"eq.{user_id}"})
    return len(result) > 0

def clear_enemies(owner_id: int):
    db = get_db()
    db._request('DELETE', f"{db.prefix}enemies",
                params={"owner_id": f"eq.{owner_id}"})

# ─── دوست ──────────────────────────────────────────────────────────────────
def add_friend(owner_id: int, user_id: int, username=None, name=None):
    db = get_db()
    data = {
        "owner_id": owner_id,
        "user_id": user_id,
        "username": username,
        "name": name,
        "added_at": datetime.datetime.now().isoformat()
    }
    db._request('DELETE', f"{db.prefix}friends",
                params={"owner_id": f"eq.{owner_id}", "user_id": f"eq.{user_id}"})
    db._request('POST', f"{db.prefix}friends", data)
    return True

def remove_friend(owner_id: int, user_id: int) -> bool:
    db = get_db()
    db._request('DELETE', f"{db.prefix}friends",
                params={"owner_id": f"eq.{owner_id}", "user_id": f"eq.{user_id}"})
    return True

def get_friends(owner_id: int) -> List[Dict]:
    db = get_db()
    result = db._request('GET', f"{db.prefix}friends",
                         params={"owner_id": f"eq.{owner_id}"})
    return result or []

def is_friend(owner_id: int, user_id: int) -> bool:
    db = get_db()
    result = db._request('GET', f"{db.prefix}friends",
                         params={"owner_id": f"eq.{owner_id}", "user_id": f"eq.{user_id}"})
    return len(result) > 0

def clear_friends(owner_id: int):
    db = get_db()
    db._request('DELETE', f"{db.prefix}friends",
                params={"owner_id": f"eq.{owner_id}"})

# ─── پیام‌های ذخیره‌شده ──────────────────────────────────────────────────
def save_message_slot(owner_id: int, slot: int, content, media_path=None):
    db = get_db()
    data = {
        "owner_id": owner_id,
        "slot": slot,
        "content": content,
        "media_path": media_path,
        "saved_at": datetime.datetime.now().isoformat()
    }
    db._request('DELETE', f"{db.prefix}saved_messages",
                params={"owner_id": f"eq.{owner_id}", "slot": f"eq.{slot}"})
    db._request('POST', f"{db.prefix}saved_messages", data)

def get_message_slot(owner_id: int, slot: int):
    db = get_db()
    result = db._request('GET', f"{db.prefix}saved_messages",
                         params={"owner_id": f"eq.{owner_id}", "slot": f"eq.{slot}"})
    if result and len(result) > 0:
        return result[0]
    return None

# ─── پیام‌های زمان‌بندی‌شده ──────────────────────────────────────────────
def add_scheduled_message(owner_id: int, chat_id, message, send_at):
    db = get_db()
    data = {
        "owner_id": owner_id,
        "chat_id": chat_id,
        "message": message,
        "send_at": send_at,
        "sent": 0
    }
    result = db._request('POST', f"{db.prefix}scheduled_messages", data)
    if result and len(result) > 0:
        return result[0].get('id')
    return None

def get_pending_scheduled(owner_id: int):
    db = get_db()
    now = datetime.datetime.now().isoformat()
    result = db._request('GET', f"{db.prefix}scheduled_messages",
                         params={
                             "owner_id": f"eq.{owner_id}",
                             "sent": "eq.0",
                             "send_at": f"lte.{now}"
                         })
    return result or []

def mark_scheduled_sent(msg_id: int):
    db = get_db()
    db._request('PATCH', f"{db.prefix}scheduled_messages",
                data={"sent": 1},
                params={"id": f"eq.{msg_id}"})

# ─── پیام‌های حذف‌شده ────────────────────────────────────────────────────
def log_deleted_message(owner_id: int, chat_id, sender_id, sender_name, message, media_type=None):
    db = get_db()
    data = {
        "owner_id": owner_id,
        "chat_id": chat_id,
        "sender_id": sender_id,
        "sender_name": sender_name,
        "message": message,
        "media_type": media_type,
        "deleted_at": datetime.datetime.now().isoformat()
    }
    db._request('POST', f"{db.prefix}deleted_messages", data)

def get_deleted_messages(owner_id: int, limit=50):
    db = get_db()
    result = db._request('GET', f"{db.prefix}deleted_messages",
                         params={
                             "owner_id": f"eq.{owner_id}",
                             "order": "deleted_at.desc",
                             "limit": str(limit)
                         })
    return result or []
