import { ServiceError, type FreshService } from "./types";

/** HTTP transport only. All quantities, matching and inventory decisions come from FastAPI. */
export function createHttpService(
  baseUrl = import.meta.env["VITE_API_BASE_URL"] || "http://127.0.0.1:8000/api",
  fetcher: typeof fetch = (...args) => fetch(...args),
): FreshService {
  const base = baseUrl.replace(/\/+$/, "");
  async function request<T>(path: string, method = "GET", body?: unknown): Promise<T> {
    let response: Response;
    try {
      response = await fetcher(`${base}${path}`, {
        method,
        headers: {
          Accept: "application/json",
          ...(body === undefined ? {} : { "Content-Type": "application/json" }),
        },
        ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      });
    } catch {
      throw new ServiceError(
        0,
        "NETWORK_ERROR",
        "Cannot reach FreshFirst. Check that the backend is running and try again.",
      );
    }
    if (!response.ok) {
      const error = await response.json().catch(() => null);
      throw new ServiceError(
        response.status,
        error?.code || "HTTP_ERROR",
        error?.message || `FreshFirst request failed (${response.status}). Please try again.`,
      );
    }
    if (response.status === 204) return undefined as T;
    try {
      return (await response.json()) as T;
    } catch {
      throw new ServiceError(
        response.status,
        "INVALID_RESPONSE",
        "FreshFirst returned an invalid response. Please try again.",
      );
    }
  }
  const id = encodeURIComponent;
  return {
    listIngredients: () => request("/ingredients"),
    listSubstitutionRules: () => request("/substitution-rules"),
    listPantry: () => request("/pantry"),
    createPantryItem: (input) => request("/pantry", "POST", input),
    updatePantryItem: (key, input) => request(`/pantry/${id(key)}`, "PUT", input),
    deletePantryItem: (key) => request(`/pantry/${id(key)}`, "DELETE"),
    listRecipes: (params = {}) => {
      const query = new URLSearchParams();
      for (const [key, value] of Object.entries(params))
        if (value !== undefined) query.set(key, value);
      return request(`/recipes?${query}`);
    },
    getRecipe: (key, servings, substitutions) => {
      const query = new URLSearchParams();
      if (servings !== undefined) query.set("servings", String(servings));
      if (substitutions !== undefined) query.set("substitutions", JSON.stringify(substitutions));
      return request(`/recipes/${id(key)}?${query}`);
    },
    importRecipes: () => request("/recipes/import", "POST"),
    getBasket: () => request("/basket"),
    addToBasket: (recipe_id, servings) => request("/basket/items", "POST", { recipe_id, servings }),
    updateBasketItem: (key, patch) => request(`/basket/items/${id(key)}`, "PATCH", patch),
    removeBasketItem: (key) => request(`/basket/items/${id(key)}`, "DELETE"),
    getShoppingList: () => request("/shopping-list"),
    generateShoppingList: (opts = {}) => request("/shopping-list/generate", "POST", opts),
    addShoppingItem: (input) => request("/shopping-list/items", "POST", input),
    updateShoppingItem: (key, patch) => request(`/shopping-list/items/${id(key)}`, "PATCH", patch),
    removeShoppingItem: (key) => request(`/shopping-list/items/${id(key)}`, "DELETE"),
    transferToPantry: (key, input) =>
      request(`/shopping-list/items/${id(key)}/transfer-to-pantry`, "POST", input),
    previewCook: (input) => request("/cooking/preview", "POST", input),
    confirmCook: (input) => request("/cooking/confirm", "POST", input),
    listHistory: () => request("/cooking/history"),
    getDashboard: () => request("/dashboard"),
  };
}
