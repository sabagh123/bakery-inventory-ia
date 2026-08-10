PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ingredients (
    ingredient_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    unit TEXT NOT NULL
        CHECK (unit IN ('g', 'kg', 'ml', 'unit')),
    stock_quantity REAL NOT NULL DEFAULT 0
        CHECK (stock_quantity >= 0),
    reorder_level REAL NOT NULL
        CHECK (reorder_level >= 0),
    unit_cost REAL NOT NULL
        CHECK (unit_cost >= 0),
    is_active INTEGER NOT NULL DEFAULT 1
        CHECK (is_active IN (0, 1))
);

CREATE TABLE IF NOT EXISTS products (
    product_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    selling_price REAL NOT NULL
        CHECK (selling_price >= 0),
    is_active INTEGER NOT NULL DEFAULT 1
        CHECK (is_active IN (0, 1))
);

CREATE TABLE IF NOT EXISTS recipe_ingredients (
    recipe_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    ingredient_id INTEGER NOT NULL,
    quantity_required REAL NOT NULL
        CHECK (quantity_required > 0),

    FOREIGN KEY (product_id)
        REFERENCES products(product_id),

    FOREIGN KEY (ingredient_id)
        REFERENCES ingredients(ingredient_id),

    UNIQUE (product_id, ingredient_id)
);

CREATE TABLE IF NOT EXISTS production_logs (
    production_id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    performed_by INTEGER NOT NULL,
    portions INTEGER NOT NULL
        CHECK (portions > 0),
    total_ingredient_cost REAL NOT NULL
        CHECK (total_ingredient_cost >= 0),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (product_id)
        REFERENCES products(product_id),

    FOREIGN KEY (performed_by)
        REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS stock_transactions (
    transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ingredient_id INTEGER NOT NULL,
    production_id INTEGER,
    performed_by INTEGER NOT NULL,
    quantity_change REAL NOT NULL,
    reason TEXT NOT NULL
        CHECK (reason IN ('Purchase', 'production', 'correction')),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (ingredient_id)
        REFERENCES ingredients(ingredient_id),

    FOREIGN KEY (production_id)
        REFERENCES production_logs(production_id),

    FOREIGN KEY (performed_by)
        REFERENCES users(user_id)
);