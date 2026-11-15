import { spawnSync } from "node:child_process";
import { createServer } from "node:net";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { expect, test, type Page } from "@playwright/test";

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const composeFile = resolve(repoRoot, "compose.yaml");
const docker = process.platform === "win32" ? "docker.exe" : "docker";

type Runtime = {
  project: string;
  envDir: string;
  envFile: string;
  database: string;
  databaseUser: string;
  port: number;
};

let runtime: Runtime | undefined;

function command(args: string[], env?: NodeJS.ProcessEnv): string {
  const result = spawnSync(docker, ["compose", ...args], {
    cwd: repoRoot,
    env,
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
    timeout: 180_000,
    killSignal: "SIGTERM",
    windowsHide: true,
  });
  if (result.status !== 0) {
    throw new Error(`Docker Compose command failed (exit ${result.status ?? "unknown"}).`);
  }
  return `${result.stdout ?? ""}${result.stderr ?? ""}`;
}

function compose(runtimeValue: Runtime, args: string[]): string {
  return command([
    "--env-file",
    runtimeValue.envFile,
    "-p",
    runtimeValue.project,
    "-f",
    composeFile,
    ...args,
  ]);
}

function freePort(): Promise<number> {
  return new Promise((resolvePort, reject) => {
    const server = createServer();
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      if (!address || typeof address === "string") {
        server.close();
        reject(new Error("Could not allocate an isolated browser port."));
        return;
      }
      server.close(() => resolvePort(address.port));
    });
  });
}

async function waitForHealth(port: number): Promise<void> {
  const deadline = Date.now() + 120_000;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(`http://127.0.0.1:${port}/healthz`);
      if (response.ok) return;
    } catch {
      // The production container may still be starting or the port may not be bound yet.
    }
    await new Promise((resolveDelay) => setTimeout(resolveDelay, 1_000));
  }
  throw new Error("The isolated Compose application did not become healthy.");
}

async function startRuntime(): Promise<Runtime> {
  const port = await freePort();
  const suffix = `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 8)}`;
  const value: Runtime = {
    project: `freshfirst-e2e-${suffix}`.toLowerCase(),
    envDir: mkdtempSync(resolve(tmpdir(), "freshfirst-e2e-")),
    envFile: "",
    database: `freshfirst_e2e_${suffix}`,
    databaseUser: `freshfirst_e2e_${suffix}`,
    port,
  };
  value.envFile = resolve(value.envDir, "compose.env");
  const password = `db-${suffix}-password`;
  const secret = `auth-${suffix}-secret-with-enough-entropy`;
  writeFileSync(
    value.envFile,
    [
      `POSTGRES_DB=${value.database}`,
      `POSTGRES_USER=${value.databaseUser}`,
      `POSTGRES_PASSWORD=${password}`,
      `FRESHFIRST_AUTH_SECRET=${secret}`,
      `FRESHFIRST_PORT=${port}`,
      `FRESHFIRST_TRUSTED_ORIGINS=http://127.0.0.1:${port},http://localhost:${port}`,
      "",
    ].join("\n"),
    { encoding: "utf8" },
  );
  compose(value, ["up", "--build", "-d"]);
  await waitForHealth(port);
  return value;
}

async function recreateApp(value: Runtime): Promise<void> {
  compose(value, ["up", "--force-recreate", "-d", "app"]);
  await waitForHealth(value.port);
}

function cleanupRuntime(value: Runtime | undefined): void {
  if (!value) return;
  try {
    compose(value, ["down", "-v", "--remove-orphans"]);
  } finally {
    rmSync(value.envDir, { recursive: true, force: true });
  }
}

