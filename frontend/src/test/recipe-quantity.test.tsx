import { spawn, type ChildProcess } from "node:child_process";
import { once } from "node:events";
import { mkdirSync } from "node:fs";
import { rm } from "node:fs/promises";
import { createServer } from "node:net";
import { join, resolve } from "node:path";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { RecipePage, Route } from "@/routes/recipes.$id";
import { BasketPage } from "@/routes/basket";
import { ShoppingPage } from "@/routes/shopping";
import { Dashboard } from "@/routes/index";
import { createHttpService } from "@/services/httpService";
import { createMockService } from "@/services/mock/mockService";
import { setService, type AuthService, type FreshService } from "@/services";

vi.mock("@tanstack/react-router", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@tanstack/react-router")>()),
  Link: ({ children }: { children: React.ReactNode }) => <span>{children}</span>,
}));

let backend: ChildProcess;
let service: FreshService & AuthService;
let directory: string;
let sessionCookie = "";
const browserFetch: typeof fetch = async (input, init = {}) => {
  const headers = new Headers(init.headers);
  if (sessionCookie) headers.set("Cookie", sessionCookie);
  const response = await fetch(input, { ...init, headers });
  const setCookie = response.headers.get("set-cookie");
  if (setCookie?.startsWith("freshfirst_session=")) {
    sessionCookie = setCookie.includes("Max-Age=0") ? "" : setCookie.split(";", 1)[0]!;
  }
  return response;
};

beforeAll(async () => {
  directory = resolve("../backend", `.frontend-batch-ui-test-${globalThis.process.pid}`);
  mkdirSync(directory);
  const socket = createServer();
  socket.listen(0, "127.0.0.1");
  await once(socket, "listening");
  const port = (socket.address() as { port: number }).port;
  await new Promise<void>((done) => socket.close(() => done()));
  const cwd = resolve("../backend");
  const python =
    process.env["FRESHFIRST_TEST_PYTHON"] ||
    resolve(cwd, process.platform === "win32" ? ".venv/Scripts/python.exe" : ".venv/bin/python");
  backend = spawn(
    python,
    ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", String(port)],
    {
      cwd,
      env: {
        ...process.env,
        DATABASE_URL: `sqlite:///${join(directory, "test.db")}`,
        FRESHFIRST_AUTH_SECRET: "isolated batch UI test secret at least 32 bytes",
      },
      stdio: "pipe",
    },
  );
  let output = "";
  backend.stderr?.on("data", (chunk) => {
    output += chunk;
  });
  backend.on("error", (error) => {
    output += error.message;
  });
  service = createHttpService(`http://127.0.0.1:${port}/api`, browserFetch);
  for (let attempt = 0; attempt < 100; attempt++) {
    try {
      await service.listIngredients();
      await service.restoreSession();
      await service.registerAccount({
        email: "batch-ui@example.com",
        password: "a long enough batch UI password",
      });
      setService(service);
      return;
    } catch {
      await new Promise((done) => setTimeout(done, 100));
    }
  }
  throw new Error(`Normal backend unavailable: ${output}`);
}, 20000);

