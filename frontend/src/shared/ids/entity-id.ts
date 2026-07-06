declare const entityIdBrand: unique symbol;

export type EntityId = string & {
  readonly [entityIdBrand]: "EntityId";
};

export function createEntityId(value: string): EntityId {
  assertUuidCompatible(value, "EntityId");
  return value as EntityId;
}

export function generateEntityId(): EntityId {
  return createEntityId(crypto.randomUUID());
}

function assertUuidCompatible(value: string, label: string): void {
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value)) {
    throw new Error(`${label} must be UUID-compatible.`);
  }
}
