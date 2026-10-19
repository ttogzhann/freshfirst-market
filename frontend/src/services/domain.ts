// Pure computations shared by the mock service (and mirrored later by the backend).
import type {
  CanonicalUnit,
  ConfirmedSubstitution,
  DemandLine,
  ExpiryStatus,
  Ingredient,
  InputUnit,
  MatchInfo,
  PantryItem,
  Recipe,
  SubstitutionRule,
  SubstitutionSuggestion,
} from "./types";

export const EXPIRY_THRESHOLD_DAYS = 3;
export const MIN_SERVINGS = 1;
export const MAX_SERVINGS = 8;

const UNIT_FACTORS: Record<InputUnit, { canonical: CanonicalUnit; factor: number }> = {
  g: { canonical: "g", factor: 1 },
  kg: { canonical: "g", factor: 1000 },
  ml: { canonical: "ml", factor: 1 },
  l: { canonical: "ml", factor: 1000 },
  tsp: { canonical: "ml", factor: 5 },
  tbsp: { canonical: "ml", factor: 15 },
  pcs: { canonical: "pcs", factor: 1 },
};

export function compatibleUnits(canonical: CanonicalUnit): InputUnit[] {
  return (Object.keys(UNIT_FACTORS) as InputUnit[]).filter(
    (u) => UNIT_FACTORS[u].canonical === canonical,
  );
}

/** Returns canonical quantity, or null when the unit is incompatible. Never guesses. */
export function toCanonical(
  quantity: number,
  unit: InputUnit,
  canonical: CanonicalUnit,
): number | null {
  const f = UNIT_FACTORS[unit];
  if (!f || f.canonical !== canonical) return null;
  return round(quantity * f.factor);
}

export function round(n: number): number {
  return Math.round(n * 100) / 100;
}

export function formatQty(q: number, unit: CanonicalUnit | string): string {
  if (unit === "g" && q >= 1000) return `${round(q / 1000)} kg`;
  if (unit === "ml" && q >= 1000) return `${round(q / 1000)} l`;
  return `${round(q)} ${unit}`;
}

export function isValidDate(s: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(s)) return false;
  const d = new Date(s + "T00:00:00Z");
  return !Number.isNaN(d.getTime()) && d.toISOString().slice(0, 10) === s;
}

