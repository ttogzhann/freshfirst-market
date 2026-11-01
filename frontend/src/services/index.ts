// Single entry point for backend calls; tests can inject a service explicitly.
import { createHttpService } from "./httpService";
import type { AuthService, FreshService } from "./types";

export * from "./types";
let instance: (FreshService & AuthService) | null = null;
export function getService(): FreshService {
  return (instance ??= createHttpService());
}
export function getAuthService(): AuthService {
  return (instance ??= createHttpService());
}
export function setService(s: FreshService) {
  instance = s as FreshService & AuthService;
}
