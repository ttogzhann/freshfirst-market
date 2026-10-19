import * as D from "../domain";
import {
  ServiceError,
  type BasketItem,
  type ConfirmedSubstitution,
  type CookRequest,
  type CookingRecord,
  type FreshService,
  type ImportReport,
  type Ingredient,
  type PantryInput,
  type PantryItem,
  type Recipe,
  type RecipeSummary,
  type ShoppingItem,
} from "../types";
import { CATALOG, EXTERNAL_MEALS, IMPORT_TARGET, SUBSTITUTION_RULES, type RawMeal } from "./seed";

export interface KeyValueStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

export function memoryStorage(): KeyValueStorage {
  const m = new Map<string, string>();
  return { getItem: (k) => m.get(k) ?? null, setItem: (k, v) => void m.set(k, v) };
}

interface State {
  pantry: PantryItem[];
  recipes: Recipe[];
  basket: BasketItem[];
  shopping: ShoppingItem[];
  history: CookingRecord[];
  seq: number;
}

export interface MockOptions {
  storage?: KeyValueStorage;
  latencyMs?: number;
  today?: () => string;
  /** Simulated external source (TheMealDB); defaults to the bundled fixtures. */
  externalMeals?: RawMeal[];
  seedPantry?: boolean;
}

const KEY = "freshfirst:mock-db:v1";
const clone = <T,>(v: T): T => JSON.parse(JSON.stringify(v));

