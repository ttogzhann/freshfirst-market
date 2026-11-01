import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { RecipePage, Route } from "@/routes/recipes.$id";
import { Toaster } from "@/components/ui/sonner";
import { AuthenticatedTestProvider } from "@/test/authenticated-test-provider";
import { createMockService } from "@/services/mock/mockService";
import { setService, type ConfirmedSubstitution, type FreshService } from "@/services";

vi.mock("@tanstack/react-router", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@tanstack/react-router")>()),
  Link: ({ children }: { children: React.ReactNode }) => <span>{children}</span>,
}));

const spinachToMushrooms: ConfirmedSubstitution = {
  rule_id: "r8",
  original_ingredient_id: "spinach",
  substitute_ingredient_id: "mushroom",
};
const cheeseToParmesan: ConfirmedSubstitution = {
  rule_id: "r5",
  original_ingredient_id: "cheese",
  substitute_ingredient_id: "parmesan",
};

let service: FreshService;
let recipeId: string;

function show() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const page = render(
    <QueryClientProvider client={client}>
      <AuthenticatedTestProvider>
        <RecipePage />
        <Toaster />
      </AuthenticatedTestProvider>
    </QueryClientProvider>,
  );
  return {
    ...page,
    rerenderRoute: () =>
      page.rerender(
        <QueryClientProvider client={client}>
          <AuthenticatedTestProvider>
            <RecipePage />
            <Toaster />
          </AuthenticatedTestProvider>
        </QueryClientProvider>,
      ),
  };
}

async function addStock(ingredient_id: string, quantity: number, unit: "g" | "ml") {
  await service.createPantryItem({
    ingredient_id,
    quantity,
    unit,
    expiry_date: "2099-01-01",
  });
}

