import asyncio
import re
import os
import time
import datetime
import threading
from telethon import TelegramClient, events
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.functions.contacts import BlockRequest, UnblockRequest
from telethon.errors import FloodWaitError, SessionPasswordNeededError
import database as db
import config

# ─── فونت‌ها ───────────────────────────────────────────────────────────────────
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


def _convert_font(text, chars):
    result = []
    for ch in text:
        if ch in _ALPHA:
            result.append(chars[_ALPHA.index(ch)])
        else:
            result.append(ch)
    return "".join(result)


def apply_font(text):
    font_id = db.get_setting("selected_font", "0")
    fn = FONTS.get(font_id, FONTS["0"])
    return fn(text)


# ─── کلاینت ────────────────────────────────────────────────────────────────────
client = None
_spam_task = None
_clock_task = None
_scheduler_task = None


def build_client(session_string=None):
    global client
    if session_string:
        from telethon.sessions import StringSession
        client = TelegramClient(StringSession(session_string), config.API_ID, config.API_HASH)
    else:
        client = TelegramClient(config.SESSION_NAME, config.API_ID, config.API_HASH)
    return client


# ─── ابزار ─────────────────────────────────────────────────────────────────────
def persian_time():
    now = datetime.datetime.now()
    h = str(now.hour).zfill(2)
    m = str(now.minute).zfill(2)
    s = str(now.second).zfill(2)
    return f"⏰ {h}:{m}:{s}"


BADWORDS = ["فحش", "بد", "کثیف", "احمق", "گاو", "خر", "مرتیکه"]

LINK_PATTERN = re.compile(
    r"(https?://|t\.me/|@\w+|www\.|telegram\.me/)", re.IGNORECASE
)


async def safe_reply(event, text):
    try:
        await event.reply(apply_font(text))
    except FloodWaitError as e:
        await asyncio.sleep(e.seconds + 1)
    except Exception:
        pass


async def safe_edit(event, text):
    try:
        await event.edit(apply_font(text))
    except FloodWaitError as e:
        await asyncio.sleep(e.seconds + 1)
    except Exception:
        pass


