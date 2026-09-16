type Api = <T>(path: string, options?: RequestInit) => Promise<T>;

// Per workspace and user, keyed by project URL. Only reusable snapshots; live checks and job polling bypass it.
export function workspaceRequestCache(source: Api, ttl = 30_000) {
  const entries = new Map<string, { expires: number; pending: Promise<unknown> }>();
  const reusable = (path: string) => /^\/sites\/[^/]+\/(overview|sections|content|tasks|prompt-templates|publication-campaigns|publication-logs|network)(\?|$)/.test(path)
    || path.startsWith("/menu-templates?") || /^\/auto-reglue\/projects\/[^/?]+$/.test(path);
  const clear = () => entries.clear();
  const api: Api = async <T,>(path: string, options?: RequestInit): Promise<T> => {
    const method = (options?.method || "GET").toUpperCase();
    if (method !== "GET") {
      clear();
      try { return await source<T>(path, options); }
      finally { clear(); }
    }
    if (!reusable(path)) return source<T>(path, options);
    const key = path.replace(/\?refresh=true$/, "");
    if (options?.cache === "no-store") entries.delete(key);
    const cached = entries.get(key);
    if (cached && cached.expires > Date.now()) return cached.pending as Promise<T>;
    const entry = { expires: Infinity, pending: Promise.resolve() as Promise<unknown> };
    entry.pending = source<T>(path, options).then(value => {
      entry.expires = Date.now() + ttl;
      return value;
    }).catch(error => {
      if (entries.get(key) === entry) entries.delete(key);
      throw error;
    });
    entries.set(key, entry);
    if (entries.size > 200) entries.delete(entries.keys().next().value!);
    return entry.pending as Promise<T>;
  };
  return { api, clear };
}
