document.addEventListener("DOMContentLoaded", function () {
    const recipeContainer = document.getElementById("recipe-rows");
    const addIngredientButton = document.getElementById("add-ingredient");

    function createRecipeRow() {
        const row = document.createElement("div");
        row.className = "recipe-row";

        const select = document.createElement("select");
        select.name = "ingredient_id";

        const ingredientOptions = document.querySelector("template#ingredient-option-template").content.cloneNode(true);
        select.append(...ingredientOptions.children);

        const quantity = document.createElement("input");
        quantity.type = "text";
        quantity.name = "quantity";
        quantity.placeholder = "Quantity per portion";

        const removeButton = document.createElement("button");
        removeButton.type = "button";
        removeButton.textContent = "Remove";
        removeButton.className = "remove-recipe-row";
        removeButton.addEventListener("click", function () {
            if (recipeContainer.querySelectorAll(".recipe-row").length > 1) {
                row.remove();
            }
        });

        row.appendChild(select);
        row.appendChild(quantity);
        row.appendChild(removeButton);

        return row;
    }

    addIngredientButton.addEventListener("click", function (event) {
        event.preventDefault();
        recipeContainer.appendChild(createRecipeRow());
    });

    const initialRows = recipeContainer.querySelectorAll(".recipe-row");
    if (initialRows.length === 0) {
        recipeContainer.appendChild(createRecipeRow());
    } else {
        initialRows.forEach(function (row) {
            const removeButton = document.createElement("button");
            removeButton.type = "button";
            removeButton.textContent = "Remove";
            removeButton.className = "remove-recipe-row";
            removeButton.addEventListener("click", function () {
                if (recipeContainer.querySelectorAll(".recipe-row").length > 1) {
                    row.remove();
                }
            });
            row.appendChild(removeButton);
        });
    }
});