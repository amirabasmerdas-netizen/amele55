import asyncio
import os
import threading
import sys
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import (
    SessionPasswordNeededError,
    PhoneCodeInvalidError,
    PhoneCodeExpiredError,
    FloodWaitError,
)
import database as db
import config

app = Flask(__name__)
app.secret_key = config.SECRET_KEY

# کلاینت موقت برای لاگین
_login_client = None
_phone_code_hash = None
_loop = None


def get_loop():
    global _loop
    if _loop is None or _loop.is_closed():
        _loop = asyncio.new_event_loop()
        t = threading.Thread(target=_loop.run_forever, daemon=True)
        t.start()
    return _loop


def run_async(coro):
    loop = get_loop()
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result(timeout=30)


# ─── keep-alive ──────────────────────────────────────────────────────────────
@app.route("/ping")
def ping():
    return "pong", 200


@app.route("/health")
def health():
    return jsonify({"status": "ok", "bot": config.BOT_NAME}), 200


# ─── صفحه اصلی / پنل ─────────────────────────────────────────────────────────
@app.route("/")
def index():
    logged_in = db.get_setting("logged_in", "0") == "1"
    if not logged_in:
        return redirect(url_for("login_page"))
    return render_template("panel.html")


# ─── لاگین ───────────────────────────────────────────────────────────────────
@app.route("/login")
def login_page():
    return render_template("panel.html", page="login")


