import os
from werkzeug.security import generate_password_hash
from db import init_database, get_connection

username = os.environ.get("ADMIN_USERNAME")
password = os.environ.get("ADMIN_PASSWORD")

if not username or not password or len(password) < 12:
    raise RuntimeError("Set ADMIN_USERNAME and ADMIN_PASSWORD (12+ characters).")

init_database()

conn = get_connection()

try:
    conn.execute(
        "INSERT OR IGNORE INTO users (username, password_hash) VALUES (?, ?)",
        (username, generate_password_hash(password))
    )
    conn.commit()
finally:
    conn.close()
