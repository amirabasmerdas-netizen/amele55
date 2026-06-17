import threading
import time
import telebot
from telebot import types
import database as db
import config
import datetime
import random
import asyncio

_bot = None
BOT_USERNAME = None
OWNER_TG_ID = 8296865861

# ─── کش ──────────────────────────────────────────────────────────────────────
class SmartCache:
    def __init__(self):
        self._data = {}
        self._timestamps = {}
    
    def get(self, key, default=None):
        if key in self._data and key in self._timestamps:
            ttl = self._get_ttl(key)
            if time.time() - self._timestamps[key] < ttl:
                return self._data[key]
            else:
                del self._data[key]
                del self._timestamps[key]
        return default
    
    def set(self, key, value):
        self._data[key] = value
        self._timestamps[key] = time.time()
    
    def invalidate(self, pattern=None):
        if pattern is None:
            self._data.clear()
            self._timestamps.clear()
        else:
            keys_to_del = [k for k in list(self._data.keys()) if k.startswith(pattern)]
            for k in keys_to_del:
                self._data.pop(k, None)
                self._timestamps.pop(k, None)
    
    def _get_ttl(self, key):
        if key.startswith("membership_"):
            return 900
        if key.startswith("account_"):
            return 300
        if key.startswith("stats_"):
            return 60
        if key.startswith("challenge_"):
            return 120
        if key.startswith("lottery_"):
            return 60
        return 300

cache = SmartCache()
_owner_states = {}
_lottery_players = {}


def get_bot():
    return _bot


def _check_membership_cached(user_id):
    cache_key = f"membership_{user_id}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    try:
        is_member, missing = db.check_user_membership(_bot, user_id)
        result = (is_member, missing)
        cache.set(cache_key, result)
        return result
    except Exception as e:
        print(f"⚠️ خطا در بررسی عضویت: {e}")
        return True, []


def _get_account_cached(tg_id):
    cache_key = f"account_{tg_id}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    account = db.get_account_by_tg_id(tg_id)
    if account:
        cache.set(cache_key, account)
    return account


