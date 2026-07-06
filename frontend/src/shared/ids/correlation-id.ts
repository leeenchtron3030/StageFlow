declare const correlationIdBrand: unique symbol;

export type CorrelationId = string & {
  readonly [correlationIdBrand]: "CorrelationId";
};

export function createCorrelationId(value: string): CorrelationId {
  assertUuidCompatible(value, "CorrelationId");
  return value as CorrelationId;
}

export function generateCorrelationId(): CorrelationId {
  return createCorrelationId(crypto.randomUUID());
}

function assertUuidCompatible(value: string, label: string): void {
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value)) {
    throw new Error(`${label} must be UUID-compatible.`);
  }
}
