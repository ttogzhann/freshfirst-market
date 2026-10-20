import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { toast } from "sonner";
import { CookDialog } from "@/components/fresh/CookDialog";
import { createMockService } from "@/services/mock/mockService";
import {
  ServiceError,
  setService,
  type CookRequest,
  type CookingRecord,
  type FreshService,
} from "@/services";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

async function cookFixture(extraStock = 0) {
  const mock = createMockService({ seedPantry: false });
  const recipe = await mock.getRecipe("rec_52906", 1);
  for (const line of recipe.lines) {
    await mock.createPantryItem({
      ingredient_id: line.ingredient_id,
      quantity: line.required + extraStock,
      unit: line.unit,
      expiry_date: "2099-01-01",
    });
  }
  return {
    mock,
    recipe,
    request: { recipe_id: recipe.id, servings: 1, substitutions: [] } satisfies CookRequest,
  };
}

function DialogHarness({ request }: { request: CookRequest }) {
  const [open, setOpen] = useState(true);
  return (
    <>
      <button onClick={() => setOpen(true)}>Open cook dialog</button>
      <CookDialog
        request={request}
        title="test recipe"
        baseServings={1}
        open={open}
        onOpenChange={setOpen}
      />
    </>
  );
}

function newQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
}

async function seedRelevantViews(queryClient: QueryClient, request: CookRequest) {
  const keys = [
    ["pantry"] as const,
    ["recipe", request.recipe_id, request.servings, request.substitutions] as const,
    ["recipes", undefined, undefined, "match"] as const,
    ["shopping"] as const,
    ["dashboard"] as const,
    ["history"] as const,
  ];
  const refetches = keys.map(() => vi.fn().mockResolvedValue([]));
  for (const [index, queryKey] of keys.entries()) {
    await queryClient.fetchQuery({
      queryKey,
      queryFn: refetches[index]!,
      staleTime: Infinity,
    });
  }
  return refetches;
}

function renderCookDialog(
  service: FreshService,
  request: CookRequest,
  queryClient = newQueryClient(),
) {
  setService(service);
  const invalidate = vi.spyOn(queryClient, "invalidateQueries");
  render(
    <QueryClientProvider client={queryClient}>
      <DialogHarness request={request} />
    </QueryClientProvider>,
  );
  return { invalidate, queryClient };
}

