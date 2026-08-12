import pytest
import sqlite3
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
        client.post(
            "/login",
            data={"username": "testuser", "password": "testpass"}
        )
        yield client


def setup_product_with_ingredients(db, ingredient_data, product_name="Prod"):
    # ingredient_data: list of tuples (name, unit, stock, reorder, cost)
    ids = []
    for name, unit, stock, reorder, cost in ingredient_data:
        db.execute(
            "INSERT INTO ingredients (name, unit, stock_quantity, reorder_level, unit_cost) VALUES (?, ?, ?, ?, ?)",
            (name, unit, stock, reorder, cost)
        )
    db.commit()

    ing_rows = db.execute(
        "SELECT ingredient_id FROM ingredients WHERE name IN (%s)" % 
        ",".join(['?']*len(ingredient_data)),
        tuple([row[0] for row in ingredient_data])
    ).fetchall()

    ids = [r["ingredient_id"] for r in ing_rows]

    db.execute(
        "INSERT INTO products (name, selling_price) VALUES (?, ?)",
        (product_name, 10.0)
    )
    product_id = db.execute("SELECT product_id FROM products WHERE name = ?", (product_name,)).fetchone()["product_id"]

    return product_id, ids


def test_valid_production_deducts_stock(client):
    db = database.get_connection()

    # create ingredients
    db.execute("INSERT INTO ingredients (name, unit, stock_quantity, reorder_level, unit_cost) VALUES (?, ?, ?, ?, ?)", ("Flour", "kg", 10, 1, 2.0))
    db.execute("INSERT INTO ingredients (name, unit, stock_quantity, reorder_level, unit_cost) VALUES (?, ?, ?, ?, ?)", ("Sugar", "kg", 20, 1, 1.0))
    db.commit()

    flour_id = db.execute("SELECT ingredient_id FROM ingredients WHERE name = 'Flour'").fetchone()["ingredient_id"]
    sugar_id = db.execute("SELECT ingredient_id FROM ingredients WHERE name = 'Sugar'").fetchone()["ingredient_id"]

    db.execute("INSERT INTO products (name, selling_price) VALUES (?, ?)", ("Cake", 5.0))
    product_id = db.execute("SELECT product_id FROM products WHERE name = 'Cake'").fetchone()["product_id"]

    db.execute("INSERT INTO recipe_ingredients (product_id, ingredient_id, quantity_required) VALUES (?, ?, ?)", (product_id, flour_id, 2.0))
    db.execute("INSERT INTO recipe_ingredients (product_id, ingredient_id, quantity_required) VALUES (?, ?, ?)", (product_id, sugar_id, 1.0))
    db.commit()

    response = client.post("/capacity", data={"product_id": product_id, "portions": "3"}, follow_redirects=True)
    assert response.status_code == 200

    db = database.get_connection()
    flour = db.execute("SELECT stock_quantity FROM ingredients WHERE ingredient_id = ?", (flour_id,)).fetchone()["stock_quantity"]
    sugar = db.execute("SELECT stock_quantity FROM ingredients WHERE ingredient_id = ?", (sugar_id,)).fetchone()["stock_quantity"]

    # flour deducted by 2*3=6 -> 4 left
    assert flour == 4
    # sugar deducted by 1*3=3 -> 17 left
    assert sugar == 17

    # production log created
    prod = db.execute("SELECT * FROM production_logs WHERE product_id = ?", (product_id,)).fetchone()
    assert prod is not None

    # stock transactions created
    tx = db.execute("SELECT * FROM stock_transactions WHERE production_id = ?", (prod["production_id"],)).fetchall()
    assert len(tx) == 2
    assert all(t["quantity_change"] < 0 for t in tx)

    db.close()


def test_production_exact_capacity_succeeds(client):
    db = database.get_connection()
    db.execute("INSERT INTO ingredients (name, unit, stock_quantity, reorder_level, unit_cost) VALUES (?, ?, ?, ?, ?)", ("Milk", "ml", 6000, 1, 0.5))
    db.execute("INSERT INTO ingredients (name, unit, stock_quantity, reorder_level, unit_cost) VALUES (?, ?, ?, ?, ?)", ("Yeast", "g", 3, 1, 0.2))
    db.commit()

    milk = db.execute("SELECT ingredient_id FROM ingredients WHERE name = 'Milk'").fetchone()["ingredient_id"]
    yeast = db.execute("SELECT ingredient_id FROM ingredients WHERE name = 'Yeast'").fetchone()["ingredient_id"]

    db.execute("INSERT INTO products (name, selling_price) VALUES (?, ?)", ("Bread", 2.0))
    pid = db.execute("SELECT product_id FROM products WHERE name = 'Bread'").fetchone()["product_id"]

    # quantities are in the same unit as stock (ml and g)
    db.execute("INSERT INTO recipe_ingredients (product_id, ingredient_id, quantity_required) VALUES (?, ?, ?)", (pid, milk, 2000.0))
    db.execute("INSERT INTO recipe_ingredients (product_id, ingredient_id, quantity_required) VALUES (?, ?, ?)", (pid, yeast, 1.0))
    db.commit()

    # capacity: milk 6/2=3, yeast 3/1=3 -> 3
    response = client.post("/capacity", data={"product_id": pid, "portions": "3"}, follow_redirects=True)
    assert response.status_code == 200

    db = database.get_connection()
    prod = db.execute("SELECT * FROM production_logs WHERE product_id = ?", (pid,)).fetchone()
    assert prod is not None
    db.close()


