import punycode from "punycode/punycode.js";

/** Decode individual IDN labels so partial Cyrillic domain searches work too. */
export function normalizeProjectSearch(value: string): string {
  return value.toLowerCase().replace(/\bxn--[a-z0-9-]+/g, (label) => {
    try {
      return punycode.toUnicode(label);
    } catch {
      // An invalid cached domain must not break the project list.
      return label;
    }
  }).normalize("NFC");
}

export function projectSearchKeywords(values: string[]): string {
  const original = values.filter(Boolean).join(" ").toLowerCase();
  return `${original} ${normalizeProjectSearch(original)}`;
}

export function matchesProjectSearch(value: string, query: string): boolean {
  const keywords = projectSearchKeywords([value]);
  const normalizedQuery = query.trim().toLowerCase();
  return keywords.includes(normalizedQuery) || keywords.includes(normalizeProjectSearch(normalizedQuery));
}

/** Accept pasted URLs without changing ordinary project-name searches. */
export function normalizeDomainQuery(value: string): string {
  const query = value.trim().toLowerCase().replace(/^(?:https?|htpps):\/\//, "").replace(/^\/\//, "");
  if (/^[^\s/?#]+\.[^\s/?#]+/.test(query)) {
    return query.split(/[/?#]/, 1)[0].replace(/\.$/, "");
  }
  return query.replace(/\/+$/, "");
}

function domainSearchKey(value: string): string {
  return normalizeProjectSearch(normalizeDomainQuery(value));
}

export function isExactNetworkDomainSearch(domains: string[], query: string): boolean {
  const queryKey = domainSearchKey(query);
  return Boolean(queryKey) && domains.some((domain) => domainSearchKey(domain) === queryKey);
}
