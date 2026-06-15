import asyncio
import os
import re
import random
import logging
from datetime import datetime
from pathlib import Path

import pytz
from telethon import TelegramClient, events
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument
from telethon.errors import FloodWaitError

import database as db
import texts
from config import API_ID, API_HASH, SESSION_NAME, TIMEZONE

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

tz = pytz.timezone(TIMEZONE)

MEDIA_DIR = Path("saved_media")
MEDIA_DIR.mkdir(exist_ok=True)

client: TelegramClient = None
_owner_id: int = None
_message_cache: dict = {}  # chat_id -> {msg_id: message}


def now_str() -> str:
    return datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")


def now_display() -> str:
    return datetime.now(tz).strftime("%H:%M:%S - %Y/%m/%d")


async def get_owner_id() -> int:
    global _owner_id
    if _owner_id is None:
        me = await client.get_me()
        _owner_id = me.id
    return _owner_id


async def is_owner(event) -> bool:
    owner = await get_owner_id()
    return event.sender_id == owner


def is_exact_command(text: str, command: str) -> bool:
    return text.strip() == command.strip()


async def handle_scheduled():
    while True:
        try:
            pending = db.get_pending_scheduled(now_str())
            for msg in pending:
                try:
                    await client.send_message(int(msg["chat_id"]), msg["message"])
                    db.mark_scheduled_sent(msg["id"])
                except Exception as e:
                    logger.error(f"Scheduled send error: {e}")
        except Exception as e:
            logger.error(f"Scheduler error: {e}")
        await asyncio.sleep(30)


