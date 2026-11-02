const detailDocument = crypto.randomUUID();

export function openDetailPage(path: string, parameters: Record<string, string> = {}) {
  const from = window.location.pathname + window.location.search + window.location.hash;
  sessionStorage.setItem(`detail-return:${from}`, JSON.stringify({ left: window.scrollX, top: window.scrollY }));
  window.history.pushState({ detailFrom: from, detailDocument }, "", `${path}?${new URLSearchParams({ ...parameters, from })}`);
  window.dispatchEvent(new PopStateEvent("popstate"));
  window.scrollTo(0, 0);
}

export function detailReturnPath(fallback = "/content") {
  const from = new URLSearchParams(window.location.search).get("from") || fallback;
  return from.startsWith("/") && !from.startsWith("//") && !from.includes("\\") ? from : fallback;
}

export function backFromDetail(fallback = "/content") {
  const from = detailReturnPath(fallback);
  if (window.history.state?.detailFrom === from && window.history.state?.detailDocument === detailDocument) window.history.back();
  else {
    window.history.replaceState(null, "", from);
    window.dispatchEvent(new PopStateEvent("popstate"));
  }
  const restore = () => {
    try { const position = JSON.parse(sessionStorage.getItem(`detail-return:${from}`) || "null"); if (position) window.scrollTo(position); } catch { /* No saved position. */ }
  };
  window.setTimeout(restore, 200);
}
