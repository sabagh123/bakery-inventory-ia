import os

from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import check_password_hash

from db import get_connection


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


@app.route("/logout")
def logout():
    session.clear()

    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(debug=True)