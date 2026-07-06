import type { CorrelationId } from "@/shared/ids/correlation-id";
import type { EntityId } from "@/shared/ids/entity-id";
import type { Timestamp } from "@/shared/time/clock";

export type DomainEventMetadata = Readonly<Record<string, unknown>>;

export type DomainEvent = Readonly<{
  eventId: EntityId;
  eventType: string;
  occurredAt: Timestamp;
  correlationId: CorrelationId;
  actor?: string;
  metadata?: DomainEventMetadata;
}>;
