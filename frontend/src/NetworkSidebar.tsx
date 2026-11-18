import React from "react";

/** Keep useful context visible even when the main network contains one domain. */
export function NetworkSidebar({children}: {children: React.ReactNode}) {
  const ref = React.useRef<HTMLElement>(null);
  React.useLayoutEffect(() => {
    const sidebar = ref.current;
    if (!sidebar) return;
    const history = sidebar.querySelector<HTMLElement>(".lastReglueSummary");
    const navigation = sidebar.querySelector<HTMLElement>(".networkBrandNavigation");
    const list = navigation?.querySelector("ul");
    const entries = Array.from(history?.querySelectorAll("article") || []).slice(0, 3);
    const measure = () => {
      // Expanded markup stays scrollable instead of lifting the 30-row ceiling.
      const historyHeight = entries.length ? entries.reduce((height, entry) => {
        const summary = entry.querySelector("details[open] > summary");
        const bounds = entry.getBoundingClientRect();
        const style = getComputedStyle(entry);
        const collapsedHeight = summary ? summary.getBoundingClientRect().bottom - bounds.top
          + parseFloat(style.paddingBottom) + parseFloat(style.borderBottomWidth) : bounds.height;
        return height + collapsedHeight;
      }, 0) : history ? Math.max(45, Array.from(history.children).reduce(
        (height, child) => height + child.getBoundingClientRect().height, 0)) : 0;
      // Reserve an extra slot for the current project, so four OTHER networks fit.
      const count = list ? Math.min(list.children.length, list.querySelector('[aria-current="page"]') ? 5 : 4) : 0;
      const rowHeight = list?.querySelector("li")?.getBoundingClientRect().height || 56;
      const listStyle = list ? getComputedStyle(list) : null;
      const listHeight = count * rowHeight + Math.max(0, count - 1) * (parseFloat(listStyle?.rowGap || "0") || 0)
        + (parseFloat(listStyle?.paddingTop || "0") || 0) + (parseFloat(listStyle?.paddingBottom || "0") || 0);
      const navHeight = navigation ? listHeight + (navigation.querySelector(".networkBrandNavigationHeading")?.getBoundingClientRect().height || 0) + 2 : 0;
      sidebar.style.setProperty("--network-history-min", `${Math.ceil(historyHeight)}px`);
      sidebar.style.setProperty("--network-peers-min", `${Math.ceil(navHeight)}px`);
      sidebar.style.setProperty("--network-peers-list-min", `${Math.ceil(listHeight)}px`);
      sidebar.style.setProperty("--network-sidebar-min", `${Math.ceil(historyHeight + navHeight + (history && navigation ? 12 : 0))}px`);
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(sidebar);
    entries.forEach(entry => observer.observe(entry));
    const heading = navigation?.querySelector(".networkBrandNavigationHeading");
    if (heading) observer.observe(heading);
    return () => observer.disconnect();
  });
  return <aside ref={ref} className="networkSidebar">{children}</aside>;
}
