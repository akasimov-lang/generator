export type BonusFact = { label: string; value: string };
export type BrandOffer = { id: string; title: string; category: string; facts: BonusFact[]; observed_at: string; status: "saved" | "verified" | "expired"; valid_until?: string };
export type BonusBrand = { id: string; name: string; geo: string; logo_url: string; offers: BrandOffer[] };
export type BonusCatalog = { updated_at: string; items: BonusBrand[]; total: number; offers_total: number; countries: { code: string; name: string; flag: string; brands: number; offers: number }[] };

export function bonusRoute(path: string) {
  const match = /^\/brand-bonuses(?:\/(pl|cz)(?:\/([a-z0-9-]+))?)?\/?$/i.exec(path);
  return match ? { geo: (match[1] || "").toUpperCase(), id: match[2] || "", valid: true } : { geo: "", id: "", valid: false };
}
export function bonusPath(geo = "", id = "") { return `/brand-bonuses${geo ? `/${geo.toLowerCase()}` : ""}${id ? `/${id}` : ""}`; }
function searchText(text: string) { return text.toLocaleLowerCase().normalize("NFKD").replace(/\p{M}/gu, "").replace(/ł/g, "l"); }
export function filterBonusBrands(items: BonusBrand[], geo: string, query: string) {
  const words = searchText(query.trim()).split(/\s+/).filter(Boolean);
  return items.filter(item => (!geo || item.geo === geo) && words.every(word => searchText([item.name, ...item.offers.flatMap(offer => [offer.title, ...offer.facts.map(f => f.value)])].join(" ")).includes(word)));
}
