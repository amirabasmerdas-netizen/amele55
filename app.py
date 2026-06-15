import asyncio
import os
import threading
from functools import wraps
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
from bot import bot_manager

app = Flask(__name__)
app.secret_key = config.SECRET_KEY

# ─── event loop ────────────────────────────────────────────────────────────────
_loop = None
_login_clients = {}
_phone_hashes = {}
_phone_numbers = {}

def get_loop():
    global _loop
    if _loop is None or _loop.is_closed():
        _loop = asyncio.new_event_loop()
        t = threading.Thread(target=_loop.run_forever, daemon=True)
        t.start()
    return _loop

def run_async(coro):
    return asyncio.run_coroutine_threadsafe(coro, get_loop()).result(timeout=30)

# ─── احراز هویت ────────────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("owner_id"):
            if request.path.startswith("/api/"):
                return jsonify({"ok": False, "error": "وارد نشده‌اید"}), 401
            return redirect(url_for("panel_login_page"))
        return f(*args, **kwargs)
    return decorated

def owner_id() -> int:
    return int(session["owner_id"])

# ─── health checks ─────────────────────────────────────────────────────────────
@app.route("/ping")
def ping():
    return "pong", 200

@app.route("/health")
def health():
    return jsonify({"status": "ok", "bot": config.BOT_NAME}), 200

# =============================================================================
# ✅ مسیرهای ثبت‌نام و ورود (اصلاح شده)
# =============================================================================

@app.route("/")
@login_required
def index():
    if db.get_setting(owner_id(), "logged_in") != "1":
        return redirect(url_for("tg_login_page"))
    return render_template(
        "panel.html",
        page="panel",
        username=db.get_account(owner_id())["username"],
        owner_id=owner_id(),
    )

# ✅ صفحه ثبت‌نام
@app.route("/register", methods=["GET"])
def register_page():
    if session.get("owner_id"):
        return redirect(url_for("index"))
    return render_template("panel.html", page="register")

# ✅ API ثبت‌نام (POST)
@app.route("/api/register", methods=["POST"])
def api_register():
    try:
        data = request.get_json()
        
        # بررسی وجود داده
        if not data:
            return jsonify({"ok": False, "error": "داده‌ای ارسال نشده است"}), 400
        
        username = data.get("username", "").strip()
        password = data.get("password", "").strip()
        
        # اعتبارسنجی
        if not username or not password:
            return jsonify({"ok": False, "error": "یوزرنیم و رمز عبور الزامی هستند"}), 400
        
        if len(username) < 3:
            return jsonify({"ok": False, "error": "یوزرنیم باید حداقل ۳ کاراکتر باشد"}), 400
        
        if len(password) < 6:
            return jsonify({"ok": False, "error": "رمز عبور باید حداقل ۶ کاراکتر باشد"}), 400
        
        # ایجاد حساب
        new_id = db.create_account(username, password)
        
        if new_id is None:
            # بررسی اینکه آیا یوزرنیم تکراری است
            existing = db.get_account_by_username(username)
            if existing:
                return jsonify({"ok": False, "error": "این یوزرنیم قبلاً ثبت شده است"}), 409
            return jsonify({"ok": False, "error": "خطا در ایجاد حساب کاربری"}), 500
        
        # مقداردهی اولیه تنظیمات
        db.init_user_settings(new_id)
        
        # ذخیره در session
        session["owner_id"] = new_id
        session.permanent = True
        
        return jsonify({"ok": True, "message": "ثبت‌نام با موفقیت انجام شد"})
        
    except Exception as e:
        print(f"❌ خطا در ثبت‌نام: {e}")
        return jsonify({"ok": False, "error": f"خطای سرور: {str(e)}"}), 500

# ✅ صفحه ورود به پنل
@app.route("/panel-login", methods=["GET"])
def panel_login_page():
    if session.get("owner_id"):
        return redirect(url_for("index"))
    has_accounts = db.account_exists()
    return render_template("panel.html", page="panel_login", has_accounts=has_accounts)

# ✅ API ورود به پنل (POST)
@app.route("/api/panel-login", methods=["POST"])
def api_panel_login():
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"ok": False, "error": "داده‌ای ارسال نشده است"}), 400
        
        username = data.get("username", "").strip()
        password = data.get("password", "").strip()
        
        if not username or not password:
            return jsonify({"ok": False, "error": "یوزرنیم و رمز عبور الزامی هستند"}), 400
        
        uid = db.verify_account(username, password)
        
        if uid is None:
            return jsonify({"ok": False, "error": "یوزرنیم یا رمز عبور اشتباه است"}), 401
        
        session["owner_id"] = uid
        session.permanent = True
        
        # اگر قبلاً لاگین کرده بود، بات را شروع کن
        if db.get_setting(uid, "logged_in") == "1":
            bot_manager.start(uid, get_loop(), check_tokens=False)
        
        return jsonify({"ok": True, "message": "ورود موفقیت‌آمیز بود"})
        
    except Exception as e:
        print(f"❌ خطا در ورود: {e}")
        return jsonify({"ok": False, "error": f"خطای سرور: {str(e)}"}), 500

@app.route("/api/panel-logout", methods=["POST"])
@login_required
def api_panel_logout():
    session.pop("owner_id", None)
    return jsonify({"ok": True})

# ─── ادامه بقیه کد (لاگین تلگرام، تنظیمات، توکن‌ها و...) ───────────────────────
# ... (بقیه کدهای قبلی شما همینجا ادامه دارد)