def setup_handlers(tg_client: TelegramClient):
    global client
    client = tg_client

    # ── کش پیام‌ها برای ضد حذف ─────────────────────────────────────────────
    @tg_client.on(events.NewMessage())
    async def cache_message(event):
        try:
            cid = event.chat_id
            mid = event.message.id
            if cid not in _message_cache:
                _message_cache[cid] = {}
            _message_cache[cid][mid] = event.message
            # ذخیره فقط 200 پیام آخر در هر چت
            if len(_message_cache[cid]) > 200:
                oldest = sorted(_message_cache[cid].keys())[0]
                del _message_cache[cid][oldest]
        except Exception:
            pass

    # ── ضد حذف ──────────────────────────────────────────────────────────────
    @tg_client.on(events.MessageDeleted())
    async def anti_delete(event):
        if not db.is_active():
            return
        if db.get_setting("anti_delete_active") != "true":
            return
        try:
            owner = await get_owner_id()
            for mid in event.deleted_ids:
                cid = event.chat_id
                cached = _message_cache.get(cid, {}).get(mid)
                if cached is None:
                    continue
                sender_id = cached.sender_id or 0
                sender_name = getattr(cached.sender, "first_name", str(sender_id))
                text = cached.message or ""
                media_path = ""
                if cached.media:
                    try:
                        path = await tg_client.download_media(cached.media, file=str(MEDIA_DIR))
                        media_path = path or ""
                    except Exception:
                        pass
                db.save_deleted_message(cid, sender_id, str(sender_name), text, media_path)
                notif = texts.ANTI_DELETE_SAVED.format(sender=sender_name, text=text or "[مدیا]")
                await tg_client.send_message("me", notif)
        except Exception as e:
            logger.error(f"Anti-delete error: {e}")

    # ── مدیریت پیام‌های دریافتی در پیوی ─────────────────────────────────────
    @tg_client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
    async def handle_pv_incoming(event):
        if not db.is_active():
            return
        sender_id = event.sender_id
        owner = await get_owner_id()
        if sender_id == owner:
            return

        # دوست → نادیده بگیر
        if db.is_friend(sender_id):
            return

        # قفل پیوی → حذف پیام از هر دو طرف
        if db.get_setting("pv_lock_active") == "true":
            try:
                await event.delete()
            except Exception:
                pass
            try:
                await tg_client.send_message(sender_id, texts.PV_LOCK_MSG)
            except Exception:
                pass
            return

        # ضد لینک در پیوی
        if db.get_setting("anti_link_active") == "true":
            url_pattern = r"(https?://|www\.|t\.me/|telegram\.me/)\S+"
            if re.search(url_pattern, event.message.message or ""):
                try:
                    await event.delete()
                except Exception:
                    pass
                return

        # دشمن → پاسخ خودکار
        if db.is_enemy(sender_id):
            try:
                await tg_client.send_message(sender_id, texts.get_enemy_reply())
            except Exception:
                pass
            return

        # منشی
        if db.get_setting("secretary_active") == "true":
            custom = db.get_setting("secretary_text")
            try:
                await tg_client.send_message(sender_id, texts.get_secretary_reply(custom))
            except Exception:
                pass

        # خوانده خودکار
        if db.get_setting("auto_seen_active") == "true":
            try:
                await tg_client.send_read_acknowledge(event.chat_id, max_id=event.message.id)
            except Exception:
                pass

        # واکنش خودکار
        if db.get_setting("auto_react_active") == "true":
            emoji = db.get_setting("auto_react_emoji") or "👍"
            try:
                from telethon.tl.functions.messages import SendReactionRequest
                from telethon.tl.types import ReactionEmoji
                await tg_client(SendReactionRequest(
                    peer=event.chat_id,
                    msg_id=event.message.id,
                    reaction=[ReactionEmoji(emoticon=emoji)]
                ))
            except Exception:
                pass

    # ── پردازش دستورات صاحب ─────────────────────────────────────────────────
    @tg_client.on(events.NewMessage(outgoing=True))
    async def handle_owner_commands(event):
        if not event.message.message:
            return
        raw = event.message.message.strip()
        owner = await get_owner_id()
        if event.sender_id != owner:
            return

        # ─── کنترل اصلی ───
        if is_exact_command(raw, "سلف روشن"):
            db.set_setting("bot_active", "true")
            await event.edit(texts.BOT_ON_MSG.format(time=now_display()))
            return

        if is_exact_command(raw, "سلف خاموش"):
            db.set_setting("bot_active", "false")
            await event.edit(texts.BOT_OFF_MSG.format(time=now_display()))
            return

        # برای بقیه دستورات، بات باید فعال باشد
        if not db.is_active():
            return

        # ─── منشی ───
        if is_exact_command(raw, "منشی روشن"):
            db.set_setting("secretary_active", "true")
            await event.edit(texts.FEATURE_ON.format(feature=texts.FEATURES["secretary"]))
            return

        if is_exact_command(raw, "منشی خاموش"):
            db.set_setting("secretary_active", "false")
            await event.edit(texts.FEATURE_OFF.format(feature=texts.FEATURES["secretary"]))
            return

        # ─── ضد حذف ───
        if is_exact_command(raw, "ضد حذف روشن"):
            db.set_setting("anti_delete_active", "true")
            await event.edit(texts.FEATURE_ON.format(feature=texts.FEATURES["anti_delete"]))
            return

        if is_exact_command(raw, "ضد حذف خاموش"):
            db.set_setting("anti_delete_active", "false")
            await event.edit(texts.FEATURE_OFF.format(feature=texts.FEATURES["anti_delete"]))
            return

        # ─── قفل پیوی ───
        if is_exact_command(raw, "قفل پیوی روشن"):
            db.set_setting("pv_lock_active", "true")
            await event.edit(texts.FEATURE_ON.format(feature=texts.FEATURES["pv_lock"]))
            return

        if is_exact_command(raw, "قفل پیوی خاموش"):
            db.set_setting("pv_lock_active", "false")
            await event.edit(texts.FEATURE_OFF.format(feature=texts.FEATURES["pv_lock"]))
            return

        # ─── ضد لینک ───
        if is_exact_command(raw, "ضد لینک روشن"):
            db.set_setting("anti_link_active", "true")
            await event.edit(texts.FEATURE_ON.format(feature=texts.FEATURES["anti_link"]))
            return

        if is_exact_command(raw, "ضد لینک خاموش"):
            db.set_setting("anti_link_active", "false")
            await event.edit(texts.FEATURE_OFF.format(feature=texts.FEATURES["anti_link"]))
            return

        # ─── دشمن ───
        if raw.startswith("تنظیم دشمن "):
            target = raw[len("تنظیم دشمن "):].strip()
            uid, uname = await resolve_user(target)
            if uid:
                db.add_enemy(uid, uname)
                await event.edit(texts.ENEMY_ADDED.format(user=uname or target))
            else:
                await event.edit("❌ کاربر پیدا نشد.")
            return

        if raw.startswith("حذف دشمن "):
            target = raw[len("حذف دشمن "):].strip()
            uid, uname = await resolve_user(target)
            if uid:
                db.remove_enemy(uid)
                await event.edit(texts.ENEMY_REMOVED.format(user=uname or target))
            else:
                await event.edit("❌ کاربر پیدا نشد.")
            return

        if is_exact_command(raw, "نمایش لیست دشمن"):
            enemies = db.get_enemies()
            if not enemies:
                await event.edit("📋 لیست دشمنان خالی است.")
            else:
                lines = [f"🔴 {e['username'] or e['user_id']}" for e in enemies]
                await event.edit("📋 لیست دشمنان:\n" + "\n".join(lines))
            return

        # ─── دوست ───
        if raw.startswith("تنظیم دوست "):
            target = raw[len("تنظیم دوست "):].strip()
            uid, uname = await resolve_user(target)
            if uid:
                db.add_friend(uid, uname)
                await event.edit(texts.FRIEND_ADDED.format(user=uname or target))
            else:
                await event.edit("❌ کاربر پیدا نشد.")
            return

        if raw.startswith("حذف دوست "):
            target = raw[len("حذف دوست "):].strip()
            uid, uname = await resolve_user(target)
            if uid:
                db.remove_friend(uid)
                await event.edit(texts.FRIEND_REMOVED.format(user=uname or target))
            else:
                await event.edit("❌ کاربر پیدا نشد.")
            return

        if is_exact_command(raw, "نمایش لیست دوست"):
            friends = db.get_friends()
            if not friends:
                await event.edit("📋 لیست دوستان خالی است.")
            else:
                lines = [f"🟢 {f['username'] or f['user_id']}" for f in friends]
                await event.edit("📋 لیست دوستان:\n" + "\n".join(lines))
            return

        # ─── ذخیره پیام در اسلات ───
        # فرمت: ذخیره 1  (در ریپلای به پیام)
        if raw.startswith("ذخیره ") and event.is_reply:
            parts = raw.split()
            if len(parts) == 2 and parts[1].isdigit():
                slot = int(parts[1])
                if 1 <= slot <= 10:
                    reply_msg = await event.get_reply_message()
                    content = reply_msg.message or ""
                    db.save_slot(slot, content)
                    await event.edit(f"✅ پیام در اسلات {slot} ذخیره شد.")
                    return

        # ─── ارسال اسلات ───
        # فرمت: ارسال 1
        if raw.startswith("ارسال "):
            parts = raw.split()
            if len(parts) == 2 and parts[1].isdigit():
                slot = int(parts[1])
                content = db.get_slot(slot)
                if content:
                    await event.edit(content)
                else:
                    await event.edit(f"❌ اسلات {slot} خالی است.")
                return

        # ─── نمایش اسلات‌ها ───
        if is_exact_command(raw, "نمایش اسلات"):
            slots = db.all_slots()
            if not slots:
                await event.edit("📋 هیچ پیامی ذخیره نشده.")
            else:
                lines = [f"🗂 اسلات {s['slot']}: {s['content'][:50]}..." for s in slots]
                await event.edit("📋 پیام‌های ذخیره‌شده:\n" + "\n".join(lines))
            return

        # ─── اسپم ───
        # فرمت: اسپم 5 متن پیام
        if raw.startswith("اسپم "):
            parts = raw.split(None, 2)
            if len(parts) >= 3 and parts[1].isdigit():
                count = int(parts[1])
                msg_text = parts[2]
                delay = float(db.get_setting("spam_delay") or "2")
                await event.delete()
                for i in range(count):
                    try:
                        await tg_client.send_message(event.chat_id, msg_text)
                        await asyncio.sleep(delay)
                    except FloodWaitError as e:
                        await asyncio.sleep(e.seconds)
                return

        # ─── زمان‌بندی پیام ───
        # فرمت: زمان‌بندی 1403/10/20 15:30 متن پیام
        if raw.startswith("زمان‌بندی "):
            parts = raw.split(None, 3)
            if len(parts) == 4:
                date_str, time_str, msg_text = parts[1], parts[2], parts[3]
                try:
                    send_at = f"{date_str} {time_str}:00"
                    db.add_scheduled(event.chat_id, msg_text, send_at)
                    await event.edit(f"⏰ پیام در {send_at} ارسال خواهد شد.")
                except Exception:
                    await event.edit("❌ فرمت تاریخ/ساعت نامعتبر است.")
                return

        # ─── ترجمه ───
        # فرمت: ترجمه fa→en متن
        if raw.startswith("ترجمه "):
            parts = raw.split(None, 2)
            if len(parts) >= 3:
                direction = parts[1]
                text_to_tr = parts[2]
                translated = await translate_text(text_to_tr, direction)
                await event.edit(f"🌐 ترجمه:\n{translated}")
                return

        # ─── تبدیل متن به صدا ───
        # فرمت: صدا متن
        if raw.startswith("صدا "):
            text_to_speak = raw[len("صدا "):].strip()
            audio_path = await text_to_voice(text_to_speak)
            if audio_path:
                await event.delete()
                await tg_client.send_file(event.chat_id, audio_path, voice_note=True)
                os.remove(audio_path)
            else:
                await event.edit("❌ تبدیل متن به صدا ناموفق بود.")
            return

        # ─── فوروارد خودکار ───
        # فرمت: فوروارد @مقصد (در ریپلای به پیام)
        if raw.startswith("فوروارد ") and event.is_reply:
            target_chat = raw[len("فوروارد "):].strip()
            reply_msg = await event.get_reply_message()
            try:
                await tg_client.forward_messages(target_chat, reply_msg)
                await event.edit(f"✅ پیام به {target_chat} فوروارد شد.")
            except Exception as e:
                await event.edit(f"❌ خطا: {e}")
            return

        # ─── وضعیت بات ───
        if is_exact_command(raw, "وضعیت"):
            settings = db.get_all_settings()
            status_map = {
                "bot_active": "سلف",
                "secretary_active": "منشی",
                "anti_delete_active": "ضد حذف",
                "pv_lock_active": "قفل پیوی",
                "anti_link_active": "ضد لینک",
                "auto_seen_active": "خوانده خودکار",
                "auto_react_active": "واکنش خودکار",
            }
            lines = []
            for key, label in status_map.items():
                val = settings.get(key, "false")
                icon = "✅" if val == "true" else "⭕"
                lines.append(f"{icon} {label}")
            await event.edit("📊 وضعیت سیستم:\n" + "\n".join(lines) + f"\n\n🕐 {now_display()}")
            return

        # ─── راهنما ───
        if is_exact_command(raw, "راهنما"):
            help_text = """📖 راهنمای AMEL SELF55

🔧 کنترل اصلی:
• سلف روشن / سلف خاموش

👥 مدیریت مخاطبین:
• تنظیم دشمن @user
• حذف دشمن @user
• نمایش لیست دشمن
• تنظیم دوست @user
• حذف دوست @user
• نمایش لیست دوست

⚙️ ویژگی‌ها:
• منشی روشن / خاموش
• ضد حذف روشن / خاموش
• قفل پیوی روشن / خاموش
• ضد لینک روشن / خاموش

💾 مدیریت پیام:
• ذخیره [1-10] (در ریپلای)
• ارسال [1-10]
• نمایش اسلات

📤 ارسال:
• اسپم [تعداد] [متن]
• فوروارد @مقصد (در ریپلای)
• زمان‌بندی [تاریخ] [ساعت] [متن]

🌐 ابزار:
• ترجمه fa→en [متن]
• ترجمه en→fa [متن]
• صدا [متن]
• وضعیت"""
            await event.edit(help_text)
            return

    logger.info("✅ هندلرهای بات تنظیم شدند.")
    asyncio.ensure_future(handle_scheduled())


