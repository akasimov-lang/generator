import React from "react";

export type InternalPages = {
  enabled?: boolean; count: number; menu?: {title: string; slug: string}[];
  status?: string; reason?: string; task_id?: string;
  generated?: number; published?: number; failed?: number; progress?: number;
};

const labels: Record<string, string> = {
  planned: "Запланировано", queued: "В очереди", running: "Подготовка страниц",
  generating: "Генерация текстов", publishing: "Публикация", completed: "Опубликовано",
  waiting_reglue: "Тексты готовы · ждём завершения переклея",
  failed: "Ошибка", partial: "Частично", skipped: "Пропущено", cancelled: "Отменено", waiting: "Ждём подтверждения",
};

export function PilotInternalPages({data, project}: {data?: InternalPages; project: string}) {
  if (!data || data.enabled === false) return null;
  const active = data.status && data.status !== "planned";
  return <div className="pilotInternalPages">
    <strong>Внутренние страницы · {data.count}</strong>
    <small>Меню в один уровень · автопубликация</small>
    {active && <>
      <small>{labels[data.status!] || data.status}</small>
      <progress aria-label={`Внутренние страницы ${project}`} value={data.progress ?? 0} max={100}/>
      <small>Готово текстов: {data.generated ?? 0} · Опубликовано: {data.published ?? 0} / {data.count}{data.failed ? ` · Ошибок: ${data.failed}` : ""}</small>
    </>}
    {!!data.menu?.length && <details><summary>Пункты меню</summary>{data.menu.map(item => <small key={item.slug}>{item.title} · {item.slug}</small>)}</details>}
    {data.reason && <small role="status">{data.reason}</small>}
    {data.task_id && <a href={`/project-generation/${encodeURIComponent(project)}/`} onClick={() => {
      try { sessionStorage.setItem("workspace_open_task_id", data.task_id!); } catch { /* Project task list remains accessible. */ }
    }}>Открыть задание</a>}
  </div>;
}
