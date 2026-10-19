import type { Ingredient, SubstitutionRule } from "../types";

const I = (id: string, name: string, category: string, canonical_unit: Ingredient["canonical_unit"]): Ingredient => ({
  id,
  name,
  category,
  canonical_unit,
});

export const CATALOG: Ingredient[] = [
  I("chicken", "Chicken breast", "Meat & Fish", "g"),
  I("beef", "Ground beef", "Meat & Fish", "g"),
  I("salmon", "Salmon fillet", "Meat & Fish", "g"),
  I("bacon", "Bacon", "Meat & Fish", "g"),
  I("egg", "Eggs", "Dairy & Eggs", "pcs"),
  I("milk", "Milk", "Dairy & Eggs", "ml"),
  I("butter", "Butter", "Dairy & Eggs", "g"),
  I("cheese", "Cheddar cheese", "Dairy & Eggs", "g"),
  I("parmesan", "Parmesan", "Dairy & Eggs", "g"),
  I("cream", "Heavy cream", "Dairy & Eggs", "ml"),
  I("yogurt", "Greek yogurt", "Dairy & Eggs", "g"),
  I("onion", "Onion", "Vegetables", "pcs"),
  I("garlic", "Garlic clove", "Vegetables", "pcs"),
  I("tomato", "Tomato", "Vegetables", "pcs"),
  I("potato", "Potato", "Vegetables", "g"),
  I("carrot", "Carrot", "Vegetables", "pcs"),
  I("spinach", "Spinach", "Vegetables", "g"),
  I("pepper", "Bell pepper", "Vegetables", "pcs"),
  I("mushroom", "Mushrooms", "Vegetables", "g"),
  I("lemon", "Lemon", "Fruit", "pcs"),
  I("banana", "Banana", "Fruit", "pcs"),
  I("apple", "Apple", "Fruit", "pcs"),
  I("rice", "Rice", "Pantry staples", "g"),
  I("pasta", "Pasta", "Pantry staples", "g"),
  I("flour", "Flour", "Pantry staples", "g"),
  I("sugar", "Sugar", "Pantry staples", "g"),
  I("olive_oil", "Olive oil", "Pantry staples", "ml"),
  I("soy_sauce", "Soy sauce", "Pantry staples", "ml"),
  I("tomato_sauce", "Tomato passata", "Pantry staples", "ml"),
  I("stock", "Chicken stock", "Pantry staples", "ml"),
  I("bread", "Bread", "Bakery", "pcs"),
  I("oats", "Rolled oats", "Pantry staples", "g"),
];

const R = (
  id: string,
  original_ingredient_id: string,
  substitute_ingredient_id: string,
  ratio: number,
  context: string,
  note: string,
): SubstitutionRule => ({ id, original_ingredient_id, substitute_ingredient_id, ratio, context, note });

export const SUBSTITUTION_RULES: SubstitutionRule[] = [
  R("r1", "cream", "milk", 1, "Sauces & soups", "Milk gives a thinner sauce; simmer a little longer."),
  R("r2", "yogurt", "cream", 1, "Dressings & marinades", "Cream is richer and less tangy; add lemon if desired."),
  R("r3", "butter", "olive_oil", 0.8, "Sautéing", "Use 80% of the butter amount in olive oil."),
  R("r4", "parmesan", "cheese", 1, "Topping", "Cheddar melts softer and tastes milder."),
  R("r5", "cheese", "parmesan", 0.75, "Topping", "Parmesan is stronger; use 75% of the amount."),
  R("r6", "chicken", "beef", 1, "Stir-fries & bakes", "Brown ground beef fully before continuing."),
  R("r7", "stock", "milk", 1, "Creamy soups only", "Only for creamy soups; flavour will be milder."),
  R("r8", "spinach", "mushroom", 1, "Pasta & eggs", "Sauté mushrooms until golden first."),
  R("r9", "pasta", "rice", 0.8, "Bowls", "Serve as a rice bowl; use 80% of the pasta weight."),
  R("r10", "tomato_sauce", "tomato", 0.005, "Sauces", "Use ~1 fresh tomato per 200 ml passata, cooked down."),
  R("r11", "milk", "cream", 0.5, "Baking", "Use half the volume in cream, top up with water."),
];

export interface RawMeal {
  idMeal: string;
  strMeal: string;
  strCategory: string;
  strInstructions: string;
  strMealThumb: string;
  servings: number;
  ingredients: [string, string][]; // [ingredient name as written, free-text measure]
}

/** Raw recipes as they would arrive from TheMealDB (names + free-text measures). */
const img = (slug: string) => `https://www.themealdb.com/images/media/meals/${slug}.jpg`;

