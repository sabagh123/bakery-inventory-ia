import math
import os
import sqlite3

from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import check_password_hash

import db as database
from validation import (
    validate_ingredient,
    validate_ingredient_edit,
    validate_stock_change,
    validate_product
)


def calculate_capacity(recipe_ingredients):
    if not recipe_ingredients:
        return 0

    available = []
    for ingredient in recipe_ingredients:
        quantity_required = ingredient.get("quantity_required")
        stock_quantity = ingredient.get("stock_quantity")

        if quantity_required is None or quantity_required <= 0:
            continue

        available.append(math.floor(stock_quantity / quantity_required))

    return min(available) if available else 0


def perform_production(product_id, portions, performed_by):
    """Perform the production transactionally using database.get_connection().

    Raises sqlite3.Error on failure; commits on success.
    """
    conn = database.get_connection()
    try:
        # load recipe and ingredient data
        recipe = conn.execute(
            """
            SELECT ri.ingredient_id, ri.quantity_required, i.stock_quantity, i.unit_cost
            FROM recipe_ingredients ri
            JOIN ingredients i ON ri.ingredient_id = i.ingredient_id
            WHERE ri.product_id = ?
            """,
            (product_id,)
        ).fetchall()

        if not recipe:
            raise sqlite3.Error("Product has no recipe.")

        # compute deductions and total cost
        deductions = []
        total_cost = 0
        for row in recipe:
            qty_req = row["quantity_required"]
            deduction = qty_req * portions
            deductions.append((row["ingredient_id"], deduction, qty_req, row["unit_cost"]))
            total_cost += qty_req * portions * row["unit_cost"]

        # begin transaction
        conn.execute("BEGIN")

        cursor = conn.execute(
            "INSERT INTO production_logs (product_id, performed_by, portions, total_ingredient_cost) VALUES (?, ?, ?, ?)",
            (product_id, performed_by, portions, total_cost)
        )
        production_id = cursor.lastrowid

        for ingredient_id, deduction, qty_req, unit_cost in deductions:
            current = conn.execute(
                "SELECT stock_quantity FROM ingredients WHERE ingredient_id = ?",
                (ingredient_id,)
            ).fetchone()["stock_quantity"]

            if current - deduction < 0:
                raise sqlite3.Error("Insufficient stock during production")

            conn.execute(
                "UPDATE ingredients SET stock_quantity = stock_quantity - ? WHERE ingredient_id = ?",
                (deduction, ingredient_id)
            )

            conn.execute(
                "INSERT INTO stock_transactions (ingredient_id, production_id, performed_by, quantity_change, reason) VALUES (?, ?, ?, ?, ?)",
                (ingredient_id, production_id, performed_by, -deduction, "production")
            )

        conn.commit()
        return production_id

    except sqlite3.Error:
        try:
            conn.rollback()
        except Exception:
            pass
        raise


def get_low_stock_ingredients():
    """Return active ingredients where stock_quantity <= reorder_level."""
    conn = database.get_connection()
    rows = conn.execute(
        """
        SELECT ingredient_id, name, unit, stock_quantity, reorder_level
        FROM ingredients
        WHERE is_active = 1 AND stock_quantity <= reorder_level
        ORDER BY name
        """
    ).fetchall()
    conn.close()
    return rows


