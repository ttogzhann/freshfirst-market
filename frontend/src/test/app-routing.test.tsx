import { QueryClient } from "@tanstack/react-query";
import { createRouter, rootRouteId } from "@tanstack/react-router";
import { describe, expect, it } from "vitest";

import { routeTree } from "@/routeTree.gen";

// Match routes without running loaders or rendering: loaders may need a server or
// network the test run lacks, and jsdom never loads the stylesheets React waits on.
describe("App routing", () => {
  it.each(["/", "/basket", "/shopping", "/pantry", "/recipes", "/recipes/rec_52982"])(
    "matches a page for %s instead of falling back to not found",
    (path) => {
      const router = createRouter({ routeTree, context: { queryClient: new QueryClient() } });

      const matches = router.matchRoutes(path);

      expect(matches.at(-1)?.routeId).not.toBe(rootRouteId);
      expect(matches.at(-1)?.pathname.replace(/\/$/, "")).toBe(path.replace(/\/$/, ""));
    },
  );

  it.each(["/login", "/register"])("matches the auth screen %s", (path) => {
    const router = createRouter({ routeTree, context: { queryClient: new QueryClient() } });
    expect(router.matchRoutes(path).at(-1)?.pathname).toBe(path);
  });
});