# ─── هندلرها ───────────────────────────────────────────────────────────────────
def register_handlers(cl):

    # ─── ضد حذف ─────────────────────────────────────────────────────────────
    @cl.on(events.MessageDeleted())
    async def on_delete(event):
        if db.get_setting("anti_delete_active") != "1":
            return
        for msg_id in event.deleted_ids:
            # ذخیره شده در حافظه اگر موجود بود
            pass  # لاگ اصلی در MessageEdited انجام می‌شود

    # ─── پیام‌های دریافتی ───────────────────────────────────────────────────
    @cl.on(events.NewMessage(incoming=True))
    async def on_incoming(event):
        msg = event.message
        sender = await event.get_sender()
        chat = await event.get_chat()
        sender_id = getattr(sender, "id", 0)
        chat_id = getattr(chat, "id", 0)
        text = msg.text or ""

        # سایلنت چت / کاربر - نادیده گرفتن
        if db.is_silent_chat(chat_id) or db.is_silent_user(sender_id):
            return

        # ذخیره خودکار مدیا
        if db.get_setting("auto_save_media") == "1" and msg.media:
            try:
                await cl.download_media(msg, file="saved_media/")
            except Exception:
                pass

        # سین خودکار
        if db.get_setting("auto_seen_active") == "1":
            try:
                await cl.send_read_acknowledge(chat_id, msg)
            except Exception:
                pass

        # منشی خودکار (فقط پیوی)
        if db.get_setting("secretary_active") == "1" and event.is_private:
            sec_msg = db.get_setting("secretary_message", "در حال حاضر در دسترس نیستم.")
            await safe_reply(event, f"🤖 منشی خودکار:\n{sec_msg}")
            return

        # ری‌اکشن خودکار
        if db.get_setting("auto_reaction_active") == "1":
            emoji = db.get_setting("auto_reaction_emoji", "❤️")
            try:
                from telethon.tl.functions.messages import SendReactionRequest
                from telethon.tl.types import ReactionEmoji
                await cl(SendReactionRequest(
                    peer=chat_id,
                    msg_id=msg.id,
                    reaction=[ReactionEmoji(emoticon=emoji)],
                ))
            except Exception:
                pass

        # پاسخ به دشمن
        if db.get_setting("enemy_reply_active") == "1" and db.is_enemy(sender_id):
            await safe_reply(event, "⚠️ پیام شما دریافت شد اما شما در لیست دشمن هستید.")

        # ضد لینک
        if db.get_setting("anti_link_active") == "1" and LINK_PATTERN.search(text):
            try:
                await msg.delete()
            except Exception:
                pass

        # ضد فحش
        if any(w in text for w in BADWORDS):
            try:
                await msg.delete()
            except Exception:
                pass

    # ─── پیام‌های ارسالی (دستورات) ──────────────────────────────────────────
    @cl.on(events.NewMessage(outgoing=True))
    async def on_outgoing(event):
        if db.get_setting("self_bot_active") != "1":
            return
        text = event.raw_text.strip()
        await handle_command(event, text)

    async def handle_command(event, text):
        msg = event.message

        # ─── دستورات اصلی ─────────────────────────────────────────────────
        if text == "سلف روشن":
            db.set_setting("self_bot_active", "1")
            await safe_edit(event, "✅ سلف‌بات روشن شد.")

        elif text == "سلف خاموش":
            db.set_setting("self_bot_active", "0")
            await safe_edit(event, "❌ سلف‌بات خاموش شد.")

        # ─── دشمن ────────────────────────────────────────────────────────
        elif text.startswith("تنظیم دشمن"):
            parts = text.split()
            target = await _resolve_target(event, parts)
            if target:
                db.add_enemy(target["id"], target.get("username"), target.get("name"))
                await safe_edit(event, f"🔴 {target.get('name', target['id'])} به لیست دشمن اضافه شد.")
            else:
                await safe_edit(event, "❗ روی پیام کاربر ریپلای کن یا آیدی عددی بنویس.")

        elif text.startswith("حذف دشمن"):
            parts = text.split()
            target = await _resolve_target(event, parts)
            if target:
                removed = db.remove_enemy(target["id"])
                await safe_edit(event, "✅ از لیست دشمن حذف شد." if removed else "❗ در لیست نبود.")
            else:
                await safe_edit(event, "❗ روی پیام کاربر ریپلای کن یا آیدی عددی بنویس.")

        elif text == "نمایش لیست دشمن":
            enemies = db.get_enemies()
            if not enemies:
                await safe_edit(event, "📋 لیست دشمن خالی است.")
            else:
                lines = [f"🔴 لیست دشمن ({len(enemies)} نفر):\n"]
                for e in enemies:
                    lines.append(f"• {e['name'] or e['username'] or e['user_id']} — `{e['user_id']}`")
                await safe_edit(event, "\n".join(lines))

        elif text == "پاک کردن لیست دشمن":
            db.clear_enemies()
            await safe_edit(event, "🗑️ لیست دشمن پاک شد.")

        # ─── دوست ────────────────────────────────────────────────────────
        elif text.startswith("تنظیم دوست"):
            parts = text.split()
            target = await _resolve_target(event, parts)
            if target:
                db.add_friend(target["id"], target.get("username"), target.get("name"))
                await safe_edit(event, f"💚 {target.get('name', target['id'])} به لیست دوست اضافه شد.")
            else:
                await safe_edit(event, "❗ روی پیام کاربر ریپلای کن یا آیدی عددی بنویس.")

        elif text.startswith("حذف دوست"):
            parts = text.split()
            target = await _resolve_target(event, parts)
            if target:
                removed = db.remove_friend(target["id"])
                await safe_edit(event, "✅ از لیست دوست حذف شد." if removed else "❗ در لیست نبود.")
            else:
                await safe_edit(event, "❗ روی پیام کاربر ریپلای کن یا آیدی عددی بنویس.")

        elif text == "نمایش لیست دوست":
            friends = db.get_friends()
            if not friends:
                await safe_edit(event, "📋 لیست دوست خالی است.")
            else:
                lines = [f"💚 لیست دوست ({len(friends)} نفر):\n"]
                for f in friends:
                    lines.append(f"• {f['name'] or f['username'] or f['user_id']} — `{f['user_id']}`")
                await safe_edit(event, "\n".join(lines))

        elif text == "پاک کردن لیست دوست":
            db.clear_friends()
            await safe_edit(event, "🗑️ لیست دوست پاک شد.")

        # ─── منشی ────────────────────────────────────────────────────────
        elif text == "منشی روشن":
            db.set_setting("secretary_active", "1")
            await safe_edit(event, "🤖 منشی خودکار روشن شد.")

        elif text == "منشی خاموش":
            db.set_setting("secretary_active", "0")
            await safe_edit(event, "🤖 منشی خودکار خاموش شد.")

        elif text.startswith("پیام منشی "):
            new_msg = text[len("پیام منشی "):].strip()
            db.set_setting("secretary_message", new_msg)
            await safe_edit(event, "✅ پیام منشی تنظیم شد.")

        # ─── ضد حذف ──────────────────────────────────────────────────────
        elif text == "ضد حذف روشن":
            db.set_setting("anti_delete_active", "1")
            await safe_edit(event, "🛡️ ضد حذف روشن شد.")

        elif text == "ضد حذف خاموش":
            db.set_setting("anti_delete_active", "0")
            await safe_edit(event, "🛡️ ضد حذف خاموش شد.")

        # ─── ضد لینک ─────────────────────────────────────────────────────
        elif text == "ضد لینک روشن":
            db.set_setting("anti_link_active", "1")
            await safe_edit(event, "🔗 ضد لینک روشن شد.")

        elif text == "ضد لینک خاموش":
            db.set_setting("anti_link_active", "0")
            await safe_edit(event, "🔗 ضد لینک خاموش شد.")

        # ─── قفل پیوی ────────────────────────────────────────────────────
        elif text == "قفل پیوی روشن":
            db.set_setting("private_lock_active", "1")
            await safe_edit(event, "🔒 قفل پیوی روشن شد.")

        elif text == "قفل پیوی خاموش":
            db.set_setting("private_lock_active", "0")
            await safe_edit(event, "🔓 قفل پیوی خاموش شد.")

        # ─── سین خودکار ──────────────────────────────────────────────────
        elif text == "سین خودکار روشن":
            db.set_setting("auto_seen_active", "1")
            await safe_edit(event, "👁️ سین خودکار روشن شد.")

        elif text == "سین خودکار خاموش":
            db.set_setting("auto_seen_active", "0")
            await safe_edit(event, "👁️ سین خودکار خاموش شد.")

        # ─── ری‌اکشن خودکار ───────────────────────────────────────────────
        elif text == "ری‌اکشن روشن":
            db.set_setting("auto_reaction_active", "1")
            await safe_edit(event, "❤️ ری‌اکشن خودکار روشن شد.")

        elif text == "ری‌اکشن خاموش":
            db.set_setting("auto_reaction_active", "0")
            await safe_edit(event, "❤️ ری‌اکشن خودکار خاموش شد.")

        elif text.startswith("ری‌اکشن "):
            emoji = text[len("ری‌اکشن "):].strip()
            db.set_setting("auto_reaction_emoji", emoji)
            await safe_edit(event, f"✅ ری‌اکشن پیش‌فرض: {emoji}")

        # ─── ذخیره خودکار مدیا ────────────────────────────────────────────
        elif text == "ذخیره مدیا روشن":
            os.makedirs("saved_media", exist_ok=True)
            db.set_setting("auto_save_media", "1")
            await safe_edit(event, "💾 ذخیره خودکار مدیا روشن شد.")

        elif text == "ذخیره مدیا خاموش":
            db.set_setting("auto_save_media", "0")
            await safe_edit(event, "💾 ذخیره خودکار مدیا خاموش شد.")

        # ─── سایلنت ──────────────────────────────────────────────────────
        elif text == "سایلنت چت روشن":
            chat = await event.get_chat()
            db.add_silent_chat(chat.id)
            await safe_edit(event, "🔇 این چت سایلنت شد.")

        elif text == "سایلنت چت خاموش":
            chat = await event.get_chat()
            db.remove_silent_chat(chat.id)
            await safe_edit(event, "🔔 سایلنت این چت برداشته شد.")

        elif text.startswith("سایلنت کاربر "):
            uid = int(text.split()[-1])
            db.add_silent_user(uid)
            await safe_edit(event, f"🔇 کاربر {uid} سایلنت شد.")

        elif text.startswith("لغو سایلنت کاربر "):
            uid = int(text.split()[-1])
            db.remove_silent_user(uid)
            await safe_edit(event, f"🔔 سایلنت کاربر {uid} برداشته شد.")

        # ─── پاسخ به دشمن ────────────────────────────────────────────────
        elif text == "پاسخ دشمن روشن":
            db.set_setting("enemy_reply_active", "1")
            await safe_edit(event, "⚔️ پاسخ خودکار به دشمن روشن شد.")

        elif text == "پاسخ دشمن خاموش":
            db.set_setting("enemy_reply_active", "0")
            await safe_edit(event, "⚔️ پاسخ خودکار به دشمن خاموش شد.")

        # ─── فونت ────────────────────────────────────────────────────────
        elif text.startswith("فونت "):
            font_id = text.split()[-1]
            if font_id in FONTS:
                db.set_setting("selected_font", font_id)
                await safe_edit(event, f"🔤 فونت {font_id} انتخاب شد.")
            else:
                await safe_edit(event, "❗ شماره فونت باید بین ۰ تا ۸ باشد.")

        elif text == "لیست فونت":
            lines = ["📝 فونت‌های موجود:\n"]
            samples = {
                "0": "متن عادی",
                "1": "𝗕𝗼𝗹𝗱 𝗦𝗮𝗻𝘀",
                "2": "𝘐𝘵𝘢𝘭𝘪𝘤 𝘚𝘢𝘯𝘴",
                "3": "𝙼𝚘𝚗𝚘𝚜𝚙𝚊𝚌𝚎",
                "4": "Ｆｕｌｌｗｉｄｔｈ",
                "5": "𝐒𝐞𝐫𝐢𝐟 𝐁𝐨𝐥𝐝",
                "6": "𝒮𝒸𝓇𝒾𝓅𝓉",
                "7": "S̶t̶r̶i̶k̶e̶",
                "8": "U̲n̲d̲e̲r̲l̲i̲n̲e̲",
            }
            for k, v in samples.items():
                lines.append(f"فونت {k} — {v}")
            await safe_edit(event, "\n".join(lines))

        # ─── ساعت در نام ─────────────────────────────────────────────────
        elif text == "ساعت نام روشن":
            db.set_setting("clock_name_active", "1")
            await safe_edit(event, "⏰ ساعت در نام روشن شد.")

        elif text == "ساعت نام خاموش":
            db.set_setting("clock_name_active", "0")
            await safe_edit(event, "⏰ ساعت در نام خاموش شد.")

        elif text == "ساعت بیو روشن":
            db.set_setting("clock_bio_active", "1")
            await safe_edit(event, "⏰ ساعت در بیو روشن شد.")

        elif text == "ساعت بیو خاموش":
            db.set_setting("clock_bio_active", "0")
            await safe_edit(event, "⏰ ساعت در بیو خاموش شد.")

        # ─── اسپم ────────────────────────────────────────────────────────
        elif text.startswith("اسپم "):
            parts = text.split(" ", 2)
            if len(parts) >= 3:
                count_str = parts[1]
                spam_text = parts[2]
                try:
                    count = int(count_str)
                    db.set_setting("spam_count", str(min(count, 50)))
                    db.set_setting("spam_text", spam_text)
                    db.set_setting("spam_active", "1")
                    await safe_edit(event, f"💣 اسپم شروع شد — {count} بار")
                    global _spam_task
                    chat = await event.get_chat()
                    _spam_task = asyncio.ensure_future(_do_spam(cl, chat.id, spam_text, min(count, 50)))
                except ValueError:
                    await safe_edit(event, "❗ فرمت: اسپم [تعداد] [متن]")

        elif text == "توقف اسپم":
            db.set_setting("spam_active", "0")
            if _spam_task:
                _spam_task.cancel()
            await safe_edit(event, "🛑 اسپم متوقف شد.")

        # ─── حذف خودکار پیام ─────────────────────────────────────────────
        elif text.startswith("حذف بعد "):
            parts = text.split()
            if len(parts) >= 3:
                try:
                    secs = int(parts[2])
                    await safe_edit(event, f"⏱️ پیام بعد از {secs} ثانیه حذف می‌شود.")
                    await asyncio.sleep(secs)
                    await msg.delete()
                except Exception:
                    pass

        # ─── ذخیره پیام ──────────────────────────────────────────────────
        elif text.startswith("ذخیره "):
            parts = text.split()
            if len(parts) >= 2:
                try:
                    slot = int(parts[1])
                    if 1 <= slot <= 10:
                        replied = await event.get_reply_message()
                        if replied:
                            db.save_message_slot(slot, replied.text or "")
                            await safe_edit(event, f"💾 پیام در اسلات {slot} ذخیره شد.")
                        else:
                            await safe_edit(event, "❗ روی پیام مورد نظر ریپلای کن.")
                    else:
                        await safe_edit(event, "❗ اسلات باید بین ۱ تا ۱۰ باشد.")
                except ValueError:
                    await safe_edit(event, "❗ فرمت: ذخیره [1-10]")

        elif text.startswith("ارسال ذخیره "):
            parts = text.split()
            if len(parts) >= 3:
                try:
                    slot = int(parts[2])
                    saved = db.get_message_slot(slot)
                    if saved:
                        chat = await event.get_chat()
                        await cl.send_message(chat.id, saved["content"])
                        await msg.delete()
                    else:
                        await safe_edit(event, f"❗ اسلات {slot} خالی است.")
                except ValueError:
                    pass

        # ─── ترجمه ───────────────────────────────────────────────────────
        elif text.startswith("ترجمه "):
            to_translate = text[len("ترجمه "):].strip()
            if not to_translate:
                replied = await event.get_reply_message()
                if replied:
                    to_translate = replied.text or ""
            if to_translate:
                translated = await _translate(to_translate)
                await safe_edit(event, f"🌐 ترجمه:\n{translated}")
            else:
                await safe_edit(event, "❗ متن یا ریپلای لازم است.")

        # ─── هواشناسی ────────────────────────────────────────────────────
        elif text.startswith("هوا "):
            city = text[len("هوا "):].strip()
            weather_info = await _get_weather(city)
            await safe_edit(event, weather_info)

        # ─── قیمت ارز ────────────────────────────────────────────────────
        elif text == "قیمت دلار" or text == "ارز":
            price_info = await _get_currency()
            await safe_edit(event, price_info)

        # ─── وضعیت سلف‌بات ───────────────────────────────────────────────
        elif text == "وضعیت":
            lines = [f"📊 وضعیت {config.BOT_NAME} v{config.BOT_VERSION}\n"]
            status_map = {
                "self_bot_active": "سلف‌بات",
                "secretary_active": "منشی",
                "anti_delete_active": "ضد حذف",
                "anti_link_active": "ضد لینک",
                "auto_seen_active": "سین خودکار",
                "auto_reaction_active": "ری‌اکشن",
                "private_lock_active": "قفل پیوی",
                "enemy_reply_active": "پاسخ دشمن",
                "auto_save_media": "ذخیره مدیا",
                "clock_name_active": "ساعت نام",
                "clock_bio_active": "ساعت بیو",
            }
            for key, label in status_map.items():
                val = db.get_setting(key, "0")
                icon = "✅" if val == "1" else "❌"
                lines.append(f"{icon} {label}")
            lines.append(f"\n🔤 فونت فعال: {db.get_setting('selected_font', '0')}")
            lines.append(f"👥 دشمن: {len(db.get_enemies())} نفر")
            lines.append(f"💚 دوست: {len(db.get_friends())} نفر")
            await safe_edit(event, "\n".join(lines))

        # ─── راهنما ───────────────────────────────────────────────────────
        elif text == "راهنما" or text == "help":
            await safe_edit(event, _help_text())

        # ─── ارسال زمان‌بندی شده ─────────────────────────────────────────
        elif text.startswith("ارسال زمان‌بندی "):
            # فرمت: ارسال زمان‌بندی [YYYY-MM-DD HH:MM] متن
            pattern = r"^ارسال زمان‌بندی (\d{4}-\d{2}-\d{2} \d{2}:\d{2}) (.+)$"
            m = re.match(pattern, text, re.DOTALL)
            if m:
                dt_str, sched_text = m.group(1), m.group(2)
                chat = await event.get_chat()
                db.add_scheduled_message(chat.id, sched_text, dt_str + ":00")
                await safe_edit(event, f"📅 پیام در {dt_str} ارسال خواهد شد.")
            else:
                await safe_edit(event, "❗ فرمت: ارسال زمان‌بندی [YYYY-MM-DD HH:MM] متن")

    # ─── هندلر ویرایش (برای ضد حذف محلی) ──────────────────────────────────
    @cl.on(events.MessageEdited())
    async def on_edit(event):
        pass


