import asyncio
import threading
import logging
import os
from datetime import datetime

import pytz
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, PhoneCodeExpiredError, PhoneCodeInvalidError

import database as db
from config import SECRET_KEY, PORT, TIMEZONE, SESSION_NAME, PANEL_PASSWORD

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = SECRET_KEY

tz = pytz.timezone(TIMEZONE)

# وضعیت اتصال بات
_bot_thread: threading.Thread = None
_bot_loop: asyncio.AbstractEventLoop = None
_tg_client: TelegramClient = None
_pending_phone_code: dict = {}  # {"phone": ..., "phone_code_hash": ..., "client": ...}


def now_display() -> str:
    return datetime.now(tz).strftime("%H:%M:%S - %Y/%m/%d")


# ── راه‌اندازی پایگاه داده ─────────────────────────────────────────────────
db.init_db()


# ── مسیر Keep-Alive برای UptimeRobot ─────────────────────────────────────
@app.route("/keepalive")
@app.route("/ping")
def keepalive():
    return jsonify({"status": "alive", "time": now_display(), "bot": "AMEL SELF55"})


@app.route("/healthz")
def health():
    return jsonify({"ok": True})


# ── احراز هویت پنل ──────────────────────────────────────────────────────
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        password = request.form.get("password", "")
        if password == PANEL_PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("panel"))
        return render_template("panel.html", page="login", error="رمز عبور اشتباه است.")
    return render_template("panel.html", page="login", error=None)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


def require_login(f):
    from functools import wraps
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


# ── پنل اصلی ─────────────────────────────────────────────────────────────
@app.route("/")
@require_login
def panel():
    settings = db.get_all_settings()
    friends = db.get_friends()
    enemies = db.get_enemies()
    deleted = db.get_deleted_messages(20)
    slots = db.all_slots()
    connected = _tg_client is not None and _tg_client.is_connected() if _tg_client else False
    return render_template(
        "panel.html",
        page="panel",
        settings=settings,
        friends=friends,
        enemies=enemies,
        deleted_messages=deleted,
        slots=slots,
        connected=connected,
        now=now_display(),
    )


# ── API پنل: تغییر تنظیمات ──────────────────────────────────────────────
@app.route("/api/setting", methods=["POST"])
@require_login
def api_setting():
    data = request.get_json()
    key = data.get("key")
    value = data.get("value")
    allowed_keys = [
        "bot_active", "secretary_active", "anti_delete_active",
        "pv_lock_active", "anti_link_active", "auto_seen_active",
        "auto_react_active", "secretary_text", "auto_react_emoji", "spam_delay"
    ]
    if key not in allowed_keys:
        return jsonify({"ok": False, "error": "کلید نامعتبر"}), 400
    db.set_setting(key, str(value))
    return jsonify({"ok": True})


@app.route("/api/status")
@require_login
def api_status():
    connected = _tg_client is not None and _tg_client.is_connected() if _tg_client else False
    return jsonify({
        "ok": True,
        "connected": connected,
        "settings": db.get_all_settings(),
        "now": now_display(),
    })


# ── ورود تلگرام: مرحله اول (شماره) ─────────────────────────────────────
@app.route("/api/tg/send_code", methods=["POST"])
@require_login
def tg_send_code():
    global _pending_phone_code
    data = request.get_json()
    phone = data.get("phone", "").strip()
    api_id = int(data.get("api_id", 0))
    api_hash = data.get("api_hash", "").strip()

    if not phone or not api_id or not api_hash:
        return jsonify({"ok": False, "error": "اطلاعات ناقص است."})

    async def _send():
        client = TelegramClient(SESSION_NAME, api_id, api_hash)
        await client.connect()
        result = await client.send_code_request(phone)
        return client, result.phone_code_hash

    try:
        loop = asyncio.new_event_loop()
        client, phone_code_hash = loop.run_until_complete(_send())
        loop.close()
        _pending_phone_code = {
            "phone": phone,
            "phone_code_hash": phone_code_hash,
            "api_id": api_id,
            "api_hash": api_hash,
        }
        return jsonify({"ok": True, "message": "کد تأیید ارسال شد."})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


