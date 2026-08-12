import pytest
from werkzeug.security import generate_password_hash

import db as database
from app import app, calculate_capacity


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


def test_calculate_capacity_normal():
    recipe = [
        {"stock_quantity": 10, "quantity_required": 2},
        {"stock_quantity": 15, "quantity_required": 4},
    ]

    assert calculate_capacity(recipe) == 3


def test_calculate_capacity_exact_boundary():
    recipe = [
        {"stock_quantity": 10, "quantity_required": 2},
        {"stock_quantity": 9, "quantity_required": 3},
    ]

    assert calculate_capacity(recipe) == 3


def test_calculate_capacity_zero_stock():
    recipe = [
        {"stock_quantity": 0, "quantity_required": 1},
        {"stock_quantity": 5, "quantity_required": 2},
    ]

    assert calculate_capacity(recipe) == 0


def test_calculate_capacity_no_recipe():
    assert calculate_capacity([]) == 0


def test_calculate_capacity_does_not_modify_stock(client):
    client.post(
        "/ingredients",
        data={
            "name": "Flour",
            "unit": "kg",
            "stock": "10",
            "reorder": "1",
            "cost": "1.00"
        }
    )
    client.post(
        "/ingredients",
        data={
            "name": "Sugar",
            "unit": "kg",
            "stock": "5",
            "reorder": "1",
            "cost": "1.00"
        }
    )

    db = database.get_connection()
    ingredients = db.execute(
        "SELECT ingredient_id FROM ingredients WHERE name IN ('Flour', 'Sugar')"
    ).fetchall()
    db.close()

    db = database.get_connection()
    db.execute(
        "INSERT INTO products (name, selling_price) VALUES (?, ?)",
        ("Test Product", 5.0)
    )
    product_id = db.execute("SELECT product_id FROM products WHERE name = ?", ("Test Product",)).fetchone()["product_id"]

    flour_id, sugar_id = ingredients[0]["ingredient_id"], ingredients[1]["ingredient_id"]
    db.execute(
        "INSERT INTO recipe_ingredients (product_id, ingredient_id, quantity_required) VALUES (?, ?, ?)",
        (product_id, flour_id, 2.0)
    )
    db.execute(
        "INSERT INTO recipe_ingredients (product_id, ingredient_id, quantity_required) VALUES (?, ?, ?)",
        (product_id, sugar_id, 1.0)
    )
    db.commit()

    before_stocks = db.execute(
        "SELECT stock_quantity FROM ingredients ORDER BY ingredient_id"
    ).fetchall()
    db.close()

    response = client.get(f"/capacity?product_id={product_id}")
    assert response.status_code == 200

    db = database.get_connection()
    after_stocks = db.execute(
        "SELECT stock_quantity FROM ingredients ORDER BY ingredient_id"
    ).fetchall()
    db.close()

    assert [row["stock_quantity"] for row in before_stocks] == [row["stock_quantity"] for row in after_stocks]
