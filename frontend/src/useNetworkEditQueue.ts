import React from "react";
import { NetworkEditQueue } from "./networkEditQueue";

export function useNetworkEditQueue<T>(siteId: string, api: <R>(path: string, options?: RequestInit) => Promise<R>, networkBusy = false) {
  const apiRef = React.useRef(api); apiRef.current = api;
  const queue = React.useMemo(() => new NetworkEditQueue<T>(siteId, (path, options) => apiRef.current(path, options)), [siteId]);
  const [, render] = React.useReducer(value => value + 1, 0);
  React.useEffect(() => {
    const unsubscribe = queue.subscribe(render);
    void queue.refresh();
    const timer = window.setInterval(() => { void queue.refresh(); }, 3000);
    return () => { unsubscribe(); window.clearInterval(timer); };
  }, [queue]);
  React.useEffect(() => {
    queue.setNetworkBusy(networkBusy);
    if (!networkBusy) void queue.refresh();
  }, [queue, networkBusy]);
  return queue;
}
