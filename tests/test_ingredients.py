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
        client.post(
            "/login",
            data={
                "username": "testuser",
                "password": "testpass"
            }
        )

        yield client


def test_add_ingredient(client):
    response = client.post(
        "/ingredients",
        data={
            "name": "Flour",
            "unit": "kg",
            "stock": "10",
            "reorder": "3",
            "cost": "2.10"
        },
        follow_redirects=True
    )

    assert response.status_code == 200
    assert b"Flour" in response.data


def test_zero_stock_allowed(client):
    response = client.post(
        "/ingredients",
        data={
            "name": "Eggs",
            "unit": "unit",
            "stock": "0",
            "reorder": "24",
            "cost": "0.20"
        },
        follow_redirects=True
    )

    assert response.status_code == 200
    assert b"Eggs" in response.data


def test_invalid_cost(client):
    response = client.post(
        "/ingredients",
        data={
            "name": "Butter",
            "unit": "kg",
            "stock": "5",
            "reorder": "2",
            "cost": "abc"
        }
    )

    assert b"Unit cost must be a number." in response.data


def test_duplicate_name(client):
    ingredient = {
        "name": "Flour",
        "unit": "kg",
        "stock": "10",
        "reorder": "3",
        "cost": "2.10"
    }

    client.post("/ingredients", data=ingredient)

    ingredient["name"] = " flour "

    response = client.post(
        "/ingredients",
        data=ingredient
    )

    assert b"already exists" in response.data

def test_edit_ingredient(client):
    client.post(
        "/ingredients",
        data={
            "name": "Flour",
            "unit": "kg",
            "stock": "10",
            "reorder": "3",
            "cost": "2.10"
        }
    )

    db = database.get_connection()

    ingredient = db.execute(
        "SELECT * FROM ingredients WHERE name = 'Flour'"
    ).fetchone()

    db.close()

    client.post(
        f"/ingredients/{ingredient['ingredient_id']}/edit",
        data={
            "name": "Flour",
            "unit": "kg",
            "reorder": "4",
            "cost": "2.20"
        }
    )

    db = database.get_connection()

    updated = db.execute(
        "SELECT * FROM ingredients WHERE ingredient_id = ?",
        (ingredient["ingredient_id"],)
    ).fetchone()

    db.close()

    assert updated["reorder_level"] == 4
    assert updated["unit_cost"] == 2.20


def test_deactivate_ingredient(client):
    client.post(
        "/ingredients",
        data={
            "name": "Butter",
            "unit": "kg",
            "stock": "5",
            "reorder": "2",
            "cost": "8.50"
        }
    )

    db = database.get_connection()

    ingredient = db.execute(
        "SELECT * FROM ingredients WHERE name = 'Butter'"
    ).fetchone()

    db.close()

    client.post(
        f"/ingredients/{ingredient['ingredient_id']}/deactivate"
    )

    db = database.get_connection()

    updated = db.execute(
        "SELECT * FROM ingredients WHERE ingredient_id = ?",
        (ingredient["ingredient_id"],)
    ).fetchone()

    db.close()

    assert updated["is_active"] == 0


def test_stock_adjustment_creates_log(client):
    client.post(
        "/ingredients",
        data={
            "name": "Flour",
            "unit": "kg",
            "stock": "10",
            "reorder": "3",
            "cost": "2.10"
        }
    )

    db = database.get_connection()

    ingredient = db.execute(
        "SELECT * FROM ingredients WHERE name = 'Flour'"
    ).fetchone()

    db.close()

    client.post(
        f"/ingredients/{ingredient['ingredient_id']}/stock",
        data={
            "change": "5",
            "reason": "Purchase"
        }
    )

    db = database.get_connection()

    updated = db.execute(
        "SELECT * FROM ingredients WHERE ingredient_id = ?",
        (ingredient["ingredient_id"],)
    ).fetchone()

    transaction = db.execute(
        """
        SELECT *
        FROM stock_transactions
        WHERE ingredient_id = ?
        """,
        (ingredient["ingredient_id"],)
    ).fetchone()

    db.close()

    assert updated["stock_quantity"] == 15
    assert transaction["quantity_change"] == 5
    assert transaction["reason"] == "Purchase"


def test_stock_cannot_become_negative(client):
    client.post(
        "/ingredients",
        data={
            "name": "Eggs",
            "unit": "unit",
            "stock": "2",
            "reorder": "10",
            "cost": "0.20"
        }
    )

    db = database.get_connection()

    ingredient = db.execute(
        "SELECT * FROM ingredients WHERE name = 'Eggs'"
    ).fetchone()

    db.close()

    response = client.post(
        f"/ingredients/{ingredient['ingredient_id']}/stock",
        data={
            "change": "-3",
            "reason": "correction"
        }
    )

    assert b"Stock cannot become negative." in response.data

    db = database.get_connection()

    updated = db.execute(
        "SELECT * FROM ingredients WHERE ingredient_id = ?",
        (ingredient["ingredient_id"],)
    ).fetchone()

    transactions = db.execute(
        """
        SELECT COUNT(*) AS total
        FROM stock_transactions
        WHERE ingredient_id = ?
        """,
        (ingredient["ingredient_id"],)
    ).fetchone()

    db.close()

    assert updated["stock_quantity"] == 2
    assert transactions["total"] == 0