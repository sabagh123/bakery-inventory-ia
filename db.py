from pathlib import Path
import sqlite3


BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
DATABASE_PATH = INSTANCE_DIR / "bakery.db"


def get_connection():
    """Create and return a connection to the SQLite database."""
    INSTANCE_DIR.mkdir(exist_ok=True)

    connection = sqlite3.connect(DATABASE_PATH)

    # Allows rows to be accessed using column names.
    connection.row_factory = sqlite3.Row

    # SQLite requires foreign-key enforcement to be enabled per connection.
    connection.execute("PRAGMA foreign_keys = ON")

    return connection


def init_database():
    """Create all database tables using schema.sql."""
    connection = get_connection()

    schema_path = BASE_DIR / "schema.sql"

    with open(schema_path, "r", encoding="utf-8") as schema_file:
        connection.executescript(schema_file.read())

    connection.close()


if __name__ == "__main__":
    init_database()
    print("Database initialized successfully.")