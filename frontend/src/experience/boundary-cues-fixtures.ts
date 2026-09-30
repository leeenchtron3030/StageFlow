import { fixtureId as id } from "./session-outputs-fixtures.ts";
import type { BoundaryCueData, CueCatalog, CueComposition } from "./boundary-cues-api.ts";

// Synthetic vocabulary exercises overlapping sources and roles without event data.
export const cueCatalogFixture: CueCatalog = {
  id: "boundary-cue-catalog", version: 1, digest: "a".repeat(64),
  profiles: [
    { key: "conference", name: "Conference stage", group_keys: ["openings", "closings", "inside"] },
    { key: "small", name: "Small gathering", group_keys: ["openings", "closings"] },
  ],
  groups: [
    { key: "openings", version: 1, name: "Opening greetings", category: "Stage", phrases: [
      { text: "Hello everyone", role: "start", default: true, evidence: "M 2/2" },
      { text: "Our shared phrase", role: "start", default: true, evidence: "R [1]" },
      { text: "Optional welcome", role: "changeover", default: false, evidence: "M 1/3 ⚠" },
    ] },
    { key: "closings", version: 1, name: "Closing thanks", category: "Stage", phrases: [
      { text: "Thank you everyone", role: "end", default: true, evidence: "R [1]" },
      { text: "OUR shared, phrase!", role: "end", default: true, evidence: "M 2/3, R [1]" },
      { text: "Optional welcome", role: "changeover", default: false, evidence: "M 1/3 ⚠" },
    ] },
    { key: "inside", version: 1, name: "Studio takes", category: "Studio", phrases: [
      { text: "Take one", role: "segment", default: true, evidence: "R [2]" },
    ] },
  ],
};
export const cueCompositionFixture: CueComposition = {
  event_id: id(3), version: 1, command_id: id(4), request_digest: "b".repeat(64),
  catalog_id: cueCatalogFixture.id, catalog_version: 1, catalog_digest: cueCatalogFixture.digest, profile_key: "conference",
  groups: cueCatalogFixture.groups.map(({ key, version }) => ({ key, version })), include: [], exclude: [], custom_phrases: [],
  segment_phrases: [{ text: "Take one", source_group: "inside" }],
  composed_by: id(9), composed_at: "2026-09-29T14:05:00Z", start_cue_list: { id: id(5), version: 1 }, end_cue_list: { id: id(6), version: 1 },
};
export const cueNoneFixture: BoundaryCueData = { catalog: cueCatalogFixture, current: null, history: { items: [], next_after: null, limit: 50 } };
export const cueCurrentFixture: BoundaryCueData = { catalog: cueCatalogFixture, current: cueCompositionFixture, history: { items: [cueCompositionFixture], next_after: null, limit: 50 } };

export const cueCheckpointFixture: BoundaryCueData = {
  ...cueCurrentFixture,
  catalog: { ...cueCatalogFixture, groups: [...cueCatalogFixture.groups,
    { key: "extra", version: 1, name: "Extra greetings", category: "Stage", phrases: [
      { text: "OUR shared phrase", role: "start", default: true, evidence: "R [3]" },
      { text: "Extra opening", role: "start", default: true, evidence: "M 1/2" },
    ] },
    { key: "wraps", version: 1, name: "Studio: wraps", category: "Studio", phrases: [
      { text: "moving on", role: "end", default: true, evidence: "M 1/4 ⚠" },
    ] },
    { key: "slate", version: 1, name: "Studio: slate and takes", category: "Studio", phrases:
      ["rolling", "speed", "action", "cut", "reset"].map((text) => ({ text, role: "segment" as const, default: true, evidence: "R ⚠" })),
    },
    { key: "regional", version: 1, name: "Regional greetings", category: "Regional add-ons (never pre-ticked)", phrases: [
      { text: "Regional hello", role: "start", default: true, evidence: "R" },
    ] },
  ] },
};
