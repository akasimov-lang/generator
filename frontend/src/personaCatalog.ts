export type PersonaAward = { title: string; year: number };
export type Persona = {
  id: string; first_name: string; last_name: string; geo: string; country: string; flag: string;
  language: string; specialization: string; specializations: string[]; awards: PersonaAward[];
  biography: string; biography_excerpt?: string; word_count: number; portrait_url: string;
  fictional: boolean; revision: number; created_at: string; updated_at: string;
};
export type PersonaCountry = { code: string; name: string; flag: string; language: string; count: number };
export type PersonaCatalog = { items: Persona[]; total: number; countries: PersonaCountry[] };

const normalize = (value: string) => value.normalize("NFD").replace(/\p{M}/gu, "").replace(/ł/gi, "l").replace(/ø/gi, "o").toLocaleLowerCase().trim();
export function filterPersonas(items: Persona[], geo: string, query: string) {
  const words = normalize(query).split(/\s+/).filter(Boolean);
  return items.filter(item => (!geo || item.geo === geo) && words.every(word => normalize([
    item.first_name, item.last_name, item.geo, item.country, item.specialization, ...item.specializations,
  ].join(" ")).includes(word)));
}
export function personaWords(value: string) {
  return (value.match(/[\p{L}\p{N}]+(?:['’–-][\p{L}\p{N}]+)*/gu) || []).length;
}
export function personaId(path: string) {
  const match = path.match(/^\/personas\/([a-z0-9-]+)\/?$/);
  return match?.[1] || null;
}
