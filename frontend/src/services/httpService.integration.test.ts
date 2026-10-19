// @vitest-environment node
import { spawn, type ChildProcess } from "node:child_process";
import { once } from "node:events";
import { createServer } from "node:net";
import { resolve } from "node:path";
import { beforeAll, afterAll, describe, expect, it } from "vitest";
import { createHttpService } from "./httpService";
import type { FreshService } from "./types";

let process: ChildProcess;
let service: FreshService;
let base: string;
beforeAll(async () => {
  const socket = createServer();
  socket.listen(0, "127.0.0.1");
  await once(socket, "listening");
  const port = (socket.address() as { port: number }).port;
  await new Promise<void>((done) => socket.close(() => done()));
  base = `http://127.0.0.1:${port}/api`;
  const backend = resolve("../backend");
  const python =
    globalThis.process.env["FRESHFIRST_TEST_PYTHON"] ||
    resolve(
      backend,
      globalThis.process.platform === "win32" ? ".venv/Scripts/python.exe" : ".venv/bin/python",
    );
  process = spawn(python, ["tests/http_server.py", String(port)], { cwd: backend, stdio: "pipe" });
  let output = "";
  process.stderr?.on("data", (data) => {
    output += data;
  });
  process.on("error", (error) => {
    output += error.message;
  });
  service = createHttpService(base);
  for (let attempt = 0; attempt < 100; attempt++) {
    try {
      await service.listIngredients();
      return;
    } catch {
      await new Promise((done) => setTimeout(done, 100));
    }
  }
  throw new Error(`Integration backend did not start: ${output}`);
}, 20000);
afterAll(async () => {
  if (process && process.exitCode === null) {
    const exited = once(process, "exit");
    process.kill();
    await exited;
  }
});

