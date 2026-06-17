import asyncio
import re
import os
import datetime
import random
import threading
import time
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.functions.messages import SendReactionRequest
from telethon.tl.types import ReactionEmoji
from telethon.errors import FloodWaitError
import database as db
import config
from texts import ENEMY_REPLIES, FRIEND_REPLIES


# ══════════════════════════════════════════════════════════════════════════════
# 🎨 فونت‌ها
# ══════════════════════════════════════════════════════════════════════════════
FONTS = {
    "0": lambda t: t,
    "1": lambda t: _convert_font(t, "𝗔𝗕𝗖𝗗𝗘𝗙𝗚𝗛𝗜𝗝𝗞𝗟𝗠𝗡𝗢𝗣𝗤𝗥𝗦𝗧𝗨𝗩𝗪𝗫𝗬𝗭𝗮𝗯𝗰𝗱𝗲𝗳𝗴𝗵𝗶𝗷𝗸𝗹𝗺𝗻𝗼𝗽𝗾𝗿𝘀𝘁𝘂𝘃𝘄𝘅𝘆𝘇"),
    "2": lambda t: _convert_font(t, "𝘈𝘉𝘊𝘋𝘌𝘍𝘎𝘏𝘐𝘑𝘒𝘓𝘔𝘕𝘖𝘗𝘘𝘙𝘚𝘛𝘜𝘝𝘞𝘟𝘠𝘡𝘢𝘣𝘤𝘥𝘦𝘧𝘨𝘩𝘪𝘫𝘬𝘭𝘮𝘯𝘰𝘱𝘲𝘳𝘴𝘵𝘶𝘷𝘸𝘹𝘺𝘻"),
    "3": lambda t: _convert_font(t, "𝙰𝙱𝙲𝙳𝙴𝙵𝙶𝙷𝙸𝙹𝙺𝙻𝙼𝙽𝙾𝙿𝚀𝚁𝚂𝚃𝚄𝚅𝚆𝚇𝚈𝚉𝚊𝚋𝚌𝚍𝚎𝚏𝚐𝚑𝚒𝚓𝚔𝚕𝚖𝚗𝚘𝚙𝚚𝚛𝚜𝚝𝚞𝚟𝚠𝚡𝚢𝚣"),
    "4": lambda t: _convert_font(t, "ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ"),
    "5": lambda t: _convert_font(t, "𝐀𝐁𝐂𝐃𝐄𝐅𝐆𝐇𝐈𝐉𝐊𝐋𝐌𝐍𝐎𝐏𝐐𝐑𝐒𝐓𝐔𝐕𝐖𝐗𝐘𝐙𝐚𝐛𝐜𝐝𝐞𝐟𝐠𝐡𝐢𝐣𝐤𝐥𝐦𝐧𝐨𝐩𝐪𝐫𝐬𝐭𝐮𝐯𝐰𝐱𝐲𝐳"),
    "6": lambda t: _convert_font(t, "𝒜ℬ𝒞𝒟ℰℱ𝒢ℋℐ𝒥𝒦ℒℳ𝒩𝒪𝒫𝒬ℛ𝒮𝒯𝒰𝒱𝒲𝒳𝒴𝒵𝒶𝒷𝒸𝒹ℯ𝒻ℊ𝒽𝒾𝒿𝓀𝓁𝓂𝓃ℴ𝓅𝓆𝓇𝓈𝓉𝓊𝓋𝓌𝓍𝓎𝓏"),
    "7": lambda t: "".join(c + "\u0336" for c in t),
    "8": lambda t: "".join(c + "\u0332" for c in t),
}
_ALPHA = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"

LINK_PATTERN = re.compile(
    r"(https?://\S+|t\.me/\S+|telegram\.me/\S+|www\.\S+)", re.IGNORECASE
)


# ══════════════════════════════════════════════════════════════════════════════
# ⏱️ محدودیت زمانی + ردیابی پیام‌های پاسخ داده شده
# ══════════════════════════════════════════════════════════════════════════════
_last_secretary_reply = {}  # {chat_id: timestamp} - برای منشی
_last_friend_reply = {}     # {user_id: timestamp} - برای دوست (cooldown)

# ✅ ردیابی پیام‌های پاسخ داده شده (هر پیام = یک جواب)
_replied_messages = set()  # مجموعه msg_id های پاسخ داده شده
_replied_lock = threading.Lock()


def _mark_replied(msg_id: int):
    """علامت‌گذاری پیام به عنوان پاسخ داده شده"""
    with _replied_lock:
        _replied_messages.add(msg_id)
        # پاک کردن پیام‌های قدیمی (حداکثر 10000 تا)
        if len(_replied_messages) > 10000:
            # حذف 5000 تای قدیمی
            to_remove = list(_replied_messages)[:5000]
            for m in to_remove:
                _replied_messages.discard(m)