def test_production_above_capacity_rejected(client):
    db = database.get_connection()
    db.execute("INSERT INTO ingredients (name, unit, stock_quantity, reorder_level, unit_cost) VALUES (?, ?, ?, ?, ?)", ("A", "unit", 2, 1, 1.0))
    db.commit()

    aid = db.execute("SELECT ingredient_id FROM ingredients WHERE name = 'A'").fetchone()["ingredient_id"]
    db.execute("INSERT INTO products (name, selling_price) VALUES (?, ?)", ("P", 1.0))
    pid = db.execute("SELECT product_id FROM products WHERE name = 'P'").fetchone()["product_id"]
    db.execute("INSERT INTO recipe_ingredients (product_id, ingredient_id, quantity_required) VALUES (?, ?, ?)", (pid, aid, 1.0))
    db.commit()

    response = client.post("/capacity", data={"product_id": pid, "portions": "3"}, follow_redirects=True)
    assert b"Requested portions exceed current capacity." in response.data

    # ensure no production logs
    db = database.get_connection()
    prod = db.execute("SELECT * FROM production_logs WHERE product_id = ?", (pid,)).fetchone()
    assert prod is None
    db.close()


def test_zero_negative_non_numeric_portions_rejected(client):
    db = database.get_connection()
    db.execute("INSERT INTO ingredients (name, unit, stock_quantity, reorder_level, unit_cost) VALUES (?, ?, ?, ?, ?)", ("B", "unit", 10, 1, 1.0))
    db.commit()
    bid = db.execute("SELECT ingredient_id FROM ingredients WHERE name = 'B'").fetchone()["ingredient_id"]
    db.execute("INSERT INTO products (name, selling_price) VALUES (?, ?)", ("Q", 1.0))
    qid = db.execute("SELECT product_id FROM products WHERE name = 'Q'").fetchone()["product_id"]
    db.execute("INSERT INTO recipe_ingredients (product_id, ingredient_id, quantity_required) VALUES (?, ?, ?)", (qid, bid, 2.0))
    db.commit()

    resp = client.post("/capacity", data={"product_id": qid, "portions": "0"}, follow_redirects=True)
    assert b"Portions must be a positive whole number." in resp.data

    resp = client.post("/capacity", data={"product_id": qid, "portions": "-1"}, follow_redirects=True)
    assert b"Portions must be a positive whole number." in resp.data

    resp = client.post("/capacity", data={"product_id": qid, "portions": "abc"}, follow_redirects=True)
    assert b"Portions must be a positive whole number." in resp.data

    db.close()


def test_failed_production_rollback(client, monkeypatch):
    db = database.get_connection()
    db.execute("INSERT INTO ingredients (name, unit, stock_quantity, reorder_level, unit_cost) VALUES (?, ?, ?, ?, ?)", ("X", "unit", 10, 1, 1.0))
    db.execute("INSERT INTO ingredients (name, unit, stock_quantity, reorder_level, unit_cost) VALUES (?, ?, ?, ?, ?)", ("Y", "unit", 10, 1, 1.0))
    db.commit()

    x = db.execute("SELECT ingredient_id FROM ingredients WHERE name = 'X'").fetchone()["ingredient_id"]
    y = db.execute("SELECT ingredient_id FROM ingredients WHERE name = 'Y'").fetchone()["ingredient_id"]

    db.execute("INSERT INTO products (name, selling_price) VALUES (?, ?)", ("Z", 1.0))
    pid = db.execute("SELECT product_id FROM products WHERE name = 'Z'").fetchone()["product_id"]

    db.execute("INSERT INTO recipe_ingredients (product_id, ingredient_id, quantity_required) VALUES (?, ?, ?)", (pid, x, 2.0))
    db.execute("INSERT INTO recipe_ingredients (product_id, ingredient_id, quantity_required) VALUES (?, ?, ?)", (pid, y, 2.0))
    db.commit()
    db.close()

    # monkeypatch database.get_connection to fail after first few executes
    real_conn = database.get_connection()
    class FailConn:
        def __init__(self, conn, fail_after=3):
            self._conn = conn
            self._count = 0
            self._fail_after = fail_after
        def execute(self, *args, **kwargs):
            self._count += 1
            if self._count > self._fail_after:
                raise sqlite3.Error("simulated failure")
            return self._conn.execute(*args, **kwargs)
        def __getattr__(self, name):
            return getattr(self._conn, name)

    def fake_get_connection():
        return FailConn(real_conn, fail_after=3)

    monkeypatch.setattr(database, "get_connection", fake_get_connection)

    # attempt production which should fail and rollback
    resp = client.post("/capacity", data={"product_id": pid, "portions": "2"}, follow_redirects=True)
    assert b"Production failed and was rolled back." in resp.data

    # check stock unchanged
    db2 = database.get_connection()
    stocks = db2.execute("SELECT stock_quantity FROM ingredients WHERE ingredient_id IN (?, ?) ORDER BY ingredient_id", (x, y)).fetchall()
    assert stocks[0]["stock_quantity"] == 10
    assert stocks[1]["stock_quantity"] == 10

    # no production logs
    prod = db2.execute("SELECT * FROM production_logs WHERE product_id = ?", (pid,)).fetchone()
    assert prod is None
    db2.close()
