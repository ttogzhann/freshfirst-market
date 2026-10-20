import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Toaster } from "@/components/ui/sonner";
import { Recipes } from "@/routes/recipes.index";
import { createMockService } from "@/services/mock/mockService";
import { setService, type FreshService, type ImportReport } from "@/services";

vi.mock("@tanstack/react-router", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@tanstack/react-router")>()),
  Link: ({ children }: { children: React.ReactNode }) => <span>{children}</span>,
}));

const importReport: ImportReport = {
  imported: 0,
  updated: 0,
  total_recipes: 2,
  skipped: Array.from({ length: 100 }, (_, index) => ({
    external_id: String(index + 1),
    title: index === 99 ? "Final skipped source record" : `Skipped source record ${index + 1}`,
    reason: "Unsupported source quantity",
  })),
};

let service: FreshService;

function showRecipes() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <Recipes />
      <Toaster />
    </QueryClientProvider>,
  );
}

async function openReport() {
  const trigger = screen.getByRole("button", { name: "Re-import recipes" });
  trigger.focus();
  fireEvent.click(trigger);
  const dialog = await screen.findByRole("dialog", { name: "Import report" });
  return { dialog, trigger };
}

beforeEach(() => {
  service = createMockService({ seedPantry: false });
  setService(service);
  vi.spyOn(service, "importRecipes").mockResolvedValue(importReport);
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("recipe import report dialog", () => {
  it("bounds the dialog and scrolls report results through the final entry", async () => {
    showRecipes();
    const { dialog } = await openReport();
    const results = within(dialog).getByRole("region", { name: "Import report results" });

    expect(dialog).toHaveClass("max-h-[calc(100dvh-2rem)]", "overflow-hidden");
    expect(results).toHaveClass("max-h-[calc(100dvh-8rem)]", "overflow-y-auto");
    expect(within(dialog).getByRole("heading", { name: "Import report" })).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "Close" })).toBeInTheDocument();
    expect(within(results).getByText("Final skipped source record")).toBeInTheDocument();
  });

  it.each(["Escape", "Close"] as const)(
    "returns focus to Re-import recipes after %s",
    async (close) => {
      showRecipes();
      const { dialog, trigger } = await openReport();

      if (close === "Escape") {
        fireEvent.keyDown(dialog, { key: "Escape" });
      } else {
        fireEvent.click(within(dialog).getByRole("button", { name: "Close" }));
      }

      await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
      expect(trigger).toHaveFocus();
    },
  );
});
