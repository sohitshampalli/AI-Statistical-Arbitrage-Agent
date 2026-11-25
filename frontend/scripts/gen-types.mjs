// Generate src/api/types.ts from src/api/schema.json (written by
// `uv run python -m statarb_agent.api.schema_export`). A vitest test fails if
// the committed types.ts differs from what this produces.
import { readFile, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { compile } from "json-schema-to-typescript";

const here = dirname(fileURLToPath(import.meta.url));
export const SCHEMA_PATH = join(here, "..", "src", "api", "schema.json");
export const TYPES_PATH = join(here, "..", "src", "api", "types.ts");

const BANNER =
  "/* Generated from src/api/schema.json by `npm run gen:types`. Do not edit. */";

// pydantic gives every field a title, which would become one type alias per
// field; only the model titles are kept.
function dropFieldTitles(node, isModel) {
  if (Array.isArray(node)) return node.map((x) => dropFieldTitles(x, false));
  if (node === null || typeof node !== "object") return node;
  const out = {};
  for (const [key, value] of Object.entries(node)) {
    if (key === "title" && !isModel) continue;
    out[key] = key === "properties"
      ? Object.fromEntries(Object.entries(value).map(([k, v]) => [k, dropFieldTitles(v, false)]))
      : dropFieldTitles(value, false);
  }
  return out;
}

export async function generate() {
  const raw = JSON.parse(await readFile(SCHEMA_PATH, "utf8"));
  const document = {
    $defs: Object.fromEntries(
      Object.entries(raw.$defs).map(([name, def]) => [name, dropFieldTitles(def, true)]),
    ),
  };
  const names = Object.keys(document.$defs).sort();
  const root = {
    title: "ApiSchema",
    type: "object",
    properties: Object.fromEntries(names.map((n) => [n, { $ref: `#/$defs/${n}` }])),
    required: names,
    additionalProperties: false,
    $defs: document.$defs,
  };
  return compile(root, "ApiSchema", {
    bannerComment: BANNER,
    additionalProperties: false,
    unreachableDefinitions: true,
    strictIndexSignatures: true,
    format: true,
    style: { singleQuote: false, semi: true, printWidth: 100 },
  });
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  await writeFile(TYPES_PATH, await generate(), "utf8");
  console.warn(`wrote ${TYPES_PATH}`);
}
