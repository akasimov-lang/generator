const filters = ["reserve_drops", "newregs", "drops", "other", "internal_pages"] as const;
export type PilotDomainFilter = typeof filters[number];
export function pilotDomainFilter(search: string): PilotDomainFilter | null {
  const value = new URLSearchParams(search).get("domainFilter");
  return filters.includes(value as PilotDomainFilter) ? value as PilotDomainFilter : null;
}
export function pilotFilterReturnPath(value: string | null): string | null {
  if (!value || !value.startsWith("/") || value.startsWith("//") || /[\\\u0000-\u0020]/.test(value)) return null;
  try {
    const url = new URL(value, "https://pagepilot.invalid");
    if (!["/auto-reglue/pilot", "/auto-reglue/pilot/logs", "/auto-reglue/pilot/report"].includes(url.pathname)) return null;
    const maintenance = url.pathname === "/auto-reglue/pilot/report" && url.searchParams.get("maintenance");
    if (!maintenance && (!url.searchParams.get("id") || !pilotDomainFilter(url.search))) return null;
    return url.pathname + url.search + url.hash;
  } catch { return null; }
}
export function projectFromPilotFilter(path: string, report: string | null): string {
  const from = pilotFilterReturnPath(report);
  return from ? `${path}?${new URLSearchParams({pilotReturn: from})}` : path;
}
