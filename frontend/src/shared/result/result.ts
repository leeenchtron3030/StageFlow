import type { StageFlowError } from "@/shared/errors/errors";

export type Result<T> =
  | Readonly<{
      ok: true;
      value: T;
    }>
  | Readonly<{
      ok: false;
      error: StageFlowError;
    }>;

export function ok<T>(value: T): Result<T> {
  return { ok: true, value };
}

export function fail<T = never>(error: StageFlowError): Result<T> {
  return { ok: false, error };
}

export function isSuccess<T>(result: Result<T>): result is Extract<Result<T>, { ok: true }> {
  return result.ok;
}

export function isFailure<T>(result: Result<T>): result is Extract<Result<T>, { ok: false }> {
  return !result.ok;
}
