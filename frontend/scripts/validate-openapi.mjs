import SwaggerParser from "@apidevtools/swagger-parser";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const document = await SwaggerParser.validate(
  fileURLToPath(new URL("../../openapi.yaml", import.meta.url)),
);
const types = readFileSync(new URL("../src/services/types.ts", import.meta.url), "utf8");
function methodsOf(name) {
  const start = types.indexOf(`export interface ${name} {`);
  if (start < 0) throw new Error(`Missing ${name} interface`);
  const end = types.indexOf("\n}", start);
  return [...types.slice(start, end).matchAll(/^\s{2}(\w+)\(/gm)].map((match) => match[1]);
}
const methods = [...methodsOf("FreshService"), ...methodsOf("AuthService")];
const operations = Object.values(document.paths).flatMap((path) =>
  Object.values(path).filter((value) => value?.operationId),
);
const ids = operations.map((operation) => operation.operationId);
const originalDomainIds = new Set([
  "listIngredients",
  "listSubstitutionRules",
  "listPantry",
  "createPantryItem",
  "updatePantryItem",
  "deletePantryItem",
  "listRecipes",
  "getRecipe",
  "importRecipes",
  "getBasket",
  "addToBasket",
  "updateBasketItem",
  "removeBasketItem",
  "getShoppingList",
  "generateShoppingList",
  "addShoppingItem",
  "updateShoppingItem",
  "removeShoppingItem",
  "transferToPantry",
  "previewCook",
  "confirmCook",
  "listHistory",
  "getDashboard",
]);
const missingServices = ids.filter((id) => !methods.includes(id));
const orphanServices = methods.filter((method) => !ids.includes(method));
if (
  new Set(ids).size !== ids.length ||
  methods.length !== ids.length ||
  orphanServices.length > 0 ||
  missingServices.length > 0 ||
  originalDomainIds.size !== 23 ||
  [...originalDomainIds].some((id) => !ids.includes(id)) ||
  ids.length !== 27
) {
  throw new Error(
    `OpenAPI service mismatch: ${ids.length} operations, ${methods.length} service methods, duplicate IDs: ${ids.length - new Set(ids).size}, missing services: ${missingServices.join(", ")}, orphan services: ${orphanServices.join(", ")}, original set size: ${originalDomainIds.size}`,
  );
}
const publicReadIds = new Set(["restoreSession", "listIngredients", "listSubstitutionRules"]);
for (const operation of operations) {
  const security = operation.security ?? document.security ?? [];
  const schemes = new Set(security.flatMap((requirement) => Object.keys(requirement)));
  if (!publicReadIds.has(operation.operationId) && !schemes.has("SessionCookie"))
    throw new Error(`${operation.operationId} must require an account session`);
  const method = Object.values(document.paths).find((path) =>
    Object.values(path).includes(operation),
  );
  if (!method) throw new Error(`Cannot locate route for ${operation.operationId}`);
}
for (const [route, path] of Object.entries(document.paths)) {
  for (const method of ["post", "put", "patch", "delete"]) {
    const operation = path[method];
    if (!operation) continue;
    const security = operation.security ?? document.security ?? [];
    const schemes = new Set(security.flatMap((requirement) => Object.keys(requirement)));
    if (!schemes.has("SessionCookie") || !schemes.has("CsrfToken"))
      throw new Error(`${operation.operationId} at ${route} must require session and CSRF proof`);
    if (operation.requestBody && !operation.responses["422"])
      throw new Error(`${operation.operationId} is missing a validation response`);
  }
}
console.log(
  `Validated OpenAPI ${document.openapi}: 27 operations map to services; auth security is declared.`,
);
