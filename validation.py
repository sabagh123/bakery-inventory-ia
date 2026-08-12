def validate_ingredient(name, unit, stock, reorder, cost):
    errors = []
    name = name.strip()

    if not name:
        errors.append("Ingredient name is required.")

    if unit not in {"g", "kg", "ml", "unit"}:
        errors.append("Invalid unit.")

    numbers = {}

    fields = [
        ("stock", "Stock", stock),
        ("reorder", "Reorder level", reorder),
        ("cost", "Unit cost", cost)
    ]

    for key, label, value in fields:
        try:
            number = float(value)

            if number < 0:
                errors.append(f"{label} cannot be negative.")

            numbers[key] = number

        except ValueError:
            errors.append(f"{label} must be a number.")
            numbers[key] = None

    return errors, name, numbers


def validate_ingredient_edit(name, unit, reorder, cost):
    errors = []
    name = name.strip()

    if not name:
        errors.append("Ingredient name is required.")

    if unit not in {"g", "kg", "ml", "unit"}:
        errors.append("Invalid unit.")

    numbers = {}

    fields = [
        ("reorder", "Reorder level", reorder),
        ("cost", "Unit cost", cost)
    ]

    for key, label, value in fields:
        try:
            number = float(value)

            if number < 0:
                errors.append(f"{label} cannot be negative.")

            numbers[key] = number

        except ValueError:
            errors.append(f"{label} must be a number.")
            numbers[key] = None

    return errors, name, numbers


def validate_stock_change(change, reason, current_stock):
    errors = []

    try:
        amount = float(change)

        if amount == 0:
            errors.append("Stock change cannot be zero.")

        if current_stock + amount < 0:
            errors.append("Stock cannot become negative.")

    except ValueError:
        errors.append("Stock change must be a number.")
        amount = None

    if reason not in {"Purchase", "correction"}:
        errors.append("Invalid adjustment reason.")

    return errors, amount
def validate_product(name, price, ingredient_ids, quantities):
    errors = []
    name = name.strip()

    if not name:
        errors.append("Product name is required.")

    try:
        price = float(price)

        if price < 0:
            errors.append("Selling price cannot be negative.")

    except ValueError:
        errors.append("Selling price must be a number.")
        price = None

    if not ingredient_ids:
        errors.append("A recipe must contain at least one ingredient.")

    if len(ingredient_ids) != len(set(ingredient_ids)):
        errors.append("The same ingredient cannot appear twice.")

    recipe = []

    for ingredient_id, quantity in zip(ingredient_ids, quantities):
        try:
            quantity = float(quantity)

            if quantity <= 0:
                errors.append("Recipe quantities must be greater than zero.")

            recipe.append((int(ingredient_id), quantity))

        except ValueError:
            errors.append("Recipe quantities must be numbers.")

    return errors, name, price, recipe