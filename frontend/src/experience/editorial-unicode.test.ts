import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import * as unicode from "./editorial-unicode.ts";

test("generated Unicode tables record one well-formed backend version", () => {
  const regenerate = "Regenerate with backend/.venv's Python: python frontend/scripts/generate-editorial-unicode.py (from repository root), then run backend/tests/test_editorial_unicode_drift.py and frontend normalization parity tests.";
  const source = readFileSync(new URL("./editorial-unicode.ts", import.meta.url), "utf8");
  const versions = [...source.matchAll(/^export const backendUnicodeVersion = "([0-9]+\.[0-9]+\.[0-9]+)";\r?$/gm)];
  assert.equal(versions.length, 1, regenerate);
  assert.equal(typeof unicode.backendUnicodeVersion, "string", regenerate);
  assert.match(unicode.backendUnicodeVersion, /^[0-9]+\.[0-9]+\.[0-9]+$/, regenerate);
  assert.equal(versions[0][1], unicode.backendUnicodeVersion, regenerate);
});