# ─── توابع کمکی ────────────────────────────────────────────────────────────────
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
    # آیدی عددی
    for p in parts[1:]:
        if p.lstrip("-").isdigit():
            return {"id": int(p), "username": None, "name": p}
    return None


async def _do_spam(cl, chat_id, text, count):
    delay = float(db.get_setting("spam_delay", "2"))
    for i in range(count):
        if db.get_setting("spam_active") != "1":
            break
        try:
            await cl.send_message(chat_id, text)
            await asyncio.sleep(delay)
        except FloodWaitError as e:
            await asyncio.sleep(e.seconds + 1)
        except Exception:
            break
    db.set_setting("spam_active", "0")


async def _translate(text):
    try:
        import urllib.request
        import urllib.parse
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=fa&dt=t&q={urllib.parse.quote(text)}"
        with urllib.request.urlopen(url, timeout=5) as resp:
            import json
            data = json.loads(resp.read().decode())
            return data[0][0][0]
    except Exception:
        return "⚠️ خطا در ترجمه"


async def _get_weather(city):
    try:
        import urllib.request
        import json
        import urllib.parse
        api_key = config.WEATHER_API_KEY
        if not api_key:
            return "⚠️ کلید API هواشناسی تنظیم نشده."
        url = f"https://api.openweathermap.org/data/2.5/weather?q={urllib.parse.quote(city)}&appid={api_key}&units=metric&lang=fa"
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            desc = data["weather"][0]["description"]
            temp = data["main"]["temp"]
            feels = data["main"]["feels_like"]
            humidity = data["main"]["humidity"]
            return (
                f"🌤️ هوای {city}:\n"
                f"وضعیت: {desc}\n"
                f"دما: {temp}°C (احساس {feels}°C)\n"
                f"رطوبت: {humidity}%"
            )
    except Exception:
        return "⚠️ خطا در دریافت اطلاعات هوا"