def _is_replied(msg_id: int) -> bool:
    """بررسی اینکه آیا پیام قبلاً پاسخ داده شده"""
    with _replied_lock:
        return msg_id in _replied_messages


SECRETARY_COOLDOWN = 86400  # 24 ساعت
FRIEND_COOLDOWN = 3600      # 1 ساعت


# ══════════════════════════════════════════════════════════════════════════════
# 🔧 توابع کمکی
# ══════════════════════════════════════════════════════════════════════════════
def _convert_font(text, chars):
    result = []
    for ch in text:
        if ch in _ALPHA:
            result.append(chars[_ALPHA.index(ch)])
        else:
            result.append(ch)
    return "".join(result)


def _apply_font(owner_id, text):
    font_id = db.get_setting(owner_id, "font", "0")
    fn = FONTS.get(font_id, FONTS["0"])
    return fn(text)


def persian_time():
    iran_tz = datetime.timezone(datetime.timedelta(hours=3, minutes=30))
    now = datetime.datetime.now(iran_tz)
    return f"{now.hour:02d}:{now.minute:02d}"


# ══════════════════════════════════════════════════════════════════════════════
# 🤖 BotManager
# ══════════════════════════════════════════════════════════════════════════════
class BotManager:
    def __init__(self):
        self._bots = {}
        self._timers = {}

    def is_running(self, owner_id: int) -> bool:
        entry = self._bots.get(owner_id)
        return bool(entry and not entry["task"].done())

    def get_client(self, owner_id: int):
        entry = self._bots.get(owner_id)
        return entry["client"] if entry else None

    def _cancel_timer(self, owner_id: int):
        t = self._timers.pop(owner_id, None)
        if t:
            t.cancel()

    def start(self, owner_id: int, loop: asyncio.AbstractEventLoop, check_tokens: bool = True) -> bool:
        if self.is_running(owner_id):
            self.stop(owner_id)

        account = db.get_account(owner_id)
        is_owner = (account and account.get("telegram_user_id") == config.OWNER_TG_ID)

        tokens_deducted = 0
        if check_tokens and not is_owner:
            balance = db.get_balance(owner_id)
            if balance < config.SELF_PRICE:
                return False
            db.deduct_balance(owner_id, config.SELF_PRICE)
            tokens_deducted = config.SELF_PRICE

        entry = {
            "client": None, "task": None, "stop": False,
            "is_owner": is_owner, "tokens_deducted": tokens_deducted,
            "owner_refunded": False
        }
        self._bots[owner_id] = entry
        task = asyncio.run_coroutine_threadsafe(self._run_bot(owner_id), loop)
        entry["task"] = task

        if not is_owner:
            self._cancel_timer(owner_id)
            timer = threading.Timer(7200, self.stop, args=[owner_id])  # 2 ساعت
            timer.daemon = True
            timer.start()
            self._timers[owner_id] = timer

        return True

    def stop(self, owner_id: int):
        self._cancel_timer(owner_id)
        entry = self._bots.get(owner_id)
        if not entry:
            return
        entry["stop"] = True
        cl = entry.get("client")
        if cl and cl.is_connected():
            try:
                asyncio.run_coroutine_threadsafe(cl.disconnect(), asyncio.get_event_loop())
            except Exception:
                pass

    def stop_all(self):
        for oid in list(self._bots.keys()):
            self.stop(oid)

    async def _run_bot(self, owner_id: int):
        entry = self._bots[owner_id]
        retry_delay = 5

        while not entry["stop"]:
            try:
                session_data = db.get_session(owner_id)
                if not session_data:
                    print(f"⚠️ [{owner_id}] سشن یافت نشد")
                    await asyncio.sleep(10)
                    continue

                cl = TelegramClient(
                    StringSession(session_data),
                    config.API_ID,
                    config.API_HASH,
                )
                entry["client"] = cl
                _register_handlers(cl, owner_id, entry)

                await cl.start()
                me = await cl.get_me()
                print(f"✅ [{owner_id}] بات راه‌اندازی شد — {me.first_name}")

                db.save_telegram_user_id(owner_id, me.id)

                is_now_owner = (me.id == config.OWNER_TG_ID)

                if is_now_owner:
                    entry["is_owner"] = True
                    self._cancel_timer(owner_id)
                    if not entry.get("owner_refunded") and entry.get("tokens_deducted", 0) > 0:
                        db.add_balance(owner_id, entry["tokens_deducted"])
                        entry["owner_refunded"] = True
                        print(f"👑 [{owner_id}] مالک — {entry['tokens_deducted']} الماس برگشت")

                clock_task = asyncio.ensure_future(_clock_loop(cl, owner_id))
                sched_task = asyncio.ensure_future(_scheduler_loop(cl, owner_id))

                retry_delay = 5
                await cl.run_until_disconnected()

                clock_task.cancel()
                sched_task.cancel()

                if entry["stop"]:
                    break
                print(f"⚠️ [{owner_id}] اتصال قطع شد، اتصال مجدد...")

            except Exception as e:
                print(f"❌ [{owner_id}] خطا: {e}")
                if entry["stop"]:
                    break

            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 120)

        print(f"🛑 [{owner_id}] بات متوقف شد.")


