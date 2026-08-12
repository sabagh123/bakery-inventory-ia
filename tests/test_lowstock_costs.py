import pytest
import sqlite3
from werkzeug.security import generate_password_hash

import db as database
from app import get_low_stock_ingredients, calculate_cost_contribution


@pytest.fixture
def setup_db(tmp_path, monkeypatch):
    test_database = tmp_path / "test.db"
    monkeypatch.setattr(database, "database_path", test_database)
    database.init_database()
    yield


def test_low_stock_flags(setup_db):
    db = database.get_connection()
    # below reorder
    db.execute("INSERT INTO ingredients (name, unit, stock_quantity, reorder_level, unit_cost) VALUES (?, ?, ?, ?, ?)", ("Low", "unit", 1, 5, 1.0))
    # equal reorder
    db.execute("INSERT INTO ingredients (name, unit, stock_quantity, reorder_level, unit_cost) VALUES (?, ?, ?, ?, ?)", ("Equal", "unit", 5, 5, 1.0))
    # above reorder
    db.execute("INSERT INTO ingredients (name, unit, stock_quantity, reorder_level, unit_cost) VALUES (?, ?, ?, ?, ?)", ("High", "unit", 10, 5, 1.0))
    # inactive low stock
    db.execute("INSERT INTO ingredients (name, unit, stock_quantity, reorder_level, unit_cost, is_active) VALUES (?, ?, ?, ?, ?, ?)", ("InactiveLow", "unit", 1, 5, 1.0, 0))
    db.commit()

    rows = get_low_stock_ingredients()
    names = [r["name"] for r in rows]

    assert "Low" in names
    assert "Equal" in names
    assert "High" not in names
    assert "InactiveLow" not in names

    db.close()


def test_cost_and_contribution_and_no_stock_change(setup_db):
    db = database.get_connection()
    # ingredients
    db.execute("INSERT INTO ingredients (name, unit, stock_quantity, reorder_level, unit_cost) VALUES (?, ?, ?, ?, ?)", ("Flour", "kg", 100, 10, 2.0))
    db.execute("INSERT INTO ingredients (name, unit, stock_quantity, reorder_level, unit_cost) VALUES (?, ?, ?, ?, ?)", ("Sugar", "kg", 100, 10, 1.0))
    db.commit()

    flour = db.execute("SELECT ingredient_id FROM ingredients WHERE name = 'Flour'").fetchone()["ingredient_id"]
    sugar = db.execute("SELECT ingredient_id FROM ingredients WHERE name = 'Sugar'").fetchone()["ingredient_id"]

    # product
    db.execute("INSERT INTO products (name, selling_price) VALUES (?, ?)", ("Cake", 20.0))
    pid = db.execute("SELECT product_id FROM products WHERE name = 'Cake'").fetchone()["product_id"]

    # recipe: 2 Flour, 1 Sugar
    db.execute("INSERT INTO recipe_ingredients (product_id, ingredient_id, quantity_required) VALUES (?, ?, ?)", (pid, flour, 2.0))
    db.execute("INSERT INTO recipe_ingredients (product_id, ingredient_id, quantity_required) VALUES (?, ?, ?)", (pid, sugar, 1.0))
    db.commit()

    # record stock before
    before_flour = db.execute("SELECT stock_quantity FROM ingredients WHERE ingredient_id = ?", (flour,)).fetchone()["stock_quantity"]
    before_sugar = db.execute("SELECT stock_quantity FROM ingredients WHERE ingredient_id = ?", (sugar,)).fetchone()["stock_quantity"]

    cost, contribution = calculate_cost_contribution(pid)

    assert cost == pytest.approx(2.0*2.0 + 1.0*1.0)
    assert contribution == pytest.approx(20.0 - cost)

    # ensure no stock change
    after_flour = db.execute("SELECT stock_quantity FROM ingredients WHERE ingredient_id = ?", (flour,)).fetchone()["stock_quantity"]
    after_sugar = db.execute("SELECT stock_quantity FROM ingredients WHERE ingredient_id = ?", (sugar,)).fetchone()["stock_quantity"]

    assert before_flour == after_flour
    assert before_sugar == after_sugar

    db.close()


def test_zero_cost_and_no_recipe(setup_db):
    db = database.get_connection()
    db.execute("INSERT INTO ingredients (name, unit, stock_quantity, reorder_level, unit_cost) VALUES (?, ?, ?, ?, ?)", ("Free", "unit", 10, 1, 0.0))
    db.commit()

    free = db.execute("SELECT ingredient_id FROM ingredients WHERE name = 'Free'").fetchone()["ingredient_id"]

    db.execute("INSERT INTO products (name, selling_price) VALUES (?, ?)", ("FreeItem", 5.0))
    pid = db.execute("SELECT product_id FROM products WHERE name = 'FreeItem'").fetchone()["product_id"]

    # add recipe with zero-cost ingredient
    db.execute("INSERT INTO recipe_ingredients (product_id, ingredient_id, quantity_required) VALUES (?, ?, ?)", (pid, free, 1.0))
    db.commit()

    cost, contribution = calculate_cost_contribution(pid)
    assert cost == pytest.approx(0.0)
    assert contribution == pytest.approx(5.0)

    # product with no recipe
    db.execute("INSERT INTO products (name, selling_price) VALUES (?, ?)", ("NoRecipe", 3.0))
    pid2 = db.execute("SELECT product_id FROM products WHERE name = 'NoRecipe'").fetchone()["product_id"]
    db.commit()

    c2, cont2 = calculate_cost_contribution(pid2)
    assert c2 is None and cont2 is None

    db.close()