async def resolve_user(target: str):
    """شناسه یا یوزرنیم را به آی‌دی تبدیل می‌کند"""
    try:
        entity = await client.get_entity(target)
        uid = entity.id
        username = getattr(entity, "username", "") or ""
        first_name = getattr(entity, "first_name", "") or ""
        display = username or first_name or str(uid)
        return uid, display
    except Exception:
        return None, None


async def translate_text(text: str, direction: str = "fa→en") -> str:
    """ترجمه متن با استفاده از API رایگان"""
    try:
        import urllib.request
        import json
        if "en" in direction and "fa" in direction:
            src, tgt = ("fa", "en") if direction.startswith("fa") else ("en", "fa")
        else:
            src, tgt = "fa", "en"
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl={src}&tl={tgt}&dt=t&q={urllib.parse.quote(text)}"
        import urllib.parse
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            return data[0][0][0]
    except Exception as e:
        return f"❌ خطا در ترجمه: {e}"


async def text_to_voice(text: str) -> str | None:
    """تبدیل متن فارسی به فایل صوتی با gTTS"""
    try:
        from gtts import gTTS
        import tempfile
        tts = gTTS(text=text, lang="fa")
        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tts.save(tmp.name)
        return tmp.name
    except Exception as e:
        logger.error(f"TTS error: {e}")
        return None


async def start_bot(phone: str = None, session_name: str = None, api_id: int = None, api_hash: str = None):
    """راه‌اندازی بات تلگرام"""
    from config import PHONE, SESSION_NAME, API_ID, API_HASH
    _phone = phone or PHONE
    _session = session_name or SESSION_NAME
    _api_id = api_id or API_ID
    _api_hash = api_hash or API_HASH

    global client
    client = TelegramClient(_session, _api_id, _api_hash)
    await client.start(phone=_phone)
    setup_handlers(client)
    logger.info("🚀 AMEL SELF55 آماده به کار است.")
    await client.run_until_disconnected()