bot_manager = BotManager()


# ══════════════════════════════════════════════════════════════════════════════
# 📝 ثبت هندلرها
# ══════════════════════════════════════════════════════════════════════════════
def _register_handlers(cl: TelegramClient, owner_id: int, entry: dict):
    _me_info = {"id": None, "username": None}

    async def get_me_cached():
        if _me_info["id"] is None:
            me = await cl.get_me()
            _me_info["id"] = me.id
            _me_info["username"] = (me.username or "").lower()
        return _me_info["id"], _me_info["username"]

    @cl.on(events.NewMessage(incoming=True))
    async def on_incoming(event):
        try:
            msg = event.message
            sender = await event.get_sender()
            chat = await event.get_chat()
            sender_id = getattr(sender, "id", 0)
            chat_id = getattr(chat, "id", 0)
            text = msg.text or ""
            msg_id = msg.id

            is_private = event.is_private
            is_tagged = False

            # بررسی تگ در گروه‌ها
            if not is_private:
                my_id, my_username = await get_me_cached()

                if msg.entities:
                    for entity in msg.entities:
                        if hasattr(entity, 'user_id') and entity.user_id == my_id:
                            is_tagged = True
                            break

                if not is_tagged:
                    try:
                        replied_msg = await event.get_reply_message()
                        if replied_msg and replied_msg.sender_id == my_id:
                            is_tagged = True
                    except:
                        pass

                if not is_tagged and my_username and my_username in text.lower():
                    is_tagged = True

            # در گروه اگر تگ نشده، فقط سین و ذخیره مدیا
            if not is_private and not is_tagged:
                if db.get_setting(owner_id, "auto_seen", "0") == "1":
                    try:
                        await cl.send_read_acknowledge(chat_id, msg)
                    except:
                        pass

                if db.get_setting(owner_id, "save_media", "0") == "1" and msg.media:
                    try:
                        media_dir = f"saved_media/{owner_id}"
                        os.makedirs(media_dir, exist_ok=True)
                        await cl.download_media(msg, file=media_dir + "/")
                    except:
                        pass
                return

            # ✅ بررسی سایلنت
            if db.is_silent_chat(owner_id, chat_id) or db.is_silent_user(owner_id, sender_id):
                return

            # ذخیره مدیا
            if db.get_setting(owner_id, "save_media", "0") == "1" and msg.media:
                try:
                    media_dir = f"saved_media/{owner_id}"
                    os.makedirs(media_dir, exist_ok=True)
                    await cl.download_media(msg, file=media_dir + "/")
                except:
                    pass

            # مدیای تایمدار
            if is_private and msg.media:
                ttl = getattr(msg.media, "ttl_seconds", None)
                if ttl:
                    try:
                        my_id, _ = await get_me_cached()
                        media_dir = f"saved_media/{owner_id}"
                        os.makedirs(media_dir, exist_ok=True)
                        path = await cl.download_media(msg, file=media_dir + "/")
                        if path:
                            sender_name = getattr(sender, 'first_name', str(getattr(sender, "id", "?")))
                            sender_id_val = getattr(sender, "id", "?")
                            await cl.send_file(my_id, path,
                                caption=f"📥 مدیای تایمدار ذخیره شد\n👤 از: {sender_name} ({sender_id_val})")
                    except:
                        pass

            # سین خودکار
            if db.get_setting(owner_id, "auto_seen", "0") == "1":
                try:
                    await cl.send_read_acknowledge(chat_id, msg)
                except:
                    pass

            # ═══════════════════════════════════════════════════════════════
            # 🆕 منشی (فقط پیوی - 24 ساعت)
            # ═══════════════════════════════════════════════════════════════
            if db.get_setting(owner_id, "secretary", "0") == "1" and is_private:
                now = time.time()
                last_reply = _last_secretary_reply.get(chat_id, 0)

                if now - last_reply >= SECRETARY_COOLDOWN:
                    sec_msg = db.get_setting(owner_id, "secretary_msg", "در دسترس نیستم")
                    try:
                        await event.reply(f"🤖 منشی:\n{sec_msg}")
                        _last_secretary_reply[chat_id] = now
                    except:
                        pass
                return

            # ═══════════════════════════════════════════════════════════════
            # 🆕 پاسخ به دوست (هر پیام = یک جواب)
            # ═══════════════════════════════════════════════════════════════
            if db.get_setting(owner_id, "friend_reply", "0") == "1" and is_private:
                if db.is_friend(owner_id, sender_id):
                    # ✅ بررسی اینکه این پیام قبلاً پاسخ داده شده یا نه
                    if not _is_replied(msg_id):
                        now = time.time()
                        last_reply = _last_friend_reply.get(sender_id, 0)
                        
                        # بررسی cooldown (1 ساعت بین هر کاربر)
                        if now - last_reply >= FRIEND_COOLDOWN:
                            try:
                                reply_text = random.choice(FRIEND_REPLIES)
                                await event.reply(reply_text)
                                _last_friend_reply[sender_id] = now
                                _mark_replied(msg_id)  # ✅ علامت‌گذاری
                            except Exception as e:
                                print(f"⚠️ خطا در پاسخ به دوست: {e}")

            # ═══════════════════════════════════════════════════════════════
            # 🆕 پاسخ به دشمن (هر پیام = یک جواب)
            # ═══════════════════════════════════════════════════════════════
            if db.get_setting(owner_id, "enemy_reply", "0") == "1":
                if db.is_enemy(owner_id, sender_id):
                    # ✅ بررسی اینکه این پیام قبلاً پاسخ داده شده یا نه
                    if not _is_replied(msg_id):
                        try:
                            reply_text = random.choice(ENEMY_REPLIES)
                            await event.reply(reply_text)
                            _mark_replied(msg_id)  # ✅ علامت‌گذاری
                        except Exception as e:
                            print(f"⚠️ خطا در پاسخ به دشمن: {e}")

            # ری‌اکشن خودکار
            if db.get_setting(owner_id, "auto_reaction", "0") == "1":
                emoji = db.get_setting(owner_id, "reaction_emoji", "❤️")
                try:
                    await cl(SendReactionRequest(
                        peer=chat_id, msg_id=msg.id,
                        reaction=[ReactionEmoji(emoticon=emoji)],
                        big=False, add_to_recent=True
                    ))
                except Exception as e:
                    print(f"⚠️ خطا در ری‌اکشن: {e}")

            # ضد لینک (فقط پیوی)
            if db.get_setting(owner_id, "anti_link", "0") == "1" and is_private and LINK_PATTERN.search(text):
                try:
                    await msg.delete()
                except:
                    pass

            # قفل پیوی
            if db.get_setting(owner_id, "private_lock", "0") == "1" and is_private:
                try:
                    await msg.delete()
                except:
                    pass

        except Exception as e:
            print(f"⚠️ خطا در on_incoming: {e}")

    @cl.on(events.NewMessage(outgoing=True))
    async def on_outgoing(event):
        try:
            text = event.raw_text.strip()

            # دستورات همیشه فعال
            if text == "سلف روشن":
                db.set_setting(owner_id, "self_active", "1")
                await _safe_edit(event, owner_id, "✅ سلف روشن شد")
                return
            if text == "سلف خاموش":
                db.set_setting(owner_id, "self_active", "0")
                await _safe_edit(event, owner_id, "❌ سلف خاموش شد")
                return

            config_commands = [
                "منشی روشن", "منشی خاموش", "پیام منشی",
                "ضد حذف روشن", "ضد حذف خاموش",
                "ضد لینک روشن", "ضد لینک خاموش",
                "قفل پیوی روشن", "قفل پیوی خاموش",
                "سین خودکار روشن", "سین خودکار خاموش",
                "ری‌اکشن روشن", "ری‌اکشن خاموش",
                "ذخیره مدیا روشن", "ذخیره مدیا خاموش",
                "ساعت نام روشن", "ساعت نام خاموش",
                "ساعت بیو روشن", "ساعت بیو خاموش",
                "پاسخ دشمن روشن", "پاسخ دشمن خاموش",
                "پاسخ دوست روشن", "پاسخ دوست خاموش",
                "تنظیم دشمن", "حذف دشمن", "نمایش لیست دشمن", "پاک کردن لیست دشمن",
                "تنظیم دوست", "حذف دوست", "نمایش لیست دوست", "پاک کردن لیست دوست",
                "سایلنت چت روشن", "سایلنت چت خاموش", "سایلنت کاربر", "لغو سایلنت کاربر",
                "فونت ", "لیست فونت",
                "ذخیره ", "ارسال ذخیره ",
                "ارسال زمان‌بندی ",
                "وضعیت", "راهنما", "help",
            ]

            is_config_command = any(text.startswith(cmd) or text == cmd for cmd in config_commands)

            if not is_config_command and db.get_setting(owner_id, "self_active", "0") != "1":
                return

            await _handle_command(cl, event, text, owner_id)

        except Exception as e:
            print(f"⚠️ خطا در on_outgoing: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# 🎯 پردازش دستورات
# ══════════════════════════════════════════════════════════════════════════════
async def _handle_command(cl, event, text, owner_id):
    def gs(key, default=None):
        return db.get_setting(owner_id, key, default)

    def ss(key, value):
        db.set_setting(owner_id, key, value)

    async def edit(t):
        await _safe_edit(event, owner_id, t)

    # ─── منشی ────────────────────────────────────────────────────────────────
    if text == "منشی روشن":
        ss("secretary", "1"); await edit("🤖 منشی روشن شد\n💡 هر کاربر هر 24 ساعت یک بار پاسخ می‌گیرد")
    elif text == "منشی خاموش":
        ss("secretary", "0"); await edit("🤖 منشی خاموش شد")
    elif text.startswith("پیام منشی "):
        ss("secretary_msg", text[len("پیام منشی "):].strip())
        await edit("✅ پیام منشی تنظیم شد")

    # ─── ضد حذف ──────────────────────────────────────────────────────────────
    elif text == "ضد حذف روشن":
        ss("anti_delete", "1"); await edit("🛡️ ضد حذف روشن شد")
    elif text == "ضد حذف خاموش":
        ss("anti_delete", "0"); await edit("🛡️ ضد حذف خاموش شد")

    # ─── ضد لینک ─────────────────────────────────────────────────────────────
    elif text == "ضد لینک روشن":
        ss("anti_link", "1"); await edit("🔗 ضد لینک روشن شد")
    elif text == "ضد لینک خاموش":
        ss("anti_link", "0"); await edit("🔗 ضد لینک خاموش شد")

    # ─── قفل پیوی ────────────────────────────────────────────────────────────
    elif text == "قفل پیوی روشن":
        ss("private_lock", "1"); await edit("🔒 قفل پیوی روشن شد")
    elif text == "قفل پیوی خاموش":
        ss("private_lock", "0"); await edit("🔓 قفل پیوی خاموش شد")

    # ─── سین خودکار ──────────────────────────────────────────────────────────
    elif text == "سین خودکار روشن":
        ss("auto_seen", "1"); await edit("👁️ سین خودکار روشن شد")
    elif text == "سین خودکار خاموش":
        ss("auto_seen", "0"); await edit("👁️ سین خودکار خاموش شد")

    # ─── ری‌اکشن ─────────────────────────────────────────────────────────────
    elif text == "ری‌اکشن روشن":
        ss("auto_reaction", "1"); await edit("❤️ ری‌اکشن روشن شد")
    elif text == "ری‌اکشن خاموش":
        ss("auto_reaction", "0"); await edit("❤️ ری‌اکشن خاموش شد")
    elif text.startswith("ری‌اکشن "):
        emoji = text[len("ری‌اکشن "):].strip()
        ss("reaction_emoji", emoji); await edit(f"✅ ری‌اکشن: {emoji}")

    # ─── ذخیره مدیا ──────────────────────────────────────────────────────────
    elif text == "ذخیره مدیا روشن":
        os.makedirs(f"saved_media/{owner_id}", exist_ok=True)
        ss("save_media", "1"); await edit("💾 ذخیره مدیا روشن شد")
    elif text == "ذخیره مدیا خاموش":
        ss("save_media", "0"); await edit("💾 ذخیره مدیا خاموش شد")

    # ─── 🆕 پاسخ دشمن ────────────────────────────────────────────────────────
    elif text == "پاسخ دشمن روشن":
        ss("enemy_reply", "1"); await edit("⚔️ پاسخ خودکار به دشمن روشن شد\n💡 هر پیام دشمن = یک جواب")
    elif text == "پاسخ دشمن خاموش":
        ss("enemy_reply", "0"); await edit("⚔️ پاسخ خودکار به دشمن خاموش شد")

    # ─── 🆕 پاسخ دوست ────────────────────────────────────────────────────────
    elif text == "پاسخ دوست روشن":
        ss("friend_reply", "1"); await edit("💚 پاسخ خودکار به دوست روشن شد\n💡 هر پیام دوست = یک جواب\n💡 هر کاربر هر 1 ساعت یک بار پاسخ می‌گیرد")
    elif text == "پاسخ دوست خاموش":
        ss("friend_reply", "0"); await edit("💚 پاسخ خودکار به دوست خاموش شد")

    # ─── 🆕 دشمن ─────────────────────────────────────────────────────────────
    elif text.startswith("تنظیم دشمن"):
        target = await _resolve_target(event, text.split())
        if target:
            db.add_enemy(owner_id, target["id"], target.get("username"), target.get("name"))
            await edit(f"🔴 {target.get('name', target['id'])} به لیست دشمن اضافه شد.")
        else:
            await edit("❗ روی پیام کاربر ریپلای کن یا آیدی عددی بنویس.")

    elif text.startswith("حذف دشمن"):
        target = await _resolve_target(event, text.split())
        if target:
            removed = db.remove_enemy(owner_id, target["id"])
            await edit("✅ از لیست دشمن حذف شد." if removed else "❗ در لیست نبود.")
        else:
            await edit("❗ روی پیام کاربر ریپلای کن یا آیدی عددی بنویس.")

    elif text == "نمایش لیست دشمن":
        enemies = db.get_enemies(owner_id)
        if not enemies:
            await edit("📋 لیست دشمن خالی است.")
        else:
            lines = [f"🔴 لیست دشمن ({len(enemies)} نفر):\n"]
            for e in enemies:
                lines.append(f"• {e['name'] or e['username'] or e['user_id']} — `{e['user_id']}`")
            await edit("\n".join(lines))

    elif text == "پاک کردن لیست دشمن":
        db.clear_enemies(owner_id)
        await edit("🗑️ لیست دشمن پاک شد.")

    # ─── 🆕 دوست ─────────────────────────────────────────────────────────────
    elif text.startswith("تنظیم دوست"):
        target = await _resolve_target(event, text.split())
        if target:
            db.add_friend(owner_id, target["id"], target.get("username"), target.get("name"))
            await edit(f"💚 {target.get('name', target['id'])} به لیست دوست اضافه شد.")
        else:
            await edit("❗ روی پیام کاربر ریپلای کن یا آیدی عددی بنویس.")

    elif text.startswith("حذف دوست"):
        target = await _resolve_target(event, text.split())
        if target:
            removed = db.remove_friend(owner_id, target["id"])
            await edit("✅ از لیست دوست حذف شد." if removed else "❗ در لیست نبود.")
        else:
            await edit("❗ روی پیام کاربر ریپلای کن یا آیدی عددی بنویس.")

    elif text == "نمایش لیست دوست":
        friends = db.get_friends(owner_id)
        if not friends:
            await edit("📋 لیست دوست خالی است.")
        else:
            lines = [f"💚 لیست دوست ({len(friends)} نفر):\n"]
            for f in friends:
                lines.append(f"• {f['name'] or f['username'] or f['user_id']} — `{f['user_id']}`")
            await edit("\n".join(lines))

    elif text == "پاک کردن لیست دوست":
        db.clear_friends(owner_id)
        await edit("🗑️ لیست دوست پاک شد.")

    # ─── 🆕 سایلنت ───────────────────────────────────────────────────────────
    elif text == "سایلنت چت روشن":
        chat = await event.get_chat()
        db.add_silent_chat(owner_id, chat.id); await edit("🔇 این چت سایلنت شد.")
    elif text == "سایلنت چت خاموش":
        chat = await event.get_chat()
        db.remove_silent_chat(owner_id, chat.id); await edit("🔔 سایلنت این چت برداشته شد.")
    elif text.startswith("سایلنت کاربر "):
        uid = int(text.split()[-1])
        db.add_silent_user(owner_id, uid); await edit(f"🔇 کاربر {uid} سایلنت شد.")
    elif text.startswith("لغو سایلنت کاربر "):
        uid = int(text.split()[-1])
        db.remove_silent_user(owner_id, uid); await edit(f"🔔 سایلنت کاربر {uid} برداشته شد.")

    # ─── فونت ────────────────────────────────────────────────────────────────
    elif text.startswith("فونت "):
        font_id = text.split()[-1]
        if font_id in FONTS:
            ss("font", font_id); await edit(f"🔤 فونت {font_id} انتخاب شد")
        else:
            await edit("❗ شماره فونت باید بین ۰ تا ۸ باشد")
    elif text == "لیست فونت":
        samples = {
            "0": "متن عادی", "1": "𝗕𝗼𝗹𝗱", "2": "𝘐𝘵𝘢𝘭𝘪𝘤",
            "3": "𝙼𝚘𝚗𝚘", "4": "Ｆｕｌｌ", "5": "𝐒𝐞𝐫𝐢𝐟",
            "6": "𝒮𝒸𝓇𝒾𝓅𝓉", "7": "S̶t̶r̶i̶k̶e̶", "8": "U̲n̲d̲e̲r̲"
        }
        lines = ["📝 فونت‌های موجود:\n"] + [f"فونت {k} — {v}" for k, v in samples.items()]
        lines.append("\n💡 فونت روی ساعت و پیام‌ها اعمال می‌شود!")
        await edit("\n".join(lines))

    # ─── ساعت ────────────────────────────────────────────────────────────────
    elif text == "ساعت نام روشن":
        ss("clock_name", "1"); await edit("⏰ ساعت نام روشن شد")
    elif text == "ساعت نام خاموش":
        ss("clock_name", "0"); await edit("⏰ ساعت نام خاموش شد")
    elif text == "ساعت بیو روشن":
        ss("clock_bio", "1"); await edit("⏰ ساعت بیو روشن شد")
    elif text == "ساعت بیو خاموش":
        ss("clock_bio", "0"); await edit("⏰ ساعت بیو خاموش شد")

    # ─── 🆕 ذخیره پیام ───────────────────────────────────────────────────────
    elif text.startswith("ذخیره "):
        parts = text.split()
        if len(parts) >= 2 and parts[1].isdigit():
            slot = int(parts[1])
            if 1 <= slot <= 10:
                replied = await event.get_reply_message()
                if replied and replied.text:
                    db.save_message_slot(owner_id, slot, replied.text)
                    await edit(f"💾 پیام در اسلات {slot} ذخیره شد.")
                else:
                    await edit("❗ روی پیام متنی ریپلای کن.")
            else:
                await edit("❗ اسلات باید بین ۱ تا ۱۰ باشد.")
        else:
            await edit("❗ فرمت: ذخیره [1-10]")

    elif text.startswith("ارسال ذخیره "):
        parts = text.split()
        if len(parts) >= 3 and parts[2].isdigit():
            slot = int(parts[2])
            saved = db.get_message_slot(owner_id, slot)
            if saved:
                chat = await event.get_chat()
                await cl.send_message(chat.id, saved["content"])
                await event.message.delete()
            else:
                await edit(f"❗ اسلات {slot} خالی است.")
        else:
            await edit("❗ فرمت: ارسال ذخیره [1-10]")

    # ─── 🆕 ارسال زمان‌بندی‌شده ──────────────────────────────────────────────
    elif text.startswith("ارسال زمان‌بندی "):
        m = re.match(r"^ارسال زمان‌بندی (\d{4}-\d{2}-\d{2} \d{2}:\d{2}) (.+)$", text, re.DOTALL)
        if m:
            chat = await event.get_chat()
            db.add_scheduled_message(owner_id, chat.id, m.group(2), m.group(1) + ":00")
            await edit(f"📅 پیام در {m.group(1)} ارسال خواهد شد.")
        else:
            await edit("❗ فرمت: ارسال زمان‌بندی [YYYY-MM-DD HH:MM] متن")

    # ─── وضعیت ───────────────────────────────────────────────────────────────
    elif text == "وضعیت":
        status_map = {
            "self_active": "سلف‌بات", "secretary": "منشی",
            "anti_delete": "ضد حذف", "anti_link": "ضد لینک",
            "auto_seen": "سین خودکار", "auto_reaction": "ری‌اکشن",
            "private_lock": "قفل پیوی", "save_media": "ذخیره مدیا",
            "clock_name": "ساعت نام", "clock_bio": "ساعت بیو",
            "enemy_reply": "پاسخ دشمن", "friend_reply": "پاسخ دوست",
        }
        lines = [f"📊 وضعیت {config.BOT_NAME}\n"]
        for key, label in status_map.items():
            icon = "✅" if gs(key) == "1" else "❌"
            lines.append(f"{icon} {label}")
        lines.append(f"\n🔤 فونت: {gs('font', '0')}")
        lines.append(f"🔴 دشمن: {len(db.get_enemies(owner_id))} نفر")
        lines.append(f"💚 دوست: {len(db.get_friends(owner_id))} نفر")
        await edit("\n".join(lines))

    # ─── راهنما ──────────────────────────────────────────────────────────────
    elif text in ("راهنما", "help"):
        await edit(_help_text())


# ══════════════════════════════════════════════════════════════════════════════
# 🔧 توابع کمکی
# ══════════════════════════════════════════════════════════════════════════════
async def _safe_edit(event, owner_id, text):
    try:
        fn = FONTS.get(db.get_setting(owner_id, "font", "0"), FONTS["0"])
        await event.edit(fn(text))
    except FloodWaitError as e:
        await asyncio.sleep(e.seconds + 1)
    except Exception:
        pass


async def _resolve_target(event, parts):
    replied = await event.get_reply_message()
    if replied:
        sender = await replied.get_sender()
        if sender:
            return {
                "id": sender.id,
                "username": getattr(sender, "username", None),
                "name": getattr(sender, "first_name", str(sender.id)),
            }
    for p in parts[1:]:
        if p.lstrip("-").isdigit():
            return {"id": int(p), "username": None, "name": p}
    return None


# ══════════════════════════════════════════════════════════════════════════════
# ⏰ حلقه ساعت
# ══════════════════════════════════════════════════════════════════════════════
async def _clock_loop(cl, owner_id):
    last_updated = ""

    while True:
        try:
            now = datetime.datetime.now()
            seconds_until_next = 60 - now.second

            if seconds_until_next == 0:
                seconds_until_next = 60

            await asyncio.sleep(seconds_until_next)

            time_str = persian_time()

            if time_str != last_updated:
                font_id = db.get_setting(owner_id, "font", "0")
                fn = FONTS.get(font_id, FONTS["0"])
                styled_time = fn(time_str)

                if db.get_setting(owner_id, "clock_name", "0") == "1":
                    try:
                        await cl(UpdateProfileRequest(last_name=styled_time[:64]))
                    except FloodWaitError as e:
                        await asyncio.sleep(e.seconds + 1)
                    except:
                        pass

                if db.get_setting(owner_id, "clock_bio", "0") == "1":
                    try:
                        await cl(UpdateProfileRequest(about=f"⏰ {styled_time}"[:70]))
                    except FloodWaitError as e:
                        await asyncio.sleep(e.seconds + 1)
                    except:
                        pass

                last_updated = time_str

        except asyncio.CancelledError:
            break
        except Exception:
            await asyncio.sleep(1)


# ══════════════════════════════════════════════════════════════════════════════
# 🆕 حلقه ارسال زمان‌بندی‌شده
# ══════════════════════════════════════════════════════════════════════════════
async def _scheduler_loop(cl, owner_id):
    while True:
        try:
            for p in db.get_pending_scheduled(owner_id):
                try:
                    await cl.send_message(p["chat_id"], p["message"])
                    db.mark_scheduled_sent(p["id"])
                except Exception:
                    pass
        except Exception:
            pass
        await asyncio.sleep(30)


# ══════════════════════════════════════════════════════════════════════════════
# 📖 راهنما
# ══════════════════════════════════════════════════════════════════════════════
def _help_text():
    return f"""📖 راهنمای {config.BOT_NAME}

🔹 اصلی:
• سلف روشن / سلف خاموش
• وضعیت

🔹 منشی:
• منشی روشن/خاموش
• پیام منشی [متن]
💡 هر کاربر هر 24 ساعت یک بار پاسخ می‌گیرد

🔹 لیست‌ها:
• تنظیم دشمن / حذف دشمن [ریپلای یا آیدی]
• نمایش لیست دشمن / پاک کردن لیست دشمن
• تنظیم دوست / حذف دوست
• نمایش لیست دوست / پاک کردن لیست دوست

🔹 پاسخ خودکار:
• پاسخ دشمن روشن/خاموش
• پاسخ دوست روشن/خاموش
💡 هر پیام = یک جواب (بدون تکرار)
💡 پاسخ به دوست: هر 1 ساعت یک بار

🔹 امنیت:
• ضد حذف روشن/خاموش
• ضد لینک روشن/خاموش
• قفل پیوی روشن/خاموش

🔹 اتوماسیون:
• سین خودکار روشن/خاموش
• ری‌اکشن روشن/خاموش / ری‌اکشن [ایموجی]
• ذخیره مدیا روشن/خاموش
• ساعت نام روشن/خاموش
• ساعت بیو روشن/خاموش

🔹 سایلنت:
• سایلنت چت روشن/خاموش
• سایلنت کاربر [آیدی]
• لغو سایلنت کاربر [آیدی]

🔹 پیام:
• ذخیره [1-10] — ریپلای
• ارسال ذخیره [1-10]
• ارسال زمان‌بندی [YYYY-MM-DD HH:MM] متن

🔹 فونت:
• فونت [0-8]
• لیست فونت

💡 فونت روی ساعت و پیام‌ها اعمال می‌شود!
💡 در گروه‌ها فقط وقتی تگ شوید پاسخ می‌دهد!
"""
