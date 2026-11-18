import * as React from "react";

export type FieldChange = {before: string; after: string; domain: string; page_path?: string | null};
export function ProjectFieldChange({change}: {change: FieldChange}) {
  return <>
    <span>{change.domain}{change.page_path}</span>
    <details className="lastAlternatesChange"><summary>Значение до и после</summary>
      <div><strong>Было</strong><pre>{change.before || "Не заполнено"}</pre></div>
      <div><strong>Стало</strong><pre>{change.after || "Не заполнено"}</pre></div>
    </details>
  </>;
}
