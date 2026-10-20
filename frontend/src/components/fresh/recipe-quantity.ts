// Older records do not carry yield metadata; preserve their recorded quantity.
export function recipeQuantity(value: number, base?: number): string {
  return base === 1 ? `${value} ${value === 1 ? "batch" : "batches"}` : `Recipe quantity ${value}`;
}

export function quantityControlLabel(base: number): string {
  return base === 1 ? "Batches" : "Recipe quantity";
}
