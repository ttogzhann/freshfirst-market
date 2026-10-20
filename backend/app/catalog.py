"""Supported identities and reviewed, context-limited substitution rules.

Units identify stock dimensions, never implicit mass/volume density conversions.
"""

from .models import Ingredient, SubstitutionRule

_INGREDIENTS = [
    ("chicken", "Chicken breast", "Meat & Fish", "g"),
    ("beef", "Ground beef", "Meat & Fish", "g"),
    ("salmon", "Salmon fillet", "Meat & Fish", "g"),
    ("bacon", "Bacon", "Meat & Fish", "g"),
    ("egg", "Eggs", "Dairy & Eggs", "pcs"),
    ("milk", "Milk", "Dairy & Eggs", "ml"),
    ("butter", "Butter", "Dairy & Eggs", "g"),
    ("cheese", "Cheddar cheese", "Dairy & Eggs", "g"),
    ("parmesan", "Parmesan", "Dairy & Eggs", "g"),
    ("cream", "Heavy cream", "Dairy & Eggs", "ml"),
    ("yogurt", "Greek yogurt", "Dairy & Eggs", "g"),
    ("onion", "Onion", "Vegetables", "pcs"),
    ("garlic", "Garlic clove", "Vegetables", "pcs"),
    ("tomato", "Tomato", "Vegetables", "pcs"),
    ("potato", "Potato", "Vegetables", "g"),
    ("carrot", "Carrot", "Vegetables", "pcs"),
    ("spinach", "Spinach", "Vegetables", "g"),
    ("pepper", "Bell pepper", "Vegetables", "pcs"),
    ("mushroom", "Mushrooms", "Vegetables", "g"),
    ("lemon", "Lemon", "Fruit", "pcs"),
    ("banana", "Banana", "Fruit", "pcs"),
    ("apple", "Apple", "Fruit", "pcs"),
    ("rice", "Rice", "Pantry staples", "g"),
    ("pasta", "Pasta", "Pantry staples", "g"),
    ("flour", "Flour", "Pantry staples", "g"),
    ("sugar", "Sugar", "Pantry staples", "g"),
    ("olive_oil", "Olive oil", "Pantry staples", "ml"),
    ("soy_sauce", "Soy sauce", "Pantry staples", "ml"),
    ("tomato_sauce", "Tomato passata", "Pantry staples", "ml"),
    ("stock", "Chicken stock", "Pantry staples", "ml"),
    ("bread", "Bread", "Bakery", "pcs"),
    ("oats", "Rolled oats", "Pantry staples", "g"),
    ("salt", "Salt", "Seasonings", "ml"),
    ("black_pepper", "Black pepper", "Seasonings", "ml"),
    ("water", "Water", "Pantry staples", "ml"),
    ("vegetable_oil", "Vegetable oil", "Pantry staples", "ml"),
    ("baking_powder", "Baking powder", "Pantry staples", "ml"),
    ("vanilla", "Vanilla extract", "Pantry staples", "ml"),
    ("cocoa", "Cocoa powder", "Pantry staples", "g"),
    ("honey", "Honey", "Pantry staples", "ml"),
    ("plain_chocolate", "Plain chocolate", "Pantry staples", "g"),
]
CATALOG = {
    i[0]: Ingredient(id=i[0], name=i[1], category=i[2], canonical_unit=i[3]) for i in _INGREDIENTS
}

# Explicit aliases only. Do not collapse a whole chicken to chicken breast, for example.
ALIASES = {i.name.casefold(): i.id for i in CATALOG.values()}
ALIASES.update(
    {
        "chicken breasts": "chicken",
        "minced beef": "beef",
        "beef mince": "beef",
        "eggs": "egg",
        "egg": "egg",
        "onions": "onion",
        "garlic": "garlic",
        "garlic cloves": "garlic",
        "tomatoes": "tomato",
        "potatoes": "potato",
        "carrots": "carrot",
        "lemons": "lemon",
        "apples": "apple",
        "bananas": "banana",
        "red pepper": "pepper",
        "green pepper": "pepper",
        "cheddar": "cheese",
        "cheddar cheese": "cheese",
        "parmesan cheese": "parmesan",
        "double cream": "cream",
        "mushroom": "mushroom",
        "spaghetti": "pasta",
        "penne rigate": "pasta",
        "plain flour": "flour",
        "caster sugar": "sugar",
        "granulated sugar": "sugar",
        "rolled oats": "oats",
        "passata": "tomato_sauce",
        "olive oil": "olive_oil",
        "vegetable oil": "vegetable_oil",
        "vanilla essence": "vanilla",
    }
)

_RULES = [
    (
        "r1",
        "cream",
        "milk",
        1,
        "Sauces & soups",
        "Milk makes a thinner sauce.",
        {"Pasta", "Soup", "Seafood"},
    ),
    (
        "r2",
        "cheese",
        "parmesan",
        0.75,
        "Topping",
        "Use less Parmesan for a stronger topping.",
        {"Pasta", "Side"},
    ),
    (
        "r3",
        "parmesan",
        "cheese",
        1,
        "Topping",
        "Cheddar gives a milder topping.",
        {"Pasta", "Side"},
    ),
    (
        "r4",
        "olive_oil",
        "vegetable_oil",
        1,
        "Frying",
        "Neutral oil changes the flavour.",
        {"Chicken", "Beef", "Pasta", "Vegetarian", "Side"},
    ),
    (
        "r5",
        "vegetable_oil",
        "olive_oil",
        1,
        "Frying",
        "Olive oil adds flavour.",
        {"Chicken", "Beef", "Pasta", "Vegetarian", "Side"},
    ),
    ("r6", "chicken", "beef", 1, "Stir-fries", "Use ground beef and brown fully.", {"Stir-fry"}),
    ("r7", "stock", "water", 1, "Soups", "Water gives a milder broth.", {"Soup"}),
    (
        "r8",
        "spinach",
        "mushroom",
        1,
        "Pasta & eggs",
        "Cook mushrooms fully before adding eggs.",
        {"Pasta", "Breakfast"},
    ),
    ("r9", "milk", "cream", 1, "Sauces", "Cream gives a richer sauce.", {"Pasta", "Soup"}),
    ("r10", "pasta", "rice", 0.8, "Bowls", "Cook as a rice bowl instead.", {"Bowl"}),
]
RULES = {
    r[0]: SubstitutionRule(
        id=r[0],
        original_ingredient_id=r[1],
        substitute_ingredient_id=r[2],
        ratio=r[3],
        context=r[4],
        note=r[5],
    )
    for r in _RULES
}
RULE_CATEGORIES = {r[0]: r[6] for r in _RULES}
