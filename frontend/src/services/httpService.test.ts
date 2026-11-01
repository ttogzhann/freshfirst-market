import { describe, expect, it, vi } from "vitest";
import { createHttpService } from "./httpService";

const reply = (status: number, body: string) =>
  ({
    ok: status >= 200 && status < 300,
    status,
    json: async () => JSON.parse(body),
  }) as Response;

describe("HTTP failures and request encoding", () => {
  it("uses credentialed fetches and bootstraps an in-memory CSRF proof for mutations", async () => {
    const fetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(
        reply(
          200,
          JSON.stringify({ authenticated: false, user: null, csrf_token: "bootstrap-proof" }),
        ),
      )
      .mockResolvedValueOnce(
        reply(
          200,
          JSON.stringify({
            id: "p1",
            ingredient_id: "egg",
            quantity: 2,
            expiry_date: "2026-11-01",
          }),
        ),
      );
    const service = createHttpService("http://api/api", fetcher);

    await service.createPantryItem({
      ingredient_id: "egg",
      quantity: 2,
      unit: "pcs",
      expiry_date: "2026-11-01",
    });

    expect(fetcher).toHaveBeenCalledTimes(2);
    expect(fetcher.mock.calls[0]?.[1]).toMatchObject({
      method: "GET",
      credentials: "include",
    });
    expect(fetcher.mock.calls[0]?.[0]).toBe("http://api/api/auth/session");
    expect(fetcher.mock.calls[1]?.[1]).toMatchObject({
      method: "POST",
      credentials: "include",
    });
    expect(new Headers(fetcher.mock.calls[1]?.[1]?.headers).get("X-CSRF-Token")).toBe(
      "bootstrap-proof",
    );
    expect(localStorage.length).toBe(0);
    expect(sessionStorage.length).toBe(0);
  });

  it("replaces the CSRF proof after authentication and clears it after logout", async () => {
    const fetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(
        reply(
          200,
          JSON.stringify({ authenticated: false, user: null, csrf_token: "anonymous-proof" }),
        ),
      )
      .mockResolvedValueOnce(
        reply(
          200,
          JSON.stringify({ user: { id: "u1", email: "u@example.com" }, csrf_token: "user-proof" }),
        ),
      )
      .mockResolvedValueOnce(reply(204, ""))
      .mockResolvedValueOnce(
        reply(
          200,
          JSON.stringify({ authenticated: false, user: null, csrf_token: "new-anonymous-proof" }),
        ),
      )
      .mockResolvedValueOnce(
        reply(
          200,
          JSON.stringify({ user: { id: "u1", email: "u@example.com" }, csrf_token: "login-proof" }),
        ),
      );
    const service = createHttpService("http://api/api", fetcher);

    await service.registerAccount({
      email: "u@example.com",
      password: "a long enough test password",
    });
    expect(new Headers(fetcher.mock.calls[1]?.[1]?.headers).get("X-CSRF-Token")).toBe(
      "anonymous-proof",
    );
    await service.logoutAccount();
    await service.restoreSession();
    await service.loginAccount({ email: "u@example.com", password: "a long enough test password" });
    expect(new Headers(fetcher.mock.calls[4]?.[1]?.headers).get("X-CSRF-Token")).toBe(
      "new-anonymous-proof",
    );
    expect(fetcher.mock.calls.every((call) => call[1]?.credentials === "include")).toBe(true);
  });

  it("notifies auth state when a private request receives 401", async () => {
    const fetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValue(
        reply(
          401,
          JSON.stringify({ code: "AUTH_REQUIRED", message: "Authentication is required." }),
        ),
      );
    const onUnauthorized = vi.fn();
    window.addEventListener("freshfirst:unauthorized", onUnauthorized);
    try {
      await expect(createHttpService("http://api/api", fetcher).listPantry()).rejects.toMatchObject(
        {
          status: 401,
          code: "AUTH_REQUIRED",
        },
      );
      expect(onUnauthorized).toHaveBeenCalledOnce();
    } finally {
      window.removeEventListener("freshfirst:unauthorized", onUnauthorized);
    }
  });

  it("exposes network failures as recoverable ServiceErrors", async () => {
    const fetcher = vi.fn<typeof fetch>().mockRejectedValue(new TypeError("Failed to fetch"));
    await expect(createHttpService("http://api/api", fetcher).listPantry()).rejects.toMatchObject({
      status: 0,
      code: "NETWORK_ERROR",
    });
  });
  it("preserves backend validation and conflict messages", async () => {
    const fetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValue(
        reply(
          422,
          JSON.stringify({ code: "VALIDATION_ERROR", message: "quantity must be positive" }),
        ),
      );
    await expect(createHttpService("http://api/api", fetcher).listPantry()).rejects.toMatchObject({
      status: 422,
      code: "VALIDATION_ERROR",
      message: "quantity must be positive",
    });
  });
  it("handles a non-JSON error and malformed success body", async () => {
    const fetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(reply(502, "upstream unavailable"))
      .mockResolvedValueOnce(reply(200, "invalid JSON"));
    const service = createHttpService("http://api/api", fetcher);
    await expect(service.listPantry()).rejects.toMatchObject({ status: 502, code: "HTTP_ERROR" });
    await expect(service.listPantry()).rejects.toMatchObject({ code: "INVALID_RESPONSE" });
  });
  it("encodes opaque IDs and JSON query choices without changing quantities", async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(reply(200, "{}"));
    const choices = [
      { rule_id: "r9", original_ingredient_id: "milk", substitute_ingredient_id: "cream" },
    ];
    await createHttpService("http://api/api/", fetcher).getRecipe("a/b ?", 3, choices);
    const url = new URL(String(fetcher.mock.calls[0]![0]));
    expect(url.pathname).toBe("/api/recipes/a%2Fb%20%3F");
    expect(url.searchParams.get("servings")).toBe("3");
    expect(JSON.parse(url.searchParams.get("substitutions")!)).toEqual(choices);
  });
});
