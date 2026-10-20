import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { BasketPage } from "@/routes/basket";
import { ShoppingPage } from "@/routes/shopping";
import { createMockService } from "@/services/mock/mockService";
import { setService, type FreshService } from "@/services";

vi.mock("@tanstack/react-router", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@tanstack/react-router")>()),
  Link: ({ children }: { children: React.ReactNode }) => <span>{children}</span>,
}));

let service: FreshService;
function show(page: React.ReactNode) {
  return render(
    <QueryClientProvider
      client={
        new QueryClient({
          defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
        })
      }
    >
      {page}
    </QueryClientProvider>,
  );
}
beforeEach(() => {
  service = createMockService({ seedPantry: false, today: () => "2026-10-20" });
  setService(service);
});
afterEach(cleanup);

describe("basket and shopping journeys", () => {
  it("keeps a pending purchase unconfirmed until the backend responds", async () => {
    const item = await service.addShoppingItem({ label: "Eggs", quantity: 6, unit: "pcs" });
    await service.updateShoppingItem(item.id, { purchased: true });
    const original = service.transferToPantry.bind(service);
    let release!: () => void;
    const pending = new Promise<void>((resolve) => {
      release = resolve;
    });
    const transfer = vi.spyOn(service, "transferToPantry").mockImplementation(async (...args) => {
      await pending;
      return original(...args);
    });
    show(<ShoppingPage />);
    fireEvent.change(await screen.findByLabelText("Expiry date"), {
      target: { value: "2026-11-01" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Confirm transfer to pantry" }));
    await waitFor(() => expect(transfer).toHaveBeenCalledOnce());
    expect(screen.getByRole("button", { name: "Confirm transfer to pantry" })).toBeDisabled();
    expect(screen.queryByText("Added to pantry")).not.toBeInTheDocument();
    expect(await service.listPantry()).toEqual([]);
    release();
    expect(await screen.findByText("Added to pantry")).toBeInTheDocument();
    expect((await service.listPantry())[0]?.quantity).toBe(6);
  });

  it("updates basket servings and removes selections", async () => {
    await service.addToBasket("rec_52982", 2);
    show(<BasketPage />);
    const select = await screen.findByLabelText(/Recipe quantity for/);
    fireEvent.change(select, { target: { value: "4" } });
    await waitFor(async () => expect((await service.getBasket()).items[0]?.servings).toBe(4));
    expect(await screen.findByText("Cumulative ingredients")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Remove" }));
    expect(await screen.findByText("Your basket is empty")).toBeInTheDocument();
  });

  it("requires confirmation before overwriting edited generated lines", async () => {
    await service.addToBasket("rec_52982", 2);
    const lines = await service.generateShoppingList();
    await service.updateShoppingItem(lines[0]!.id, { quantity: 999 });
    await service.addShoppingItem({ label: "Paper towels", quantity: 1, unit: "pcs" });
    show(<ShoppingPage />);
    fireEvent.click(await screen.findByRole("button", { name: "Generate from basket" }));
    expect(await screen.findByRole("alertdialog")).toBeInTheDocument();
    expect((await service.getShoppingList()).some((i) => i.quantity === 999)).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Confirm regeneration" }));
    await waitFor(() => expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument());
    expect((await service.getShoppingList()).some((i) => i.label === "Paper towels")).toBe(true);
  });

  it("only transfers a purchase after actual quantity and expiry are confirmed", async () => {
    const item = await service.addShoppingItem({ label: "Eggs", quantity: 6, unit: "pcs" });
    show(<ShoppingPage />);
    fireEvent.click(await screen.findByLabelText("Eggs (manual)"));
    await screen.findByRole("button", { name: "Confirm transfer to pantry" });
    expect(await service.listPantry()).toEqual([]);
    fireEvent.change(screen.getByLabelText("Actual quantity (pcs)"), { target: { value: "4" } });
    fireEvent.change(screen.getByLabelText("Expiry date"), { target: { value: "2026-11-01" } });
    fireEvent.click(screen.getByRole("button", { name: "Confirm transfer to pantry" }));
    expect(await screen.findByText("Added to pantry")).toBeInTheDocument();
    await service.transferToPantry(item.id, { quantity: 4, expiry_date: "2026-11-01" });
    expect((await service.listPantry())[0]?.quantity).toBe(4);
  });

  it("keeps a failed transfer recoverable and does not change inventory", async () => {
    const item = await service.addShoppingItem({ label: "Eggs", quantity: 6, unit: "pcs" });
    await service.updateShoppingItem(item.id, { purchased: true });
    vi.spyOn(service, "transferToPantry").mockRejectedValue(new Error("Network unavailable"));
    show(<ShoppingPage />);
    fireEvent.change(await screen.findByLabelText("Expiry date"), {
      target: { value: "2026-11-01" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Confirm transfer to pantry" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Network unavailable");
    expect(screen.queryByText("Added to pantry")).not.toBeInTheDocument();
    expect(await service.listPantry()).toEqual([]);
  });
});
