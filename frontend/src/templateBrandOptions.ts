export type TemplateProject = { brand?: string; cache_geo?: string | null; is_active?: boolean };
export type KnowledgeScope = { brand: string; geo: string; count: number };
const key = (value: string) => value.toLocaleLowerCase().replace(/[^\p{L}\p{N}]/gu, "");
export const isGeneralBrand = (brand: string) => ["общиеключи", "онлайнказино", "onlinecasino"].includes(key(brand));
const geoCode = (value?: string | null) => (value || "").toUpperCase().split(/[-_]/).filter(Boolean).pop() || "";
export function templateBrandOptions(projects: TemplateProject[], scopes: KnowledgeScope[], geo: string) {
  const names = [...projects.filter(p => p.is_active !== false && geoCode(p.cache_geo) === geo).map(p => p.brand || "Общие ключи"), ...scopes.filter(s => s.geo === geo).map(s => s.brand)];
  const brands = new Map<string, string>();
  names.filter(name => !isGeneralBrand(name)).forEach(name => brands.set(key(name), name.trim()));
  return [{ value: "Онлайн казино", label: "Онлайн казино — общие ключи", keywords: "Общие ключи" }, ...[...brands.values()].sort((a,b) => a.localeCompare(b)).map(value => ({value,label:value,keywords:key(value)}))];
}
