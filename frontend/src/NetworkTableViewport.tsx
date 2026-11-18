import React from "react";

const VISIBLE_ROWS = 30;

export function NetworkTableViewport({ rowKey, rowCount, children }: {
  rowKey: string; rowCount: number; children: React.ReactNode;
}) {
  const ref = React.useRef<HTMLDivElement>(null);
  const limited = rowCount > VISIBLE_ROWS;
  React.useLayoutEffect(() => {
    const viewport = ref.current;
    if (!viewport) return;
    viewport.scrollTop = 0;
    if (!limited) {
      viewport.style.removeProperty("max-height");
      return;
    }
    const table = viewport.querySelector("table");
    if (!table) return;
    const measure = () => {
      const lastVisibleRow = table.tBodies[0]?.rows[VISIBLE_ROWS - 1];
      if (!lastVisibleRow) return;
      const height = lastVisibleRow.getBoundingClientRect().bottom
        - viewport.getBoundingClientRect().top + viewport.scrollTop
        + viewport.offsetHeight - viewport.clientHeight;
      viewport.style.maxHeight = `${Math.ceil(height)}px`;
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(table);
    return () => observer.disconnect();
  }, [rowKey, limited]);
  return <div ref={ref} className={`networkTableWrap${limited ? " networkTableWrapLimited" : ""}`}
    tabIndex={0} role="region" aria-label="Домены сетки">{children}</div>;
}
