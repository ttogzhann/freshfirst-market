import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { parseExpiryDays } from "@/expiry-config";

vi.mock("@tanstack/react-router", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@tanstack/react-router")>()),
  Link: ({ children }: { children: React.ReactNode }) => <span>{children}</span>,
}));

afterEach(() => {
  cleanup();
  vi.unstubAllEnvs();
  vi.useRealTimers();
  vi.restoreAllMocks();
});

function show(page: React.ReactNode) {
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      {page}
    </QueryClientProvider>,
  );
}

describe("expiry configuration", () => {
  it.each([undefined, "0", "3", "5"])("loads real Vite environment value %s", async (value) => {
    vi.stubEnv("VITE_FRESHFIRST_EXPIRY_DAYS", value);
    vi.resetModules();
    const config = await import("@/config");
    expect(config.EXPIRY_THRESHOLD_DAYS).toBe(value === undefined ? 3 : Number(value));
  });

  it.each(["-1", "1.5", "abc", "NaN", "Infinity", "", " ", "9007199254740992"])(
    "rejects invalid actual environment %s",
    async (value) => {
      vi.stubEnv("VITE_FRESHFIRST_EXPIRY_DAYS", value);
      vi.resetModules();
      await expect(import("@/config")).rejects.toThrow("VITE_FRESHFIRST_EXPIRY_DAYS");
      expect(() => parseExpiryDays(value)).toThrow("VITE_FRESHFIRST_EXPIRY_DAYS");
    },
  );

  it.each([3, 5])(
    "renders consistent pantry/filter/dashboard/recipe boundaries at %i days",
    async (threshold) => {
      vi.stubEnv("VITE_FRESHFIRST_EXPIRY_DAYS", String(threshold));
      vi.resetModules();
      vi.useFakeTimers({ toFake: ["Date"] });
      vi.setSystemTime(new Date(2026, 9, 20, 12));
      const { createMockService } = await import("@/services/mock/mockService");
      const { setService } = await import("@/services");
      const { Pantry } = await import("@/routes/pantry");
      const { Dashboard } = await import("@/routes/index");
      const { RecipePage, Route } = await import("@/routes/recipes.$id");
      const domain = await import("@/services/domain");
      // Explicit synthetic quantified source; this tests urgency boundaries, not live provenance.
      const ingredients: [string, string][] = [
        ["Pasta", "100g"],
        ["Milk", "100ml"],
        ["Butter", "10g"],
        ["Sugar", "10g"],
        ["Flour", "10g"],
        ["Rice", "10g"],
      ];
      const service = createMockService({
        seedPantry: false,
        today: () => "2026-10-20",
        externalMeals: [
          {
            idMeal: "boundary",
            strMeal: "Boundary recipe",
            strCategory: "Pasta",
            strInstructions: "Cook exact ingredients.",
            strMealThumb: "https://example.test/recipe.jpg",
            servings: 1,
            ingredients,
          },
        ],
      });
      setService(service);
      const identities = ["pasta", "milk", "butter", "sugar", "flour", "rice"];
      const dates = [
        "2026-10-19",
        "2026-10-20",
        "2026-10-23",
        "2026-10-24",
        "2026-10-25",
        "2026-10-26",
      ];
      for (let index = 0; index < identities.length; index++) {
        await service.createPantryItem({
          ingredient_id: identities[index]!,
          quantity: index < 2 ? 100 : 10,
          unit: index === 1 ? "ml" : "g",
          expiry_date: dates[index]!,
        });
      }
      expect(dates.map((d) => domain.expiryStatus(d, "2026-10-20"))).toEqual(
        threshold === 3
          ? ["expired", "expiring", "expiring", "fresh", "fresh", "fresh"]
          : ["expired", "expiring", "expiring", "expiring", "expiring", "fresh"],
      );
      const pantry = show(<Pantry />);
      await screen.findByRole("button", { name: "Edit Pasta" });
      expect(screen.getByRole("button", { name: "Edit Pasta" })).toBeEnabled();
      expect(screen.getByText("Pasta").closest(".shadow-card")).toHaveTextContent("Expired");
      fireEvent.click(screen.getByRole("button", { name: "Edit Pasta" }));
      const editDialog = await screen.findByRole("dialog");
      fireEvent.change(within(editDialog).getByRole("spinbutton", { name: "Quantity" }), {
        target: { value: "90" },
      });
      fireEvent.click(within(editDialog).getByRole("button", { name: "Save" }));
      await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
      expect(
        (await service.listPantry()).find((item) => item.ingredient_id === "pasta"),
      ).toMatchObject({ quantity: 90, expiry_date: "2026-10-19" });
      await waitFor(() =>
        expect(screen.getByText("Pasta").closest(".shadow-card")).toHaveTextContent("Expired"),
      );
      expect(screen.getByText("Milk").closest(".shadow-card")).toHaveTextContent("Expires today");
      expect(screen.getByText("Butter").closest(".shadow-card")).toHaveTextContent("3d left");
      expect(screen.getByText("4d left").className.includes("bg-warning")).toBe(threshold === 5);
      expect(screen.getByText("5d left").className.includes("bg-warning")).toBe(threshold === 5);
      expect(screen.getByText("6d left")).toHaveClass("bg-secondary");
      window.HTMLElement.prototype.scrollIntoView = vi.fn();
      fireEvent.keyDown(screen.getByRole("combobox", { name: "Expiry status" }), { key: "Enter" });
      fireEvent.click(await screen.findByRole("option", { name: "Expiring soon" }));
      expect(screen.queryByText("Pasta")).not.toBeInTheDocument();
      expect(screen.queryByText("Rice")).not.toBeInTheDocument();
      expect(screen.getAllByRole("button", { name: /Edit / })).toHaveLength(
        threshold === 3 ? 2 : 4,
      );
      pantry.unmount();
      const dashboard = await service.getDashboard();
      expect([dashboard.expired, dashboard.expiring_soon]).toEqual([1, threshold === 3 ? 2 : 4]);
      const dash = show(<Dashboard />);
      const label = await screen.findByText(`Expiring in ${threshold} days`);
      expect(label.parentElement).toHaveTextContent(String(threshold === 3 ? 2 : 4));
      expect(screen.getByText("Expired").parentElement).toHaveTextContent("1");
      dash.unmount();
      vi.spyOn(Route, "useParams").mockReturnValue({ id: "rec_boundary" });
      show(<RecipePage />);
      const urgent = threshold === 3 ? ["Milk", "Butter"] : ["Milk", "Butter", "Sugar", "Flour"];
      expect(
        await screen.findByText(
          `Uses ${urgent.join(", ")}, which expire within ${threshold} days.`,
        ),
      ).toBeInTheDocument();
      const recipe = await service.getRecipe("rec_boundary");
      expect(recipe.match.expiring_used).toEqual(urgent);
      expect(recipe.lines.find((l) => l.ingredient_id === "pasta")?.available).toBe(0);
      expect(recipe.lines.find((l) => l.ingredient_id === "milk")?.available).toBe(100);
      await service.addToBasket(recipe.id, 1);
      expect(
        (await service.generateShoppingList()).map((l) => [l.ingredient_id, l.quantity]),
      ).toEqual([["pasta", 100]]);
      expect(
        (await service.previewCook({ recipe_id: recipe.id, servings: 1, substitutions: [] }))
          .can_cook,
      ).toBe(false);
    },
  );
});