describe("CookDialog recovery", () => {
  it("retries a failed preview only and renders the new preview", async () => {
    const { mock, request } = await cookFixture();
    const validPreview = await mock.previewCook(request);
    const preview = vi
      .spyOn(mock, "previewCook")
      .mockRejectedValueOnce(new Error("preview unavailable"))
      .mockResolvedValueOnce(validPreview);
    const confirm = vi.spyOn(mock, "confirmCook");
    renderCookDialog(mock, request);

    const dialog = await screen.findByRole("dialog");
    expect(
      await within(dialog).findByText(/Something went wrong: preview unavailable/),
    ).toBeVisible();
    fireEvent.click(within(dialog).getByRole("button", { name: "Retry preview" }));

    expect(await within(dialog).findByText(validPreview.lines[0]!.name)).toBeVisible();
    expect(preview).toHaveBeenCalledTimes(2);
    expect(confirm).not.toHaveBeenCalled();
    expect(within(dialog).queryByText(/Enjoy your/)).not.toBeInTheDocument();
  });

  it("reconciles a stale-stock 409 and keeps confirmation disabled on the fresh preview", async () => {
    const { mock, request } = await cookFixture();
    const confirm = vi.spyOn(mock, "confirmCook");
    const preview = vi.spyOn(mock, "previewCook");
    const beforeHistory = await mock.listHistory();
    const queryClient = newQueryClient();
    const refetches = await seedRelevantViews(queryClient, request);
    const { invalidate } = renderCookDialog(mock, request, queryClient);
    const dialog = await screen.findByRole("dialog");
    const confirmButton = await within(dialog).findByRole("button", { name: "Confirm & deduct" });
    expect(confirmButton).toBeEnabled();

    const firstLine = (await mock.getRecipe(request.recipe_id, request.servings)).lines[0]!;
    const pantryItem = (await mock.listPantry()).find(
      (item) => item.ingredient_id === firstLine.ingredient_id,
    )!;
    await mock.deletePantryItem(pantryItem.id);
    const afterExternalStockChange = await mock.listPantry();

    fireEvent.click(confirmButton);
    await waitFor(() => expect(confirm).toHaveBeenCalledTimes(1));
    expect(await within(dialog).findByText(/Some ingredients are short/)).toBeVisible();
    expect(preview).toHaveBeenCalledTimes(2);
    expect(within(dialog).getByRole("button", { name: "Confirm & deduct" })).toBeDisabled();
    expect(await mock.listPantry()).toEqual(afterExternalStockChange);
    expect(await mock.listHistory()).toEqual(beforeHistory);
    expect(invalidate).toHaveBeenCalledWith({ refetchType: "all" });
    await waitFor(() =>
      expect(refetches.every((refetch) => refetch.mock.calls.length === 2)).toBe(true),
    );
    expect(within(dialog).queryByText(/Enjoy your/)).not.toBeInTheDocument();
  });

  it.each([
    [404, "NOT_FOUND"],
    [422, "VALIDATION_ERROR"],
  ] as const)(
    "shows definitive HTTP %i confirmation rejection as recoverable, not unknown",
    async (status, code) => {
      const { mock, request } = await cookFixture();
      const confirm = vi
        .spyOn(mock, "confirmCook")
        .mockRejectedValueOnce(new ServiceError(status, code, "Cook request was rejected."));
      const preview = vi.spyOn(mock, "previewCook");
      const pantryBefore = await mock.listPantry();
      const historyBefore = await mock.listHistory();
      renderCookDialog(mock, request);
      const dialog = await screen.findByRole("dialog");

      fireEvent.click(await within(dialog).findByRole("button", { name: "Confirm & deduct" }));

      expect(await within(dialog).findByText("Cook request was rejected.")).toBeVisible();
      expect(within(dialog).queryByText(/Cooking outcome unknown/)).not.toBeInTheDocument();
      expect(within(dialog).getByRole("button", { name: "Retry preview" })).toBeEnabled();
      expect(within(dialog).getByRole("button", { name: "Confirm & deduct" })).toBeDisabled();
      expect(confirm).toHaveBeenCalledTimes(1);
      expect(await mock.listPantry()).toEqual(pantryBefore);
      expect(await mock.listHistory()).toEqual(historyBefore);

      fireEvent.click(within(dialog).getByRole("button", { name: "Retry preview" }));
      expect(
        await within(dialog).findByText(
          (await mock.getRecipe(request.recipe_id, 1)).lines[0]!.name,
        ),
      ).toBeVisible();
      expect(preview).toHaveBeenCalledTimes(2);
      expect(confirm).toHaveBeenCalledTimes(1);
    },
  );

  it("reports a pre-commit lost response as unknown and requires close before previewing again", async () => {
    const { mock, recipe, request } = await cookFixture();
    const confirm = vi
      .spyOn(mock, "confirmCook")
      .mockRejectedValueOnce(new Error("connection lost"));
    const preview = vi.spyOn(mock, "previewCook");
    const pantryBefore = await mock.listPantry();
    const historyBefore = await mock.listHistory();
    const queryClient = newQueryClient();
    const refetches = await seedRelevantViews(queryClient, request);
    const { invalidate } = renderCookDialog(mock, request, queryClient);
    const dialog = await screen.findByRole("dialog");
    fireEvent.click(await within(dialog).findByRole("button", { name: "Confirm & deduct" }));

    expect(await within(dialog).findByText(/Cooking outcome unknown/)).toBeVisible();
    expect(within(dialog).getByText(/Inspect Pantry and recent cooking history/)).toBeVisible();
    expect(within(dialog).getByRole("button", { name: "Confirm & deduct" })).toBeDisabled();
    expect(within(dialog).queryByRole("button", { name: "Retry preview" })).not.toBeInTheDocument();
    expect(confirm).toHaveBeenCalledTimes(1);
    expect(await mock.listPantry()).toEqual(pantryBefore);
    expect(await mock.listHistory()).toEqual(historyBefore);
    expect(invalidate).toHaveBeenCalledWith({ refetchType: "all" });
    await waitFor(() =>
      expect(refetches.every((refetch) => refetch.mock.calls.length === 2)).toBe(true),
    );

    fireEvent.click(within(dialog).getAllByRole("button", { name: "Close" }).at(-1)!);
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Open cook dialog" }));
    const reopened = await screen.findByRole("dialog");
    expect(await within(reopened).findByText(recipe.lines[0]!.name)).toBeVisible();
    expect(preview).toHaveBeenCalledTimes(2);
    expect(confirm).toHaveBeenCalledTimes(1);
  });

  it("does not replay a cook committed before its response was dropped", async () => {
    const { mock, request } = await cookFixture();
    const commit = mock.confirmCook.bind(mock);
    const confirm = vi.spyOn(mock, "confirmCook").mockImplementationOnce(async (input) => {
      await commit(input);
      throw new Error("response dropped");
    });
    const preview = vi.spyOn(mock, "previewCook");
    const { invalidate } = renderCookDialog(mock, request);
    const dialog = await screen.findByRole("dialog");
    fireEvent.click(await within(dialog).findByRole("button", { name: "Confirm & deduct" }));

    expect(await within(dialog).findByText(/Cooking outcome unknown/)).toBeVisible();
    expect(confirm).toHaveBeenCalledTimes(1);
    expect(await mock.listHistory()).toHaveLength(1);
    expect((await mock.listPantry()).every((item) => item.quantity === 0)).toBe(true);
    expect(invalidate).toHaveBeenCalledWith({ refetchType: "all" });

    fireEvent.click(within(dialog).getAllByRole("button", { name: "Close" }).at(-1)!);
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Open cook dialog" }));
    const reopened = await screen.findByRole("dialog");
    expect(await within(reopened).findByText(/Some ingredients are short/)).toBeVisible();
    expect(within(reopened).getByRole("button", { name: "Confirm & deduct" })).toBeDisabled();
    expect(preview).toHaveBeenCalledTimes(2);
    expect(confirm).toHaveBeenCalledTimes(1);
    expect(await mock.listHistory()).toHaveLength(1);
  });

  it.each([
    [
      "invalid date-time",
      (record: CookingRecord): CookingRecord => ({ ...record, cooked_at: "not-a-date" }),
    ],
    [
      "negative consumed quantity",
      (record: CookingRecord): CookingRecord => ({
        ...record,
        consumed: [{ ingredient_id: "egg", quantity: -1 }],
      }),
    ],
  ])("treats a response with %s as unknown, not success", async (_caseName, corrupt) => {
    const { mock, recipe, request } = await cookFixture();
    const validRecord: CookingRecord = {
      id: "history-1",
      recipe_id: request.recipe_id,
      recipe_title: recipe.title,
      servings: request.servings,
      cooked_at: "2026-10-20T09:00:00Z",
      consumed: recipe.lines.map(({ ingredient_id, required }) => ({
        ingredient_id,
        quantity: required,
      })),
    };
    const confirm = vi.spyOn(mock, "confirmCook").mockResolvedValueOnce(corrupt(validRecord));
    const success = vi.spyOn(toast, "success");
    const pantryBefore = await mock.listPantry();
    const historyBefore = await mock.listHistory();
    const { invalidate } = renderCookDialog(mock, request);
    const dialog = await screen.findByRole("dialog");
    fireEvent.click(await within(dialog).findByRole("button", { name: "Confirm & deduct" }));

    expect(await within(dialog).findByText(/Cooking outcome unknown/)).toBeVisible();
    expect(confirm).toHaveBeenCalledTimes(1);
    expect(success).not.toHaveBeenCalled();
    expect(await mock.listPantry()).toEqual(pantryBefore);
    expect(await mock.listHistory()).toEqual(historyBefore);
    expect(invalidate).toHaveBeenCalledWith({ refetchType: "all" });
  });

  it("shows success and closes only after one valid confirmed record", async () => {
    const { mock, request } = await cookFixture();
    const confirm = vi.spyOn(mock, "confirmCook");
    const success = vi.spyOn(toast, "success");
    const { invalidate } = renderCookDialog(mock, request);
    const dialog = await screen.findByRole("dialog");
    fireEvent.click(await within(dialog).findByRole("button", { name: "Confirm & deduct" }));

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(confirm).toHaveBeenCalledTimes(1);
    expect(success).toHaveBeenCalledTimes(1);
    expect(await mock.listHistory()).toHaveLength(1);
    expect(invalidate).toHaveBeenCalledWith({ refetchType: "all" });
  });
});