async def _get_currency():
    try:
        import urllib.request
        import json
        url = "https://api.exchangerate-api.com/v4/latest/USD"
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            usd_eur = round(1 / data["rates"]["EUR"], 4)
            return (
                f"💵 نرخ ارز:\n"
                f"دلار/یورو: {usd_eur}\n"
                f"دلار/پوند: {round(1/data['rates']['GBP'], 4)}\n"
                f"دلار/روبل: {round(data['rates']['RUB'], 2)}\n"
                f"منبع: exchangerate-api.com"
            )
    except Exception:
        return "⚠️ خطا در دریافت قیمت ارز"


def _help_text():
    return """📖 راهنمای AMEL SELF55

🔹 اصلی:
• سلف روشن / سلف خاموش
• وضعیت — نمایش وضعیت همه قابلیت‌ها

🔹 لیست‌ها:
• تنظیم دشمن / حذف دشمن [ریپلای یا آیدی]
• نمایش لیست دشمن / پاک کردن لیست دشمن
• تنظیم دوست / حذف دوست [ریپلای یا آیدی]
• نمایش لیست دوست / پاک کردن لیست دوست

🔹 منشی:
• منشی روشن / منشی خاموش
• پیام منشی [متن]

🔹 امنیت:
• ضد حذف روشن / خاموش
• ضد لینک روشن / خاموش
• قفل پیوی روشن / خاموش
• پاسخ دشمن روشن / خاموش

🔹 سایلنت:
• سایلنت چت روشن / خاموش
• سایلنت کاربر [آیدی] / لغو سایلنت کاربر [آیدی]

🔹 اتوماسیون:
• سین خودکار روشن / خاموش
• ری‌اکشن روشن / خاموش
• ری‌اکشن [ایموجی]
• ذخیره مدیا روشن / خاموش

🔹 فونت:
• فونت [0-8]
• لیست فونت

🔹 ساعت:
• ساعت نام روشن / خاموش
• ساعت بیو روشن / خاموش

🔹 ابزار:
• ترجمه [متن] — یا ریپلای روی پیام
• هوا [شهر]
• ارز / قیمت دلار

🔹 اسپم:
• اسپم [تعداد] [متن]
• توقف اسپم

🔹 پیام:
• ذخیره [1-10] — ریپلای روی پیام
• ارسال ذخیره [1-10]
• حذف بعد [ثانیه]
• ارسال زمان‌بندی [YYYY-MM-DD HH:MM] متن
"""


