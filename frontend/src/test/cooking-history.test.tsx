import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Dashboard } from "@/routes/index";
import { createMockService } from "@/services/mock/mockService";
import { setService, type CookingRecord, type FreshService } from "@/services";
import { recipeQuantity } from "@/components/fresh/recipe-quantity";

vi.mock("@tanstack/react-router", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@tanstack/react-router")>()),
  Link: ({ children }: { children: React.ReactNode }) => <span>{children}</span>,
}));

// Deterministic UI records only; genuine source cooking/restart is checked separately.
const records: CookingRecord[] = Array.from({ length: 7 }, (_, index) => ({
  id: `history-${index}`,
  recipe_id: `recipe-${index}`,
  recipe_title: `Stored recipe title ${index}`,
  servings: index === 6 ? 8 : index + 1,
  cooked_at: `2026-10-${String(index + 20).padStart(2, "0")}T12:30:00Z`,
  consumed: [],
}));
const newestFirst = [...records].reverse();
let service: FreshService;

function show() {
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <Dashboard />
    </QueryClientProvider>,
  );
}

async function expand() {
  fireEvent.click(await screen.findByRole("button", { name: "View all cooking history" }));
  return screen.getByRole("region", { name: "Cooking history" });
}

beforeEach(() => {
  service = createMockService({ seedPantry: false });
  setService(service);
  vi.spyOn(service, "getDashboard").mockResolvedValue({
    total_items: 3,
    expiring_soon: 1,
    expired: 0,
    recommendations: [],
    recent_history: newestFirst.slice(0, 5),
  });
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("complete cooking history", () => {
  it("preserves recent five and stats, lazily opens all seven newest-first with exact record fields, and collapses", async () => {
    const history = vi.spyOn(service, "listHistory").mockResolvedValue(records);
    show();
    const recent = await screen.findByRole("region", { name: "Recently cooked" });
    expect(within(recent).getAllByRole("listitem")).toHaveLength(5);
    expect(screen.getByText("Pantry items")).toBeInTheDocument();
    expect(screen.getByText("Cook these first")).toBeInTheDocument();
    expect(history).not.toHaveBeenCalled();
    const complete = await expand();
    const rows = await within(complete).findAllByRole("listitem");
    expect(rows).toHaveLength(7);
    rows.forEach((row, index) => {
      const record = newestFirst[index]!;
      expect(within(row).getByText(record.recipe_title)).toBeInTheDocument();
      expect(row).toHaveTextContent(recipeQuantity(record.servings));
      expect(row.querySelector("time")).toHaveAttribute("datetime", record.cooked_at);
      expect(row).toHaveTextContent(new Date(record.cooked_at).toLocaleString());
    });
    expect(records[0]!.id).toBe("history-0"); // Source order is not mutated by sorting.
    fireEvent.click(screen.getByRole("button", { name: "Show recent only" }));
    expect(screen.getAllByRole("listitem")).toHaveLength(5);
    expect(screen.queryByText(records[0]!.recipe_title)).not.toBeInTheDocument();
  });

  it("distinguishes loading from empty and permits return while loading", async () => {
    let resolve!: (value: CookingRecord[]) => void;
    vi.spyOn(service, "listHistory").mockImplementation(
      () =>
        new Promise((done) => {
          resolve = done;
        }),
    );
    show();
    await expand();
    expect(screen.getByText("Loading cooking history…")).toBeInTheDocument();
    expect(screen.queryByText("No cooking history yet")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Show recent only" }));
    expect(screen.getByRole("region", { name: "Recently cooked" })).toBeInTheDocument();
    resolve([]);
  });

  it("shows a successful empty history distinctly", async () => {
    vi.spyOn(service, "listHistory").mockResolvedValue([]);
    show();
    await expand();
    expect(await screen.findByText("No cooking history yet")).toBeInTheDocument();
    expect(screen.queryByText("Loading cooking history…")).not.toBeInTheDocument();
  });

  it("shows an actionable failure and retries all rows using read operations only", async () => {
    const history = vi
      .spyOn(service, "listHistory")
      .mockRejectedValueOnce(new Error("History unavailable"))
      .mockResolvedValue(records);
    const mutations = [
      vi.spyOn(service, "confirmCook"),
      vi.spyOn(service, "createPantryItem"),
      vi.spyOn(service, "addToBasket"),
      vi.spyOn(service, "generateShoppingList"),
    ];
    show();
    await expand();
    expect(await screen.findByText(/History unavailable/)).toBeInTheDocument();
    expect(screen.queryByText("No cooking history yet")).not.toBeInTheDocument();
    expect(screen.queryAllByRole("listitem")).toHaveLength(0);
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findAllByRole("listitem")).toHaveLength(7);
    expect(history).toHaveBeenCalledTimes(2);
    mutations.forEach((mutation) => expect(mutation).not.toHaveBeenCalled());
  });
});