@app.route("/api/login/send_code", methods=["POST"])
def send_code():
    global _login_client, _phone_code_hash
    data = request.json or {}
    phone = data.get("phone", "").strip()
    if not phone:
        return jsonify({"ok": False, "error": "شماره تلفن الزامی است"}), 400
    if not config.API_ID or not config.API_HASH:
        return jsonify({"ok": False, "error": "API_ID و API_HASH تنظیم نشده‌اند"}), 400

    async def _send():
        global _login_client, _phone_code_hash
        _login_client = TelegramClient(StringSession(), config.API_ID, config.API_HASH)
        await _login_client.connect()
        result = await _login_client.send_code_request(phone)
        _phone_code_hash = result.phone_code_hash
        return {"ok": True}

    try:
        result = run_async(_send())
        session["phone"] = phone
        return jsonify(result)
    except FloodWaitError as e:
        return jsonify({"ok": False, "error": f"محدودیت: {e.seconds} ثانیه صبر کنید"}), 429
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/login/verify_code", methods=["POST"])
def verify_code():
    global _login_client, _phone_code_hash
    data = request.json or {}
    code = data.get("code", "").strip()
    phone = session.get("phone", "")
    if not code or not phone:
        return jsonify({"ok": False, "error": "کد یا شماره تلفن موجود نیست"}), 400

    async def _verify():
        global _login_client
        await _login_client.sign_in(phone=phone, code=code, phone_code_hash=_phone_code_hash)
        session_str = _login_client.session.save()
        db.set_setting("session_data", session_str)
        db.set_setting("logged_in", "1")
        await _login_client.disconnect()
        return {"ok": True}

    try:
        result = run_async(_verify())
        return jsonify(result)
    except SessionPasswordNeededError:
        return jsonify({"ok": False, "need_2fa": True}), 200
    except (PhoneCodeInvalidError, PhoneCodeExpiredError):
        return jsonify({"ok": False, "error": "کد اشتباه یا منقضی شده"}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/login/verify_2fa", methods=["POST"])
def verify_2fa():
    global _login_client
    data = request.json or {}
    password = data.get("password", "").strip()
    if not password:
        return jsonify({"ok": False, "error": "رمز دو مرحله‌ای الزامی است"}), 400

    async def _verify():
        global _login_client
        await _login_client.sign_in(password=password)
        session_str = _login_client.session.save()
        db.set_setting("session_data", session_str)
        db.set_setting("logged_in", "1")
        await _login_client.disconnect()
        return {"ok": True}

    try:
        result = run_async(_verify())
        return jsonify(result)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/logout", methods=["POST"])
def logout():
    db.set_setting("logged_in", "0")
    db.set_setting("session_data", "")
    return jsonify({"ok": True})


# ─── API تنظیمات ─────────────────────────────────────────────────────────────
@app.route("/api/settings", methods=["GET"])
def get_settings():
    keys = [
        "self_bot_active", "secretary_active", "anti_delete_active",
        "anti_link_active", "auto_seen_active", "auto_reaction_active",
        "private_lock_active", "enemy_reply_active", "auto_save_media",
        "clock_name_active", "clock_bio_active", "selected_font",
        "secretary_message", "auto_reaction_emoji", "spam_delay",
    ]
    return jsonify({k: db.get_setting(k) for k in keys})


@app.route("/api/settings", methods=["POST"])
def update_settings():
    data = request.json or {}
    allowed = [
        "secretary_message", "auto_reaction_emoji", "selected_font",
        "spam_delay", "spam_count",
    ]
    for k in allowed:
        if k in data:
            db.set_setting(k, data[k])
    return jsonify({"ok": True})


@app.route("/api/toggle/<key>", methods=["POST"])
def toggle(key):
    allowed_toggles = [
        "self_bot_active", "secretary_active", "anti_delete_active",
        "anti_link_active", "auto_seen_active", "auto_reaction_active",
        "private_lock_active", "enemy_reply_active", "auto_save_media",
        "clock_name_active", "clock_bio_active",
    ]
    if key not in allowed_toggles:
        return jsonify({"ok": False, "error": "کلید مجاز نیست"}), 400
    new_state = db.toggle_setting(key)
    return jsonify({"ok": True, "active": new_state})


# ─── API لیست‌ها ──────────────────────────────────────────────────────────────
@app.route("/api/enemies", methods=["GET"])
def get_enemies():
    return jsonify(db.get_enemies())


@app.route("/api/enemies", methods=["POST"])
def add_enemy():
    data = request.json or {}
    uid = data.get("user_id")
    if not uid:
        return jsonify({"ok": False, "error": "آیدی کاربر الزامی است"}), 400
    db.add_enemy(int(uid), data.get("username"), data.get("name"))
    return jsonify({"ok": True})


@app.route("/api/enemies/<int:uid>", methods=["DELETE"])
def del_enemy(uid):
    db.remove_enemy(uid)
    return jsonify({"ok": True})


@app.route("/api/enemies/clear", methods=["POST"])
def clear_enemies_api():
    db.clear_enemies()
    return jsonify({"ok": True})


@app.route("/api/friends", methods=["GET"])
def get_friends():
    return jsonify(db.get_friends())


@app.route("/api/friends", methods=["POST"])
def add_friend():
    data = request.json or {}
    uid = data.get("user_id")
    if not uid:
        return jsonify({"ok": False, "error": "آیدی کاربر الزامی است"}), 400
    db.add_friend(int(uid), data.get("username"), data.get("name"))
    return jsonify({"ok": True})


@app.route("/api/friends/<int:uid>", methods=["DELETE"])
def del_friend(uid):
    db.remove_friend(uid)
    return jsonify({"ok": True})


@app.route("/api/friends/clear", methods=["POST"])
def clear_friends_api():
    db.clear_friends()
    return jsonify({"ok": True})


# ─── API پیام‌های حذف شده ─────────────────────────────────────────────────────
@app.route("/api/deleted_messages", methods=["GET"])
def deleted_messages():
    return jsonify(db.get_deleted_messages(50))


# ─── راه‌اندازی بات در thread جداگانه ────────────────────────────────────────
def start_bot_thread():
    loop = get_loop()

    async def _run():
        from bot import start_bot
        await start_bot()

    asyncio.run_coroutine_threadsafe(_run(), loop)


# ─── اجرا ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    db.init_db()
    logged_in = db.get_setting("logged_in", "0") == "1"
    if logged_in:
        start_bot_thread()
    app.run(host="0.0.0.0", port=config.PORT, debug=False)
