import os
import sqlite3

from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import check_password_hash

from db import get_connection
from validation import (
    validate_ingredient,
    validate_ingredient_edit,
    validate_stock_change,
    validate_product
)


app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "development-key")


@app.route("/")
def home():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None

    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        db = get_connection()

        user = db.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,)
        ).fetchone()

        db.close()

        if user is None or not check_password_hash(user["password_hash"], password):
            error = "Invalid username or password."

        else:
            session.clear()
            session["user_id"] = user["user_id"]

            return redirect(url_for("dashboard"))

    return render_template("login.html", error=error)


@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    return render_template("dashboard.html")


@app.route("/ingredients", methods=["GET", "POST"])
def ingredients():
    if "user_id" not in session:
        return redirect(url_for("login"))

    error = None

    if request.method == "POST":
        errors, name, numbers = validate_ingredient(
            request.form["name"],
            request.form["unit"],
            request.form["stock"],
            request.form["reorder"],
            request.form["cost"]
        )

        db = get_connection()

        if name:
            duplicate = db.execute(
                """
                SELECT ingredient_id, is_active
                FROM ingredients
                WHERE LOWER(TRIM(name)) = LOWER(TRIM(?))
                """,
                (name,)
            ).fetchone()

            if duplicate:
                errors.append("An ingredient with that name already exists.")

        if not errors:
            db.execute(
                """
                INSERT INTO ingredients
                (name, unit, stock_quantity, reorder_level, unit_cost)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    name,
                    request.form["unit"],
                    numbers["stock"],
                    numbers["reorder"],
                    numbers["cost"]
                )
            )

            db.commit()
            db.close()

            return redirect(url_for("ingredients"))

        db.close()
        error = " ".join(errors)

    db = get_connection()

    active_ingredients = db.execute(
        """
        SELECT *
        FROM ingredients
        WHERE is_active = 1
        ORDER BY name
        """
    ).fetchall()

    inactive_ingredients = db.execute(
        """
        SELECT *
        FROM ingredients
        WHERE is_active = 0
        ORDER BY name
        """
    ).fetchall()

    db.close()

    return render_template(
        "ingredients.html",
        active_ingredients=active_ingredients,
        inactive_ingredients=inactive_ingredients,
        error=error,
        form=request.form
    )


@app.route("/ingredients/<int:ingredient_id>/edit", methods=["GET", "POST"])
def edit_ingredient(ingredient_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    db = get_connection()

    ingredient = db.execute(
        "SELECT * FROM ingredients WHERE ingredient_id = ?",
        (ingredient_id,)
    ).fetchone()

    if ingredient is None:
        db.close()
        return redirect(url_for("ingredients"))

    error = None

    if request.method == "POST":
        errors, name, numbers = validate_ingredient_edit(
            request.form["name"],
            request.form["unit"],
            request.form["reorder"],
            request.form["cost"]
        )

        duplicate = db.execute(
            """
            SELECT ingredient_id
            FROM ingredients
            WHERE LOWER(TRIM(name)) = LOWER(TRIM(?))
            AND ingredient_id != ?
            """,
            (name, ingredient_id)
        ).fetchone()

        if duplicate:
            errors.append("An ingredient with that name already exists.")

        if not errors:
            db.execute(
                """
                UPDATE ingredients
                SET name = ?, unit = ?, reorder_level = ?, unit_cost = ?
                WHERE ingredient_id = ?
                """,
                (
                    name,
                    request.form["unit"],
                    numbers["reorder"],
                    numbers["cost"],
                    ingredient_id
                )
            )

            db.commit()
            db.close()

            return redirect(url_for("ingredients"))

        error = " ".join(errors)

    db.close()

    return render_template(
        "edit_ingredient.html",
        ingredient=ingredient,
        error=error,
        form=request.form
    )


@app.route("/ingredients/<int:ingredient_id>/deactivate", methods=["POST"])
def deactivate_ingredient(ingredient_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    db = get_connection()

    db.execute(
        """
        UPDATE ingredients
        SET is_active = 0
        WHERE ingredient_id = ?
        """,
        (ingredient_id,)
    )

    db.commit()
    db.close()

    return redirect(url_for("ingredients"))

@app.route("/ingredients/<int:ingredient_id>/reactivate", methods=["POST"])
def reactivate_ingredient(ingredient_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    db = get_connection()

    db.execute(
        """
        UPDATE ingredients
        SET is_active = 1
        WHERE ingredient_id = ?
        """,
        (ingredient_id,)
    )

    db.commit()
    db.close()

    return redirect(url_for("ingredients"))


@app.route("/ingredients/<int:ingredient_id>/stock", methods=["GET", "POST"])
def adjust_stock(ingredient_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    db = get_connection()

    ingredient = db.execute(
        """
        SELECT *
        FROM ingredients
        WHERE ingredient_id = ?
        AND is_active = 1
        """,
        (ingredient_id,)
    ).fetchone()

    if ingredient is None:
        db.close()
        return redirect(url_for("ingredients"))

    error = None

    if request.method == "POST":
        errors, amount = validate_stock_change(
            request.form["change"],
            request.form["reason"],
            ingredient["stock_quantity"]
        )

        if not errors:
            try:
                db.execute("BEGIN")

                db.execute(
                    """
                    UPDATE ingredients
                    SET stock_quantity = stock_quantity + ?
                    WHERE ingredient_id = ?
                    """,
                    (amount, ingredient_id)
                )

                db.execute(
                    """
                    INSERT INTO stock_transactions
                    (ingredient_id, performed_by, quantity_change, reason)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        ingredient_id,
                        session["user_id"],
                        amount,
                        request.form["reason"]
                    )
                )

                db.commit()
                db.close()

                return redirect(url_for("ingredients"))

            except sqlite3.Error:
                db.rollback()
                error = "Stock adjustment could not be saved."

        else:
            error = " ".join(errors)

    db.close()

    return render_template(
        "adjust_stock.html",
        ingredient=ingredient,
        error=error
    )

