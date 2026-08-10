from db import get_connection, init_database


def test_tables_exist():
    init_database()

    db = get_connection()

    rows = db.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    ).fetchall()

    db.close()

    table_names = {row["name"] for row in rows}

    expected_tables = {
        "users",
        "ingredients",
        "products",
        "recipe_ingredients",
        "production_logs",
        "stock_transactions",
    }

    assert expected_tables.issubset(table_names)