# Development Log

## 2026-08-10 - Database Foundation

**Success criteria:** SC-09

Created the initial SQLite database structure based on the Criterion C ERD and data dictionary.

Implemented:
- `users`
- `ingredients`
- `products`
- `recipe_ingredients`
- `production_logs`
- `stock_transactions`

Created `db.py` to initialize and connect to the database.

Created `tests/test_database.py` to verify that all six required tables exist.

**Test:** `python -m pytest`

**Result:** 1 test passed.

**Development outcome:** Database foundation successfully initialized and verified before continuing to authentication.

## 2026-08-11 - Authentication

**Success criterion:** SC-10

Created the Flask application and login interface.

Implemented:
- hashed password storage using Werkzeug
- username lookup from SQLite
- password hash verification
- Flask session creation after successful login
- protected dashboard access
- logout and session removal
- generic invalid-login feedback

Manual tests confirmed:
- valid login redirects to the dashboard
- invalid passwords are rejected
- logout removes the session and blocks protected dashboard access

Created `tests/test_auth.py` using a temporary SQLite database so the tests do not modify the real application database.

During the first automated test run, the authentication tests could not access the expected `database_path` variable from `db.py`. After checking the imported module and saving the corrected file, the tests were repeated successfully.

**Test:** `python -m pytest`

**Result:** 4 tests passed.

**Development outcome:** Authentication and session protection were verified before beginning ingredient management.