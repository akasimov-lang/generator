import React from "react";
import { createVisiblePoll } from "./visiblePoll";
import "./styles/menu-generation-tasks.css";

type Api = <T>(path: string, init?: RequestInit) => Promise<T>;
type Job = {
  id: string; status: string; error?: string; created_at: string; create_pages: boolean; project_name?: string;
  events?: { at: string; status: string; message: string }[];
  settings: { menu_type: string }; applied?: { page_task_error?: string };
  progress: { total: number; generated: number; published: number; deleted: number; errors: number };
  pages: { id: string; topic: string; slug: string; status: string; generation_progress: number; error?: string }[];
};
const labels: Record<string, string> = { queued: "В очереди", generating: "Генерация структуры меню",
  applying: "Добавление меню на сайт", awaiting_review: "Структура готова — ожидает принятия", failed: "Ошибка", expired: "Срок хранения истёк", cancelled: "Отменено" };
const pageLabels: Record<string, string> = { draft: "Ожидает генерации", queued: "В очереди", generating: "Генерация текста",
  generated: "Текст готов", approved: "Текст принят", publishing: "Публикация", published: "Опубликовано",
  publication_pending_confirmation: "Проверка публикации", publication_failed: "Ошибка публикации",
  generation_failed: "Ошибка генерации", deleted: "Удалено", scheduled: "Ожидает публикации", retry_scheduled: "Повторная публикация запланирована" };

export function MenuGenerationTasks({ api, siteId, projectName, showEmpty }: { api: Api; siteId?: string; projectName?: string; showEmpty: boolean }) {
  const [jobs, setJobs] = React.useState<Job[]>([]);
  const [error, setError] = React.useState("");
  const [loading, setLoading] = React.useState(true);
  React.useEffect(() => {
    let active = true;
    setJobs([]); setLoading(true);
    const stop = createVisiblePoll({ intervalMs: 5000, immediate: true, load: async () => {
      const result = await api<Job[]>(siteId ? `/sites/${siteId}/menu-generations` : '/menu-generations', { cache: "no-store" });
      if (active) { setJobs(result); setError(""); setLoading(false); }
    }, onError: cause => { if (active) { setError(cause instanceof Error ? cause.message : "Не удалось обновить задания меню"); setLoading(false); } } });
    return () => { active = false; stop(); };
  }, [api, siteId]);
  return <div className="menuGenerationTasks">
    {error && <p role="alert" className="formError">{error}</p>}
    {loading && <p role="status">Загружаем задания меню…</p>}
    {!loading && !error && !jobs.length && showEmpty && <p className="muted">Заданий пока нет.</p>}
    {jobs.map(job => {
      const p = job.progress;
      const status = job.status === "completed" ? job.applied?.page_task_error ? "Меню добавлено · ошибка создания страниц"
        : p.errors ? "Меню добавлено · есть ошибки страниц"
        : p.total && p.published + p.deleted < p.total ? "Меню добавлено · страницы в работе" : "Завершено" : labels[job.status] || job.status;
      const query = new URLSearchParams({ menuJob: job.id });
      const back = new URLSearchParams(window.location.search).get("pilotReturn");
      if (back) query.set("pilotReturn", back);
      return <article className="menuGenerationTask" key={job.id}>
        <div className="menuGenerationTaskHeader"><div><strong>Генерация меню{job.create_pages ? " и страниц" : ""} · {job.settings.menu_type === "header" ? "Header" : "Footer"}</strong>
          {!siteId && <small>{job.project_name}</small>}
          <small>{new Date(job.created_at).toLocaleString("ru-RU", { timeZone: 'Europe/Moscow' })} МСК · {status}</small></div>
          {!['expired', 'cancelled'].includes(job.status) && <a className="button secondary compact" href={`/project-menu/${encodeURIComponent(projectName || job.project_name || '')}/?${query}`}>Открыть результат</a>}</div>
        {p.total > 0 && <div className="menuGenerationTaskProgress"><span>Тексты: {p.generated} / {p.total}</span><progress aria-label="Готовые тексты" value={p.generated} max={p.total} />
          <span>Опубликовано: {p.published} / {p.total}{p.deleted ? ` · удалено: ${p.deleted}` : ""}{p.errors ? ` · ошибок: ${p.errors}` : ""}</span><progress aria-label="Опубликованные страницы" value={p.published} max={p.total} /></div>}
        {(job.error || job.applied?.page_task_error) && <p className="formError" role="alert">{job.error || job.applied?.page_task_error}</p>}
        {!!job.events?.length && <details><summary>Журнал этапов · {job.events.length}</summary>{job.events.map((event, index) => <small className="menuGenerationEvent" key={index}>{new Date(event.at).toLocaleString('ru-RU', { timeZone: 'Europe/Moscow' })} МСК · {event.message}</small>)}</details>}
        {!!job.pages.length && <details><summary>Страницы · {p.total}</summary><div className="menuGenerationTaskPages">{job.pages.map(page => <div key={page.id}><span>{page.topic}<small>{page.slug}</small></span><span>{pageLabels[page.status] || page.status}{page.status === "generating" ? ` · ${page.generation_progress}%` : ""}{page.error && <small className="formError">{page.error}</small>}</span></div>)}</div></details>}
      </article>;
    })}
  </div>;
}