def calculate_cost_contribution(product_id):
    """Return (cost_per_portion, contribution_per_portion) or (None, None) if no recipe.

    cost_per_portion = sum(quantity_required * unit_cost) over recipe ingredients.
    contribution = selling_price - cost_per_portion (None if product missing)
    """
    conn = database.get_connection()
    rows = conn.execute(
        """
        SELECT ri.quantity_required, i.unit_cost
        FROM recipe_ingredients ri
        JOIN ingredients i ON ri.ingredient_id = i.ingredient_id
        WHERE ri.product_id = ?
        """,
        (product_id,)
    ).fetchall()

    if not rows:
        conn.close()
        return None, None

    cost = sum(r["quantity_required"] * r["unit_cost"] for r in rows)

    prod = conn.execute(
        "SELECT selling_price FROM products WHERE product_id = ?",
        (product_id,)
    ).fetchone()
    conn.close()

    if prod is None:
        return cost, None

    contribution = prod["selling_price"] - cost
    return cost, contribution


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

        db = database.get_connection()

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

    conn = database.get_connection()

    active_ingredients_count = conn.execute(
        "SELECT COUNT(*) as cnt FROM ingredients WHERE is_active = 1"
    ).fetchone()["cnt"]

    low_stock_rows = get_low_stock_ingredients()
    low_stock_count = len(low_stock_rows)

    active_products_count = conn.execute(
        "SELECT COUNT(*) as cnt FROM products WHERE is_active = 1"
    ).fetchone()["cnt"]

    recent_transactions = conn.execute(
        "SELECT st.*, i.name as ingredient_name FROM stock_transactions st JOIN ingredients i ON st.ingredient_id = i.ingredient_id ORDER BY st.created_at DESC LIMIT 5"
    ).fetchall()

    conn.close()

    return render_template(
        "dashboard.html",
        active_ingredients_count=active_ingredients_count,
        low_stock_count=low_stock_count,
        active_products_count=active_products_count,
        recent_transactions=recent_transactions,
        low_stock_rows=low_stock_rows,
    )


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

        db = database.get_connection()

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

    db = database.get_connection()

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

    db = database.get_connection()

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

    db = database.get_connection()

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

    db = database.get_connection()

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

    db = database.get_connection()

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

    db = database.get_connection()
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

    active_product_rows = db.execute(
        """
        SELECT *
        FROM products
        WHERE is_active = 1
        ORDER BY name
        """
    ).fetchall()
    inactive_product_rows = db.execute(
        """
        SELECT *
        FROM products
        WHERE is_active = 0
        ORDER BY name
        """
    ).fetchall()

    products_with_costs = []
    for p in active_product_rows:
        cost, contribution = calculate_cost_contribution(p["product_id"])
        products_with_costs.append({
            **dict(p),
            "cost_per_portion": cost,
            "contribution_per_portion": contribution,
        })

    inactive_products_with_costs = []
    for p in inactive_product_rows:
        cost, contribution = calculate_cost_contribution(p["product_id"])
        inactive_products_with_costs.append({
            **dict(p),
            "cost_per_portion": cost,
            "contribution_per_portion": contribution,
        })

    db.close()

    return render_template(
        "products.html",
        products=products_with_costs,
        inactive_products=inactive_products_with_costs,
        ingredients=ingredient_rows,
        error=error
    )

