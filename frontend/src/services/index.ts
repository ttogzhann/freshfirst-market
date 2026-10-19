// Single entry point for backend calls; tests can inject a service explicitly.
import { createHttpService } from "./httpService";
import type { FreshService } from "./types";

export * from "./types";
let instance: FreshService | null = null;
export function getService(): FreshService {
  return (instance ??= createHttpService());
}
export function setService(s: FreshService) {
  instance = s;
}
