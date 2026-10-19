// Domain types + the single service interface every screen talks to.
// The mock implementation lives in ./mock; a future HTTP client implements the same interface.

export type CanonicalUnit = "g" | "ml" | "pcs";
export type InputUnit = "g" | "kg" | "ml" | "l" | "tsp" | "tbsp" | "pcs";

export interface Ingredient {
  id: string;
  name: string;
  category: string;
  canonical_unit: CanonicalUnit;
}

export type ExpiryStatus = "fresh" | "expiring" | "expired";

export interface PantryItem {
  id: string;
  ingredient_id: string;
  /** Quantity in the ingredient's canonical unit. */
  quantity: number;
  /** ISO date YYYY-MM-DD */
  expiry_date: string;
}

export interface PantryInput {
  ingredient_id: string;
  quantity: number;
  unit: InputUnit;
  expiry_date: string;
}

export interface RecipeIngredient {
  ingredient_id: string;
  /** Canonical quantity for base_servings. */
  quantity: number;
}

export interface Recipe {
  id: string;
  external_id: string;
  title: string;
  category: string;
  instructions: string;
  image_url: string;
  base_servings: number;
  ingredients: RecipeIngredient[];
}

export interface MatchInfo {
  score: number;
  covered: number;
  total: number;
  missing: string[];
  expiring_used: string[];
}

export interface RecipeSummary extends Recipe {
  match: MatchInfo;
}

export interface SubstitutionRule {
  id: string;
  original_ingredient_id: string;
  substitute_ingredient_id: string;
  ratio: number;
  context: string;
  note: string;
}

export interface ConfirmedSubstitution {
  rule_id: string;
  original_ingredient_id: string;
  substitute_ingredient_id: string;
}

export interface DemandLine {
  ingredient_id: string;
  name: string;
  unit: CanonicalUnit;
  required: number;
  available: number;
  sufficient: boolean;
  /** Set when this line is a confirmed substitute for another ingredient. */
  substituted_from?: string;
}

export interface SubstitutionSuggestion {
  rule: SubstitutionRule;
  original_name: string;
  substitute_name: string;
  required: number;
  unit: CanonicalUnit;
}

export interface RecipeDetail extends RecipeSummary {
  servings: number;
  lines: DemandLine[];
  suggestions: SubstitutionSuggestion[];
}

export interface BasketItem {
  id: string;
  recipe_id: string;
  servings: number;
  substitutions: ConfirmedSubstitution[];
}

export interface BasketView {
  items: (BasketItem & { recipe: Recipe })[];
  totals: DemandLine[];
}

export interface ShoppingItem {
  id: string;
  ingredient_id: string | null;
  label: string;
  quantity: number;
  unit: string;
  origin: "generated" | "manual";
  purchased: boolean;
  transferred_to_pantry: boolean;
  edited: boolean;
}

export interface CookRequest {
  recipe_id: string;
  servings: number;
  substitutions: ConfirmedSubstitution[];
}

export interface CookPreview {
  recipe_id: string;
  servings: number;
  lines: DemandLine[];
  can_cook: boolean;
}

export interface CookingRecord {
  id: string;
  recipe_id: string;
  recipe_title: string;
  servings: number;
  cooked_at: string;
  consumed: { ingredient_id: string; quantity: number }[];
}

export interface ImportReport {
  imported: number;
  updated: number;
  skipped: { external_id: string; title: string; reason: string }[];
  total_recipes: number;
}

export interface Dashboard {
  total_items: number;
  expiring_soon: number;
  expired: number;
  recommendations: RecipeSummary[];
  recent_history: CookingRecord[];
}

export class ServiceError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
    this.name = "ServiceError";
  }
}

export interface FreshService {
  listIngredients(): Promise<Ingredient[]>;
  listSubstitutionRules(): Promise<SubstitutionRule[]>;

  listPantry(): Promise<PantryItem[]>;
  createPantryItem(input: PantryInput): Promise<PantryItem>;
  updatePantryItem(id: string, input: PantryInput): Promise<PantryItem>;
  deletePantryItem(id: string): Promise<void>;

  listRecipes(params?: {
    query?: string;
    category?: string;
    sort?: "match" | "title";
  }): Promise<RecipeSummary[]>;
  getRecipe(
    id: string,
    servings?: number,
    substitutions?: ConfirmedSubstitution[],
  ): Promise<RecipeDetail>;
  importRecipes(): Promise<ImportReport>;

  getBasket(): Promise<BasketView>;
  addToBasket(recipe_id: string, servings: number): Promise<BasketItem>;
  updateBasketItem(
    id: string,
    patch: { servings?: number; substitutions?: ConfirmedSubstitution[] },
  ): Promise<BasketItem>;
  removeBasketItem(id: string): Promise<void>;

  getShoppingList(): Promise<ShoppingItem[]>;
  /** Throws 409 EDITS_WOULD_BE_LOST when edited generated lines exist and force is not set. */
  generateShoppingList(opts?: { resetAll?: boolean; force?: boolean }): Promise<ShoppingItem[]>;
  addShoppingItem(input: {
    label: string;
    quantity: number;
    unit: string;
    ingredient_id?: string | null;
  }): Promise<ShoppingItem>;
  updateShoppingItem(
    id: string,
    patch: { quantity?: number; purchased?: boolean },
  ): Promise<ShoppingItem>;
  removeShoppingItem(id: string): Promise<void>;
  transferToPantry(
    id: string,
    input: { quantity: number; expiry_date: string },
  ): Promise<ShoppingItem>;

  previewCook(req: CookRequest): Promise<CookPreview>;
  confirmCook(req: CookRequest): Promise<CookingRecord>;
  listHistory(): Promise<CookingRecord[]>;

  getDashboard(): Promise<Dashboard>;
}
