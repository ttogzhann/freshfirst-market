import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { toast } from "sonner";
import { Pantry } from "@/routes/pantry";
import { ShoppingPage } from "@/routes/shopping";
import { createMockService } from "@/services/mock/mockService";
import { ServiceError, setService, type FreshService } from "@/services";

vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
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
  window.HTMLElement.prototype.scrollIntoView = vi.fn();
  vi.mocked(toast.success).mockClear();
  vi.mocked(toast.error).mockClear();
});
afterEach(cleanup);

describe("recoverable pantry and shopping form errors", () => {
  it("validates pantry quantity and date inline without sending a mutation", async () => {
    const egg = await service.createPantryItem({
      ingredient_id: "egg",
      quantity: 2,
      unit: "pcs",
      expiry_date: "2026-11-30",
    });
    const update = vi.spyOn(service, "updatePantryItem");
    show(<Pantry />);

    fireEvent.click(await screen.findByRole("button", { name: "Edit Eggs" }));
    fireEvent.change(screen.getByLabelText("Quantity"), { target: { value: "0" } });
    fireEvent.change(screen.getByLabelText("Expiry date"), { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByText("Enter a finite quantity above zero")).toBeInTheDocument();
    expect(screen.getByText("Enter a valid calendar date")).toBeInTheDocument();
    expect(screen.getByLabelText("Quantity")).toHaveValue(0);
    expect(screen.getByLabelText("Expiry date")).toHaveValue("");
    expect(update).not.toHaveBeenCalled();
    expect((await service.listPantry()).find((item) => item.id === egg.id)?.quantity).toBe(2);
  });

  it("retains a rejected pantry update and retries the corrected value", async () => {
    const egg = await service.createPantryItem({
      ingredient_id: "egg",
      quantity: 2,
      unit: "pcs",
      expiry_date: "2026-11-30",
    });
    const update = vi
      .spyOn(service, "updatePantryItem")
      .mockRejectedValueOnce(
        new ServiceError(422, "VALIDATION_ERROR", "Quantity must be positive"),
      );
    show(<Pantry />);

    fireEvent.click(await screen.findByRole("button", { name: "Edit Eggs" }));
    fireEvent.change(screen.getByLabelText("Quantity"), { target: { value: "4" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Quantity must be positive");
    expect(screen.getByLabelText("Quantity")).toHaveValue(4);
    expect(screen.getByLabelText("Expiry date")).toHaveValue("2026-11-30");
    expect((await service.listPantry()).find((item) => item.id === egg.id)?.quantity).toBe(2);
    expect(toast.error).toHaveBeenCalledOnce();

    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect((await service.listPantry()).find((item) => item.id === egg.id)?.quantity).toBe(4);
    expect(update).toHaveBeenCalledTimes(2);
    expect(toast.success).toHaveBeenCalledOnce();
  });

  it("retains a rejected pantry create, shows expiry guidance and allows a confirmed retry", async () => {
    await service.createPantryItem({
      ingredient_id: "egg",
      quantity: 2,
      unit: "pcs",
      expiry_date: "2026-11-30",
    });
    show(<Pantry />);

    const addButton = await screen.findByRole("button", { name: "Add item" });
    await waitFor(() => expect(addButton).toBeEnabled());
    fireEvent.click(addButton);
    await screen.findByRole("dialog");
    fireEvent.click(screen.getByLabelText("Ingredient"));
    fireEvent.click(await screen.findByRole("option", { name: "Eggs" }));
    fireEvent.change(screen.getByLabelText("Quantity"), { target: { value: "3" } });
    fireEvent.change(screen.getByLabelText("Expiry date"), { target: { value: "2026-12-01" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/edit the existing entry/i);
    expect(screen.getByLabelText("Ingredient")).toHaveTextContent("Eggs");
    expect(screen.getByLabelText("Quantity")).toHaveValue(3);
    expect(screen.getByLabelText("Expiry date")).toHaveValue("2026-12-01");
    expect(toast.error).toHaveBeenCalledOnce();
    expect((await service.listPantry())[0]?.quantity).toBe(2);

    fireEvent.change(screen.getByLabelText("Expiry date"), { target: { value: "2026-11-30" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect((await service.listPantry())[0]?.quantity).toBe(5);
    expect(toast.success).toHaveBeenCalledOnce();
  });

  it("preserves a rejected shopping quantity edit for correction and retry", async () => {
    const item = await service.addShoppingItem({ label: "Eggs", quantity: 6, unit: "pcs" });
    const update = vi
      .spyOn(service, "updateShoppingItem")
      .mockRejectedValueOnce(
        new ServiceError(422, "VALIDATION_ERROR", "Quantity must be positive"),
      );
    show(<ShoppingPage />);

    const input = await screen.findByLabelText("Quantity for Eggs");
    fireEvent.change(input, { target: { value: "0" } });
    fireEvent.click(screen.getByRole("button", { name: "Save quantity" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/quantity above zero/i);
    expect(update).not.toHaveBeenCalled();
    expect((await service.getShoppingList()).find((line) => line.id === item.id)?.quantity).toBe(6);

    fireEvent.change(input, { target: { value: "8" } });
    fireEvent.click(screen.getByRole("button", { name: "Save quantity" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Quantity must be positive");
    expect(screen.getByLabelText("Quantity for Eggs")).toHaveValue(8);
    expect((await service.getShoppingList()).find((line) => line.id === item.id)?.quantity).toBe(6);
    expect(toast.error).toHaveBeenCalledOnce();

    fireEvent.click(screen.getByRole("button", { name: "Save quantity" }));
    await waitFor(async () =>
      expect((await service.getShoppingList()).find((line) => line.id === item.id)?.quantity).toBe(
        8,
      ),
    );
    expect(update).toHaveBeenCalledTimes(2);
    expect(toast.success).toHaveBeenCalledOnce();
  });

  it("validates purchase quantity and expiry inline before calling the service", async () => {
    const item = await service.addShoppingItem({
      label: "Eggs",
      quantity: 4,
      unit: "pcs",
      ingredient_id: "egg",
    });
    await service.updateShoppingItem(item.id, { purchased: true });
    const transfer = vi.spyOn(service, "transferToPantry");
    show(<ShoppingPage />);

    const quantity = await screen.findByLabelText("Actual quantity (pcs)");
    fireEvent.change(quantity, { target: { value: "0" } });
    fireEvent.change(screen.getByLabelText("Expiry date"), { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: "Confirm transfer to pantry" }));

    expect(await screen.findByText("Enter a finite quantity above zero.")).toBeInTheDocument();
    expect(screen.getByText("Enter a valid calendar date.")).toBeInTheDocument();
    expect(screen.getByLabelText("Actual quantity (pcs)")).toHaveValue(0);
    expect(screen.getByLabelText("Expiry date")).toHaveValue("");
    expect(transfer).not.toHaveBeenCalled();
    expect(await service.listPantry()).toEqual([]);
  });

  it("retains a rejected purchase transfer and completes only after a corrected retry", async () => {
    await service.createPantryItem({
      ingredient_id: "egg",
      quantity: 2,
      unit: "pcs",
      expiry_date: "2026-11-30",
    });
    const item = await service.addShoppingItem({
      label: "Eggs",
      quantity: 4,
      unit: "pcs",
      ingredient_id: "egg",
    });
    await service.updateShoppingItem(item.id, { purchased: true });
    show(<ShoppingPage />);

    const quantity = await screen.findByLabelText("Actual quantity (pcs)");
    const expiry = screen.getByLabelText("Expiry date");
    fireEvent.change(quantity, { target: { value: "3" } });
    fireEvent.change(expiry, { target: { value: "2026-12-01" } });
    fireEvent.click(screen.getByRole("button", { name: "Confirm transfer to pantry" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/edit the pantry entry first/i);
    expect(screen.getByLabelText("Actual quantity (pcs)")).toHaveValue(3);
    expect(screen.getByLabelText("Expiry date")).toHaveValue("2026-12-01");
    expect(screen.queryByText("Added to pantry")).not.toBeInTheDocument();
    expect((await service.listPantry())[0]?.quantity).toBe(2);
    expect(toast.error).toHaveBeenCalledOnce();

    fireEvent.change(screen.getByLabelText("Expiry date"), {
      target: { value: "2026-11-30" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Confirm transfer to pantry" }));
    expect(await screen.findByText("Added to pantry")).toBeInTheDocument();
    expect((await service.listPantry())[0]?.quantity).toBe(5);
    expect(toast.success).toHaveBeenCalledOnce();
  });

  it("waits for pantry confirmation before closing the editor or showing success", async () => {
    const egg = await service.createPantryItem({
      ingredient_id: "egg",
      quantity: 2,
      unit: "pcs",
      expiry_date: "2026-11-30",
    });
    const originalUpdate = service.updatePantryItem.bind(service);
    let release!: () => void;
    const pending = new Promise<void>((resolve) => {
      release = resolve;
    });
    const update = vi.spyOn(service, "updatePantryItem").mockImplementation(async (...args) => {
      await pending;
      return originalUpdate(...args);
    });
    show(<Pantry />);

    fireEvent.click(await screen.findByRole("button", { name: "Edit Eggs" }));
    fireEvent.change(screen.getByLabelText("Quantity"), { target: { value: "4" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(update).toHaveBeenCalledOnce());
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(toast.success).not.toHaveBeenCalled();
    expect((await service.listPantry()).find((item) => item.id === egg.id)?.quantity).toBe(2);

    release();
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect((await service.listPantry()).find((item) => item.id === egg.id)?.quantity).toBe(4);
    expect(toast.success).toHaveBeenCalledOnce();
  });

  it("waits for transfer confirmation before showing completion or success", async () => {
    const item = await service.addShoppingItem({
      label: "Eggs",
      quantity: 4,
      unit: "pcs",
      ingredient_id: "egg",
    });
    await service.updateShoppingItem(item.id, { purchased: true });
    const originalTransfer = service.transferToPantry.bind(service);
    let release!: () => void;
    const pending = new Promise<void>((resolve) => {
      release = resolve;
    });
    const transfer = vi.spyOn(service, "transferToPantry").mockImplementation(async (...args) => {
      await pending;
      return originalTransfer(...args);
    });
    show(<ShoppingPage />);

    fireEvent.change(await screen.findByLabelText("Expiry date"), {
      target: { value: "2026-11-30" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Confirm transfer to pantry" }));
    await waitFor(() => expect(transfer).toHaveBeenCalledOnce());
    expect(screen.queryByText("Added to pantry")).not.toBeInTheDocument();
    expect(toast.success).not.toHaveBeenCalled();
    expect(await service.listPantry()).toEqual([]);

    release();
    expect(await screen.findByText("Added to pantry")).toBeInTheDocument();
    expect((await service.listPantry())[0]?.quantity).toBe(4);
    expect(toast.success).toHaveBeenCalledOnce();
  });
});
