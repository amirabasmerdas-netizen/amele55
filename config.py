import os
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
SESSION_NAME = os.environ.get("SESSION_NAME", "amel_session")
SECRET_KEY = os.environ.get("SECRET_KEY", "amel_self55_secret_key_change_me")
PORT = int(os.environ.get("PORT", 5000))
DATABASE_PATH = os.environ.get("DATABASE_PATH", "amel.db")

BOT_NAME = "AMEL SELF55"
BOT_VERSION = "1.0.0"

WEATHER_API_KEY = os.environ.get("WEATHER_API_KEY", "")
EXCHANGE_API_KEY = os.environ.get("EXCHANGE_API_KEY", "")
