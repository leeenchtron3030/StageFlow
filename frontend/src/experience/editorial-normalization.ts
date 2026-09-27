import { casefoldMappings, assignedRanges, alphanumericRanges } from "./editorial-unicode.ts";

function contains(ranges: readonly (readonly number[])[], point: number): boolean {
  let low = 0, high = ranges.length - 1;
  while (low <= high) {
    const middle = (low + high) >>> 1, [start, end] = ranges[middle];
    if (point < start) high = middle - 1;
    else if (point > end) low = middle + 1;
    else return true;
  }
  return false;
}

// Unicode normalization is stable for assigned characters. Isolate characters
// unassigned in the backend's Unicode version so newer browser engines cannot
// turn them into accepted letters (e.g. Unicode 16 outlined Latin characters).
function backendNfkc(value: string): string {
  let result = "", assigned = "";
  for (const char of value) {
    if (contains(assignedRanges, char.codePointAt(0)!)) assigned += char;
    else { result += assigned.normalize("NFKC") + char; assigned = ""; }
  }
  return result + assigned.normalize("NFKC");
}

// Python str.split/strip whitespace, including U+001C–1F and excluding U+FEFF.
const whitespace = /[\u0009-\u000d\u001c-\u0020\u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+/u;
export function trimPhrase(value: string): string {
  return value.split(whitespace).filter(Boolean).join(" ");
}
export function normalizePhrase(value: string): string {
  return trimPhrase(Array.from(backendNfkc(value), (char) => casefoldMappings[char] ?? char).join(""));
}
export function wordTokens(value: string): string[] {
  const tokens: string[] = [];
  let token = "";
  for (const char of normalizePhrase(value)) {
    if (contains(alphanumericRanges, char.codePointAt(0)!)) token += char;
    else if (token) { tokens.push(token); token = ""; }
  }
  if (token) tokens.push(token);
  return tokens;
}
export function phrasePreview(text: string) {
  const seen = new Set<string>();
  const rows = text.split(/\r?\n/).flatMap((raw, index) => {
    // Preserve internal whitespace in the published value; only trim its edges.
    const phrase = raw.replace(/^[\u0009-\u000d\u001c-\u0020\u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+|[\u0009-\u000d\u001c-\u0020\u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+$/gu, "");
    if (!phrase) return [];
    const tokens = wordTokens(phrase), key = JSON.stringify(tokens);
    const error = !tokens.length ? "No word tokens" : Array.from(phrase).length > 100 ? "Over 100 characters" : seen.has(key) ? "Duplicate token sequence" : undefined;
    seen.add(key);
    return [{ line: index + 1, phrase, normalized: normalizePhrase(phrase), tokens, error }];
  });
  return { rows, valid: rows.length > 0 && rows.length <= 200 && rows.every((r) => !r.error), error: !rows.length ? "At least one phrase is required" : rows.length > 200 ? "At most 200 phrases" : undefined };
}
