// List every npm package in package-lock.json with its licence and group, as
// a Markdown table for docs/THIRD_PARTY.md. Reads the lock file only.
import { readFile } from "node:fs/promises";

const lock = JSON.parse(await readFile(new URL("../package-lock.json", import.meta.url), "utf8"));
const rows = [];
for (const [path, entry] of Object.entries(lock.packages)) {
  if (path === "") continue;
  const name = path.replace(/^.*node_modules\//, "");
  rows.push({ name, version: entry.version, license: entry.license ?? "UNKNOWN",
              group: entry.dev ? "dev" : "runtime", optional: Boolean(entry.optional) });
}
rows.sort((a, b) => a.name.localeCompare(b.name) || a.version.localeCompare(b.version));
const json = process.argv.includes("--json");
if (json) console.warn(JSON.stringify(rows));
else for (const r of rows) console.warn(`| ${r.name} | ${r.version} | ${r.group}${r.optional ? " (optional)" : ""} | ${r.license} |`);
