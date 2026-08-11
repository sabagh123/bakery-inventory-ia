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


def test_valid_login(client):
    response = client.post(
        "/login",
        data={
            "username": "testuser",
            "password": "testpass"
        }
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/dashboard")

    with client.session_transaction() as session:
        assert "user_id" in session


def test_invalid_password(client):
    response = client.post(
        "/login",
        data={
            "username": "testuser",
            "password": "wrongpassword"
        }
    )

    assert response.status_code == 200
    assert b"Invalid username or password." in response.data

    with client.session_transaction() as session:
        assert "user_id" not in session


def test_logout_blocks_dashboard(client):
    client.post(
        "/login",
        data={
            "username": "testuser",
            "password": "testpass"
        }
    )

    client.get("/logout")

    with client.session_transaction() as session:
        assert "user_id" not in session

    response = client.get("/dashboard")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")