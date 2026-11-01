import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AuthContext, type AuthContextValue, type AuthStatus } from "@/auth/AuthContext";
import {
  useBasket,
  useDashboard,
  useHistory,
  useIngredients,
  usePantry,
  useRecipe,
  useRecipes,
  useShopping,
} from "@/hooks/use-fresh";
import { createMockService } from "@/services/mock/mockService";
import { setService } from "@/services";

const account = { id: "acct-1", email: "person@example.com" };

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  setService(createMockService());
});

function authValue(status: AuthStatus): AuthContextValue {
  return {
    status,
    user: status === "authenticated" ? account : null,
    restoreSession: async () => {},
    register: async () => {},
    login: async () => {},
    logout: async () => {},
  };
}

function PrivateQueryProbe() {
  useIngredients();
  usePantry();
  useRecipes();
  useRecipe("rec_52982");
  useBasket();
  useShopping();
  useHistory();
  useDashboard();
  return null;
}

describe("private query authentication gate", () => {
  it("starts no private route query before authentication and enables them after restore", async () => {
    const service = createMockService({ seedPantry: false });
    setService(service);
    const requests = {
      ingredients: vi.spyOn(service, "listIngredients"),
      pantry: vi.spyOn(service, "listPantry"),
      recipes: vi.spyOn(service, "listRecipes"),
      recipe: vi.spyOn(service, "getRecipe"),
      basket: vi.spyOn(service, "getBasket"),
      shopping: vi.spyOn(service, "getShoppingList"),
      history: vi.spyOn(service, "listHistory"),
      dashboard: vi.spyOn(service, "getDashboard"),
    };
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, gcTime: 0 } },
    });
    const view = (status: AuthStatus) => (
      <QueryClientProvider client={queryClient}>
        <AuthContext.Provider value={authValue(status)}>
          <PrivateQueryProbe />
        </AuthContext.Provider>
      </QueryClientProvider>
    );
    const rendered = render(view("loading"));

    await waitFor(() => expect(requests.ingredients).toHaveBeenCalledOnce());
    for (const request of Object.values(requests).slice(1)) {
      expect(request).not.toHaveBeenCalled();
    }

    rendered.rerender(view("anonymous"));
    rendered.rerender(view("unavailable"));
    for (const request of Object.values(requests).slice(1)) {
      expect(request).not.toHaveBeenCalled();
    }

    rendered.rerender(view("authenticated"));
    await waitFor(() => {
      for (const request of Object.values(requests).slice(1)) {
        expect(request).toHaveBeenCalledOnce();
      }
    });
  });
});