export function todayISO(now = new Date()): string {
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, "0");
  const d = String(now.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

export function addDays(iso: string, days: number): string {
  const d = new Date(iso + "T00:00:00Z");
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

export function daysUntil(expiry: string, today: string): number {
  const a = Date.parse(today + "T00:00:00Z");
  const b = Date.parse(expiry + "T00:00:00Z");
  return Math.round((b - a) / 86_400_000);
}

export function expiryStatus(
  expiry: string,
  today: string,
  threshold = EXPIRY_THRESHOLD_DAYS,
): ExpiryStatus {
  const d = daysUntil(expiry, today);
  if (d < 0) return "expired";
  if (d <= threshold) return "expiring";
  return "fresh";
}

/** Usable (non-expired) stock per ingredient. Expired items count as zero. */
export function usableStock(pantry: PantryItem[], today: string): Map<string, number> {
  const m = new Map<string, number>();
  for (const p of pantry) {
    if (expiryStatus(p.expiry_date, today) === "expired") continue;
    m.set(p.ingredient_id, (m.get(p.ingredient_id) ?? 0) + p.quantity);
  }
  return m;
}

export function scale(quantity: number, servings: number, base: number): number {
  return round((quantity * servings) / base);
}

export function validServings(n: number): boolean {
  return Number.isInteger(n) && n >= MIN_SERVINGS && n <= MAX_SERVINGS;
}

/** Recipe demands at requested servings, with confirmed substitutions applied. */
export function recipeDemands(
  recipe: Recipe,
  servings: number,
  substitutions: ConfirmedSubstitution[],
  rules: SubstitutionRule[],
): { ingredient_id: string; quantity: number; substituted_from?: string }[] {
  return recipe.ingredients.map((ri) => {
    const qty = scale(ri.quantity, servings, recipe.base_servings);
    const sub = substitutions.find((s) => s.original_ingredient_id === ri.ingredient_id);
    const rule = sub && rules.find((r) => r.id === sub.rule_id);
    if (rule) {
      return {
        ingredient_id: rule.substitute_ingredient_id,
        quantity: round(qty * rule.ratio),
        substituted_from: ri.ingredient_id,
      };
    }
    return { ingredient_id: ri.ingredient_id, quantity: qty };
  });
}

/** Sum demands by ingredient (canonical units only, so no cross-dimension mixing). */
export function aggregate(
  demands: { ingredient_id: string; quantity: number }[],
): Map<string, number> {
  const m = new Map<string, number>();
  for (const d of demands)
    m.set(d.ingredient_id, round((m.get(d.ingredient_id) ?? 0) + d.quantity));
  return m;
}

export function toLines(
  demands: { ingredient_id: string; quantity: number; substituted_from?: string }[],
  stock: Map<string, number>,
  ingredients: Map<string, Ingredient>,
): DemandLine[] {
  return demands.map((d) => {
    const ing = ingredients.get(d.ingredient_id)!;
    const available = stock.get(d.ingredient_id) ?? 0;
    return {
      ingredient_id: d.ingredient_id,
      name: ing?.name ?? d.ingredient_id,
      unit: ing?.canonical_unit ?? "pcs",
      required: d.quantity,
      available,
      sufficient: available >= d.quantity,
      ...(d.substituted_from ? { substituted_from: d.substituted_from } : {}),
    };
  });
}

/** match = covered lines / total lines * 100 (rounded). Substitutions excluded until confirmed. */
export function computeMatch(
  recipe: Recipe,
  pantry: PantryItem[],
  today: string,
  ingredients: Map<string, Ingredient>,
): MatchInfo {
  const stock = usableStock(pantry, today);
  let covered = 0;
  const missing: string[] = [];
  const expiring_used: string[] = [];
  for (const ri of recipe.ingredients) {
    const have = stock.get(ri.ingredient_id) ?? 0;
    const name = ingredients.get(ri.ingredient_id)?.name ?? ri.ingredient_id;
    if (have >= ri.quantity) covered++;
    else missing.push(name);
    const p = pantry.find((x) => x.ingredient_id === ri.ingredient_id);
    if (p && have > 0 && expiryStatus(p.expiry_date, today) === "expiring")
      expiring_used.push(name);
  }
  const total = recipe.ingredients.length;
  return {
    score: total === 0 ? 0 : Math.round((covered / total) * 100),
    covered,
    total,
    missing,
    expiring_used,
  };
}

/** Rank: match score first, then expiry urgency as tie-breaker, then title. */
export function rankRecipes<T extends { title: string; match: MatchInfo }>(list: T[]): T[] {
  return [...list].sort(
    (a, b) =>
      b.match.score - a.match.score ||
      b.match.expiring_used.length - a.match.expiring_used.length ||
      a.title.localeCompare(b.title),
  );
}

/** Eligible substitutes for insufficient lines: substitute must have enough non-expired stock. */
export function suggestSubstitutions(
  lines: DemandLine[],
  rules: SubstitutionRule[],
  stock: Map<string, number>,
  ingredients: Map<string, Ingredient>,
): SubstitutionSuggestion[] {
  const out: SubstitutionSuggestion[] = [];
  for (const line of lines) {
    if (line.sufficient || line.substituted_from) continue;
    const candidates = rules
      .filter((r) => r.original_ingredient_id === line.ingredient_id)
      .map((r) => ({ r, required: round(line.required * r.ratio) }))
      .filter(({ r, required }) => (stock.get(r.substitute_ingredient_id) ?? 0) >= required);
    const best = candidates[0];
    if (best) {
      const sub = ingredients.get(best.r.substitute_ingredient_id)!;
      out.push({
        rule: best.r,
        original_name: line.name,
        substitute_name: sub.name,
        required: best.required,
        unit: sub.canonical_unit,
      });
    }
  }
  return out;
}

/** to_buy = max(0, total_required - total_usable_stock), stock deducted once across the basket. */
export function computeShopping(
  totals: Map<string, number>,
  stock: Map<string, number>,
): Map<string, number> {
  const out = new Map<string, number>();
  for (const [id, req] of totals) {
    const toBuy = round(Math.max(0, req - (stock.get(id) ?? 0)));
    if (toBuy > 0) out.set(id, toBuy);
  }
  return out;
}

/**
 * Parse a free-text measure from an external recipe source.
 * Only exact, defined conversions are accepted; anything ambiguous returns null.
 */
export function parseMeasure(measure: string, canonical: CanonicalUnit): number | null {
  const m = measure
    .trim()
    .toLowerCase()
    .match(/^(\d+(?:\.\d+)?)(?:\s*)([a-z]*)$/);
  if (!m) return null;
  const qty = parseFloat(m[1]!);
  if (!(qty > 0)) return null;
  const aliases: Record<string, InputUnit> = {
    "": "pcs",
    pc: "pcs",
    pcs: "pcs",
    g: "g",
    gram: "g",
    grams: "g",
    kg: "kg",
    ml: "ml",
    l: "l",
    tsp: "tsp",
    tbsp: "tbsp",
    tbs: "tbsp",
  };
  const unit = aliases[m[2]!];
  if (!unit) return null;
  return toCanonical(qty, unit, canonical);
}
