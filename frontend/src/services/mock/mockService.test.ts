import { describe, expect, it } from "vitest";
import { createMockService, memoryStorage } from "./mockService";
import { EXTERNAL_MEALS } from "./seed";
import { ServiceError } from "../types";

const T = "2026-10-19";
const make = (storage = memoryStorage()) =>
  createMockService({ storage, today: () => T, seedPantry: false });

describe("mock service", () => {
  it("deletes pantry, basket and shopping entries and persists successful empty responses", async () => {
    const storage = memoryStorage();
    const s = make(storage);
    const pantry = await s.createPantryItem({
      ingredient_id: "egg",
      quantity: 2,
      unit: "pcs",
      expiry_date: "2026-11-01",
    });
    const basket = await s.addToBasket("rec_52982", 2);
    const shopping = await s.addShoppingItem({ label: "Eggs", quantity: 2, unit: "pcs" });
    await expect(s.deletePantryItem(pantry.id)).resolves.toBeUndefined();
    await expect(s.removeBasketItem(basket.id)).resolves.toBeUndefined();
    await expect(s.removeShoppingItem(shopping.id)).resolves.toBeUndefined();
    const restarted = make(storage);
    expect(await restarted.listPantry()).toEqual([]);
    expect((await restarted.getBasket()).items).toEqual([]);
    expect(await restarted.getShoppingList()).toEqual([]);
  });

  it("supports title sorting and rejects nonfinite quantities and blank units", async () => {
    const s = make();
    const titles = (await s.listRecipes({ sort: "title" })).map((r) => r.title);
    expect(titles).toEqual([...titles].sort((a, b) => a.localeCompare(b)));
    await expect(
      s.addShoppingItem({ label: "Eggs", quantity: Infinity, unit: "pcs" }),
    ).rejects.toMatchObject({ status: 422 });
    await expect(
      s.addShoppingItem({ label: "Eggs", quantity: 1, unit: " " }),
    ).rejects.toMatchObject({ status: 422 });
  });
  it("persists pantry across restart", async () => {
    const storage = memoryStorage();
    await make(storage).createPantryItem({
      ingredient_id: "egg",
      quantity: 6,
      unit: "pcs",
      expiry_date: "2026-10-30",
    });
    const pantry = await make(storage).listPantry();
    expect(pantry).toHaveLength(1);
  });

  it("validates pantry input", async () => {
    const s = make();
    await expect(
      s.createPantryItem({
        ingredient_id: "egg",
        quantity: 0,
        unit: "pcs",
        expiry_date: "2026-10-30",
      }),
    ).rejects.toMatchObject({ status: 422 });
    await expect(
      s.createPantryItem({
        ingredient_id: "milk",
        quantity: 1,
        unit: "kg",
        expiry_date: "2026-10-30",
      }),
    ).rejects.toMatchObject({ status: 422 });
  });

  it("merges same-expiry entries and rejects different expiry", async () => {
    const s = make();
    await s.createPantryItem({
      ingredient_id: "flour",
      quantity: 1,
      unit: "kg",
      expiry_date: "2026-12-01",
    });
    await s.createPantryItem({
      ingredient_id: "flour",
      quantity: 500,
      unit: "g",
      expiry_date: "2026-12-01",
    });
    expect((await s.listPantry())[0]!.quantity).toBe(1500);
    await expect(
      s.createPantryItem({
        ingredient_id: "flour",
        quantity: 1,
        unit: "g",
        expiry_date: "2026-12-02",
      }),
    ).rejects.toMatchObject({ code: "EXPIRY_CONFLICT" });
  });

  it("imports 15–20 recipes, skips unsupported, no duplicates on re-import", async () => {
    const s = make();
    const before = (await s.listRecipes()).length;
    expect(before).toBeGreaterThanOrEqual(15);
    expect(before).toBeLessThanOrEqual(20);
    const report = await s.importRecipes();
    expect(report.imported).toBe(0);
    expect(report.updated).toBe(before);
    expect(report.skipped.length).toBeGreaterThan(0);
    expect((await s.listRecipes()).length).toBe(before);
    const ids = (await s.listRecipes()).map((r) => r.external_id);
    expect(new Set(ids).size).toBe(ids.length);
    expect(report.skipped.map((x) => x.title)).toContain("Grandma's Biscuits");
  });

  it("basket avoids duplicates and persists", async () => {
    const storage = memoryStorage();
    const s = make(storage);
    await s.addToBasket("rec_52982", 2);
    await s.addToBasket("rec_52982", 4);
    const b = await make(storage).getBasket();
    expect(b.items).toHaveLength(1);
    expect(b.items[0]!.servings).toBe(4);
  });

  it("rejects servings outside 1–8", async () => {
    await expect(make().addToBasket("rec_52982", 9)).rejects.toBeInstanceOf(ServiceError);
  });

  it("shopping aggregates shared ingredients, deducts stock once, ignores expired", async () => {
    const s = make();
    await s.createPantryItem({
      ingredient_id: "pasta",
      quantity: 0.25,
      unit: "kg",
      expiry_date: "2027-01-01",
    });
    await s.createPantryItem({
      ingredient_id: "parmesan",
      quantity: 500,
      unit: "g",
      expiry_date: "2026-10-01",
    }); // expired
    await s.addToBasket("rec_52982", 2); // carbonara: 200g pasta, 50g parmesan
    await s.addToBasket("rec_52940", 2); // mushroom pasta: 200g pasta, 30g parmesan
    const list = await s.generateShoppingList();
    expect(list.find((i) => i.ingredient_id === "pasta")?.quantity).toBe(150);
    expect(list.find((i) => i.ingredient_id === "parmesan")?.quantity).toBe(80);
  });

  it("warns before regeneration overwrites edits and keeps manual items", async () => {
    const s = make();
    await s.addToBasket("rec_52982", 2);
    const list = await s.generateShoppingList();
    await s.addShoppingItem({ label: "Paper towels", quantity: 1, unit: "pcs" });
    await s.updateShoppingItem(list[0]!.id, { quantity: 999 });
    await expect(s.generateShoppingList()).rejects.toMatchObject({ code: "EDITS_WOULD_BE_LOST" });
    const regen = await s.generateShoppingList({ force: true });
    expect(regen.some((i) => i.label === "Paper towels")).toBe(true);
    expect(regen.some((i) => i.quantity === 999)).toBe(false);
  });

  it("transfers a purchased item to pantry exactly once", async () => {
    const s = make();
    const item = await s.addShoppingItem({ label: "Eggs", quantity: 6, unit: "pcs" });
    await expect(
      s.transferToPantry(item.id, { quantity: 6, expiry_date: "2026-11-01" }),
    ).rejects.toMatchObject({ code: "NOT_PURCHASED" });
    await s.updateShoppingItem(item.id, { purchased: true });
    await s.transferToPantry(item.id, { quantity: 6, expiry_date: "2026-11-01" });
    await s.transferToPantry(item.id, { quantity: 6, expiry_date: "2026-11-01" });
    const pantry = await s.listPantry();
    expect(pantry.find((p) => p.ingredient_id === "egg")?.quantity).toBe(6);
  });

  it("protects removed generated lines on regeneration across restart", async () => {
    const storage = memoryStorage();
    const s = make(storage);
    await s.addToBasket("rec_52982", 2);
    const list = await s.generateShoppingList();
    await s.removeShoppingItem(list[0]!.id);
    await expect(make(storage).generateShoppingList()).rejects.toMatchObject({
      code: "EDITS_WOULD_BE_LOST",
    });
    await expect(make(storage).generateShoppingList({ force: true })).resolves.toHaveLength(
      list.length,
    );
  });

  it("requires editing existing pantry expiry before merging a purchase", async () => {
    const s = make();
    await s.createPantryItem({
      ingredient_id: "egg",
      quantity: 2,
      unit: "pcs",
      expiry_date: "2026-10-01",
    });
    const item = await s.addShoppingItem({ label: "Eggs", quantity: 6, unit: "pcs" });
    await s.updateShoppingItem(item.id, { purchased: true });
    await expect(
      s.transferToPantry(item.id, { quantity: 6, expiry_date: "2026-11-01" }),
    ).rejects.toMatchObject({ code: "EXPIRY_CONFLICT" });
    expect((await s.listPantry())[0]!.quantity).toBe(2);
    expect((await s.getShoppingList())[0]!.transferred_to_pantry).toBe(false);
  });

  it("insufficient cooking leaves pantry and history unchanged", async () => {
    const s = make();
    await s.createPantryItem({
      ingredient_id: "egg",
      quantity: 1,
      unit: "pcs",
      expiry_date: "2026-11-01",
    });
    const req = { recipe_id: "rec_52906", servings: 1, substitutions: [] };
    expect((await s.previewCook(req)).can_cook).toBe(false);
    await expect(s.confirmCook(req)).rejects.toMatchObject({ code: "INSUFFICIENT_STOCK" });
    expect((await s.listPantry())[0]!.quantity).toBe(1);
    expect(await s.listHistory()).toHaveLength(0);
  });

  it("valid cooking deducts stock and records history", async () => {
    const s = make();
    for (const [id, q, u] of [
      ["egg", 5, "pcs"],
      ["spinach", 100, "g"],
      ["cheese", 30, "g"],
      ["butter", 50, "g"],
    ] as const)
      await s.createPantryItem({
        ingredient_id: id,
        quantity: q,
        unit: u,
        expiry_date: "2026-11-01",
      });
    await s.confirmCook({ recipe_id: "rec_52906", servings: 1, substitutions: [] });
    const pantry = await s.listPantry();
    expect(pantry.find((p) => p.ingredient_id === "egg")?.quantity).toBe(2);
    expect(pantry.find((p) => p.ingredient_id === "cheese")).toBeUndefined();
    expect(await s.listHistory()).toHaveLength(1);
  });

  it("uses confirmed substitutions in cooking", async () => {
    const s = make();
    for (const [id, q, u] of [
      ["egg", 3, "pcs"],
      ["mushroom", 50, "g"],
      ["cheese", 30, "g"],
      ["butter", 10, "g"],
    ] as const)
      await s.createPantryItem({
        ingredient_id: id,
        quantity: q,
        unit: u,
        expiry_date: "2026-11-01",
      });
    const detail = await s.getRecipe("rec_52906", 1);
    const sug = detail.suggestions.find((x) => x.rule.id === "r8")!;
    expect(detail.match.score).toBe(75);
    const subs = [
      {
        rule_id: sug.rule.id,
        original_ingredient_id: "spinach",
        substitute_ingredient_id: "mushroom",
      },
    ];
    expect(
      (await s.previewCook({ recipe_id: "rec_52906", servings: 1, substitutions: subs })).can_cook,
    ).toBe(true);
  });

  it("skips meals with unknown ingredients when importing", async () => {
    const s = createMockService({
      storage: memoryStorage(),
      today: () => T,
      externalMeals: EXTERNAL_MEALS.slice(0, 4),
    });
    expect(await s.listRecipes()).toHaveLength(0);
    const report = await s.importRecipes();
    expect(report.skipped).toHaveLength(4);
  });
});
