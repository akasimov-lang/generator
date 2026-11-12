import React from "react";
import { FakeMainQueue } from "./fakeMainQueue";
import { queuePollDue } from "./projectExchange";

export function useFakeMainQueue<T>(siteId: string, api: <R>(path: string, options?: RequestInit) => Promise<R>, networkBusy = false) {
  const apiRef = React.useRef(api); apiRef.current = api;
  const queue = React.useMemo(() => new FakeMainQueue<T>(siteId, (path, options) => apiRef.current(path, options)), [siteId]);
  React.useEffect(() => {
    queue.setNetworkBusy(networkBusy);
    if (!networkBusy) void queue.refresh();
  }, [queue, networkBusy]);
  const [, render] = React.useReducer(value => value + 1, 0);
  React.useEffect(() => {
    const unsubscribe = queue.subscribe(render);
    void queue.refresh();
    let lastRead = Date.now();
    const timer = window.setInterval(() => {
      const now = Date.now();
      if (queuePollDue(queue.count, lastRead, now, document.hidden)) { lastRead = now; void queue.refresh(); }
    }, 3000);
    return () => { unsubscribe(); window.clearInterval(timer); };
  }, [queue]);
  return queue;
}
