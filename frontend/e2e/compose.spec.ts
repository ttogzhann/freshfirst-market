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
    port,
  };
  value.envFile = resolve(value.envDir, "compose.env");
  const password = `db-${suffix}-password`;
  const secret = `auth-${suffix}-secret-with-enough-entropy`;
  writeFileSync(
    value.envFile,
    [
      `POSTGRES_DB=freshfirst_e2e_${suffix}`,
      `POSTGRES_USER=freshfirst_e2e_${suffix}`,
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
  await dialog.getByRole("combobox", { name: "Ingredient" }).click();
  await page.getByRole("option", { name: ingredient, exact: true }).click();
  await dialog.getByLabel("Quantity").fill(quantity);
  await dialog.getByLabel("Expiry date").fill("2030-12-31");
  await dialog.getByRole("button", { name: "Save" }).click();
  await expect(dialog).toBeHidden();
  await expect(page.getByText(ingredient, { exact: true })).toBeVisible();
}

async function goto(page: Page, path: string): Promise<void> {
  await page.goto(`http://127.0.0.1:${runtime!.port}${path}`);
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