# ── ورود تلگرام: مرحله دوم (کد) ─────────────────────────────────────────
@app.route("/api/tg/verify_code", methods=["POST"])
@require_login
def tg_verify_code():
    global _tg_client, _bot_thread, _bot_loop, _pending_phone_code
    data = request.get_json()
    code = data.get("code", "").strip()
    password = data.get("password", "").strip()

    if not _pending_phone_code:
        return jsonify({"ok": False, "error": "ابتدا شماره تلفن را وارد کنید."})

    phone = _pending_phone_code["phone"]
    phone_code_hash = _pending_phone_code["phone_code_hash"]
    api_id = _pending_phone_code["api_id"]
    api_hash = _pending_phone_code["api_hash"]

    async def _verify():
        client = TelegramClient(SESSION_NAME, api_id, api_hash)
        await client.connect()
        try:
            await client.sign_in(phone, code, phone_code_hash=phone_code_hash)
        except SessionPasswordNeededError:
            if not password:
                return client, "2fa_required"
            await client.sign_in(password=password)
        return client, "ok"

    try:
        loop = asyncio.new_event_loop()
        client, status = loop.run_until_complete(_verify())
        loop.close()

        if status == "2fa_required":
            return jsonify({"ok": False, "error": "2fa_required", "message": "رمز دو مرحله‌ای وارد کنید."})

        # راه‌اندازی بات در thread جداگانه
        _tg_client = client
        _pending_phone_code = {}
        _start_bot_thread(client, api_id, api_hash)
        return jsonify({"ok": True, "message": "✅ اتصال موفق! بات در حال اجرا است."})
    except (PhoneCodeInvalidError, PhoneCodeExpiredError):
        return jsonify({"ok": False, "error": "کد اشتباه یا منقضی شده است."})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


def _start_bot_thread(client: TelegramClient, api_id: int, api_hash: int):
    global _bot_thread, _bot_loop

    def run():
        global _bot_loop
        import bot as bot_module
        _bot_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_bot_loop)
        bot_module.client = client
        bot_module.setup_handlers(client)
        _bot_loop.run_until_complete(client.run_until_disconnected())

    _bot_thread = threading.Thread(target=run, daemon=True)
    _bot_thread.start()
    logger.info("🚀 بات در thread جداگانه اجرا شد.")


# ── حذف مخاطب از طریق پنل ───────────────────────────────────────────────
@app.route("/remove_contact")
@require_login
def remove_contact():
    contact_type = request.args.get("type")
    uid = request.args.get("uid")
    if not uid or not uid.isdigit():
        return redirect(url_for("panel"))
    uid_int = int(uid)
    if contact_type == "friend":
        db.remove_friend(uid_int)
    elif contact_type == "enemy":
        db.remove_enemy(uid_int)
    return redirect(url_for("panel") + "#contacts")


# ── قطع اتصال تلگرام ───────────────────────────────────────────────────
@app.route("/api/tg/disconnect", methods=["POST"])
@require_login
def tg_disconnect():
    global _tg_client
    if _tg_client:
        try:
            loop = asyncio.new_event_loop()
            loop.run_until_complete(_tg_client.disconnect())
            loop.close()
        except Exception:
            pass
        _tg_client = None
    return jsonify({"ok": True, "message": "⭕ اتصال قطع شد."})


# ── اگر session از قبل موجود باشد، بات را خودکار راه‌اندازی کن ─────────
def auto_start_if_session_exists():
    from config import API_ID, API_HASH
    if API_ID and API_HASH and os.path.exists(f"{SESSION_NAME}.session"):
        logger.info("📂 سشن موجود پیدا شد. راه‌اندازی خودکار...")
        async def _connect():
            client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
            await client.connect()
            if await client.is_user_authorized():
                return client
            return None
        try:
            loop = asyncio.new_event_loop()
            client = loop.run_until_complete(_connect())
            loop.close()
            if client:
                global _tg_client
                _tg_client = client
                _start_bot_thread(client, API_ID, API_HASH)
                logger.info("✅ بات به صورت خودکار راه‌اندازی شد.")
        except Exception as e:
            logger.error(f"Auto-start error: {e}")


if __name__ == "__main__":
    auto_start_if_session_exists()
    logger.info(f"🌐 پنل مدیریت روی پورت {PORT} در حال اجرا...")
    app.run(host="0.0.0.0", port=PORT, debug=False, threaded=True)
