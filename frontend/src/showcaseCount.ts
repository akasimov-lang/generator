export type ShowcaseSummary = {
  rows: { brand: string }[];
  management?: { complete: boolean; sources?: { kind: string }[] };
};

export function showcaseBrandCount(showcase: ShowcaseSummary): number | null {
  if (!showcase.management?.complete || showcase.management.sources?.some(source => source.kind === "external")) return null;
  const brands = showcase.rows.map(row => row.brand.normalize("NFKC").toLowerCase()
    .replace(/\s*casino\s*$/, "").replace(/[^\p{L}\p{N}_]/gu, "")).filter(Boolean);
  return new Set(brands).size;
}
