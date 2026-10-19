import { describe, expect, it, vi } from "vitest";
import { createHttpService } from "./httpService";

const reply = (status: number, body: string) =>
  ({
    ok: status >= 200 && status < 300,
    status,
    json: async () => JSON.parse(body),
  }) as Response;

describe("HTTP failures and request encoding", () => {
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
