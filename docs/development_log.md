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

## 2026-08-12 - Production Processing

**Success criteria:** SC-05, SC-09

Implemented for authenticated users:
- Users can select an active product and enter a positive whole number of portions.
- Requests above current capacity are rejected and do not change stock.
- Zero, negative, non-numeric and non-integer portion values are rejected.
- Batch ingredient cost is calculated before the transaction.
- A dedicated `perform_production(product_id, portions, performed_by)` helper handles production.

Atomic transaction sequence implemented (all using a single connection from `database.get_connection()`):
1. Begin transaction.
2. Insert a single `production_logs` record for the batch.
3. Obtain the new `production_id` (lastrowid).
4. For every recipe ingredient: deduct the required stock amount.
5. For every deduction: insert a `stock_transactions` record with a negative `quantity_change` and reason "production".
6. Commit only after every database operation succeeds.
7. On `sqlite3.Error`, call `rollback()` to undo all changes.

Testing confirmed:
- Valid production deducts correct stock quantities.
- Exact-capacity production succeeds.
- Over-capacity production is rejected and leaves stock unchanged.
- Invalid portion values are rejected.
- `production_logs` and `stock_transactions` are created correctly for successful runs.
- Total ingredient cost is computed and stored on the `production_logs` row.
- Simulated mid-transaction SQLite failure triggers a rollback: stock and both audit tables remain unchanged.

Development notes:
- The production processing logic was refactored into the `perform_production()` helper which obtains its connection from `database.get_connection()` and performs all transactional work on that connection. This design allows tests to monkeypatch `database.get_connection()` to inject simulated failures reliably.
- Temporary, test-specific workarounds that detected test environments or opened raw sqlite connections were removed; the production path now uses a single source of truth for connections and transaction handling.

Algorithm:
- A2 - Production validation, atomic stock deduction and audit logging

Test command:
```
python -m pytest
```

Result:
26 tests passed

Development outcome: Production processing implemented transactionally, audited, and covered by tests; rollback behavior verified under simulated failure.

## 2026-08-12 - Low-stock Monitoring (SC-06) and Cost & Contribution (SC-07)

Success criteria: SC-06, SC-07

Implemented SC-06 (Low-stock Monitoring):
- Added `get_low_stock_ingredients()` which returns active ingredients where `stock_quantity <= reorder_level`.
- Ingredients exactly equal to their `reorder_level` are included as low-stock.
- Inactive ingredients (`is_active = 0`) are excluded from low-stock results.
- Dashboard now displays a low-stock count and a low-stock table listing `name`, `unit`, `stock_quantity`, and `reorder_level`.

Implemented SC-07 (Cost & Contribution):
- Added `calculate_cost_contribution(product_id)` which computes cost and contribution per portion.
- `cost_per_portion` is computed as sum(quantity_required * unit_cost) across the product's recipe ingredients.
- `contribution_per_portion` is computed as `selling_price - cost_per_portion`.
- Calculations are read-only and do not modify ingredient stock or write audit records.
- Products with no recipe are handled safely and return `(None, None)`; the Products page displays `N/A` where appropriate.

Dashboard updates:
- Added `active_ingredients_count`.
- Added `low_stock_count` and `low_stock_rows` (table on the dashboard).
- Added `active_products_count`.
- Added `recent_transactions` (most recent 5 stock transactions) and a small summary card.

Testing covered (automated):
- below reorder level is low stock
- exactly equal to reorder level is low stock
- above reorder level is not low stock
- inactive low-stock ingredient is excluded
- product cost per portion calculation
- contribution calculation (selling price minus cost)
- zero-cost recipe produces zero cost and correct contribution
- product with no recipe is handled safely (returns `(None, None)`)
- calculations do not modify ingredient stock

Test command:
```
python -m pytest
```

Result:
29 tests passed

Development outcome: SC-06 and SC-07 implemented, dashboard and Products page updated, and automated tests added to verify behavior.

## 2026-08-12 - Reports / History and Persistence

**Success criterion:** SC-09

Implemented:
- Added a protected `/history` route.
- Replaced the placeholder Reports / History sidebar link with the real route.
- Added a read-only Stock Transaction History section showing timestamp, ingredient name, quantity change, reason, user and related production ID.
- Added a read-only Production History section showing timestamp, product name, portions, total ingredient cost and user.
- Both history sections are ordered newest first.
- Empty-history states are handled safely with clear messages instead of broken tables.

Testing and persistence verification:
- Added an explicit SQLite persistence test that commits data, closes the original connection, opens a new connection, and confirms the saved record still exists.
- Added tests confirming manual stock adjustments appear in stock transaction history.
- Added tests confirming production runs appear in production history.
- Added tests confirming production deductions appear in stock transaction history.
- Added tests confirming history access is read-only.
- Added a test confirming `/history` is protected from unauthenticated access.

Test command:
```
python -m pytest -q
```

Result:
34 tests passed

Development outcome: Data persistence and audit history are now accessible and verified through the application.