from pathlib import Path
import sqlite3


base_dir = Path(__file__).resolve().parent
instance_dir = base_dir / "instance"
database_path = instance_dir / "bakery.db"


def get_connection():
    instance_dir.mkdir(exist_ok=True)

    db = sqlite3.connect(database_path)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")

    return db


def init_database():
    db = get_connection()
    schema_path = base_dir / "schema.sql"

    with open(schema_path, "r", encoding="utf-8") as file:
        db.executescript(file.read())

    db.close()


if __name__ == "__main__":
    init_database()
    print("Database initialized successfully.")