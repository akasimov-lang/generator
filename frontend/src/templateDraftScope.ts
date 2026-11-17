import { TEMPLATE_GEOS, TEMPLATE_LANGUAGES, languageForGeo } from "./templateLocaleOptions";

export type DraftScope = { brand: string; geo: string; language: string; brandEdited: boolean };
export type DraftScopeSource = { id: string; hasHtml: boolean; suggestedGeo?: string; suggestedLanguage?: string };
type Storage = Pick<globalThis.Storage, "getItem" | "setItem">;
const prefix = "pagepilot:competitor-draft-scope:v1:";
const countryCodes = new Set(TEMPLATE_GEOS.map(option => option.value));
const languageCodes = new Set(TEMPLATE_LANGUAGES.map(option => option.value));

export function normalizeDraftGeo(value: string): string {
  const code = value.trim().replace(/_/g, "-").split("-").pop()?.toUpperCase() || "";
  const country = code === "UK" ? "GB" : code;
  return countryCodes.has(country) ? country : "";
}

export function normalizeDraftLanguage(value: string): string {
  const code = value.trim().replace(/_/g, "-").split("-")[0].toLowerCase();
  return languageCodes.has(code) ? code : "";
}

/** Country is suggested only by explicit page metadata or a matching country domain. */
export function sourceLocaleHint(url: string, htmlLanguage: string, ogLocale = "") {
  const locale = htmlLanguage.trim() || ogLocale.trim();
  const language = normalizeDraftLanguage(locale);
  let geo = locale.includes("-") || locale.includes("_") ? normalizeDraftGeo(locale) : "";
  if (!geo && ogLocale && normalizeDraftLanguage(ogLocale) === language && /[-_]/.test(ogLocale)) geo = normalizeDraftGeo(ogLocale);
  if (!geo && language) {
    try {
      const hostname = new URL(url.includes("://") ? url : `https://${url}`).hostname;
      const country = normalizeDraftGeo(hostname.split(".").pop() || "");
      // These country suffixes are also widely used by unrelated global sites.
      if (country && !["AI", "IO", "ME", "TV", "CO", "CC", "WS", "SH", "LY", "GG"].includes(country) && languageForGeo(country) === language) geo = country;
    } catch { /* Missing or invalid source URL is not a locale hint. */ }
  }
  return { suggestedGeo: geo, suggestedLanguage: language };
}

export function readDraftScope(sources: DraftScopeSource[], storage?: Storage | null): DraftScope | null {
  const htmlSources = sources.filter(source => source.hasHtml && source.id);
  if (!htmlSources.length || !storage) return null;
  try {
    const saved = htmlSources.map(source => JSON.parse(storage.getItem(prefix + source.id) || "null") as Partial<DraftScope> | null);
    if (saved.some(scope => !scope || !normalizeDraftGeo(String(scope.geo || "")) || !normalizeDraftLanguage(String(scope.language || "")))) return null;
    const first = saved[0]!;
    if (saved.some(scope => scope!.geo !== first.geo || scope!.language !== first.language || scope!.brand !== first.brand)) return null;
    return { brand: String(first.brand || ""), geo: normalizeDraftGeo(String(first.geo)),
      language: normalizeDraftLanguage(String(first.language)), brandEdited: first.brandEdited === true };
  } catch { return null; }
}

export function hasStoredDraftScope(sources: DraftScopeSource[], storage?: Storage | null): boolean {
  try { return !!storage && sources.some(source => source.hasHtml && source.id && storage.getItem(prefix + source.id)); }
  catch { return false; }
}

export function saveDraftScope(sources: DraftScopeSource[], scope: DraftScope, storage?: Storage | null) {
  if (!storage || !normalizeDraftGeo(scope.geo) || !normalizeDraftLanguage(scope.language)) return;
  try {
    for (const source of sources.filter(source => source.hasHtml && source.id)) storage.setItem(prefix + source.id, JSON.stringify(scope));
  } catch { /* Storage restrictions must not block uploading or saving competitors. */ }
}

export function recoverDraftLocale(current: {geo: string; language: string}, sources: DraftScopeSource[], saved: DraftScope | null, edited: {geo: boolean; language: boolean} = {geo: false, language: false}) {
  const htmlSources = sources.filter(source => source.hasHtml);
  const hints = htmlSources.length && htmlSources.every(source => source.suggestedGeo === htmlSources[0].suggestedGeo && source.suggestedLanguage === htmlSources[0].suggestedLanguage)
    ? htmlSources[0] : null;
  const geo = edited.geo ? current.geo : current.geo || saved?.geo || hints?.suggestedGeo || "";
  // A selected GEO wins over HTML from another country. Never silently move it.
  const language = edited.language ? current.language : current.language || (saved?.geo === geo ? saved.language : "") ||
    (hints?.suggestedGeo === geo ? hints.suggestedLanguage : "") || languageForGeo(geo);
  return { geo, language };
}
