type Api = <T>(path: string, options?: RequestInit) => Promise<T>;
export const isProjectGscRequest = (path: string) => /^\/sites\/[^/?]+\/gsc(?:\?|$)/.test(path);
type Snapshot = {
  value: string;
  loaded: boolean;
  status: "loading" | "saved" | "dirty" | "saving" | "error";
};

/** One project, one serialized save queue; no browser storage or external integrations. */
export function projectGscState(siteId: string, api: Api, delay = 700) {
  const path = `/sites/${encodeURIComponent(siteId)}/gsc`;
  let state: Snapshot = {value: "", loaded: false, status: "loading"};
  let saved = "";
  let loadRequest: Promise<void> | undefined;
  let saveRequest: Promise<void> | undefined;
  let timer: ReturnType<typeof setTimeout> | undefined;
  const listeners = new Set<() => void>();
  const update = (changes: Partial<Snapshot>) => {
    state = {...state, ...changes};
    listeners.forEach(listener => listener());
  };
  const clearTimer = () => { clearTimeout(timer); timer = undefined; };
  async function load() {
    if (state.loaded) return;
    if (loadRequest) return loadRequest;
    update({status: "loading"});
    loadRequest = (async () => {
      try {
        const result = await api<{value: string}>(path);
        saved = result.value;
        update({value: saved, loaded: true, status: "saved"});
      } catch { update({status: "error"}); }
      finally { loadRequest = undefined; }
    })();
    return loadRequest;
  }
  async function flush() {
    clearTimer();
    if (!state.loaded) return;
    if (saveRequest) return saveRequest;
    if (state.value === saved) { update({status: "saved"}); return; }
    saveRequest = (async () => {
      try {
        while (state.value !== saved) {
          const value = state.value;
          update({status: "saving"});
          await api<{value: string}>(path, {method: "PUT", body: JSON.stringify({value})});
          saved = value;
        }
        update({status: "saved"});
      } catch { update({status: "error"}); }
      finally { saveRequest = undefined; }
    })();
    return saveRequest;
  }
  return {
    snapshot: () => state,
    subscribe: (listener: () => void) => { listeners.add(listener); return () => { listeners.delete(listener); }; },
    load, flush,
    edit(value: string) {
      if (!state.loaded) return;
      clearTimer();
      update({value, status: "dirty"});
      timer = setTimeout(() => void flush(), delay);
    },
  };
}
