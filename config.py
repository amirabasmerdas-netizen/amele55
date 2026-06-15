import os
from dotenv import load_dotenv
import sys

# بارگذاری متغیرهای محیطی
load_dotenv()

# چاپ متغیرها برای دیباگ (فقط در توسعه)
print("🔧 Loading configuration...")

# تنظیمات اجباری
API_ID = int(os.environ.get("API_ID", 0))
if API_ID == 0:
    print("❌ ERROR: API_ID is not set in environment variables!")
    print("Please set API_ID in Render Dashboard -> Environment Variables")

API_HASH = os.environ.get("API_HASH", "")
if not API_HASH:
    print("❌ ERROR: API_HASH is not set in environment variables!")
    print("Please set API_HASH in Render Dashboard -> Environment Variables")

SECRET_KEY = os.environ.get("SECRET_KEY", "amel_self55_secret_key_change_me")
PORT = int(os.environ.get("PORT", 10000))  # Render uses port 10000 by default

# مسیر دیتابیس - مهم: در Render باید از دایرکتوری writable استفاده کنید
# Render فقط دایرکتوری /tmp قابل نوشتن است
DATABASE_PATH = os.environ.get("DATABASE_PATH", "/tmp/amel.db")
print(f"📁 Database path: {DATABASE_PATH}")

# تنظیمات ربات
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
if not BOT_TOKEN:
    print("⚠️ WARNING: BOT_TOKEN is not set - token system disabled")

OWNER_TG_ID = int(os.environ.get("OWNER_TG_ID", "0"))
if OWNER_TG_ID == 0:
    print("⚠️ WARNING: OWNER_TG_ID is not set - owner features disabled")

OWNER_USERNAME = os.environ.get("OWNER_USERNAME", "amele55")
OWNER_PHONE = os.environ.get("OWNER_PHONE", "").lstrip("+")

# ساخت SITE_URL برای Render
_render_host = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "")
if _render_host:
    SITE_URL = f"https://{_render_host}"
else:
    SITE_URL = os.environ.get("SITE_URL", "")

BOT_NAME = "AMEL SELF55"
BOT_VERSION = "1.2.0"

# API هواشناسی (اختیاری)
WEATHER_API_KEY = os.environ.get("WEATHER_API_KEY", "")

# تنظیمات توکن
TOKENS_PER_SESSION = 2
SESSION_HOURS = 2
DAILY_TOKEN_GIFT = 1
REFERRAL_TOKENS = 50
WELCOME_TOKENS = 10

print("✅ Configuration loaded successfully")
