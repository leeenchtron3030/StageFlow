import assert from "node:assert/strict";
import test from "node:test";

import { createDemoCommandEnvelope } from "../../experience/demo-api.ts";
import { generateCorrelationId } from "./correlation-id.ts";
import { generateEntityId } from "./entity-id.ts";
import { generateUuidV4, type UuidCryptoSource } from "./uuid-v4.ts";

const nativeUuid = "12345678-1234-4abc-9def-1234567890ab";
const uuidV4Pattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

function fallbackSource(seed = 0): UuidCryptoSource {
  return {
    getRandomValues(array) {
      for (let index = 0; index < array.length; index += 1) {
        array[index] = (seed + index) & 0xff;
      }
      return array;
    },
  };
}

test("UUID generation uses native randomUUID when available", () => {
  let randomValuesCalled = false;
  const source: UuidCryptoSource = {
    randomUUID: () => nativeUuid,
    getRandomValues(array) {
      randomValuesCalled = true;
      return array;
    },
  };

  assert.equal(generateUuidV4(source), nativeUuid);
  assert.equal(randomValuesCalled, false);
});

test("UUID generation uses getRandomValues when randomUUID is absent", () => {
  const originalMathRandom = Math.random;
  Math.random = () => {
    throw new Error("Math.random must not be used for identifiers");
  };
  try {
    const value = generateUuidV4(fallbackSource());
    assert.match(value, uuidV4Pattern);
    assert.equal(value[14], "4");
    assert.match(value[19], /[89ab]/);
  } finally {
    Math.random = originalMathRandom;
  }
});

test("UUID generation fails explicitly without cryptographically secure randomness", () => {
  assert.throws(
    () => generateUuidV4({} as UuidCryptoSource),
    /Cryptographically secure UUID generation is unavailable/,
  );
});

test("shared Entity and Correlation generators accept fallback UUID-v4 output", () => {
  const entityId = generateEntityId(fallbackSource(16));
  const correlationId = generateCorrelationId(fallbackSource(32));

  assert.match(entityId, uuidV4Pattern);
  assert.match(correlationId, uuidV4Pattern);
  assert.equal(entityId[14], "4");
  assert.match(entityId[19], /[89ab]/);
});

test("Demo command envelopes construct operation IDs without randomUUID", () => {
  const actorId = "10000000-0000-4000-8000-000000000001";
  const sessionId = "20000000-0000-4000-8000-000000000002";
  const start = createDemoCommandEnvelope(
    actorId,
    { stage_id: "30000000-0000-4000-8000-000000000003" },
    fallbackSource(48),
  );
  const other = createDemoCommandEnvelope(
    actorId,
    { session_id: sessionId, reason: "producer ended presentation" },
    fallbackSource(64),
  );

  assert.match(start.operation_id, uuidV4Pattern);
  assert.equal(start.actor_id, actorId);
  assert.equal(start.confirmed, "confirmed");
  assert.match(other.operation_id, uuidV4Pattern);
  assert.equal(other.session_id, sessionId);
  assert.equal(other.confirmed, "confirmed");
});