describe("real HTTP frontend to FastAPI integration", () => {
  it("completes pantry, recipes, basket, shopping, purchase, cooking and history journeys", async () => {
    const expiry_date = "2026-11-01";
    expect((await service.listIngredients()).length).toBeGreaterThan(20);
    expect((await service.listSubstitutionRules()).length).toBeGreaterThan(0);
    await expect(
      service.createPantryItem({ ingredient_id: "pasta", quantity: -1, unit: "g", expiry_date }),
    ).rejects.toMatchObject({ status: 422, code: "VALIDATION_ERROR" });
    const pasta = await service.createPantryItem({
      ingredient_id: "pasta",
      quantity: 0.3,
      unit: "kg",
      expiry_date,
    });
    expect(pasta.quantity).toBe(300);
    await service.updatePantryItem(pasta.id, {
      ingredient_id: "pasta",
      quantity: 250,
      unit: "g",
      expiry_date,
    });
    const temporary = await service.createPantryItem({
      ingredient_id: "egg",
      quantity: 1,
      unit: "pcs",
      expiry_date,
    });
    await service.deletePantryItem(temporary.id);
    expect((await service.listPantry()).some((item) => item.id === temporary.id)).toBe(false);
    await service.createPantryItem({
      ingredient_id: "milk",
      quantity: 999,
      unit: "ml",
      expiry_date: "2026-10-19",
    });
    await service.createPantryItem({
      ingredient_id: "cream",
      quantity: 300,
      unit: "ml",
      expiry_date,
    });
    const report = await service.importRecipes();
    expect(report.total_recipes).toBe(1);
    expect(report.imported).toBe(0);
    const recipes = await service.listRecipes({
      query: "Integration pasta",
      category: "Pasta",
      sort: "title",
    });
    expect(recipes).toHaveLength(1);
    const recipe = recipes[0]!;
    const detail = await service.getRecipe(recipe.id, 2);
    expect(detail.lines.find((line) => line.ingredient_id === "pasta")?.required).toBe(200);
    expect(detail.lines.find((line) => line.ingredient_id === "milk")?.available).toBe(0);
    const suggestion = detail.suggestions.find(
      (item) => item.rule.original_ingredient_id === "milk",
    )!;
    expect(suggestion).toBeDefined();
    const substitutions = [
      {
        rule_id: suggestion.rule.id,
        original_ingredient_id: "milk",
        substitute_ingredient_id: "cream",
      },
    ];
    const scaled = await service.getRecipe(recipe.id, 2, substitutions);
    expect(scaled.lines.find((line) => line.ingredient_id === "cream")?.required).toBe(200);
    const basket = await service.addToBasket(recipe.id, 1);
    await service.addToBasket(recipe.id, 2);
    expect((await service.getBasket()).items).toHaveLength(1);
    await service.updateBasketItem(basket.id, { servings: 2, substitutions });
    expect(
      (await service.getBasket()).totals.find((line) => line.ingredient_id === "cream")?.required,
    ).toBe(200);
    const generated = await service.generateShoppingList();
    const butter = generated.find((item) => item.ingredient_id === "butter")!;
    expect(butter.quantity).toBe(20);
    const manual = await service.addShoppingItem({
      label: "Paper towels",
      quantity: 1,
      unit: "pcs",
    });
    await service.updateShoppingItem(butter.id, { quantity: 30 });
    await expect(service.generateShoppingList()).rejects.toMatchObject({
      code: "EDITS_WOULD_BE_LOST",
    });
    expect(
      (await service.generateShoppingList({ force: true })).some((item) => item.id === manual.id),
    ).toBe(true);
    await service.removeShoppingItem(manual.id);
    const purchase = (await service.getShoppingList()).find(
      (item) => item.ingredient_id === "butter",
    )!;
    await expect(
      service.transferToPantry(purchase.id, { quantity: 20, expiry_date }),
    ).rejects.toMatchObject({ code: "NOT_PURCHASED" });
    const request = { recipe_id: recipe.id, servings: 2, substitutions };
    expect((await service.previewCook(request)).can_cook).toBe(false);
    await expect(service.confirmCook(request)).rejects.toMatchObject({
      code: "INSUFFICIENT_STOCK",
    });
    expect(await service.listHistory()).toHaveLength(0);
    await service.updateShoppingItem(purchase.id, { purchased: true });
    await service.transferToPantry(purchase.id, { quantity: 20, expiry_date });
    await service.transferToPantry(purchase.id, { quantity: 20, expiry_date });
    expect(
      (await service.listPantry()).find((item) => item.ingredient_id === "butter")?.quantity,
    ).toBe(20);
    expect((await service.previewCook(request)).can_cook).toBe(true);
    const record = await service.confirmCook(request);
    expect((await service.listHistory())[0]!.id).toBe(record.id);
    expect((await service.getDashboard()).recent_history[0]!.id).toBe(record.id);
    expect(
      (await service.listPantry()).find((item) => item.ingredient_id === "pasta")?.quantity,
    ).toBe(50);
    await service.removeBasketItem(basket.id);
    expect((await service.getBasket()).items).toHaveLength(0);
  });

  it("allows Vite preflight and actual responses, rejecting other origins", async () => {
    const response = await fetch(`${base}/pantry`, {
      method: "OPTIONS",
      headers: {
        Origin: "http://localhost:5173",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
      },
    });
    expect(response.status).toBe(200);
    expect(response.headers.get("access-control-allow-origin")).toBe("http://localhost:5173");
    const actual = await fetch(`${base}/pantry`, { headers: { Origin: "http://127.0.0.1:5173" } });
    expect(actual.headers.get("access-control-allow-origin")).toBe("http://127.0.0.1:5173");
    const denied = await fetch(`${base}/pantry`, {
      method: "OPTIONS",
      headers: {
        Origin: "http://other.example",
        "Access-Control-Request-Method": "POST",
      },
    });
    expect(denied.status).toBe(400);
    expect(denied.headers.get("access-control-allow-origin")).toBeNull();
  });
});
