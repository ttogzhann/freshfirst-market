export function parseExpiryDays(value: string | undefined): number {
  if (value === undefined) return 3;
  if (!/^\d+$/.test(value) || !Number.isSafeInteger(Number(value))) {
    throw new Error(
      "VITE_FRESHFIRST_EXPIRY_DAYS must be a nonnegative whole-day integer (maximum 9007199254740991).",
    );
  }
  return Number(value);
}
