import "server-only";
import { isIP } from "node:net";

function validPort(value: string | undefined): value is string {
  return value !== undefined && /^[1-9][0-9]{0,4}$/.test(value) && Number(value) <= 65535;
}

/** Strict authorities only: no URL normalization, credentials, wildcards or suffix matching. */
function authority(value: string): { host: string; port: string } | undefined {
  const match = /^(\[[0-9a-fA-F:]+\]|[a-zA-Z0-9.-]+):([0-9]+)$/.exec(value);
  if (!match || !validPort(match[2])) return undefined;
  const host = match[1].toLowerCase();
  if (host.startsWith("[")) {
    if (isIP(host.slice(1, -1)) !== 6) return undefined;
  } else if (/^[0-9.]+$/.test(host)) {
    if (isIP(host) !== 4) return undefined;
  } else if (host.length > 253 || !host.split(".").every((label) =>
    /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/.test(label))) return undefined;
  return { host, port: match[2] };
}

export function isAllowedUiHost(hostHeader: string | null, serverPort: string | undefined, configured?: string): boolean {
  // The listening port is supplied by Next's server, never by URL/forwarded headers.
  if (!validPort(serverPort) || !hostHeader) return false;
  const supplied = authority(hostHeader);
  if (!supplied) return false;
  if (["localhost", "127.0.0.1", "[::1]"].includes(supplied.host) && supplied.port === serverPort) return true;
  return (configured ?? "").split(",").some((entry) => {
    const allowed = authority(entry.trim());
    return allowed?.host === supplied.host && allowed.port === supplied.port;
  });
}
