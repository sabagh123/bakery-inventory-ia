import pytest
from werkzeug.security import generate_password_hash

import db as database
from app import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    test_database = tmp_path / "test.db"
    monkeypatch.setattr(database, "database_path", test_database)
    database.init_database()

    db = database.get_connection()
    db.execute(
        "INSERT INTO users (username, password_hash) VALUES (?, ?)",
        ("testuser", generate_password_hash("testpass"))
    )
    db.commit()
    db.close()

    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def login(client):
    response = client.post(
        "/login",
        data={"username": "testuser", "password": "testpass"}
    )
    assert response.status_code == 302


def test_history_requires_login(client):
    response = client.get("/history")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_persistence_across_connections(tmp_path, monkeypatch):
    test_database = tmp_path / "test.db"
    monkeypatch.setattr(database, "database_path", test_database)
    database.init_database()

    conn = database.get_connection()
    conn.execute(
        "INSERT INTO ingredients (name, unit, stock_quantity, reorder_level, unit_cost) VALUES (?, ?, ?, ?, ?)",
        ("Persist", "unit", 5, 1, 1.0)
    )
    conn.commit()
    conn.close()

    conn2 = database.get_connection()
    row = conn2.execute(
        "SELECT name, stock_quantity FROM ingredients WHERE name = ?",
        ("Persist",)
    ).fetchone()
    conn2.close()

    assert row is not None
    assert row["name"] == "Persist"
    assert row["stock_quantity"] == 5


def test_stock_adjustment_shows_in_history(client):
    login(client)

    db = database.get_connection()
    db.execute(
        "INSERT INTO ingredients (name, unit, stock_quantity, reorder_level, unit_cost) VALUES (?, ?, ?, ?, ?)",
        ("Tomato", "unit", 10, 1, 1.0)
    )
    db.commit()
    ingredient_id = db.execute(
        "SELECT ingredient_id FROM ingredients WHERE name = ?",
        ("Tomato",)
    ).fetchone()["ingredient_id"]
    db.close()

    response = client.post(
        f"/ingredients/{ingredient_id}/stock",
        data={"change": "3", "reason": "Purchase"},
        follow_redirects=True
    )

    assert response.status_code == 200
    history = client.get("/history")
    assert history.status_code == 200
    assert b"Purchase" in history.data
    assert b"Tomato" in history.data
    assert b"3.0" in history.data


def test_production_history_and_transaction_history(client):
    login(client)

    db = database.get_connection()
    db.execute(
        "INSERT INTO ingredients (name, unit, stock_quantity, reorder_level, unit_cost) VALUES (?, ?, ?, ?, ?)",
        ("Flour", "kg", 20, 1, 2.0)
    )
    flour_id = db.execute("SELECT ingredient_id FROM ingredients WHERE name = ?", ("Flour",)).fetchone()["ingredient_id"]
    db.execute("INSERT INTO products (name, selling_price) VALUES (?, ?)", ("Bread", 10.0))
    product_id = db.execute("SELECT product_id FROM products WHERE name = ?", ("Bread",)).fetchone()["product_id"]
    db.execute(
        "INSERT INTO recipe_ingredients (product_id, ingredient_id, quantity_required) VALUES (?, ?, ?)",
        (product_id, flour_id, 2.0)
    )
    db.commit()
    db.close()

    response = client.post(
        "/capacity",
        data={"product_id": product_id, "portions": "2"},
        follow_redirects=True
    )

    assert response.status_code == 200
    assert b"Production recorded successfully." in response.data

    before_stock = database.get_connection().execute(
        "SELECT stock_quantity FROM ingredients WHERE ingredient_id = ?",
        (flour_id,)
    ).fetchone()["stock_quantity"]
    database.get_connection().close()

    history = client.get("/history")
    assert history.status_code == 200
    assert b"Bread" in history.data
    assert b"2" in history.data
    assert b"4.0" in history.data

    after_stock = database.get_connection().execute(
        "SELECT stock_quantity FROM ingredients WHERE ingredient_id = ?",
        (flour_id,)
    ).fetchone()["stock_quantity"]
    database.get_connection().close()

    assert before_stock == after_stock
