import { cueCompositionSchema, type CueCatalog, type CueChoice, type CueComposition, type CueCustom, type CueRole } from "./boundary-cues-api.ts";
import { wordTokens, phrasePreview } from "./editorial-normalization.ts";
import { demoAuthorityHeaders } from "./demo-launch-context.ts";
import { generateUuidV4 } from "../shared/ids/uuid-v4.ts";
import { boundaryCueLabels as labels } from "./ui-labels.ts";

type RemovedCue = { key: string; text: string; include: CueChoice[]; custom_phrases: CueCustom[] };
export type CueDraft = { profile_key: string | null; group_keys: string[]; include: CueChoice[]; exclude: CueChoice[]; custom_phrases: CueCustom[]; removed?: RemovedCue[] };
export const phraseKey = (text: string) => JSON.stringify(wordTokens(text));
const hasChoice = (choices: CueChoice[], group_key: string, phrase: string) => choices.some((c) => c.group_key === group_key && c.phrase === phrase);
export function profileDraft(catalog: CueCatalog, key: string | null): CueDraft {
  return { profile_key: key, group_keys: [...(catalog.profiles.find((p) => p.key === key)?.group_keys ?? [])], include: [], exclude: [], custom_phrases: [] };
}
export function compositionDraft(composition: CueComposition): CueDraft {
  return { profile_key: composition.profile_key, group_keys: composition.groups.map((g) => g.key), include: [...composition.include], exclude: [...composition.exclude], custom_phrases: [...composition.custom_phrases] };
}
export function hasCueEdits(catalog: CueCatalog, draft: CueDraft): boolean {
  const preset = profileDraft(catalog, draft.profile_key);
  return JSON.stringify([...preset.group_keys].sort()) !== JSON.stringify([...draft.group_keys].sort()) ||
    draft.include.length > 0 || draft.exclude.length > 0 || draft.custom_phrases.length > 0;
}
export function cueProfileName(catalog: CueCatalog, draft: CueDraft): string {
  const profile = catalog.profiles.find((p) => p.key === draft.profile_key);
  return profile ? hasCueEdits(catalog, draft) ? labels.basedOn(profile.name) : profile.name : labels.customProfile;
}
export function removedCues(draft: CueDraft): RemovedCue[] {
  const rows = new Map((draft.removed ?? []).map((row) => [row.key, row]));
  for (const choice of draft.exclude) {
    const key = phraseKey(choice.phrase);
    if (!rows.has(key)) rows.set(key, { key, text: choice.phrase, include: [], custom_phrases: [] });
  }
  return [...rows.values()];
}
export function toggleCueGroup(catalog: CueCatalog, draft: CueDraft, key: string): CueDraft {
  const selected = draft.group_keys.includes(key);
  const removed = removedCues(draft);
  const exclude = draft.exclude.filter((c) => c.group_key !== key);
  if (!selected) for (const phrase of catalog.groups.find((g) => g.key === key)?.phrases ?? []) {
    if (phrase.default && removed.some((row) => row.key === phraseKey(phrase.text))) exclude.push({ group_key: key, phrase: phrase.text });
  }
  return { ...draft, group_keys: selected ? draft.group_keys.filter((k) => k !== key) : [...draft.group_keys, key],
    include: draft.include.filter((c) => c.group_key !== key), exclude, removed };
}
export type AggregatePhrase = { key: string; text: string; roles: CueRole[]; sources: string[]; evidence: string[]; warning: boolean };
export function aggregateCues(catalog: CueCatalog, draft: CueDraft) {
  const merged = new Map<string, AggregatePhrase>();
  const add = (text: string, role: CueRole, source: string, evidence: string[], warning: boolean) => {
    const key = phraseKey(text);
    const row = merged.get(key) ?? { key, text, roles: [], sources: [], evidence: [], warning: false };
    row.roles = [...new Set([...row.roles, role])]; row.sources = [...new Set([...row.sources, source])];
    row.evidence = [...new Set([...row.evidence, ...evidence])]; row.warning ||= warning; merged.set(key, row);
  };
  for (const group of catalog.groups) if (draft.group_keys.includes(group.key)) {
    for (const phrase of group.phrases) if ((phrase.default && !hasChoice(draft.exclude, group.key, phrase.text)) || hasChoice(draft.include, group.key, phrase.text)) {
      add(phrase.text, phrase.role, group.name, evidenceLabels(phrase.evidence), !phrase.default || phrase.evidence.includes("⚠"));
    }
  }
  for (const custom of draft.custom_phrases) add(custom.text, custom.role, labels.custom, [], false);
  const rows = [...merged.values()];
  const start = rows.filter((p) => p.roles.includes("start") || p.roles.includes("changeover"));
  const end = rows.filter((p) => p.roles.includes("end") || p.roles.includes("changeover"));
  const byRole: Record<CueRole, AggregatePhrase[]> = { start: [], end: [], changeover: [], segment: [] };
  for (const row of rows) {
    const isStart = start.includes(row), isEnd = end.includes(row);
    if (isStart && isEnd) byRole.changeover.push(row);
    else if (isStart) byRole.start.push(row);
    else if (isEnd) byRole.end.push(row);
    if (row.roles.includes("segment")) byRole.segment.push(row);
  }
  return { rows, byRole, start: start.length, end: end.length };
}
export function evidenceLabels(value: string): string[] {
  return [...(/\bM\b/.test(value) ? [labels.measured] : []), ...(/\bR\b/.test(value) ? [labels.scripts] : [])];
}
export function exceptionEvidence(evidence: string[]): string[] {
  return evidence.includes(labels.scripts) && !evidence.includes(labels.measured) ? [labels.scripts] : [];
}
export function groupCuePhrases(rows: AggregatePhrase[]) {
  const groups = new Map<string, AggregatePhrase[]>();
  for (const row of rows) {
    const source = row.sources[0];
    if (!groups.has(source)) groups.set(source, []);
    groups.get(source)!.push(row);
  }
  return [...groups].map(([source, phrases]) => ({ source, phrases }));
}
export function removeCue(catalog: CueCatalog, draft: CueDraft, key: string): CueDraft {
  const removed = removedCues(draft);
  const row = aggregateCues(catalog, draft).rows.find((p) => p.key === key);
  if (!row) return draft;
  const previous = removed.find((p) => p.key === key);
  const entry = { key, text: previous?.text ?? row.text,
    include: [...(previous?.include ?? []), ...draft.include.filter((c) => phraseKey(c.phrase) === key)],
    custom_phrases: [...(previous?.custom_phrases ?? []), ...draft.custom_phrases.filter((c) => phraseKey(c.text) === key)] };
  const exclude = [...draft.exclude];
  for (const group of catalog.groups) if (draft.group_keys.includes(group.key)) {
    for (const phrase of group.phrases) if (phrase.default && phraseKey(phrase.text) === key && !hasChoice(exclude, group.key, phrase.text)) exclude.push({ group_key: group.key, phrase: phrase.text });
  }
  return { ...draft, exclude, removed: [...removed.filter((p) => p.key !== key), entry], include: draft.include.filter((c) => phraseKey(c.phrase) !== key), custom_phrases: draft.custom_phrases.filter((c) => phraseKey(c.text) !== key) };
}
export function restoreCue(draft: CueDraft, key: string): CueDraft {
  const removed = removedCues(draft);
  const row = removed.find((p) => p.key === key);
  return { ...draft, exclude: draft.exclude.filter((c) => phraseKey(c.phrase) !== key),
    include: [...draft.include, ...(row?.include ?? []).filter((c) => draft.group_keys.includes(c.group_key) && !hasChoice(draft.include, c.group_key, c.phrase))],
    custom_phrases: [...draft.custom_phrases, ...(row?.custom_phrases ?? [])], removed: removed.filter((p) => p.key !== key) };
}
export function availableOptIns(catalog: CueCatalog, draft: CueDraft) {
  const removed = new Set(removedCues(draft).map((p) => p.key));
  return catalog.groups.filter((g) => draft.group_keys.includes(g.key)).flatMap((g) => g.phrases.filter((p) => !p.default && !hasChoice(draft.include, g.key, p.text) && !removed.has(phraseKey(p.text))).map((p) => ({ group: g, phrase: p })));
}
export function addOptIn(catalog: CueCatalog, draft: CueDraft, choice: CueChoice): CueDraft {
  if (!availableOptIns(catalog, draft).some((p) => p.group.key === choice.group_key && p.phrase.text === choice.phrase)) throw new Error(labels.invalidChoice);
  return { ...draft, include: [...draft.include, choice] };
}
export function addCustomCue(draft: CueDraft, text: string, role: CueCustom["role"]): CueDraft {
  const preview = phrasePreview(text);
  if (!["start", "end", "changeover"].includes(role) || preview.rows.length !== 1 || !preview.valid || /[\r\n]/.test(text)) throw new Error(labels.invalidCustom);
  const key = phraseKey(preview.rows[0].phrase);
  // Adding a removed phrase back as custom un-removes it everywhere, so it never shows as both.
  const base = removedCues(draft).some((p) => p.key === key)
    ? { ...draft, exclude: draft.exclude.filter((c) => phraseKey(c.phrase) !== key), removed: removedCues(draft).filter((p) => p.key !== key) }
    : draft;
  return { ...base, custom_phrases: [...base.custom_phrases, { text: preview.rows[0].phrase, role }] };
}
export function cueLimits(catalog: CueCatalog, draft: CueDraft): string[] {
  const counts = aggregateCues(catalog, draft);
  const errors = (["start", "end"] as const).flatMap((role) => counts[role] === 0 || counts[role] > 200 ? [cueCountError(role, counts[role])] : []);
  if (draft.group_keys.length > 20 || draft.include.length > 400 || draft.exclude.length > 400 || draft.custom_phrases.length > 400) errors.push(labels.tooManyChoices);
  return errors;
}
export function cueCountError(role: "start" | "end", count: number): string {
  return `${labels.roles[role]}: ${count} phrases. ${count === 0 ? "Add at least one phrase before publishing." : "Remove phrases to reach the 200-phrase limit before publishing."}`;
}
export function catalogMatches(catalog: CueCatalog, current: CueComposition): boolean {
  return catalog.id === current.catalog_id && catalog.version === current.catalog_version && catalog.digest === current.catalog_digest;
}
export function cueSummary(catalog: CueCatalog, current: CueComposition | null, timeZone?: string): string {
  if (!current) return labels.none;
  const name = cueProfileName(catalog, compositionDraft(current));
  const counts = catalogMatches(catalog, current) ? aggregateCues(catalog, compositionDraft(current)) : undefined;
  return `${name} · ${current.groups.length} groups · ${counts ? `${counts.start} start / ${counts.end} end phrases` : labels.countsUnavailable} · ${composedTime(current.composed_at, timeZone)}`;
}
export function composedTime(timestamp: string, timeZone?: string): string {
  return `Composed ${new Intl.DateTimeFormat("en-US", { weekday: "short", hour: "2-digit", minute: "2-digit", hour12: false, timeZone }).format(new Date(timestamp))}`;
}
export function prepareCueCommand(catalog: CueCatalog, draft: CueDraft) {
  if (cueLimits(catalog, draft).length) throw new Error(labels.invalidLists);
  const { profile_key, group_keys, include, exclude, custom_phrases } = structuredClone(draft);
  return { command_id: generateUuidV4(), authority_kind: "human" as const, catalog_version: catalog.version, profile_key, group_keys, include, exclude, custom_phrases };
}
export function cueError(status: number, payload: unknown): string {
  if (status === 409) return labels.conflict;
  const detail = payload && typeof payload === "object" && "detail" in payload ? payload.detail : undefined;
  if (detail && typeof detail === "object" && "code" in detail && "role" in detail && "count" in detail &&
    ["cue_list_empty", "cue_list_too_large"].includes(String(detail.code)) && (detail.role === "start" || detail.role === "end") && Number.isSafeInteger(detail.count) && Number(detail.count) >= 0) return cueCountError(detail.role, Number(detail.count));
  if (status === 403 || status === 401) return labels.readOnly;
  if (status === 413) return labels.tooLarge;
  if (status === 422) return labels.invalidChoices;
  if (status === 404) return labels.eventUnavailable;
  return labels.failed;
}
export async function sendCueCommand(eventId: string, command: ReturnType<typeof prepareCueCommand>, launchContext: string, fetcher: typeof fetch = fetch) {
  let response: Response;
  try {
    response = await fetcher(`/api/stageflow/session-suggestions/events/${eventId}/boundary-cues`, { method: "POST", cache: "no-store", redirect: "error", headers: demoAuthorityHeaders(launchContext), body: JSON.stringify(command) });
  } catch { return { retry: true, saved: false, message: labels.unknown }; }
  let payload: unknown;
  try { payload = await response.json(); } catch {
    if (response.ok) return { retry: true, saved: false, message: labels.unknown };
  }
  if (!response.ok) return { retry: response.status >= 500, saved: false, message: cueError(response.status, payload) };
  const parsed = cueCompositionSchema.safeParse(payload);
  if (!parsed.success || parsed.data.event_id !== eventId || parsed.data.command_id !== command.command_id) return { retry: true, saved: false, message: labels.unknown };
  return { retry: false, saved: true, message: labels.saved };
}
