export const PROJECT_HISTORY_EVENT = "pagepilot-project-history-changed";

export function projectHistoryChanged(siteId: string) {
  if (typeof window !== "undefined") window.dispatchEvent(new CustomEvent(PROJECT_HISTORY_EVENT, {detail: {siteId}}));
}

/** Refresh saved history only; never reload Webdev or replace form drafts. */
export function subscribeProjectHistory<T>(siteId: string, api: <R>(path: string, options?: RequestInit) => Promise<R>, receive: (history: T) => void) {
  let controller: AbortController | undefined;
  const refresh = async (event: Event) => {
    if ((event as CustomEvent<{siteId: string}>).detail.siteId !== siteId) return;
    controller?.abort();
    const request = new AbortController(); controller = request;
    try {
      const history = await api<T>(`/sites/${encodeURIComponent(siteId)}/network/history`, {cache: "no-store", signal: request.signal});
      if (!request.signal.aborted) receive(history);
    } catch { /* Keep the saved history; the next refresh reads it from the database. */ }
  };
  window.addEventListener(PROJECT_HISTORY_EVENT, refresh);
  return () => { controller?.abort(); window.removeEventListener(PROJECT_HISTORY_EVENT, refresh); };
}
