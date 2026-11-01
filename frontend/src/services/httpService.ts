import {
  ServiceError,
  type AuthCredentials,
  type AuthService,
  type AuthSession,
  type AuthUser,
  type FreshService,
} from "./types";

/** HTTP transport only. All quantities, matching and inventory decisions come from FastAPI. */
export function createHttpService(
  baseUrl = import.meta.env["VITE_API_BASE_URL"] || "http://127.0.0.1:8000/api",
  fetcher: typeof fetch = (...args) => fetch(...args),
): FreshService & AuthService {
  const base = baseUrl.replace(/\/+$/, "");
  let csrfToken: string | null = null;
  let csrfBootstrap: Promise<void> | null = null;

  async function send<T>(path: string, method = "GET", body?: unknown): Promise<T> {
    let response: Response;
    try {
      response = await fetcher(`${base}${path}`, {
        method,
        credentials: "include",
        headers: {
          Accept: "application/json",
          ...(body === undefined ? {} : { "Content-Type": "application/json" }),
          ...(csrfToken && method !== "GET" ? { "X-CSRF-Token": csrfToken } : {}),
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
      if (
        response.status === 401 &&
        path !== "/auth/login" &&
        path !== "/auth/register" &&
        typeof window !== "undefined"
      ) {
        window.dispatchEvent(new Event("freshfirst:unauthorized"));
      }
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
  async function bootstrapCsrf(): Promise<void> {
    if (csrfToken) return;
    if (!csrfBootstrap) {
      csrfBootstrap = send<{ csrf_token: string }>("/auth/session")
        .then((session) => {
          csrfToken = session.csrf_token;
        })
        .finally(() => {
          csrfBootstrap = null;
        });
    }
    await csrfBootstrap;
  }
  async function request<T>(path: string, method = "GET", body?: unknown): Promise<T> {
    if (method !== "GET") await bootstrapCsrf();
    return send<T>(path, method, body);
  }
  async function authenticatedRequest(
    path: "/auth/register" | "/auth/login",
    input: AuthCredentials,
  ) {
    await bootstrapCsrf();
    const result = await send<{ user: AuthUser; csrf_token: string }>(path, "POST", input);
    csrfToken = result.csrf_token;
    return result.user;
  }
  const id = encodeURIComponent;
  return {
    restoreSession: async (): Promise<AuthSession> => {
      const session = await send<{
        authenticated: boolean;
        user: AuthUser | null;
        csrf_token: string;
      }>("/auth/session");
      csrfToken = session.csrf_token;
      return { authenticated: session.authenticated, user: session.user };
    },
    registerAccount: (input) => authenticatedRequest("/auth/register", input),
    loginAccount: (input) => authenticatedRequest("/auth/login", input),
    logoutAccount: async () => {
      await request<void>("/auth/logout", "POST");
      csrfToken = null;
    },
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
