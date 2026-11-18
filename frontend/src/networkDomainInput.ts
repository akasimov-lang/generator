/** Normalize pasted domain lists without turning page URLs into other domains. */
export function parseNetworkDomainInput(value: string): string[] {
  const text = value
    .replace(/\[[^\]]*\]\(([^\s)]+)\)/g, "$1")
    .replace(/^\s*(?:[-*•]|\d+[.)])\s+/gm, "")
    .replace(/\\([:/])/g, "$1");
  const domains = text.split(/[\s,;]+/).map(token => token
    .replace(/^<|>$/g, "")
    .replace(/^\/+/, "")
    .replace(/^https?:\/+/i, "")
    .replace(/^\/+|\/+$/g, "")
    .replace(/\.$/, "")
    .toLowerCase()
  ).filter(Boolean);
  return [...new Set(domains)];
}

export function formatNetworkDomainInput(value: string): string {
  return parseNetworkDomainInput(value).join("\n");
}
