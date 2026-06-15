import sqlite3
import hashlib
import os
import datetime
from config import DATABASE_PATH

# اطمینان از وجود دایرکتوری دیتابیس
db_dir = os.path.dirname(DATABASE_PATH)
if db_dir and not os.path.exists(db_dir):
    try:
        os.makedirs(db_dir, exist_ok=True)
        print(f"📁 Created database directory: {db_dir}")
    except Exception as e:
        print(f"⚠️ Could not create database directory: {e}")

def get_conn():
    conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def _hash_pw(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def init_db():
    print("🔧 Initializing database tables...")
    conn = get_conn()
    c = conn.cursor()
    
    # (بقیه CREATE TABLE statements همینجا...)
    
    conn.commit()
    conn.close()
    print("✅ Database tables created/verified")