afterAll(async () => {
  if (backend && backend.exitCode === null) {
    const exited = once(backend, "exit");
    backend.kill();
    await exited;
  }
  if (directory) {
    await new Promise((done) => setTimeout(done, 300));
    await rm(directory, { recursive: true, force: true, maxRetries: 10, retryDelay: 100 });
  }
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

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

function expectLine(name: string, quantity: string, scope: HTMLElement = document.body) {
  const label = within(scope).getByText(name);
  expect(label.closest("li")).toHaveTextContent(quantity);
}

describe("honest recipe quantities", () => {
  it("uses genuine packaged baseline quantities across detail, basket, shopping, preview and history", async () => {
    for (const item of await service.listPantry()) await service.deletePantryItem(item.id);
    vi.spyOn(Route, "useParams").mockReturnValue({ id: "rec_53137" });
    const detail = show(<RecipePage />);
    expect(
      await screen.findByText("One batch uses the complete source ingredient quantities."),
    ).toBeInTheDocument();
    expect(screen.getByText("1 batch")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Decrease batches" })).toBeDisabled();
    expectLine("Milk", "1 l");
    expectLine("Sugar", "300 g");
    expectLine("Baking powder", "1.25 ml");
    expectLine("Vanilla extract", "5 ml");
    fireEvent.click(screen.getByRole("button", { name: /I cooked this/i }));
    const firstPreview = await screen.findByRole("dialog");
    await within(firstPreview).findByText("Milk");
    expect(firstPreview).toHaveTextContent("(1 batch)");
    expectLine("Milk", "1 l", firstPreview);
    expectLine("Sugar", "300 g", firstPreview);
    expectLine("Baking powder", "1.25 ml", firstPreview);
    expectLine("Vanilla extract", "5 ml", firstPreview);
    fireEvent.click(within(firstPreview).getByRole("button", { name: "Cancel" }));
    fireEvent.click(screen.getByRole("button", { name: "Increase batches" }));
    expect(await screen.findByText("2 batches")).toBeInTheDocument();
    expectLine("Milk", "2 l");
    expectLine("Sugar", "600 g");
    expectLine("Baking powder", "2.5 ml");
    expectLine("Vanilla extract", "10 ml");
    expect(document.body).not.toHaveTextContent(/servings|serves|portions/i);
    fireEvent.click(screen.getByRole("button", { name: "Add to basket" }));
    await waitFor(async () => expect((await service.getBasket()).items[0]?.servings).toBe(2));
    detail.unmount();

    const savedBasket = await service.getBasket();
    const update = vi.spyOn(service, "updateBasketItem");
    const basket = show(<BasketPage />);
    expect(await screen.findByLabelText(/Batches for/i)).toHaveValue("2");
    await screen.findAllByText("Milk");
    expect(document.body).not.toHaveTextContent(/servings|serves|portions/i);
    fireEvent.click(screen.getByRole("button", { name: "I Cooked This" }));
    const preview = await screen.findByRole("dialog");
    await within(preview).findByText("Milk");
    expect(preview).toHaveTextContent("(2 batches)");
    expectLine("Milk", "2 l", preview);
    expectLine("Sugar", "600 g", preview);
    expectLine("Baking powder", "2.5 ml", preview);
    expectLine("Vanilla extract", "10 ml", preview);
    expect(within(preview).getByRole("button", { name: "Confirm & deduct" })).toBeDisabled();
    fireEvent.click(within(preview).getByRole("button", { name: "Cancel" }));
    expect(update).not.toHaveBeenCalled();
    expect(await service.getBasket()).toEqual(savedBasket);
    basket.unmount();

    const shopping = show(<ShoppingPage />);
    fireEvent.click(await screen.findByRole("button", { name: "Generate from basket" }));
    expect(await screen.findByLabelText("Quantity for Milk")).toHaveValue(2000);
    expect(screen.getByLabelText("Quantity for Sugar")).toHaveValue(600);
    expect(screen.getByLabelText("Quantity for Baking powder")).toHaveValue(2.5);
    expect(screen.getByLabelText("Quantity for Vanilla extract")).toHaveValue(10);
    shopping.unmount();
    for (const line of (await service.getRecipe("rec_53137", 2)).lines) {
      await service.createPantryItem({
        ingredient_id: line.ingredient_id,
        quantity: line.required,
        unit: line.unit,
        expiry_date: "2099-01-01",
      });
    }
    await service.confirmCook({ recipe_id: "rec_53137", servings: 2, substitutions: [] });
    const savedHistory = await service.listHistory();
    const confirm = vi.spyOn(service, "confirmCook");
    show(<Dashboard />);
    expect(await screen.findByText(/Recipe quantity 2/)).toBeInTheDocument();
    expect(document.body).not.toHaveTextContent(/servings|serves|portions/i);
    expect(await service.listHistory()).toEqual(savedHistory);
    expect(savedHistory[0]?.servings).toBe(2);
    expect(confirm).not.toHaveBeenCalled();
  }, 20_000);

  it("keeps historical non-one-base records neutral and preserves the original ratio and raw value", async () => {
    const mock = createMockService({ seedPantry: false });
    setService(mock);
    const recipe = await mock.getRecipe("rec_52982", 2);
    expect(recipe.base_servings).toBe(2);
    await mock.addToBasket(recipe.id, 2);
    const saved = await mock.getBasket();
    const update = vi.spyOn(mock, "updateBasketItem");
    vi.spyOn(Route, "useParams").mockReturnValue({ id: recipe.id });
    const detail = show(<RecipePage />);
    expect(
      await screen.findByText("Source ingredient quantities correspond to recipe quantity 2."),
    ).toBeInTheDocument();
    expect(screen.getByText("Recipe quantity 2")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Increase recipe quantity" }));
    expect(await screen.findByText("Recipe quantity 3")).toBeInTheDocument();
    expect((await mock.getRecipe(recipe.id, 3)).lines.map((l) => l.required)).toEqual(
      recipe.lines.map((l) => l.required * 1.5),
    );
    detail.unmount();
    show(<BasketPage />);
    expect(await screen.findByLabelText(`Recipe quantity for ${recipe.title}`)).toHaveValue("2");
    expect(await mock.getBasket()).toEqual(saved);
    expect(update).not.toHaveBeenCalled();
  });

  it("labels the second genuine source recipe as batches and retains the upper bound of eight", async () => {
    setService(service);
    vi.spyOn(Route, "useParams").mockReturnValue({ id: "rec_52776" });
    show(<RecipePage />);
    expect(await screen.findByText("1 batch")).toBeInTheDocument();
    expect(
      screen.getByText("One batch uses the complete source ingredient quantities."),
    ).toBeInTheDocument();
    for (let quantity = 2; quantity <= 8; quantity++) {
      fireEvent.click(screen.getByRole("button", { name: "Increase batches" }));
      expect(await screen.findByText(`${quantity} batches`)).toBeInTheDocument();
    }
    expect(screen.getByRole("button", { name: "Increase batches" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Decrease batches" })).toBeEnabled();
    expect(document.body).not.toHaveTextContent(/servings|serves|portions/i);
  }, 15_000);
});