@app.route("/products/<int:product_id>/deactivate", methods=["POST"])
def deactivate_product(product_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    db = database.get_connection()

    db.execute(
        """
        UPDATE products
        SET is_active = 0
        WHERE product_id = ?
        """,
        (product_id,)
    )

    db.commit()
    db.close()

    return redirect(url_for("products"))


@app.route("/products/<int:product_id>/reactivate", methods=["POST"])
def reactivate_product(product_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    db = database.get_connection()

    db.execute(
        """
        UPDATE products
        SET is_active = 1
        WHERE product_id = ?
        """,
        (product_id,)
    )

    db.commit()
    db.close()

    return redirect(url_for("products"))


@app.route("/capacity", methods=["GET", "POST"])
def capacity():
    if "user_id" not in session:
        return redirect(url_for("login"))

    # handle production POST
    if request.method == "POST":
        product_id = request.form.get("product_id")
        portions_raw = request.form.get("portions")

        error = None

        try:
            portions = int(portions_raw)
            if portions <= 0:
                raise ValueError()
        except Exception:
            error = "Portions must be a positive whole number."

        if not error:
            # validate product and recipe
            db_check = database.get_connection()
            product = db_check.execute(
                "SELECT * FROM products WHERE product_id = ? AND is_active = 1",
                (product_id,)
            ).fetchone()

            if product is None:
                error = "Selected product not found."
            else:
                recipe_rows = db_check.execute(
                    """
                    SELECT ri.quantity_required, i.stock_quantity, i.unit_cost, ri.ingredient_id
                    FROM recipe_ingredients ri
                    JOIN ingredients i ON ri.ingredient_id = i.ingredient_id
                    WHERE ri.product_id = ?
                    """,
                    (product_id,)
                ).fetchall()


                if not recipe_rows:
                    error = "Product has no recipe and cannot be produced."
                else:
                    cap = calculate_capacity([
                        {"quantity_required": r["quantity_required"], "stock_quantity": r["stock_quantity"]}
                        for r in recipe_rows
                    ])

                    if portions > cap:
                        error = "Requested portions exceed current capacity."

            db_check.close()

        if error:
            db = database.get_connection()
            products = db.execute(
                "SELECT * FROM products WHERE is_active = 1 ORDER BY name"
            ).fetchall()
            db.close()

            return render_template(
                "capacity.html",
                products=products,
                selected_product=None,
                ingredients=[],
                capacity=None,
                error=error
            )

        # perform production transactionally using helper
        try:
            production_id = perform_production(product_id, portions, session["user_id"])
            return redirect(url_for("capacity", product_id=product_id, success="Production recorded successfully."))
        except sqlite3.Error:
            db = database.get_connection()
            products = db.execute(
                "SELECT * FROM products WHERE is_active = 1 ORDER BY name"
            ).fetchall()
            db.close()

            error = "Production failed and was rolled back."
            return render_template(
                "capacity.html",
                products=products,
                selected_product=None,
                ingredients=[],
                capacity=None,
                error=error
            )

    db = database.get_connection()

    products = db.execute(
        """
        SELECT *
        FROM products
        WHERE is_active = 1
        ORDER BY name
        """
    ).fetchall()

    selected_product = None
    ingredient_rows = []
    capacity_value = None
    error = None
    success = request.args.get("success")

    product_id = request.args.get("product_id")

    if product_id:
        selected_product = db.execute(
            "SELECT * FROM products WHERE product_id = ? AND is_active = 1",
            (product_id,)
        ).fetchone()

        if selected_product:
            ingredient_rows = db.execute(
                """
                SELECT ri.quantity_required, i.name, i.unit, i.stock_quantity
                FROM recipe_ingredients ri
                JOIN ingredients i ON ri.ingredient_id = i.ingredient_id
                WHERE ri.product_id = ?
                """,
                (product_id,)
            ).fetchall()

            capacity_value = calculate_capacity([
                {
                    "quantity_required": row["quantity_required"],
                    "stock_quantity": row["stock_quantity"]
                }
                for row in ingredient_rows
            ])
        else:
            error = "Selected product not found."

    db.close()

    return render_template(
        "capacity.html",
        products=products,
        selected_product=selected_product,
        ingredients=ingredient_rows,
        capacity=capacity_value,
        error=error,
        success=success
    )

@app.route("/history")
def history():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = database.get_connection()
    stock_history = conn.execute(
        """
        SELECT st.created_at, i.name AS ingredient_name, st.quantity_change,
               st.reason, u.username AS performed_by, st.production_id
        FROM stock_transactions st
        LEFT JOIN ingredients i ON st.ingredient_id = i.ingredient_id
        LEFT JOIN users u ON st.performed_by = u.user_id
        ORDER BY st.created_at DESC
        """
    ).fetchall()

    production_history = conn.execute(
        """
        SELECT pl.created_at, p.name AS product_name, pl.portions,
               pl.total_ingredient_cost, u.username AS performed_by
        FROM production_logs pl
        LEFT JOIN products p ON pl.product_id = p.product_id
        LEFT JOIN users u ON pl.performed_by = u.user_id
        ORDER BY pl.created_at DESC
        """
    ).fetchall()

    conn.close()

    return render_template(
        "history.html",
        stock_history=stock_history,
        production_history=production_history
    )

@app.route("/logout")
def logout():
    session.clear()

    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(debug=True)