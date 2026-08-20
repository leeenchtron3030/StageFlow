export const demoLaunchContextHeader = "x-stageflow-demo-launch-context";

export function demoProtectedHeaders(
  launchContext: string | undefined,
): Record<string, string> {
  return {
    "Content-Type": "application/json",
    ...(launchContext ? { [demoLaunchContextHeader]: launchContext } : {}),
  };
}

export function demoAuthorityHeaders(
  launchContext: string | undefined,
): Record<string, string> {
  return demoProtectedHeaders(launchContext);
}
