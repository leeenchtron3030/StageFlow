const displayNames: Readonly<Record<string, string>> = {
  local_file: "Local schedule",
  devcon: "Devcon",
};

export function programProviderDisplayName(provider: string | undefined): string {
  if (provider === undefined) return "Provider unknown";
  return Object.hasOwn(displayNames, provider) ? displayNames[provider] : provider;
}