# ─── تسک پس‌زمینه: ساعت ──────────────────────────────────────────────────────
async def clock_loop(cl):
    while True:
        try:
            if db.get_setting("clock_name_active") == "1":
                t = persian_time()
                me = await cl.get_me()
                fn = me.first_name or ""
                # حذف ساعت قدیمی از ابتدای نام
                fn_clean = re.sub(r"⏰ \d{2}:\d{2}:\d{2}\s*", "", fn).strip()
                await cl(UpdateProfileRequest(first_name=f"{t} {fn_clean}"[:64]))
            if db.get_setting("clock_bio_active") == "1":
                t = persian_time()
                await cl(UpdateProfileRequest(about=f"آخرین به‌روزرسانی: {t}"[:70]))
        except Exception:
            pass
        await asyncio.sleep(60)


# ─── تسک پس‌زمینه: پیام‌های زمان‌بندی شده ────────────────────────────────────
async def scheduler_loop(cl):
    while True:
        try:
            pending = db.get_pending_scheduled()
            for p in pending:
                try:
                    await cl.send_message(p["chat_id"], p["message"])
                    db.mark_scheduled_sent(p["id"])
                except Exception:
                    pass
        except Exception:
            pass
        await asyncio.sleep(30)


# ─── راه‌اندازی بات ───────────────────────────────────────────────────────────
async def start_bot():
    global client, _clock_task, _scheduler_task
    db.init_db()
    session_data = db.get_setting("session_data", "")

    if not config.API_ID or not config.API_HASH:
        print("⚠️  API_ID و API_HASH تنظیم نشده‌اند.")
        return

    build_client(session_data if session_data else None)
    register_handlers(client)

    await client.start()

    me = await client.get_me()
    print(f"✅ AMEL SELF55 راه‌اندازی شد — {me.first_name} (@{me.username})")

    _clock_task = asyncio.ensure_future(clock_loop(client))
    _scheduler_task = asyncio.ensure_future(scheduler_loop(client))

    await client.run_until_disconnected()