export function createMockService(opts: MockOptions = {}): FreshService {
  const storage = opts.storage ?? memoryStorage();
  const latency = opts.latencyMs ?? 0;
  const today = opts.today ?? (() => D.todayISO());
  const external = opts.externalMeals ?? EXTERNAL_MEALS;
  const ingredients = new Map<string, Ingredient>(CATALOG.map((i) => [i.id, i]));
  const rules = SUBSTITUTION_RULES;

  let state: State = load();

  function load(): State {
    const raw = storage.getItem(KEY);
    if (raw) return JSON.parse(raw) as State;
    const s: State = { pantry: [], recipes: [], basket: [], shopping: [], history: [], seq: 1 };
    state = s;
    runImport(); // idempotent startup seed
    if (opts.seedPantry !== false) seedPantry();
    persist();
    return state;
  }
  function persist() {
    storage.setItem(KEY, JSON.stringify(state));
  }
  function id(prefix: string) {
    return `${prefix}_${state.seq++}`;
  }
  async function wrap<T>(fn: () => T): Promise<T> {
    if (latency) await new Promise((r) => setTimeout(r, latency));
    // Work on a copy; only commit on success so failures never half-apply.
    const snapshot = clone(state);
    try {
      const out = fn();
      persist();
      return clone(out);
    } catch (e) {
      state = snapshot;
      throw e;
    }
  }
  const bad = (msg: string, code = "VALIDATION_ERROR") => new ServiceError(422, code, msg);
  const notFound = (what: string) => new ServiceError(404, "NOT_FOUND", `${what} not found`);

  function seedPantry() {
    const t = today();
    const add = (ingredient_id: string, quantity: number, days: number) =>
      state.pantry.push({ id: id("p"), ingredient_id, quantity, expiry_date: D.addDays(t, days) });
    add("egg", 6, 10);
    add("spinach", 120, 2);
    add("chicken", 400, 1);
    add("rice", 1000, 200);
    add("milk", 500, -1);
    add("butter", 200, 30);
    add("garlic", 6, 20);
    add("cheese", 150, 12);
    add("soy_sauce", 250, 180);
    add("onion", 3, 15);
    add("pasta", 500, 300);
    add("tomato", 2, 3);
  }

  function runImport(): ImportReport {
    const report: ImportReport = { imported: 0, updated: 0, skipped: [], total_recipes: 0 };
    const byName = new Map(CATALOG.map((i) => [i.name.toLowerCase(), i]));
    let accepted = 0;
    for (const meal of external) {
      if (accepted >= IMPORT_TARGET) break;
      const parsed: { ingredient_id: string; quantity: number }[] = [];
      let reason: string | null = null;
      for (const [name, measure] of meal.ingredients) {
        const ing = byName.get(name.toLowerCase());
        if (!ing) {
          reason = `Ingredient "${name}" is not in the supported catalog`;
          break;
        }
        const q = D.parseMeasure(measure, ing.canonical_unit);
        if (q === null) {
          reason = `Measure "${measure}" for ${name} has no exact conversion`;
          break;
        }
        parsed.push({ ingredient_id: ing.id, quantity: q });
      }
      if (reason) {
        report.skipped.push({ external_id: meal.idMeal, title: meal.strMeal, reason });
        continue;
      }
      accepted++;
      const data = {
        external_id: meal.idMeal,
        title: meal.strMeal,
        category: meal.strCategory,
        instructions: meal.strInstructions,
        image_url: meal.strMealThumb,
        base_servings: meal.servings,
        ingredients: parsed,
      };
      const existing = state.recipes.find((r) => r.external_id === meal.idMeal);
      if (existing) {
        Object.assign(existing, data);
        report.updated++;
      } else {
        state.recipes.push({ id: `rec_${meal.idMeal}`, ...data });
        report.imported++;
      }
    }
    report.total_recipes = state.recipes.length;
    return report;
  }

  function validatePantry(input: PantryInput): number {
    const ing = ingredients.get(input.ingredient_id);
    if (!ing) throw bad("Choose an ingredient from the catalog");
    if (!(typeof input.quantity === "number" && input.quantity > 0)) throw bad("Quantity must be greater than zero");
    if (!D.isValidDate(input.expiry_date)) throw bad("Enter a valid expiry date");
    const q = D.toCanonical(input.quantity, input.unit, ing.canonical_unit);
    if (q === null) throw bad(`Unit "${input.unit}" is not compatible with ${ing.name}`);
    return q;
  }

  function getRecipeOr404(rid: string) {
    const r = state.recipes.find((x) => x.id === rid);
    if (!r) throw notFound("Recipe");
    return r;
  }
  function checkServings(n: number) {
    if (!D.validServings(n)) throw bad(`Servings must be a whole number between ${D.MIN_SERVINGS} and ${D.MAX_SERVINGS}`);
  }
  function checkSubs(recipe: Recipe, subs: ConfirmedSubstitution[]) {
    for (const s of subs) {
      const rule = rules.find((r) => r.id === s.rule_id);
      if (
        !rule ||
        rule.original_ingredient_id !== s.original_ingredient_id ||
        rule.substitute_ingredient_id !== s.substitute_ingredient_id ||
        !recipe.ingredients.some((ri) => ri.ingredient_id === s.original_ingredient_id)
      )
        throw bad("Invalid substitution for this recipe");
    }
  }

  function summary(r: Recipe): RecipeSummary {
    return { ...r, match: D.computeMatch(r, state.pantry, today(), ingredients) };
  }

  function basketTotals() {
    const demands = state.basket.flatMap((b) =>
      D.recipeDemands(getRecipeOr404(b.recipe_id), b.servings, b.substitutions, rules),
    );
    return D.aggregate(demands);
  }

  function cookPreview(req: CookRequest) {
    const recipe = getRecipeOr404(req.recipe_id);
    checkServings(req.servings);
    checkSubs(recipe, req.substitutions);
    const stock = D.usableStock(state.pantry, today());
    const agg = D.aggregate(D.recipeDemands(recipe, req.servings, req.substitutions, rules));
    const demands = D.recipeDemands(recipe, req.servings, req.substitutions, rules);
    const lines = D.toLines(demands, stock, ingredients).map((l) => ({
      ...l,
      sufficient: (stock.get(l.ingredient_id) ?? 0) >= (agg.get(l.ingredient_id) ?? 0),
    }));
    return { recipe, agg, preview: { recipe_id: recipe.id, servings: req.servings, lines, can_cook: lines.every((l) => l.sufficient) } };
  }

  const service: FreshService = {
    listIngredients: () => wrap(() => CATALOG),
    listSubstitutionRules: () => wrap(() => rules),

    listPantry: () => wrap(() => state.pantry),

    createPantryItem: (input) =>
      wrap(() => {
        const q = validatePantry(input);
        const existing = state.pantry.find((p) => p.ingredient_id === input.ingredient_id);
        if (existing) {
          if (existing.expiry_date !== input.expiry_date)
            throw new ServiceError(
              409,
              "EXPIRY_CONFLICT",
              "This ingredient is already in your pantry with a different expiry date. Edit the existing entry instead.",
            );
          existing.quantity = D.round(existing.quantity + q);
          return existing;
        }
        const item: PantryItem = { id: id("p"), ingredient_id: input.ingredient_id, quantity: q, expiry_date: input.expiry_date };
        state.pantry.push(item);
        return item;
      }),

    updatePantryItem: (pid, input) =>
      wrap(() => {
        const item = state.pantry.find((p) => p.id === pid);
        if (!item) throw notFound("Pantry item");
        const q = validatePantry(input);
        if (state.pantry.some((p) => p.id !== pid && p.ingredient_id === input.ingredient_id))
          throw new ServiceError(409, "DUPLICATE_INGREDIENT", "Another entry already uses this ingredient");
        Object.assign(item, { ingredient_id: input.ingredient_id, quantity: q, expiry_date: input.expiry_date });
        return item;
      }),

    deletePantryItem: (pid) =>
      wrap(() => {
        const before = state.pantry.length;
        state.pantry = state.pantry.filter((p) => p.id !== pid);
        if (state.pantry.length === before) throw notFound("Pantry item");
      }),

    listRecipes: (params = {}) =>
      wrap(() => {
        const q = params.query?.trim().toLowerCase();
        const list = state.recipes
          .filter((r) => !q || r.title.toLowerCase().includes(q))
          .filter((r) => !params.category || r.category === params.category)
          .map(summary);
        return D.rankRecipes(list);
      }),

    getRecipe: (rid, servings, substitutions = []) =>
      wrap(() => {
        const recipe = getRecipeOr404(rid);
        const s = servings ?? recipe.base_servings;
        checkServings(s);
        checkSubs(recipe, substitutions);
        const stock = D.usableStock(state.pantry, today());
        const lines = D.toLines(D.recipeDemands(recipe, s, substitutions, rules), stock, ingredients);
        return {
          ...summary(recipe),
          servings: s,
          lines,
          suggestions: D.suggestSubstitutions(lines, rules, stock, ingredients),
        };
      }),

    importRecipes: () => wrap(runImport),

    getBasket: () =>
      wrap(() => {
        const stock = D.usableStock(state.pantry, today());
        const totals = basketTotals();
        return {
          items: state.basket.map((b) => ({ ...b, recipe: getRecipeOr404(b.recipe_id) })),
          totals: D.toLines(
            [...totals].map(([ingredient_id, quantity]) => ({ ingredient_id, quantity })),
            stock,
            ingredients,
          ),
        };
      }),

    addToBasket: (recipe_id, servings) =>
      wrap(() => {
        getRecipeOr404(recipe_id);
        checkServings(servings);
        const existing = state.basket.find((b) => b.recipe_id === recipe_id);
        if (existing) {
          existing.servings = servings;
          return existing;
        }
        const item: BasketItem = { id: id("b"), recipe_id, servings, substitutions: [] };
        state.basket.push(item);
        return item;
      }),

    updateBasketItem: (bid, patch) =>
      wrap(() => {
        const item = state.basket.find((b) => b.id === bid);
        if (!item) throw notFound("Basket item");
        if (patch.servings !== undefined) {
          checkServings(patch.servings);
          item.servings = patch.servings;
        }
        if (patch.substitutions) {
          checkSubs(getRecipeOr404(item.recipe_id), patch.substitutions);
          item.substitutions = patch.substitutions;
        }
        return item;
      }),

    removeBasketItem: (bid) =>
      wrap(() => {
        const before = state.basket.length;
        state.basket = state.basket.filter((b) => b.id !== bid);
        if (before === state.basket.length) throw notFound("Basket item");
      }),

    getShoppingList: () => wrap(() => state.shopping),

    generateShoppingList: ({ resetAll = false, force = false } = {}) =>
      wrap(() => {
        const edited = state.shopping.some(
          (s) => (s.origin === "generated" && (s.edited || s.purchased)) || (resetAll && s.origin === "manual"),
        );
        if (edited && !force)
          throw new ServiceError(409, "EDITS_WOULD_BE_LOST", "Regenerating will overwrite your edits to the list.");
        const toBuy = D.computeShopping(basketTotals(), D.usableStock(state.pantry, today()));
        const keep = resetAll ? [] : state.shopping.filter((s) => s.origin === "manual");
        const generated: ShoppingItem[] = [...toBuy].map(([ingredient_id, quantity]) => {
          const ing = ingredients.get(ingredient_id)!;
          return {
            id: id("s"),
            ingredient_id,
            label: ing.name,
            quantity,
            unit: ing.canonical_unit,
            origin: "generated",
            purchased: false,
            transferred_to_pantry: false,
            edited: false,
          };
        });
        state.shopping = [...generated, ...keep];
        return state.shopping;
      }),

    addShoppingItem: (input) =>
      wrap(() => {
        if (!input.label?.trim()) throw bad("Item name is required");
        if (!(input.quantity > 0)) throw bad("Quantity must be greater than zero");
        let ingredient_id = input.ingredient_id ?? null;
        let unit = input.unit?.trim() || "pcs";
        if (ingredient_id) {
          const ing = ingredients.get(ingredient_id);
          if (!ing) throw bad("Unknown ingredient");
          unit = ing.canonical_unit;
        } else {
          const match = CATALOG.find((i) => i.name.toLowerCase() === input.label.trim().toLowerCase());
          if (match && match.canonical_unit === unit) ingredient_id = match.id;
        }
        const item: ShoppingItem = {
          id: id("s"),
          ingredient_id,
          label: input.label.trim(),
          quantity: D.round(input.quantity),
          unit,
          origin: "manual",
          purchased: false,
          transferred_to_pantry: false,
          edited: false,
        };
        state.shopping.push(item);
        return item;
      }),

    updateShoppingItem: (sid, patch) =>
      wrap(() => {
        const item = state.shopping.find((s) => s.id === sid);
        if (!item) throw notFound("Shopping item");
        if (patch.quantity !== undefined) {
          if (!(patch.quantity > 0)) throw bad("Quantity must be greater than zero");
          item.quantity = D.round(patch.quantity);
          item.edited = true;
        }
        if (patch.purchased !== undefined) {
          if (item.transferred_to_pantry && !patch.purchased)
            throw new ServiceError(409, "ALREADY_TRANSFERRED", "This item was already added to the pantry");
          item.purchased = patch.purchased;
        }
        return item;
      }),

    removeShoppingItem: (sid) =>
      wrap(() => {
        const before = state.shopping.length;
        state.shopping = state.shopping.filter((s) => s.id !== sid);
        if (before === state.shopping.length) throw notFound("Shopping item");
      }),

    transferToPantry: (sid, input) =>
      wrap(() => {
        const item = state.shopping.find((s) => s.id === sid);
        if (!item) throw notFound("Shopping item");
        if (item.transferred_to_pantry) return item; // idempotent
        if (!item.purchased) throw new ServiceError(409, "NOT_PURCHASED", "Mark the item as purchased first");
        if (!item.ingredient_id) throw bad("Only catalog ingredients can be added to the pantry");
        if (!(input.quantity > 0)) throw bad("Quantity must be greater than zero");
        if (!D.isValidDate(input.expiry_date)) throw bad("Enter a valid expiry date");
        const existing = state.pantry.find((p) => p.ingredient_id === item.ingredient_id);
        const q = D.round(input.quantity);
        if (existing) {
          if (existing.expiry_date === input.expiry_date) existing.quantity = D.round(existing.quantity + q);
          else if (D.expiryStatus(existing.expiry_date, today()) === "expired" || existing.quantity <= 0)
            Object.assign(existing, { quantity: q, expiry_date: input.expiry_date });
          else
            throw new ServiceError(
              409,
              "EXPIRY_CONFLICT",
              "Your pantry already has this ingredient with a different expiry date. Use the same date or edit the pantry entry first.",
            );
        } else {
          state.pantry.push({ id: id("p"), ingredient_id: item.ingredient_id, quantity: q, expiry_date: input.expiry_date });
        }
        item.transferred_to_pantry = true;
        return item;
      }),

    previewCook: (req) => wrap(() => cookPreview(req).preview),

    confirmCook: (req) =>
      wrap(() => {
        const { recipe, agg, preview } = cookPreview(req);
        if (!preview.can_cook)
          throw new ServiceError(409, "INSUFFICIENT_STOCK", "Not enough usable stock to cook this recipe. Nothing was changed.");
        const t = today();
        for (const [ingId, qty] of agg) {
          const p = state.pantry.find((x) => x.ingredient_id === ingId && D.expiryStatus(x.expiry_date, t) !== "expired")!;
          p.quantity = D.round(p.quantity - qty);
          if (p.quantity <= 0) state.pantry = state.pantry.filter((x) => x.id !== p.id);
        }
        const record: CookingRecord = {
          id: id("h"),
          recipe_id: recipe.id,
          recipe_title: recipe.title,
          servings: req.servings,
          cooked_at: new Date().toISOString(),
          consumed: [...agg].map(([ingredient_id, quantity]) => ({ ingredient_id, quantity })),
        };
        state.history.unshift(record);
        return record;
      }),

    listHistory: () => wrap(() => state.history),

    getDashboard: () =>
      wrap(() => {
        const t = today();
        const statuses = state.pantry.map((p) => D.expiryStatus(p.expiry_date, t));
        const ranked = D.rankRecipes(state.recipes.map(summary));
        const urgent = ranked.filter((r) => r.match.expiring_used.length > 0);
        return {
          total_items: state.pantry.length,
          expiring_soon: statuses.filter((s) => s === "expiring").length,
          expired: statuses.filter((s) => s === "expired").length,
          recommendations: (urgent.length ? urgent : ranked).slice(0, 4),
          recent_history: state.history.slice(0, 5),
        };
      }),
  };
  return service;
}