export const EXTERNAL_MEALS: RawMeal[] = [
  { idMeal: "52982", strMeal: "Spaghetti Carbonara", strCategory: "Pasta", strMealThumb: img("llcbn01574260722"), servings: 2,
    strInstructions: "Boil the pasta. Fry the bacon until crisp. Whisk eggs with grated parmesan. Toss hot pasta with bacon off the heat, then stir in the egg mixture until creamy.",
    ingredients: [["Pasta", "200g"], ["Bacon", "100g"], ["Eggs", "2"], ["Parmesan", "50g"], ["Garlic clove", "1"]] },
  { idMeal: "52772", strMeal: "Teriyaki Chicken", strCategory: "Chicken", strMealThumb: img("wvpsxx1468256321"), servings: 2,
    strInstructions: "Slice the chicken. Sear in oil until golden. Add soy sauce, sugar and garlic and reduce to a glaze. Serve over rice.",
    ingredients: [["Chicken breast", "300g"], ["Soy sauce", "3tbsp"], ["Sugar", "20g"], ["Garlic clove", "2"], ["Rice", "150g"]] },
  { idMeal: "52874", strMeal: "Beef & Mushroom Stroganoff", strCategory: "Beef", strMealThumb: img("svprys1511176755"), servings: 4,
    strInstructions: "Brown the beef with onion. Add mushrooms and cook until soft. Stir in cream and simmer 5 minutes. Serve with rice.",
    ingredients: [["Ground beef", "500g"], ["Onion", "1"], ["Mushrooms", "250g"], ["Heavy cream", "200ml"], ["Rice", "300g"]] },
  { idMeal: "52959", strMeal: "Baked Lemon Salmon", strCategory: "Seafood", strMealThumb: img("1548772327"), servings: 2,
    strInstructions: "Place salmon on a tray, top with butter, garlic and lemon slices. Bake at 200°C for 15 minutes. Serve with steamed spinach.",
    ingredients: [["Salmon fillet", "300g"], ["Lemon", "1"], ["Butter", "20g"], ["Garlic clove", "2"], ["Spinach", "150g"]] },
  { idMeal: "52977", strMeal: "Tomato Basil Soup", strCategory: "Vegetarian", strMealThumb: img("stpuws1511191310"), servings: 4,
    strInstructions: "Soften onion and garlic in oil. Add chopped tomatoes, passata and stock. Simmer 20 minutes, blend, and finish with cream.",
    ingredients: [["Onion", "1"], ["Garlic clove", "2"], ["Tomato", "4"], ["Tomato passata", "400ml"], ["Chicken stock", "500ml"], ["Heavy cream", "100ml"]] },
  { idMeal: "52965", strMeal: "Cheesy Potato Bake", strCategory: "Side", strMealThumb: img("1525876468"), servings: 4,
    strInstructions: "Slice potatoes thinly. Layer with cheddar and milk in a buttered dish. Bake at 180°C for 50 minutes.",
    ingredients: [["Potato", "800g"], ["Cheddar cheese", "150g"], ["Milk", "300ml"], ["Butter", "20g"]] },
  { idMeal: "52920", strMeal: "Chicken Fried Rice", strCategory: "Chicken", strMealThumb: img("1529446352"), servings: 2,
    strInstructions: "Cook rice and let cool. Stir-fry diced chicken, carrot and pepper. Add rice and soy sauce, push aside and scramble eggs in.",
    ingredients: [["Chicken breast", "200g"], ["Rice", "200g"], ["Eggs", "2"], ["Carrot", "1"], ["Bell pepper", "1"], ["Soy sauce", "2tbsp"]] },
  { idMeal: "52854", strMeal: "Fluffy Pancakes", strCategory: "Dessert", strMealThumb: img("rwuyqx1511383174"), servings: 4,
    strInstructions: "Whisk flour, sugar, eggs and milk into a smooth batter. Cook ladlefuls in a buttered pan until golden on both sides.",
    ingredients: [["Flour", "200g"], ["Sugar", "30g"], ["Eggs", "2"], ["Milk", "300ml"], ["Butter", "20g"]] },
  { idMeal: "52906", strMeal: "Spinach & Cheese Omelette", strCategory: "Breakfast", strMealThumb: img("1550441275"), servings: 1,
    strInstructions: "Beat eggs. Wilt spinach in butter, pour over eggs, sprinkle cheese, fold and serve.",
    ingredients: [["Eggs", "3"], ["Spinach", "50g"], ["Cheddar cheese", "30g"], ["Butter", "10g"]] },
  { idMeal: "52835", strMeal: "Bolognese", strCategory: "Pasta", strMealThumb: img("sutysw1468247559"), servings: 4,
    strInstructions: "Brown beef with onion, carrot and garlic. Add passata and simmer 30 minutes. Serve over pasta with parmesan.",
    ingredients: [["Ground beef", "400g"], ["Onion", "1"], ["Carrot", "1"], ["Garlic clove", "2"], ["Tomato passata", "500ml"], ["Pasta", "400g"], ["Parmesan", "30g"]] },
  { idMeal: "52913", strMeal: "Banana Oat Bake", strCategory: "Breakfast", strMealThumb: img("1550440197"), servings: 2,
    strInstructions: "Mash bananas, mix with oats, milk and an egg. Bake at 180°C for 25 minutes.",
    ingredients: [["Banana", "2"], ["Rolled oats", "120g"], ["Milk", "200ml"], ["Eggs", "1"]] },
  { idMeal: "52940", strMeal: "Creamy Mushroom Pasta", strCategory: "Vegetarian", strMealThumb: img("1548772328"), servings: 2,
    strInstructions: "Fry mushrooms and garlic in butter. Add cream and parmesan, simmer, and toss with cooked pasta.",
    ingredients: [["Pasta", "200g"], ["Mushrooms", "200g"], ["Garlic clove", "2"], ["Heavy cream", "150ml"], ["Parmesan", "30g"], ["Butter", "15g"]] },
  { idMeal: "52846", strMeal: "Chicken & Yogurt Curry", strCategory: "Chicken", strMealThumb: img("qrqywr1503066605"), servings: 4,
    strInstructions: "Marinate chicken in yogurt and garlic. Fry onion, add chicken and passata, simmer 25 minutes. Serve with rice.",
    ingredients: [["Chicken breast", "500g"], ["Greek yogurt", "200g"], ["Onion", "2"], ["Garlic clove", "3"], ["Tomato passata", "200ml"], ["Rice", "300g"]] },
  { idMeal: "52925", strMeal: "Apple Crumble", strCategory: "Dessert", strMealThumb: img("xvsurr1511719182"), servings: 4,
    strInstructions: "Slice apples into a dish with some sugar. Rub flour, butter and oats into crumbs, scatter over, bake 35 minutes.",
    ingredients: [["Apple", "4"], ["Flour", "100g"], ["Butter", "80g"], ["Sugar", "80g"], ["Rolled oats", "50g"]] },
  { idMeal: "52962", strMeal: "Salmon Rice Bowl", strCategory: "Seafood", strMealThumb: img("1548772329"), servings: 2,
    strInstructions: "Cook rice. Pan-sear salmon, glaze with soy sauce. Serve over rice with sliced pepper and carrot.",
    ingredients: [["Salmon fillet", "250g"], ["Rice", "150g"], ["Soy sauce", "2tbsp"], ["Bell pepper", "1"], ["Carrot", "1"]] },
  { idMeal: "52870", strMeal: "Classic Cheese Toastie", strCategory: "Snack", strMealThumb: img("1550441276"), servings: 1,
    strInstructions: "Butter bread, fill with cheddar and sliced tomato, and toast in a pan until golden and melted.",
    ingredients: [["Bread", "2"], ["Cheddar cheese", "60g"], ["Butter", "10g"], ["Tomato", "1"]] },
  { idMeal: "52889", strMeal: "Roast Potatoes & Carrots", strCategory: "Side", strMealThumb: img("1550441277"), servings: 4,
    strInstructions: "Toss chunks of potato and carrot with oil and garlic. Roast at 200°C for 45 minutes, turning once.",
    ingredients: [["Potato", "1kg"], ["Carrot", "3"], ["Olive oil", "3tbsp"], ["Garlic clove", "3"]] },
  { idMeal: "52931", strMeal: "Shakshuka", strCategory: "Vegetarian", strMealThumb: img("g373701551450225"), servings: 2,
    strInstructions: "Soften onion and pepper in oil. Add tomatoes and passata, simmer, then crack in eggs and cover until set.",
    ingredients: [["Onion", "1"], ["Bell pepper", "1"], ["Tomato", "2"], ["Tomato passata", "300ml"], ["Eggs", "4"], ["Olive oil", "1tbsp"]] },
  // Unsupported examples: ambiguous measures or ingredients outside the catalog.
  { idMeal: "52893", strMeal: "Lamb Tagine", strCategory: "Lamb", strMealThumb: img("yuwtuu1511295751"), servings: 4,
    strInstructions: "Slow-cook lamb with spices.", ingredients: [["Lamb shoulder", "1kg"], ["Onion", "2"]] },
  { idMeal: "52897", strMeal: "Grandma's Biscuits", strCategory: "Dessert", strMealThumb: img("1550441278"), servings: 6,
    strInstructions: "Mix and bake.", ingredients: [["Flour", "2 cups"], ["Butter", "a knob"], ["Sugar", "pinch"]] },
  { idMeal: "52901", strMeal: "Garden Salad", strCategory: "Side", strMealThumb: img("1550441279"), servings: 2,
    strInstructions: "Toss leaves.", ingredients: [["Spinach", "handful"], ["Tomato", "2"]] },
  { idMeal: "52908", strMeal: "Saffron Risotto", strCategory: "Vegetarian", strMealThumb: img("1550441280"), servings: 2,
    strInstructions: "Stir rice with stock.", ingredients: [["Rice", "200g"], ["Saffron", "1 pinch"]] },
];

export const IMPORT_TARGET = 18;
