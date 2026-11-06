/** Keep the destination path and its case; trim only pasted URL prefixes. */
export function normalizeRedirectAddress(value: string): string {
  return value.trim().replace(/^\/+/, "").replace(/^https?:\/\//i, "").replace(/^\/+/, "");
}
