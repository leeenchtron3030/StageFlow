import type { Timestamp } from "@/shared/time/clock";

export type TimeRange = Readonly<{
  start: Timestamp;
  end: Timestamp;
  durationMs: number;
}>;

export function createTimeRange(start: Timestamp, end: Timestamp): TimeRange {
  const startMs = Date.parse(start);
  const endMs = Date.parse(end);

  if (!Number.isFinite(startMs) || !Number.isFinite(endMs)) {
    throw new Error("TimeRange requires parseable timestamps.");
  }

  if (endMs <= startMs) {
    throw new Error("TimeRange end must be after start.");
  }

  return {
    start,
    end,
    durationMs: endMs - startMs,
  };
}
