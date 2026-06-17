import os
from dotenv import load_dotenv

load_dotenv()

# Telegram API
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")

# Supabase (اصلی - پایدار)
DATABASE_URL = os.environ.get("DATABASE_URL", "")

# Render DB (سریع - SQLite)
RENDER_DB_PATH = os.environ.get("RENDER_DB_PATH", "/tmp/fast_cache.db")

# Bot
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
OWNER_TG_ID = int(os.environ.get("OWNER_TG_ID", "8296865861"))
OWNER_USERNAME = os.environ.get("OWNER_USERNAME", "Amele55")

# Channels
LOTTERY_CHANNEL = os.environ.get("LOTTERY_CHANNEL", "@SelfNexoLottery")

# Web
SECRET_KEY = os.environ.get("SECRET_KEY", "self_nexo_secret_2026")
PORT = int(os.environ.get("PORT", 5000))

_render_host = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "")
SITE_URL = os.environ.get("SITE_URL", f"https://{_render_host}" if _render_host else "")

# Project Info
BOT_NAME = "سلف ساز | Self Nexo"
BOT_VERSION = "3.0.0"

# Pricing
TOKEN_PRICE_TOMAN = 200
SELF_PRICE = 2  # الماس برای 2 ساعت
DAILY_GIFT = 1
REFERRAL_BONUS = 10
