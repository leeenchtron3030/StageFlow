export type Timestamp = string;

export type Clock = Readonly<{
  now: () => Timestamp;
}>;

export const systemClock: Clock = {
  now: () => new Date().toISOString(),
};

export function createFixedClock(fixedAt: Timestamp): Clock {
  return {
    now: () => fixedAt,
  };
}