@app.route("/products", methods=["GET", "POST"])
def products():
    if "user_id" not in session:
        return redirect(url_for("login"))

    db = get_connection()
    error = None

    ingredient_rows = db.execute(
        """
        SELECT *
        FROM ingredients
        WHERE is_active = 1
        ORDER BY name
        """
    ).fetchall()

    if request.method == "POST":
        ingredient_ids = request.form.getlist("ingredient_id")
        quantities = request.form.getlist("quantity")

        errors, name, price, recipe = validate_product(
            request.form["name"],
            request.form["price"],
            ingredient_ids,
            quantities
        )
        

        

        duplicate = db.execute(
            """
            SELECT product_id
            FROM products
            WHERE LOWER(TRIM(name)) = LOWER(TRIM(?))
            """,
            (name,)
        ).fetchone()

        if duplicate:
            errors.append("A product with that name already exists.")

        if not errors:
            try:
                db.execute("BEGIN")

                cursor = db.execute(
                    """
                    INSERT INTO products (name, selling_price)
                    VALUES (?, ?)
                    """,
                    (name, price)
                )

                product_id = cursor.lastrowid

                for ingredient_id, quantity in recipe:
                    db.execute(
                        """
                        INSERT INTO recipe_ingredients
                        (product_id, ingredient_id, quantity_required)
                        VALUES (?, ?, ?)
                        """,
                        (product_id, ingredient_id, quantity)
                    )

                db.commit()
                db.close()

                return redirect(url_for("products"))

            except sqlite3.Error:
                db.rollback()
                error = "Product could not be saved."

        else:
            error = " ".join(errors)

    product_rows = db.execute(
        """
        SELECT *
        FROM products
        WHERE is_active = 1
        ORDER BY name
        """
    ).fetchall()

    db.close()

    return render_template(
        "products.html",
        products=product_rows,
        ingredients=ingredient_rows,
        error=error
    )

@app.route("/logout")
def logout():
    session.clear()

    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(debug=True)