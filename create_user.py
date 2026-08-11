import sqlite3
from getpass import getpass

from werkzeug.security import generate_password_hash

from db import get_connection


username = input("Username: ").strip()
password = getpass("Password: ")
confirm_password = getpass("Confirm password: ")

if not username:
    print("Username cannot be empty.")

elif not password:
    print("Password cannot be empty.")

elif len(password) < 6:
    print("Password must be at least 6 characters.")

elif password != confirm_password:
    print("Passwords do not match.")

else:
    db = get_connection()

    try:
        password_hash = generate_password_hash(password)

        db.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, password_hash)
        )

        db.commit()
        print("User created successfully.")

    except sqlite3.IntegrityError:
        print("That username already exists.")

    finally:
        db.close()