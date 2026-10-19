import { describe, expect, it } from "vitest";
import * as D from "./domain";
import { CATALOG, SUBSTITUTION_RULES } from "./mock/seed";
import type { PantryItem, Recipe } from "./types";

const T = "2026-10-19";
const ings = new Map(CATALOG.map((i) => [i.id, i]));
const recipe: Recipe = {
  id: "r", external_id: "x", title: "Test", category: "C", instructions: "", image_url: "", base_servings: 2,
  ingredients: [
    { ingredient_id: "egg", quantity: 2 },
    { ingredient_id: "milk", quantity: 200 },
    { ingredient_id: "cream", quantity: 100 },
  ],
};
const p = (ingredient_id: string, quantity: number, expiry_date: string): PantryItem => ({ id: ingredient_id, ingredient_id, quantity, expiry_date });

describe("units", () => {
  it("converts kg→g and l→ml", () => {
    expect(D.toCanonical(1.5, "kg", "g")).toBe(1500);
    expect(D.toCanonical(0.25, "l", "ml")).toBe(250);
    expect(D.toCanonical(2, "tbsp", "ml")).toBe(30);
  });
  it("rejects mass↔volume", () => {
    expect(D.toCanonical(1, "kg", "ml")).toBeNull();
  });
  it("never guesses ambiguous measures", () => {
    expect(D.parseMeasure("pinch", "g")).toBeNull();
    expect(D.parseMeasure("2 cups", "g")).toBeNull();
    expect(D.parseMeasure("1kg", "g")).toBe(1000);
    expect(D.parseMeasure("3", "pcs")).toBe(3);
  });
});

describe("expiry", () => {
  it("classifies with a 3 day threshold", () => {
    expect(D.expiryStatus("2026-10-18", T)).toBe("expired");
    expect(D.expiryStatus("2026-10-22", T)).toBe("expiring");
    expect(D.expiryStatus("2026-10-23", T)).toBe("fresh");
  });
  it("treats expired stock as zero available", () => {
    const s = D.usableStock([p("milk", 500, "2026-10-18"), p("egg", 6, "2026-10-30")], T);
    expect(s.get("milk")).toBeUndefined();
    expect(s.get("egg")).toBe(6);
  });
  it("validates calendar dates", () => {
    expect(D.isValidDate("2026-02-30")).toBe(false);
    expect(D.isValidDate("2026-02-28")).toBe(true);
  });
});

describe("matching & ranking", () => {
  it("computes covered lines / total, rounded", () => {
    const m = D.computeMatch(recipe, [p("egg", 6, "2026-10-30"), p("milk", 500, "2026-10-30")], T, ings);
    expect(m.score).toBe(67);
    expect(m.missing).toEqual(["Heavy cream"]);
  });
  it("excludes expired stock from matching", () => {
    const m = D.computeMatch(recipe, [p("egg", 6, "2026-10-01")], T, ings);
    expect(m.covered).toBe(0);
  });
  it("uses expiry urgency as tie-breaker", () => {
    const base = { score: 50, covered: 1, total: 2, missing: [] };
    const ranked = D.rankRecipes([
      { title: "A", match: { ...base, expiring_used: [] } },
      { title: "B", match: { ...base, expiring_used: ["Eggs"] } },
    ]);
    expect(ranked[0].title).toBe("B");
  });
});

describe("scaling & substitutions", () => {
  it("scales all demands by servings/base", () => {
    const d = D.recipeDemands(recipe, 4, [], SUBSTITUTION_RULES);
    expect(d.map((x) => x.quantity)).toEqual([4, 400, 200]);
  });
  it("applies only confirmed substitutions with the rule ratio", () => {
    const d = D.recipeDemands(recipe, 2, [{ rule_id: "r1", original_ingredient_id: "cream", substitute_ingredient_id: "milk" }], SUBSTITUTION_RULES);
    expect(d[2]).toEqual({ ingredient_id: "milk", quantity: 100, substituted_from: "cream" });
  });
  it("suggests substitutes only with enough non-expired stock", () => {
    const stock = new Map([["milk", 50]]);
    const lines = D.toLines(D.recipeDemands(recipe, 2, [], SUBSTITUTION_RULES), stock, ings);
    expect(D.suggestSubstitutions(lines, SUBSTITUTION_RULES, stock, ings).find((s) => s.rule.id === "r1")).toBeUndefined();
    const stock2 = new Map([["milk", 500]]);
    const lines2 = D.toLines(D.recipeDemands(recipe, 2, [], SUBSTITUTION_RULES), stock2, ings);
    expect(D.suggestSubstitutions(lines2, SUBSTITUTION_RULES, stock2, ings).map((s) => s.rule.id)).toContain("r1");
  });
});

describe("shopping", () => {
  it("aggregates and deducts stock once", () => {
    const totals = D.aggregate([
      { ingredient_id: "milk", quantity: 300 },
      { ingredient_id: "milk", quantity: 400 },
      { ingredient_id: "egg", quantity: 2 },
    ]);
    const out = D.computeShopping(totals, new Map([["milk", 500], ["egg", 6]]));
    expect(out.get("milk")).toBe(200);
    expect(out.has("egg")).toBe(false);
  });
});