beforeEach(() => {
  service = createMockService({ seedPantry: false, today: () => "2026-10-20" });
  setService(service);
  recipeId = "rec_52906";
  vi.spyOn(Route, "useParams").mockImplementation(() => ({ id: recipeId }));
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("recipe detail saved choices", () => {
  it("restores saved scale and substitutions before any write", async () => {
    await addStock("mushroom", 500, "g");
    const item = await service.addToBasket("rec_52906", 3);
    await service.updateBasketItem(item.id, { substitutions: [spinachToMushrooms] });
    const add = vi.spyOn(service, "addToBasket");
    const update = vi.spyOn(service, "updateBasketItem");

    show();

    expect(await screen.findByText("3 batches")).toBeInTheDocument();
    const mushroomLine = screen.getByText("Mushrooms").closest("li");
    expect(mushroomLine).not.toBeNull();
    expect(within(mushroomLine!).getByText("substitute")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Undo substitutions" })).toBeInTheDocument();
    expect(add).not.toHaveBeenCalled();
    expect(update).not.toHaveBeenCalled();
  });

  it("keeps substitutions on a scale-only save and clears them only after explicit undo", async () => {
    await addStock("mushroom", 500, "g");
    const item = await service.addToBasket("rec_52906", 3);
    await service.updateBasketItem(item.id, { substitutions: [spinachToMushrooms] });
    const add = vi.spyOn(service, "addToBasket");
    const update = vi.spyOn(service, "updateBasketItem");
    show();

    fireEvent.click(await screen.findByRole("button", { name: "Increase batches" }));
    fireEvent.click(await screen.findByRole("button", { name: "Update basket (3 → 4)" }));
    await waitFor(async () => {
      const basket = await service.getBasket();
      expect(basket.items).toHaveLength(1);
      expect(basket.items[0]).toMatchObject({
        id: item.id,
        servings: 4,
        substitutions: [spinachToMushrooms],
      });
    });
    expect(add).toHaveBeenCalledOnce();
    expect(update).not.toHaveBeenCalled();

    const expectedLines = await service.getRecipe("rec_52906", 4, [spinachToMushrooms]);
    const savedBasket = await service.getBasket();
    expect(
      savedBasket.totals.map(({ ingredient_id, required }) => [ingredient_id, required]),
    ).toEqual(expectedLines.lines.map(({ ingredient_id, required }) => [ingredient_id, required]));

    fireEvent.click(screen.getByRole("button", { name: "Undo substitutions" }));
    fireEvent.click(await screen.findByRole("button", { name: "Update basket (4 → 4)" }));
    let clearedBasket = await service.getBasket();
    await waitFor(async () => {
      clearedBasket = await service.getBasket();
      expect(clearedBasket.items).toHaveLength(1);
      expect(clearedBasket.items[0]).toMatchObject({
        id: item.id,
        servings: 4,
        substitutions: [],
      });
    });
    expect(update).toHaveBeenCalledOnce();
    expect(update).toHaveBeenCalledWith(item.id, { substitutions: [] });
    const expectedClearedLines = await service.getRecipe("rec_52906", 4, []);
    expect(
      clearedBasket!.totals.map(({ ingredient_id, required }) => [ingredient_id, required]),
    ).toEqual(
      expectedClearedLines.lines.map(({ ingredient_id, required }) => [ingredient_id, required]),
    );
  });

  it("reports a failed substitution patch and reconciles the successful new-item add", async () => {
    await addStock("mushroom", 500, "g");
    const add = vi.spyOn(service, "addToBasket");
    const update = vi
      .spyOn(service, "updateBasketItem")
      .mockRejectedValue(new Error("Patch failed"));
    show();

    fireEvent.click(await screen.findByRole("button", { name: "Increase batches" }));
    fireEvent.click(await screen.findByRole("button", { name: "Use substitute" }));
    fireEvent.click(await screen.findByRole("button", { name: "Add to basket" }));

    expect(await screen.findByText("Something went wrong: Patch failed")).toBeInTheDocument();
    expect(add).toHaveBeenCalledOnce();
    expect(update).toHaveBeenCalledOnce();
    expect(screen.queryByText("Added to basket")).not.toBeInTheDocument();
    const basket = await service.getBasket();
    expect(basket.items).toHaveLength(1);
    expect(basket.items[0]).toMatchObject({
      recipe_id: "rec_52906",
      servings: 2,
      substitutions: [],
    });
    expect(await screen.findByRole("button", { name: "Use substitute" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Undo substitutions" })).not.toBeInTheDocument();
  });

  it("isolates local scale, substitutions, and rejected suggestions when the route changes", async () => {
    await addStock("mushroom", 500, "g");
    await addStock("parmesan", 500, "g");
    const item = await service.addToBasket("rec_52906", 3);
    await service.updateBasketItem(item.id, { substitutions: [cheeseToParmesan] });
    const page = show();

    expect(await screen.findByText("3 batches")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Increase batches" }));
    expect(await screen.findByText("4 batches")).toBeInTheDocument();
    fireEvent.click(await screen.findByRole("button", { name: "No thanks" }));
    expect(screen.getByRole("button", { name: "Undo substitutions" })).toBeInTheDocument();
    const parmesanLine = screen.getByText("Parmesan").closest("li");
    expect(parmesanLine).not.toBeNull();
    expect(within(parmesanLine!).getByText("substitute")).toBeInTheDocument();

    recipeId = "rec_52959";
    page.rerenderRoute();

    expect(await screen.findByText("Recipe quantity 2")).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Use substitute" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Undo substitutions" })).not.toBeInTheDocument();
    expect((await service.getBasket()).items[0]).toMatchObject({
      id: item.id,
      recipe_id: "rec_52906",
      servings: 3,
      substitutions: [cheeseToParmesan],
    });
  });

  it("uses the next route's saved choices instead of the previous route's local state", async () => {
    await addStock("mushroom", 500, "g");
    const item = await service.addToBasket("rec_52959", 5);
    await service.updateBasketItem(item.id, { substitutions: [spinachToMushrooms] });
    const page = show();

    recipeId = "rec_52959";
    page.rerenderRoute();

    expect(await screen.findByText("Recipe quantity 5")).toBeInTheDocument();
    const mushroomLine = screen.getByText("Mushrooms").closest("li");
    expect(mushroomLine).not.toBeNull();
    expect(within(mushroomLine!).getByText("substitute")).toBeInTheDocument();
    expect((await service.getBasket()).items).toHaveLength(1);
  });
});
