/** Pages includes the homepage, matching the project overview counter. */
export function projectPagesCount(project: { internal_pages_count?: number | null }): number | null {
  const count = project.internal_pages_count;
  return typeof count === "number" && Number.isInteger(count) && count >= 0 ? count + 1 : null;
}

/** Upgrade saved table preferences without resetting the user's column order. */
export function addPagesColumn<T extends string>(columns: readonly T[]): (T | "pagesCount")[] {
  if (columns.includes("pagesCount" as T)) return [...columns];
  const result: (T | "pagesCount")[] = [...columns];
  const showcase = result.indexOf("subdomainsCount" as T);
  result.splice(showcase < 0 ? result.length : showcase + 1, 0, "pagesCount");
  return result;
}
