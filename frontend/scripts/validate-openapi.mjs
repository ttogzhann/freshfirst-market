import SwaggerParser from "@apidevtools/swagger-parser";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const document = await SwaggerParser.validate(
  fileURLToPath(new URL("../../openapi.yaml", import.meta.url)),
);
const types = readFileSync(new URL("../src/services/types.ts", import.meta.url), "utf8");
const service = types.split("export interface FreshService {")[1];
const methods = [...service.matchAll(/^\s{2}(\w+)\(/gm)].map((match) => match[1]);
const operations = Object.values(document.paths).flatMap((path) =>
  Object.values(path).filter((value) => value?.operationId),
);
const ids = operations.map((operation) => operation.operationId);
if (
  new Set(ids).size !== ids.length ||
  methods.length !== ids.length ||
  methods.some((method) => !ids.includes(method))
) {
  throw new Error("OpenAPI operationIds must map one-to-one to FreshService methods");
}
if (document.security?.length || operations.some((operation) => operation.security?.length))
  throw new Error("v1.0 must not require authentication");
for (const path of Object.values(document.paths)) {
  for (const method of ["post", "put", "patch", "delete"]) {
    if (path[method] && !path[method].responses["422"])
      throw new Error("Mutation missing validation response");
  }
}
console.log(
  `Validated OpenAPI ${document.openapi}: ${ids.length} operations match FreshService; no authentication.`,
);
