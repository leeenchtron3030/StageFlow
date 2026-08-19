export interface UuidCryptoSource {
  randomUUID?: () => string;
  getRandomValues(array: Uint8Array): Uint8Array;
}

function hexadecimal(byte: number): string {
  return byte.toString(16).padStart(2, "0");
}

export function generateUuidV4(
  source: UuidCryptoSource | undefined = globalThis.crypto,
): string {
  if (typeof source?.randomUUID === "function") {
    return source.randomUUID.call(source);
  }

  if (typeof source?.getRandomValues !== "function") {
    throw new Error("Cryptographically secure UUID generation is unavailable");
  }

  const bytes = source.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const value = Array.from(bytes, hexadecimal).join("");
  return (
    value.slice(0, 8) +
    "-" +
    value.slice(8, 12) +
    "-" +
    value.slice(12, 16) +
    "-" +
    value.slice(16, 20) +
    "-" +
    value.slice(20)
  );
}
