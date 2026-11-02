/** Webdev also uses the Czech language code as a GEO value. */
export function siteGeoFilterCode(value: string | null | undefined): string {
  const normalized = (value || "").trim().toUpperCase();
  const parts = normalized.split(/[-_]/).filter(Boolean);
  const code = parts.length > 1
    ? [...parts].reverse().find(part => /^[A-Z]{2}$/.test(part)) || normalized
    : normalized;
  return code === "CS" ? "CZ" : code;
}