# ══════════════════════════════════════════════════════════════════════════════
# 🎨 کیبوردهای این‌لاین - طراحی مشابه تصویر
# ══════════════════════════════════════════════════════════════════════════════
def main_menu_keyboard(is_owner=False):
    """کیبورد اصلی - مشابه تصویر"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    # ردیف 1: فعال‌سازی سلف (سبز)
    markup.add(types.InlineKeyboardButton("🔌 فعالسازی سلف", callback_data="activate_self"))
    
    # ردیف 2: وضعیت و خاموش (قرمز)
    markup.add(
        types.InlineKeyboardButton("📊 وضعیت سلف", callback_data="self_status"),
        types.InlineKeyboardButton("⏹️ خاموش کردن", callback_data="deactivate_self")
    )
    
    # ردیف 3: زیرمجموعه و خرید (سبز)
    markup.add(
        types.InlineKeyboardButton("👥 زیرمجموعه‌گیری", callback_data="referrals"),
        types.InlineKeyboardButton("💎 خرید الماس", callback_data="buy_tokens")
    )
    
    # ردیف 4: پروفایل و پشتیبانی (آبی)
    markup.add(
        types.InlineKeyboardButton("👤 پروفایل کاربری", callback_data="user_profile"),
        types.InlineKeyboardButton("📞 پشتیبانی", callback_data="support")
    )
    
    # ردیف 5: مدیریت (فقط برای مالک - قرمز تیره)
    if is_owner:
        markup.add(types.InlineKeyboardButton("🔧 مدیریت", callback_data="admin_panel"))
    
    return markup


def self_panel_keyboard():
    """پنل مدیریت سلف"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    markup.add(
        types.InlineKeyboardButton("✅ روشن کردن", callback_data="self_on"),
        types.InlineKeyboardButton("❌ خاموش کردن", callback_data="self_off")
    )
    
    markup.add(
        types.InlineKeyboardButton("⚙️ تنظیمات سلف", callback_data="self_settings"),
        types.InlineKeyboardButton("📊 وضعیت", callback_data="self_status")
    )
    
    markup.add(types.InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu"))
    
    return markup


def settings_keyboard():
    """تنظیمات سلف"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    markup.add(
        types.InlineKeyboardButton("🤖 منشی", callback_data="toggle_secretary"),
        types.InlineKeyboardButton("🛡️ ضد حذف", callback_data="toggle_anti_delete")
    )
    
    markup.add(
        types.InlineKeyboardButton("🔗 ضد لینک", callback_data="toggle_anti_link"),
        types.InlineKeyboardButton("👁️ سین خودکار", callback_data="toggle_auto_seen")
    )
    
    markup.add(
        types.InlineKeyboardButton("❤️ ری‌اکشن", callback_data="toggle_reaction"),
        types.InlineKeyboardButton("🔒 قفل پیوی", callback_data="toggle_private_lock")
    )
    
    markup.add(
        types.InlineKeyboardButton("💾 ذخیره مدیا", callback_data="toggle_save_media"),
        types.InlineKeyboardButton("⏰ ساعت نام", callback_data="toggle_clock_name")
    )
    
    markup.add(types.InlineKeyboardButton("🔙 بازگشت", callback_data="self_panel"))
    
    return markup


def admin_panel_keyboard():
    """پنل مدیریت مالک"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    markup.add(
        types.InlineKeyboardButton("📢 چنل‌های اجباری", callback_data="admin_channels"),
        types.InlineKeyboardButton("👥 کاربران", callback_data="admin_users")
    )
    
    markup.add(
        types.InlineKeyboardButton("🏆 جام جهانی", callback_data="admin_wc"),
        types.InlineKeyboardButton("🎲 قرعه‌کشی", callback_data="admin_lottery")
    )
    
    markup.add(
        types.InlineKeyboardButton("💎 انتقال الماس", callback_data="admin_transfer"),
        types.InlineKeyboardButton("💰 دادن الماس", callback_data="admin_give")
    )
    
    markup.add(types.InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu"))
    
    return markup


def start_token_bot():
    global _bot, BOT_USERNAME

    if not config.BOT_TOKEN:
        print("⚠️ BOT_TOKEN تنظیم نشده — ربات الماس غیرفعال است")
        return

    _bot = telebot.TeleBot(config.BOT_TOKEN, parse_mode="HTML", threaded=True, num_threads=4)

    try:
        me = _bot.get_me()
        BOT_USERNAME = me.username
        print(f"🤖 ربات الماس: @{BOT_USERNAME}")
    except Exception as e:
        print(f"❌ خطا در اتصال ربات الماس: {e}")
        _bot = None
        return

    for _ in range(3):
        try:
            _bot.delete_webhook(drop_pending_updates=True)
            time.sleep(2)
            break
        except:
            time.sleep(2)

    # ─── توابع کمکی ───────────────────────────────────────────────────────────
    def send_forced_channels_menu(message, missing_channels):
        markup = types.InlineKeyboardMarkup(row_width=1)
        for ch in missing_channels:
            ch_clean = ch.lstrip("@")
            markup.add(types.InlineKeyboardButton(f"📢 عضویت در {ch}", url=f"https://t.me/{ch_clean}"))
        markup.add(types.InlineKeyboardButton("✅ بررسی عضویت من", callback_data="check_join"))
        
        channels_list = "\n".join([f"🔸 {ch}" for ch in missing_channels])
        _bot.reply_to(
            message,
            "⛔️ <b>ورود به ربات منوط به عضویت در کانال‌های زیر است:</b>\n\n"
            f"{channels_list}\n\n"
            "👇 روی هر کانال کلیک کنید و Join بزنید، سپس دکمه «بررسی عضویت من» را بزنید:",
            reply_markup=markup
        )

    def require_membership(message):
        if message.chat.type != 'private':
            return True
        is_member, missing = _check_membership_cached(message.from_user.id)
        if not is_member:
            send_forced_channels_menu(message, missing)
            return False
        return True

    # ══════════════════════════════════════════════════════════════════════════
    # /start - با کیبورد اینلاین
    # ══════════════════════════════════════════════════════════════════════════
    @_bot.message_handler(commands=["start"])
    def cmd_start(message):
        try:
            tg_id = message.from_user.id
            parts = message.text.strip().split()
            ref_code = parts[1] if len(parts) > 1 else None
            
            if ref_code and ref_code.startswith("ref_"):
                try:
                    referrer_id = int(ref_code[4:])
                    threading.Thread(target=_process_referral_async, args=(referrer_id, tg_id), daemon=True).start()
                except: 
                    pass

            is_member, missing = _check_membership_cached(tg_id)
            if not is_member:
                send_forced_channels_menu(message, missing)
                return

            account = _get_account_cached(tg_id)
            site_url = getattr(config, "SITE_URL", "")

            if not account:
                markup = types.InlineKeyboardMarkup()
                if site_url:
                    markup.add(types.InlineKeyboardButton("🌐 ورود به پنل وب", url=site_url))
                _bot.reply_to(message, 
                    "👋 <b>سلام!</b>\n\n"
                    "برای استفاده از ربات:\n"
                    "1️⃣ در پنل وب ثبت‌نام کنید\n"
                    "2️⃣ حساب تلگرام را وصل کنید\n"
                    "3️⃣ دوباره /start بزنید", 
                    reply_markup=markup if site_url else None)
                return

            is_owner = (tg_id == OWNER_TG_ID)
            stats = db.get_token_stats(account["id"])
            token_price = getattr(config, 'TOKEN_PRICE_TOMAN', 200)
            
            # پیام خوش‌آمدگویی با کیبورد اینلاین
            welcome_text = (
                f"👋 سلام <b>{account['username']}</b>!\n\n"
                f"💎 موجودی: <b>{stats['balance']}</b> الماس\n"
                f"📊 کل دریافتی: <b>{stats['total_earned']}</b>\n\n"
                f"⚡ هر <b>{config.TOKENS_PER_SESSION} الماس</b> = <b>{config.SESSION_HOURS} ساعت</b> سلف‌بات\n"
                f"💰 قیمت هر الماس: <b>{token_price} تومان</b>\n\n"
                f"🎯 به <b>{config.BOT_NAME}</b> خوش آمدید!"
            )
            
            _bot.reply_to(message, welcome_text, reply_markup=main_menu_keyboard(is_owner))

            if message.chat.type == 'private':
                sponsors = getattr(config, 'SPONSORS', [])
                if sponsors:
                    sponsors_text = "🤝 <b>اسپانسرهای رسمی پروژه:</b>\n"
                    for sp in sponsors:
                        sponsors_text += f"🔸 @{sp['username']}\n"
                    sponsors_text += f"\n👑 <b>مالک و پشتیبانی:</b> @{config.OWNER_USERNAME}"
                    _bot.send_message(message.chat.id, sponsors_text)
        except Exception as e:
            print(f"❌ خطا در cmd_start: {e}")

    # ══════════════════════════════════════════════════════════════════════════
    # Callback Handler اصلی - مدیریت تمام دکمه‌ها
    # ══════════════════════════════════════════════════════════════════════════
    @_bot.callback_query_handler(func=lambda call: True)
    def callback_handler(call):
        try:
            data = call.data
            tg_id = call.from_user.id
            account = _get_account_cached(tg_id)
            
            if not account:
                return _bot.answer_callback_query(call.id, "⚠️ ابتدا /start بزنید", show_alert=True)
            
            owner_id = account["id"]
            is_owner = (tg_id == OWNER_TG_ID)
            
            # ─── منوی اصلی ──────────────────────────────────────────────
            if data == "main_menu":
                _bot.edit_message_text(
                    f"👋 سلام <b>{account['username']}</b>!\n\n"
                    f"💎 موجودی: <b>{db.get_balance(owner_id)}</b> الماس",
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    reply_markup=main_menu_keyboard(is_owner)
                )
                _bot.answer_callback_query(call.id)
            
            # ─── فعال‌سازی سلف ────────────────────────────────────────
            elif data == "activate_self":
                balance = db.get_balance(owner_id)
                cost = config.SELF_PRICE
                
                if balance >= cost:
                    db.deduct_balance(owner_id, cost)
                    db.set_setting(owner_id, "self_active", "1")
                    _bot.answer_callback_query(
                        call.id, 
                        f"✅ سلف فعال شد!\n💎 {cost} الماس کسر شد\n⏰ 2 ساعت فعال است",
                        show_alert=True
                    )
                else:
                    _bot.answer_callback_query(
                        call.id, 
                        f"❌ موجودی کافی نیست!\n💎 نیاز به {cost} الماس\n💰 موجودی: {balance}",
                        show_alert=True
                    )
            
            # ─── خاموش کردن سلف ───────────────────────────────────────
            elif data == "deactivate_self":
                db.set_setting(owner_id, "self_active", "0")
                _bot.answer_callback_query(call.id, "❌ سلف غیرفعال شد", show_alert=True)
            
            # ─── پنل سلف ──────────────────────────────────────────────
            elif data == "self_panel":
                _bot.edit_message_text(
                    "🔌 <b>پنل مدیریت سلف</b>\n\nگزینه مورد نظر را انتخاب کنید:",
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    reply_markup=self_panel_keyboard()
                )
                _bot.answer_callback_query(call.id)
            
            # ─── روشن کردن سلف ────────────────────────────────────────
            elif data == "self_on":
                db.set_setting(owner_id, "self_active", "1")
                _bot.answer_callback_query(call.id, "✅ سلف روشن شد", show_alert=True)
            
            # ─── خاموش کردن سلف ───────────────────────────────────────
            elif data == "self_off":
                db.set_setting(owner_id, "self_active", "0")
                _bot.answer_callback_query(call.id, "❌ سلف خاموش شد", show_alert=True)
            
            # ─── وضعیت سلف ────────────────────────────────────────────
            elif data == "self_status":
                active = db.get_setting(owner_id, "self_active", "0")
                status = "🟢 روشن" if active == "1" else "🔴 خاموش"
                _bot.answer_callback_query(call.id, f"📊 وضعیت سلف: {status}", show_alert=True)
            
            # ─── تنظیمات سلف ──────────────────────────────────────────
            elif data == "self_settings":
                _bot.edit_message_text(
                    "⚙️ <b>تنظیمات سلف</b>\n\nگزینه را انتخاب کنید:",
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    reply_markup=settings_keyboard()
                )
                _bot.answer_callback_query(call.id)
            
            # ─── Toggle تنظیمات ───────────────────────────────────────
            elif data.startswith("toggle_"):
                setting = data.replace("toggle_", "")
                current = db.get_setting(owner_id, setting, "0")
                new_val = "0" if current == "1" else "1"
                db.set_setting(owner_id, setting, new_val)
                
                status = "✅ روشن" if new_val == "1" else "❌ خاموش"
                setting_names = {
                    "secretary": "منشی", "anti_delete": "ضد حذف",
                    "anti_link": "ضد لینک", "auto_seen": "سین خودکار",
                    "auto_reaction": "ری‌اکشن", "private_lock": "قفل پیوی",
                    "save_media": "ذخیره مدیا", "clock_name": "ساعت نام"
                }
                name = setting_names.get(setting, setting)
                _bot.answer_callback_query(call.id, f"{name}: {status}", show_alert=True)
            
            # ─── زیرمجموعه‌گیری ───────────────────────────────────────
            elif data == "referrals":
                link = f"https://t.me/{BOT_USERNAME}?start=ref_{owner_id}"
                ref_count = db.get_referral_count(owner_id)
                bonus = config.REFERRAL_TOKENS
                
                _bot.answer_callback_query(
                    call.id,
                    f"🔗 لینک رفرال:\n{link}\n\n"
                    f"👥 تعداد: {ref_count}\n"
                    f"🎁 پاداش: {bonus} الماس",
                    show_alert=True
                )
            
            # ─── خرید الماس ───────────────────────────────────────────
            elif data == "buy_tokens":
                token_price = getattr(config, 'TOKEN_PRICE_TOMAN', 200)
                _bot.answer_callback_query(
                    call.id,
                    f"🛒 برای خرید الماس:\n"
                    f"💰 قیمت: {token_price} تومان هر الماس\n"
                    f"📩 به @{config.OWNER_USERNAME} پیام دهید",
                    show_alert=True
                )
            
            # ─── پروفایل کاربری ───────────────────────────────────────
            elif data == "user_profile":
                balance = db.get_balance(owner_id)
                stats = db.get_token_stats(owner_id)
                ref_count = db.get_referral_count(owner_id)
                
                profile_text = (
                    f"👤 <b>پروفایل کاربری</b>\n\n"
                    f" نام کاربری: {account['username']}\n"
                    f"🔹 آیدی: <code>{owner_id}</code>\n"
                    f"🔹 موجودی: {balance} الماس\n"
                    f"🔹 کل دریافتی: {stats['total_earned']} الماس\n"
                    f"🔹 زیرمجموعه: {ref_count} نفر"
                )
                
                _bot.answer_callback_query(call.id, profile_text, show_alert=True)
            
            # ─── پشتیبانی ─────────────────────────────────────────────
            elif data == "support":
                _bot.answer_callback_query(
                    call.id,
                    f"📞 پشتیبانی:\n"
                    f"👤 @{config.OWNER_USERNAME}",
                    show_alert=True
                )
            
            # ─── پنل مدیریت (فقط مالک) ────────────────────────────────
            elif data == "admin_panel":
                if not is_owner:
                    return _bot.answer_callback_query(call.id, "❌ دسترسی ندارید", show_alert=True)
                
                _bot.edit_message_text(
                    "🔧 <b>پنل مدیریت مالک</b>\n\nگزینه را انتخاب کنید:",
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    reply_markup=admin_panel_keyboard()
                )
                _bot.answer_callback_query(call.id)
            
            # ─── آمار کاربران (مالک) ──────────────────────────────────
            elif data == "admin_users":
                if not is_owner:
                    return _bot.answer_callback_query(call.id, "❌ فقط مالک", show_alert=True)
                
                accounts = db.get_all_accounts()[:30]
                text = f"👥 <b>کاربران ({len(accounts)} نفر):</b>\n\n"
                for acc in accounts:
                    bal = db.get_balance(acc["id"])
                    text += f"• {acc['username']} — 💎{bal}\n"
                
                _bot.answer_callback_query(call.id, text, show_alert=True)
            
            # ─── سایر دکمه‌های مدیریت ─────────────────────────────────
            elif data in ["admin_channels", "admin_wc", "admin_lottery", "admin_transfer", "admin_give"]:
                if not is_owner:
                    return _bot.answer_callback_query(call.id, "❌ فقط مالک", show_alert=True)
                
                _bot.answer_callback_query(call.id, "️ این بخش در حال توسعه است", show_alert=True)
            
            else:
                _bot.answer_callback_query(call.id, "❌ گزینه نامعتبر")
                
        except Exception as e:
            print(f"❌ خطا در callback: {e}")
            _bot.answer_callback_query(call.id, f"❌ خطا: {str(e)[:100]}", show_alert=True)

    def _process_referral_async(referrer_id, tg_id):
        try:
            if db.process_referral(referrer_id, tg_id):
                referrer_tg = db.get_telegram_id_by_owner(referrer_id)
                if referrer_tg and _bot:
                    _bot.send_message(referrer_tg, 
                        f"🎉 یک نفر با لینک شما عضو شد!\n"
                        f"<b>+{config.REFERRAL_TOKENS} الماس</b> دریافت کردید 💎")
        except Exception as e:
            print(f"❌ خطا در رفرال: {e}")

    # ══════════════════════════════════════════════════════════════════════════
    # Polling
    # ══════════════════════════════════════════════════════════════════════════
    def _polling_loop():
        while True:
            try:
                _bot.infinity_polling(
                    timeout=20,
                    long_polling_timeout=15,
                    restart_on_change=False,
                    skip_pending=True
                )
            except Exception as e:
                if "409" in str(e):
                    time.sleep(10)
                    try:
                        _bot.delete_webhook(drop_pending_updates=True)
                    except:
                        pass
                else:
                    print(f"⚠️ خطای polling: {e}")
                    time.sleep(3)

    t = threading.Thread(target=_polling_loop, daemon=True)
    t.start()
    print(f"✅ ربات الماس @{BOT_USERNAME} استارت شد")
