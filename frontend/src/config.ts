import { parseExpiryDays } from "./expiry-config";

export const EXPIRY_THRESHOLD_DAYS = parseExpiryDays(
  import.meta.env["VITE_FRESHFIRST_EXPIRY_DAYS"],
);
