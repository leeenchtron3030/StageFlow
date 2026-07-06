export type ErrorDetails = Readonly<Record<string, unknown>>;

export type StageFlowErrorCategory =
  | "validation"
  | "domain"
  | "infrastructure"
  | "integration"
  | "configuration";

export type StageFlowError = Readonly<{
  category: StageFlowErrorCategory;
  code: string;
  message: string;
  details?: ErrorDetails;
}>;

export function createStageFlowError(
  category: StageFlowErrorCategory,
  code: string,
  message: string,
  details?: ErrorDetails,
): StageFlowError {
  return details === undefined
    ? { category, code, message }
    : { category, code, message, details };
}

export function formatStageFlowError(error: StageFlowError): string {
  return `${error.code}: ${error.message}`;
}

export const createValidationError = (
  code: string,
  message: string,
  details?: ErrorDetails,
): StageFlowError => createStageFlowError("validation", code, message, details);

export const createDomainError = (
  code: string,
  message: string,
  details?: ErrorDetails,
): StageFlowError => createStageFlowError("domain", code, message, details);

export const createInfrastructureError = (
  code: string,
  message: string,
  details?: ErrorDetails,
): StageFlowError => createStageFlowError("infrastructure", code, message, details);

export const createIntegrationError = (
  code: string,
  message: string,
  details?: ErrorDetails,
): StageFlowError => createStageFlowError("integration", code, message, details);

export const createConfigurationError = (
  code: string,
  message: string,
  details?: ErrorDetails,
): StageFlowError => createStageFlowError("configuration", code, message, details);
