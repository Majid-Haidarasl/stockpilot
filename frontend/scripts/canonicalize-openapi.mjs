/** Canonicalize OpenAPI JSON for stable drift comparison (sorted object keys). */
import { readFileSync, writeFileSync } from "node:fs";

function canonicalize(value) {
  if (Array.isArray(value)) {
    return value.map(canonicalize);
  }
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.keys(value)
        .sort()
        .map((key) => [key, canonicalize(value[key])]),
    );
  }
  return value;
}

const inputPath = process.argv[2];
const outputPath = process.argv[3] ?? inputPath;
if (!inputPath) {
  console.error("Usage: node scripts/canonicalize-openapi.mjs <input> [output]");
  process.exit(1);
}

const raw = JSON.parse(readFileSync(inputPath, "utf8"));
const text = `${JSON.stringify(canonicalize(raw), null, 2)}\n`;
writeFileSync(outputPath, text, "utf8");
