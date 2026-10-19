// Single entry point for all backend calls. Swap the implementation here
// (e.g. createHttpService()) when the real API exists.
import { createMockService, memoryStorage } from "./mock/mockService";
import type { FreshService } from "./types";

export * from "./types";

let instance: FreshService | null = null;

export function getService(): FreshService {
  if (!instance) {
    const browser = typeof window !== "undefined" && typeof window.localStorage !== "undefined";
    instance = createMockService({
      storage: browser ? window.localStorage : memoryStorage(),
      latencyMs: browser ? 200 : 0,
    });
  }
  return instance;
}

export function setService(s: FreshService) {
  instance = s;
}
