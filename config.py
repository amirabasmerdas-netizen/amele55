import os

# ─── تلگرام API ──────────────────────────────────────────────────────────
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")

# ─── پنل وب ──────────────────────────────────────────────────────────────
SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-production")
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "admin123")

# ─── سیستم الماس ─────────────────────────────────────────────────────────
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
TOKENS_PER_SESSION = int(os.environ.get("TOKENS_PER_SESSION", "10"))
SESSION_HOURS = int(os.environ.get("SESSION_HOURS", "24"))
DAILY_TOKEN_GIFT = int(os.environ.get("DAILY_TOKEN_GIFT", "2"))
REFERRAL_TOKENS = int(os.environ.get("REFERRAL_TOKENS", "5"))
OWNER_TG_ID = int(os.environ.get("OWNER_TG_ID", "0"))
OWNER_PHONE = os.environ.get("OWNER_PHONE", "").lstrip("+")

# ─── دیتابیس‌ها (جدید) ───────────────────────────────────────────────────
DATABASE_URL_PERSISTENT = os.environ.get("DATABASE_URL_PERSISTENT", "")
DATABASE_URL_TEMP = os.environ.get("DATABASE_URL_TEMP", "")

# ─── گپ مقصد چالش‌ها و جام جهانی ─────────────────────────────────────────
CHALLENGE_GROUP = os.environ.get("CHALLENGE_GROUP", "@Gp_SelfNexo")
