// The committed TypeScript types must match the committed JSON Schema.
import { readFile } from "node:fs/promises";
import { describe, expect, it } from "vitest";
import { generate, TYPES_PATH } from "../../scripts/gen-types.mjs";

describe("generated API types", () => {
  it("match src/api/schema.json (run `npm run gen:types` if this fails)", async () => {
    const committed = await readFile(TYPES_PATH, "utf8");
    expect(committed).toBe(await generate());
  });
});
