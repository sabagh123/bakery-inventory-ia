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

## 2026-08-11 - Ingredient Management

**Success criteria:** SC-01, SC-02, SC-08, SC-09

Implemented:
- add and view ingredients
- validation for numeric and negative values
- normalized duplicate-name checking
- ingredient editing
- soft deactivation using is_active
- stock adjustment using purchase/correction reasons
- automatic stock transaction logging

Stock quantity was kept separate from normal ingredient editing so every manual stock change creates an audit record.

Manual and automated tests confirmed valid entry, zero stock, invalid values, duplicate names, editing, deactivation, stock adjustment and prevention of negative stock.

**Test:** `python -m pytest`

**Result:** 12 tests passed.

**Development outcome:** Ingredient management and audited stock adjustments were verified before product and recipe development.

## 2026-08-12 - Products & Recipes

**Success criteria:** SC-02, SC-03, SC-08, SC-09

Implemented:
- ingredient reactivation for soft-deactivated ingredients
- separate display of active and inactive ingredients on the Ingredients page
- reactivation without automatic stock changes, keeping stock adjustment separate
- many-to-many recipe ingredient support for product creation
- variable-length recipe rows using JavaScript Add Ingredient / Remove controls
- validation to reject duplicate recipe ingredients
- validation to reject recipe quantities of zero or negative values
- a successful automated test storing a recipe with 5 different ingredients

Created or updated tests for:
- ingredient reactivation
- multi-ingredient product recipes
- duplicate ingredient rejection in recipes
- invalid recipe quantities

**Test:** `python -m pytest`

**Result:** 16 tests passed.

**Development outcome:** Products and recipe entry were implemented and validated while preserving existing ingredient and stock management behavior.

## 2026-08-12 - Capacity Calculation

**Success criterion:** SC-04

Implemented:
- `calculate_capacity(recipe_ingredients)` implemented in app.py
- capacity is calculated using floor(stock_quantity / quantity_required) for each recipe ingredient
- the final product capacity is the minimum of those available portions
- the calculation is read-only and does not modify stock
- active products can be selected on a protected `/capacity` page
- ingredient-level stock, required quantity, and available portions are displayed
- products with no recipe are handled safely

Algorithm:
- A1 - Maximum producible portions: for each recipe ingredient compute floor(stock_quantity / quantity_required); product capacity is the minimum of those values

Tests:
- automated tests covered normal limiting-ingredient calculation, exact boundary stock, zero stock, no-recipe handling, and confirmation that stock is unchanged

Test: `python -m pytest`

Result: 21 tests passed

Development outcome: Capacity calculation implemented and validated; read-only assessment ready for production processing milestone.