async function addPantryItem(page: Page, ingredient: string, quantity: string): Promise<void> {
  await page.getByRole("button", { name: "Add item" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByRole("combobox", { name: "Ingredient", exact: true }).click();
  await page.getByRole("option", { name: ingredient, exact: true }).click();
  await dialog.getByLabel("Quantity").fill(quantity);
  await dialog.getByLabel("Expiry date").fill("2030-12-31");
  await dialog.getByRole("button", { name: "Save" }).click();
  await expect(dialog).toBeHidden();
  await expect(page.getByText(ingredient, { exact: true })).toBeVisible();
}

async function addFreeTextPantryItem(page: Page, label: string, quantity: string): Promise<void> {
  await page.getByRole("button", { name: "Add item" }).click();
  const dialog = page.getByRole("dialog");
  const input = dialog.getByRole("combobox", { name: "Free-text ingredient", exact: true });
  await input.fill(label);
  await expect(dialog.getByRole("option").first()).toBeVisible();
  await input.press("ArrowDown");
  await input.press("Enter");
  await expect(input).toHaveValue(label);
  await expect(dialog.getByRole("button", { name: "Save" })).toBeVisible();
  await expect(page.getByText(label, { exact: true })).toHaveCount(0);
  await dialog.getByLabel("Quantity").fill(quantity);
  await dialog.getByLabel("Expiry date").fill("2030-12-31");
  const createResponse = page.waitForResponse(
    (response) => response.url().endsWith("/pantry") && response.request().method() === "POST",
  );
  await dialog.getByRole("button", { name: "Save" }).click();
  const created = await createResponse;
  const pantryItem = (await created.json()) as {
    ingredient_id: string;
    original_label: string | null;
  };
  expect(pantryItem.ingredient_id).toBe("milk");
  expect(pantryItem.original_label).toBe(label);
  await expect(dialog).toBeHidden();
  await expect(page.getByText("Milk", { exact: true })).toBeVisible();
}

async function goto(page: Page, path: string): Promise<void> {
  await page.goto(`http://127.0.0.1:${runtime!.port}${path}`);
}

async function registerUser(page: Page): Promise<{ email: string; password: string }> {
  const credentials = {
    email: `e2e-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`,
    password: `E2E-${Date.now()}-long-password`,
  };
  await goto(page, "/register");
  await page.getByLabel("Email").fill(credentials.email);
  await page.getByLabel("Password").fill(credentials.password);
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/$/);
  return credentials;
}

async function openKnownRecipe(page: Page): Promise<void> {
  await goto(page, "/recipes");
  await page.getByPlaceholder("Search recipes…").fill("Spaghetti with Spanish flavours");
  await page.getByRole("link", { name: /Spaghetti with Spanish flavours/ }).click();
  await expect(
    page.getByRole("heading", { name: "Spaghetti with Spanish flavours" }),
  ).toBeVisible();
}

test.beforeAll(async () => {
  runtime = await startRuntime();
  if (process.env.FRESHFIRST_E2E_FORCE_FAILURE === "1") {
    throw new Error("Forced cleanup probe failure.");
  }
});

test.afterAll(() => {
  cleanupRuntime(runtime);
});

test.beforeEach(() => {
  if (!runtime) throw new Error("The isolated Compose application is not running.");
  compose(runtime, [
    "exec",
    "-T",
    "db",
    "psql",
    "-U",
    runtime.databaseUser,
    "-d",
    runtime.database,
    "-c",
    "TRUNCATE TABLE auth_rate_limits",
  ]);
});

test("runs the real browser journey against production Compose and survives app recreation", async ({
  page,
}) => {
  const email = `e2e-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`;
  const password = `E2E-${Date.now()}-long-password`;

  await goto(page, "/register");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByText(email, { exact: true })).toBeVisible();

  await page.reload();
  await expect(page.getByText(email, { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Good to see you" })).toBeVisible();

  await page.getByRole("link", { name: "Pantry", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Pantry" })).toBeVisible();
  await addPantryItem(page, "Chorizo", "100");
  await addPantryItem(page, "Pasta", "400");
  await addPantryItem(page, "Parsley", "30");
  await addPantryItem(page, "Bell pepper", "2");
  await addPantryItem(page, "Olive oil", "100");

  await page.getByRole("link", { name: "Recipes", exact: true }).click();
  await page.getByPlaceholder("Search recipes…").fill("Spaghetti with Spanish flavours");
  const recipe = page.getByRole("link", { name: /Spaghetti with Spanish flavours/ });
  await expect(recipe).toBeVisible();
  await recipe.click();
  await expect(
    page.getByRole("heading", { name: "Spaghetti with Spanish flavours" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Add to basket" }).click();

  await page.getByRole("link", { name: "Basket", exact: true }).click();
  await expect(page.getByText("Spaghetti with Spanish flavours", { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "Open shopping list" }).click();
  await page.getByRole("button", { name: "Generate from basket" }).click();
  await expect(page.getByText("Parmesan (generated)", { exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByText("Parmesan (generated)", { exact: true })).toBeVisible();

  await page.getByRole("link", { name: "Pantry", exact: true }).click();
  await addPantryItem(page, "Parmesan", "60");
  await page.getByRole("link", { name: "Basket", exact: true }).click();
  await page.getByRole("button", { name: "I Cooked This" }).click();
  const cookDialog = page.getByRole("dialog");
  await expect(cookDialog.getByRole("button", { name: "Confirm & deduct" })).toBeEnabled();
  await cookDialog.getByRole("button", { name: "Confirm & deduct" }).click();
  await expect(cookDialog).toBeHidden();

  await page.getByRole("link", { name: "Dashboard", exact: true }).click();
  await page.getByRole("button", { name: "View all cooking history" }).click();
  await expect(page.getByRole("heading", { name: "Cooking history" })).toBeVisible();
  await expect(
    page.locator("#cooking-history-records").getByText("Spaghetti with Spanish flavours", {
      exact: true,
    }),
  ).toBeVisible();

  await page.getByRole("button", { name: "Log out" }).click();
  await expect(page).toHaveURL(/\/login$/);
  await goto(page, "/pantry");
  await expect(page).toHaveURL(/\/login$/);

  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/$/);
  await recreateApp(runtime!);

  await page.reload();
  await expect(page.getByText(email, { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "Basket", exact: true }).click();
  await expect(page.getByText("Spaghetti with Spanish flavours", { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "Dashboard", exact: true }).click();
  await expect(
    page.locator("#cooking-history-records").getByText("Spaghetti with Spanish flavours", {
      exact: true,
    }),
  ).toBeVisible();
});

test("covers pantry lifecycle filters, edit, expiry, and removal", async ({ page }) => {
  await registerUser(page);
  await goto(page, "/pantry");
  await addPantryItem(page, "Chorizo", "100");
  await page.getByRole("button", { name: "Add item" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByRole("combobox", { name: "Ingredient", exact: true }).click();
  await page.getByRole("option", { name: "Pasta", exact: true }).click();
  await dialog.getByLabel("Quantity").fill("400");
  await dialog.getByLabel("Expiry date").fill("2020-01-01");
  await dialog.getByRole("button", { name: "Save" }).click();
  await expect(dialog).toBeHidden();

  await page.getByPlaceholder("Search pantry…").fill("Chorizo");
  await expect(page.getByText("Chorizo", { exact: true })).toBeVisible();
  await expect(page.getByText("Pasta", { exact: true })).toBeHidden();
  await page.getByPlaceholder("Search pantry…").fill("");
  await page.getByRole("combobox", { name: "Expiry status" }).click();
  await page.getByRole("option", { name: "Expired", exact: true }).click();
  await expect(page.getByText("Pasta", { exact: true })).toBeVisible();
  await page.getByRole("combobox", { name: "Expiry status" }).click();
  await page.getByRole("option", { name: "Any status", exact: true }).click();

  await page.getByRole("button", { name: "Edit Chorizo" }).click();
  await page.getByRole("dialog").getByLabel("Quantity").fill("150");
  await page.getByRole("dialog").getByLabel("Expiry date").fill("2031-12-31");
  await page.getByRole("dialog").getByRole("button", { name: "Save" }).click();
  await expect(page.getByText("150 g", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Remove Chorizo" }).click();
  await expect(page.getByText("Chorizo", { exact: true })).toBeHidden();

  await goto(page, "/shopping");
  await page.getByLabel("Name").fill("E2E manual oats");
  await page.getByLabel("Quantity").fill("2");
  await page.getByLabel("Unit").fill("kg");
  await page.getByRole("button", { name: "Add manual item" }).click();
  await expect(page.getByText("E2E manual oats (manual)", { exact: true })).toBeVisible();
  const quantity = page.getByRole("spinbutton", { name: "Quantity for E2E manual oats" });
  await quantity.fill("3");
  await page.getByRole("button", { name: "Save quantity" }).click();
  await expect(quantity).toHaveValue("3");
  const purchased = page.getByRole("checkbox", { name: /E2E manual oats/ });
  await expect(purchased).toBeEnabled();
  await purchased.click();
  await expect(purchased).toBeChecked();
  await page.getByRole("button", { name: "Remove" }).click();
  await expect(page.getByText("E2E manual oats (manual)", { exact: true })).toBeHidden();

  await page.getByLabel("Catalog ingredient").selectOption({ label: "Parmesan" });
  await page.getByLabel("Quantity").fill("60");
  await page.getByRole("button", { name: "Add manual item" }).click();
  await expect(page.getByText("Parmesan (manual)", { exact: true })).toBeVisible();
  const parmesanPurchased = page.getByRole("checkbox", { name: /Parmesan/ });
  await parmesanPurchased.click();
  await expect(parmesanPurchased).toBeChecked();
  await page.getByLabel(/Actual quantity/).fill("60");
  await page.getByLabel("Expiry date").fill("2031-12-31");
  await page.getByRole("button", { name: "Confirm transfer to pantry" }).click();
  await expect(page.getByText("Added to pantry", { exact: true })).toBeVisible();
});

test("supports authenticated free-text autocomplete selection before saving", async ({ page }) => {
  await registerUser(page);
  await goto(page, "/pantry");
  await addFreeTextPantryItem(page, "молоко", "500");
});

test("keeps unknown labels visible and gates typo resolution on confirmation", async ({ page }) => {
  await registerUser(page);
  await goto(page, "/pantry");

  await page.getByRole("button", { name: "Add item" }).click();
  const dialog = page.getByRole("dialog");
  const input = dialog.getByRole("combobox", { name: "Free-text ingredient", exact: true });
  await input.fill("eggsx");
  await dialog.getByLabel("Quantity").fill("2");
  await dialog.getByLabel("Expiry date").fill("2030-12-31");
  await dialog.getByRole("button", { name: "Save" }).click();
  await expect(dialog).toBeHidden();

  const typoLot = page.getByText("eggsx", { exact: true });
  await expect(typoLot).toBeVisible();
  await expect(
    page.getByText("Choose a canonical ingredient to confirm this entry."),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Confirm Eggs" })).toBeVisible();
  await page.getByRole("button", { name: "Confirm Eggs" }).click();
  await expect(page.getByText("Ingredient confirmed", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Add item" }).click();
  const unknownDialog = page.getByRole("dialog");
  await unknownDialog
    .getByRole("combobox", { name: "Free-text ingredient", exact: true })
    .fill("dragonfruit");
  await unknownDialog.getByLabel("Quantity").fill("1");
  await unknownDialog.getByLabel("Expiry date").fill("2030-12-31");
  await unknownDialog.getByRole("button", { name: "Save" }).click();
  await expect(unknownDialog).toBeHidden();
  await expect(page.getByText("dragonfruit", { exact: true })).toBeVisible();
  await expect(page.getByText("This label is not matched to canonical stock.")).toBeVisible();
});

test("covers recipe filters, serving adaptation, and import reporting", async ({ page }) => {
  await registerUser(page);
  await goto(page, "/recipes");
  await page.locator("select").first().selectOption("title");
  await page.getByRole("combobox").filter({ hasText: "All categories" }).click();
  const categories = page.getByRole("option");
  await categories.last().click();
  await expect(page.getByRole("heading", { name: "Recipes" })).toBeVisible();
  await page.getByRole("button", { name: "Re-import recipes" }).click();
  const report = page.getByRole("dialog", { name: "Import report" });
  await expect(report).toBeVisible({ timeout: 60_000 });
  await expect(report.getByLabel("Import report results")).toContainText("recipes total");
  await page.keyboard.press("Escape");

  await openKnownRecipe(page);
  const increase = page.getByRole("button", { name: /Increase/ });
  await expect(increase).toBeVisible();
  await increase.click();
  await expect(page.getByRole("button", { name: "Add to basket" })).toBeVisible();
  await page.getByRole("button", { name: "Add to basket" }).click();
  await page.getByRole("link", { name: "Basket", exact: true }).click();
  const basketTitle = page.getByText("Spaghetti with Spanish flavours", { exact: true });
  await expect(basketTitle).toBeVisible();
  const servings = page.getByRole("combobox", {
    name: /for Spaghetti with Spanish flavours/,
  });
  await servings.selectOption("4");
  await expect(servings).toHaveValue("4");
  await page.getByRole("button", { name: "Remove" }).click();
  await expect(basketTitle).toBeHidden();
  await expect(page.getByText("Your basket is empty")).toBeVisible();
});

test("keeps each account's pantry data isolated in the real browser", async ({ page }) => {
  const first = await registerUser(page);
  await goto(page, "/pantry");
  await addPantryItem(page, "Chorizo", "100");
  await page.getByRole("button", { name: "Log out" }).click();
  await expect(page).toHaveURL(/\/login$/);

  await registerUser(page);
  await goto(page, "/pantry");
  await expect(page.getByText("Chorizo", { exact: true })).toBeHidden();
  await addPantryItem(page, "Pasta", "400");
  await page.getByRole("button", { name: "Log out" }).click();
  await expect(page).toHaveURL(/\/login$/);

  await goto(page, "/login");
  await page.getByLabel("Email").fill(first.email);
  await page.getByLabel("Password").fill(first.password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/$/);
  await goto(page, "/pantry");
  await expect(page.getByText("Chorizo", { exact: true })).toBeVisible();
  await expect(page.getByText("Pasta", { exact: true })).toBeHidden();
});

test("combines authenticated expanded-catalog filters with truthful loading, empty and error states", async ({
  page,
}) => {
  await registerUser(page);
  await goto(page, "/recipes");
  await page.getByLabel("Sort recipes").selectOption("title");
  await page.getByPlaceholder("Search recipes…").fill("salmon");
  await page.getByRole("combobox").filter({ hasText: "All categories" }).click();
  await page.getByRole("option", { name: "Seafood", exact: true }).click();
  const cards = page.locator('a[href^="/recipes/rec_"]');
  const seafood = [4, 13, 24, 33, 44, 64, 73].map(
    (id) => `/recipes/rec_ff-original-${String(id).padStart(3, "0")}`,
  );
  await expect(cards).toHaveCount(seafood.length);
  const firstOrder = await cards.evaluateAll((links) =>
    links.map((link) => link.getAttribute("href")),
  );
  expect([...firstOrder].sort()).toEqual([...seafood].sort());
  const titles = await cards.locator("p.font-display").allTextContents();
  expect(titles).toEqual([...titles].sort((a, b) => a.localeCompare(b)));

  // Combined filter must remain AND, rather than finding the dessert in Seafood.
  await page.getByPlaceholder("Search recipes…").fill("Butter vanilla loaf");
  await expect(page.getByText("No recipes found", { exact: true })).toBeVisible();
  await expect(cards).toHaveCount(0);
  await page.getByRole("combobox").filter({ hasText: "Seafood" }).click();
  await page.getByRole("option", { name: "Dessert", exact: true }).click();
  await expect(cards).toHaveCount(1);
  await expect(cards.first()).toHaveAttribute("href", "/recipes/rec_ff-original-009");

  let release!: () => void;
  const gate = new Promise<void>((resolveGate) => {
    release = resolveGate;
  });
  const handler = async (route: import("@playwright/test").Route) => {
    if (new URL(route.request().url()).searchParams.get("query") !== "catalog-error-probe") {
      await route.continue();
      return;
    }
    await gate;
    await route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({
        code: "CATALOG_UNAVAILABLE",
        message: "Catalog verification temporarily unavailable",
      }),
    });
  };
  await page.route("**/api/recipes?**", handler);
  await page.getByPlaceholder("Search recipes…").fill("catalog-error-probe");
  await expect(page.getByText("Loading…", { exact: true })).toBeVisible();
  await expect(cards).toHaveCount(0);
  release();
  await expect(
    page.getByText("Catalog verification temporarily unavailable", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText("No recipes found", { exact: true })).toBeHidden();
  await expect(cards).toHaveCount(0);
  await page.unroute("**/api/recipes?**", handler);
  await page.getByPlaceholder("Search recipes…").fill("Butter vanilla loaf");
  await expect(cards).toHaveCount(1);
});

test("cooks an expanded-catalog recipe through scaled basket, edited purchase, retry and restart", async ({
  page,
  browser,
}) => {
  const account = await registerUser(page);
  await goto(page, "/pantry");
  await addPantryItem(page, "Eggs", "8");
  await addPantryItem(page, "Spinach", "200");
  await addPantryItem(page, "Cheddar cheese", "80");
  await addPantryItem(page, "Butter", "20");
  await goto(page, "/recipes");
  await page.getByPlaceholder("Search recipes…").fill("Spinach and cheddar omelet");
  const omelet = page.locator('a[href="/recipes/rec_ff-original-001"]');
  await expect(omelet).toContainText("4/5 ingredients covered");
  await omelet.click();
  await expect(
    page.getByRole("heading", { name: "Spinach and cheddar omelet", exact: true }),
  ).toBeVisible();
  await expect(page.getByText(/One batch makes 2 portions/)).toBeVisible();
  const eggLine = page.locator("li").filter({ has: page.getByText("Eggs", { exact: true }) });
  await expect(eggLine).toContainText("4 pcs");
  await page.getByRole("button", { name: "Increase batches" }).click();
  await expect(eggLine).toContainText("8 pcs");
  await expect(
    page.locator("li").filter({ has: page.getByText("Spinach", { exact: true }) }),
  ).toContainText("200 g");
  await page.getByRole("button", { name: "Add to basket" }).click();
  await goto(page, "/basket");
  const scale = page.getByRole("combobox", { name: /for Spinach and cheddar omelet/ });
  await expect(scale).toHaveValue("2");
  await page.reload();
  await expect(scale).toHaveValue("2");
  await page.getByRole("link", { name: "Open shopping list" }).click();
  await page.getByRole("button", { name: "Generate from basket" }).click();
  const salt = page.locator("li").filter({ hasText: "Salt (generated)" });
  await expect(salt.getByLabel("Quantity for Salt")).toHaveValue("2");
  await salt.getByLabel("Quantity for Salt").fill("3");
  await salt.getByRole("button", { name: "Save quantity" }).click();
  await expect(salt.getByLabel("Quantity for Salt")).toHaveValue("3");
  await salt.getByRole("checkbox").check();
  await salt.getByLabel("Actual quantity (ml)").fill("3");
  await salt.getByLabel("Expiry date").fill("2030-12-31");
  const transferResponse = page.waitForResponse(
    (response) =>
      response.url().includes("/transfer-to-pantry") && response.request().method() === "POST",
  );
  await salt.getByRole("button", { name: "Confirm transfer to pantry" }).click();
  const transferred = await transferResponse;
  expect(transferred.status()).toBe(200);
  await expect(salt.getByText("Added to pantry", { exact: true })).toBeVisible();

  // A replay with the same authenticated request must not add another 3 ml.
  const origin = `http://127.0.0.1:${runtime!.port}`;
  const session = await (await page.request.get(`${origin}/api/auth/session`)).json();
  const replay = await page.request.post(transferred.url(), {
    data: { quantity: 3, expiry_date: "2030-12-31" },
    headers: { Origin: origin, "X-CSRF-Token": session.csrf_token },
  });
  expect(replay.status()).toBe(200);
  const pantryBefore = await (await page.request.get(`${origin}/api/pantry`)).json();
  expect(
    pantryBefore
      .filter((item: { ingredient_id: string }) => item.ingredient_id === "salt")
      .reduce((sum: number, item: { quantity: number }) => sum + item.quantity, 0),
  ).toBe(3);

  await goto(page, "/basket");
  await page.getByRole("button", { name: "I Cooked This" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("button", { name: "Confirm & deduct" })).toBeEnabled();
  await dialog.getByRole("button", { name: "Confirm & deduct" }).click();
  await expect(dialog).toBeHidden();
  let history = await (await page.request.get(`${origin}/api/cooking/history`)).json();
  expect(history).toHaveLength(1);
  expect(history[0]).toMatchObject({ recipe_id: "rec_ff-original-001", servings: 2 });
  expect(
    history[0].consumed.find((line: { ingredient_id: string }) => line.ingredient_id === "egg")
      .quantity,
  ).toBe(8);
  await goto(page, "/");
  await expect(
    page
      .locator("#cooking-history-records")
      .getByText("Spinach and cheddar omelet", { exact: true }),
  ).toBeVisible();
  await recreateApp(runtime!);
  await page.reload();
  await expect(page.getByText(account.email, { exact: true })).toBeVisible();
  history = await (await page.request.get(`${origin}/api/cooking/history`)).json();
  expect(history).toHaveLength(1);
  await goto(page, "/basket");
  await expect(scale).toHaveValue("2");

  const otherContext = await browser.newContext();
  try {
    const other = await otherContext.newPage();
    await registerUser(other);
    await goto(other, "/recipes");
    await other.getByPlaceholder("Search recipes…").fill("Spinach and cheddar omelet");
    await expect(other.locator('a[href="/recipes/rec_ff-original-001"]')).toContainText(
      "0/5 ingredients covered",
    );
    const otherHistory = await (await other.request.get(`${origin}/api/cooking/history`)).json();
    expect(otherHistory).toEqual([]);
    const otherBasket = await (await other.request.get(`${origin}/api/basket`)).json();
    expect(otherBasket.items).toEqual([]);
  } finally {
    await otherContext.close();
  }
});
