/**
 * Fail if committed OpenAPI schema or generated types diverge from the live backend dump.
 *
 * Env:
 *   OPENAPI_LIVE_PATH — path to live OpenAPI JSON produced by
 *     `python -m stockpilot.bootstrap.export_openapi`
 */
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { copyFileSync, existsSync, mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const committedSchema = join(root, "openapi.json");
const generatedDir = join(root, "src", "generated", "api");
const generatedSchema = join(generatedDir, "schema.ts");
const livePath = process.env.OPENAPI_LIVE_PATH;

function sha256(text) {
  return createHash("sha256").update(text).digest("hex");
}

function fail(message) {
  console.error(`OpenAPI drift check failed: ${message}`);
  process.exit(1);
}

if (!livePath) {
  fail("OPENAPI_LIVE_PATH is not set");
}
if (!existsSync(livePath)) {
  fail(`live OpenAPI file not found: ${livePath}`);
}
if (!existsSync(committedSchema)) {
  fail(`committed schema missing: ${committedSchema}`);
}
if (!existsSync(generatedSchema)) {
  fail(`generated types missing: ${generatedSchema}`);
}

const tmpDir = mkdtempSync(join(tmpdir(), "stockpilot-openapi-"));
const liveCanonical = join(tmpDir, "openapi.live.canonical.json");
const committedCanonical = join(tmpDir, "openapi.committed.canonical.json");
const regenSchema = join(tmpDir, "schema.regen.ts");
const tmpInput = join(tmpDir, "openapi.for-gen.json");

try {
  execFileSync(
    process.execPath,
    [join(root, "scripts", "canonicalize-openapi.mjs"), livePath, liveCanonical],
    { stdio: "inherit" },
  );
  execFileSync(
    process.execPath,
    [join(root, "scripts", "canonicalize-openapi.mjs"), committedSchema, committedCanonical],
    { stdio: "inherit" },
  );

  const liveText = readFileSync(liveCanonical, "utf8");
  const committedText = readFileSync(committedCanonical, "utf8");
  if (sha256(liveText) !== sha256(committedText)) {
    fail(
      "frontend/openapi.json is out of date with the backend. " +
        "Run: docker compose … run --rm openapi-export && npm run generate:api",
    );
  }

  copyFileSync(committedSchema, tmpInput);
  execFileSync("npx", ["openapi-typescript", tmpInput, "-o", regenSchema], {
    cwd: root,
    stdio: "inherit",
  });

  const committedGen = readFileSync(generatedSchema, "utf8");
  const regenerated = readFileSync(regenSchema, "utf8");
  if (sha256(committedGen) !== sha256(regenerated)) {
    fail(
      "src/generated/api/schema.ts is out of date. Run: npm run generate:api (via Compose frontend-dev)",
    );
  }

  console.log("OpenAPI drift check passed.");
} finally {
  rmSync(tmpDir, { recursive: true, force: true });
}
