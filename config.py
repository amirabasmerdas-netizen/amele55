import os
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
PHONE = os.getenv("PHONE", "")
SESSION_NAME = os.getenv("SESSION_NAME", "amel_session")
SECRET_KEY = os.getenv("SECRET_KEY", "amel-self55-secret-key-change-in-prod")
PORT = int(os.getenv("PORT", "5000"))
TIMEZONE = "Asia/Tehran"
DB_PATH = os.getenv("DB_PATH", "amel.db")
PANEL_PASSWORD = os.getenv("PANEL_PASSWORD", "admin1234")
