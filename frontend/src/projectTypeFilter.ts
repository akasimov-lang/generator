export type ProjectTypeFilter = "monobrand" | "general";
export function projectType(site: {site_type?: string | null; brand?: string | null}): ProjectTypeFilter {
  if (site.site_type === "monobrand" || site.site_type === "general") return site.site_type;
  return site.brand?.trim() && site.brand.trim().toLowerCase() !== "общие ключи" ? "monobrand" : "general";
}
export function projectTypeFilter(search: string): ProjectTypeFilter | null {
  const value = new URLSearchParams(search).get("projectType");
  return value === "monobrand" || value === "general" ? value : null;
}
export function matchesProjectType(site: {site_type?: string | null; brand?: string | null}, filter: ProjectTypeFilter | null): boolean {
  return !filter || projectType(site) === filter;
}
