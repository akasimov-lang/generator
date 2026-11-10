import * as React from "react";
import { ExternalLink, RefreshCw, Search } from "lucide-react";
import { createVisiblePoll } from "./visiblePoll";
import "./styles/dashboard-fibery-tasks.css";

type Api = <T>(path: string, options?: RequestInit) => Promise<T>;
type Project = { id: string; name: string; fibery_name: string | null; main: string | null; url: string };
type Pending = { id: string; title: string; at: string; due_at?: string; status: string; error?: string; projects: Project[] };
type Task = Pending & { number: string; url: string; verified_at: string; kind: string; fibery_project_url: string | null; project_number: string };
type Feed = { total: number; items: Task[]; pending: Pending[]; next_before: string | null };
const date = new Intl.DateTimeFormat("ru-RU", { timeZone: "Europe/Moscow", day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
const formatDate = (value: string) => date.format(new Date(value));
const taskUrl = (value: string) => /^https:\/\/hzhz\.fibery\.io\/favorites\/Alfasearch_Config\/SEO_Tasks\/\d+$/.test(value);
const projectUrl = (value: string) => /^https:\/\/hzhz\.fibery\.io\/favorites\/Alfasearch_Config\/SEO_Projects\/\d+$/.test(value);

function Projects({ projects }: { projects: Project[] }) {
  return <>{projects.map(project => <span className="dashboardFiberyProject" key={project.id}>
    <a href={project.url}>{project.name}</a>
    {project.fibery_name && <small>{project.fibery_name}</small>}
    {project.main && project.main !== project.name && <small>Main: {project.main}</small>}
  </span>)}</>;
}

export function FiberyTaskRow({ task }: { task: Task }) {
  return <li className="dashboardFiberyTask">
    <div className="dashboardFiberyDate"><time dateTime={task.at}>{formatDate(task.at)}</time><small>{task.kind === "reglue" ? "Переклей" : "SEO-работы"}</small></div>
    <div className="dashboardFiberyDetails"><strong>{task.title}</strong><Projects projects={task.projects} />
      {!task.projects.length && task.fibery_project_url && projectUrl(task.fibery_project_url) && <a href={task.fibery_project_url} target="_blank" rel="noopener noreferrer">Проект Fibery #{task.project_number}</a>}
    </div>
    <div className="dashboardFiberyLinks"><span className="dashboardFiberyStatus">Создана · #{task.number}</span>
      {taskUrl(task.url) && <a className="button secondary compact" href={task.url} target="_blank" rel="noopener noreferrer">Открыть задачу <ExternalLink size={14} /></a>}
    </div>
  </li>;
}

export function DashboardFiberyTasks({ api }: { api: Api }) {
  const [data, setData] = React.useState<Feed | null>(null);
  const [input, setInput] = React.useState("");
  const [query, setQuery] = React.useState("");
  const [cursors, setCursors] = React.useState<string[]>([]);
  const [error, setError] = React.useState("");
  const [reload, setReload] = React.useState(0);
  const before = cursors.at(-1) || "";
  React.useEffect(() => {
    const timer = window.setTimeout(() => { setQuery(input.trim()); setCursors([]); }, 300);
    return () => window.clearTimeout(timer);
  }, [input]);
  React.useEffect(() => {
    let live = true;
    setData(null); setError("");
    const stop = createVisiblePoll({ intervalMs: 15000, immediate: true, load: async () => {
        const result = await api<Feed>(`/dashboard-activity/fibery-tasks?q=${encodeURIComponent(query)}&before=${encodeURIComponent(before)}`);
        if (live) { setData(result); setError(""); }
      }, onError: e => { if (live) setError(e instanceof Error ? e.message : "Не удалось загрузить задачи Fibery."); }
    });
    return () => { live = false; stop(); };
  }, [api, query, before, reload]);
  return <section className="dataPanel dashboardFibery" aria-labelledby="dashboard-fibery-title">
    <header><h2 id="dashboard-fibery-title">Задачи Fibery{data && <span className="dashboardFiberyCount">{data.total}</span>}</h2>
      <button className="button secondary compact" type="button" onClick={() => setReload(n => n + 1)}><RefreshCw size={16} />Обновить</button></header>
    <p className="fieldHint">Все задачи, созданные из PagePilot · дата первой записи, МСК · автообновление каждые 15 секунд.</p>
    <label className="dashboardFiberySearch"><Search size={17} aria-hidden="true" /><input type="search" aria-label="Поиск задач Fibery" placeholder="Задача, номер, домен или имя проекта Fibery" maxLength={200} value={input} onChange={e => setInput(e.target.value)} /></label>
    {error && <p className="formError" role="alert">{error}{data && " Показаны последние полученные данные."}</p>}
    {!data && !error && <p role="status">Загружаем задачи…</p>}
    {data && <>
      {!!data.pending.length && <details className="dashboardFiberyPending" open><summary>Подготовка и ошибки · {data.pending.length}</summary>
        <ul>{data.pending.map(task => <li key={task.id}><strong>{task.title}</strong><Projects projects={task.projects} />
          <span>{task.status === "error" ? "Не удалось подтвердить создание" : task.status === "running" ? "Создаём задачу" : "Собираем работы после переклея"}</span>
          {task.error && <small className="formError">{task.error}</small>}
          {task.due_at && <small>Создание не ранее {formatDate(task.due_at)} МСК</small>}
        </li>)}</ul></details>}
      {!!data.items.length && <ul className="dashboardFiberyList">{data.items.map(task => <FiberyTaskRow key={task.id} task={task} />)}</ul>}
      {!data.items.length && <p>{query ? "По вашему запросу задачи не найдены." : before ? "На этой странице задач больше нет." : "Созданных задач пока нет. После подтверждения они появятся здесь автоматически."}</p>}
      {(cursors.length > 0 || data.next_before) && <nav className="dashboardFiberyPagination" aria-label="Страницы задач Fibery">
        <button type="button" className="button secondary compact" disabled={!cursors.length} onClick={() => setCursors(values => values.slice(0, -1))}>Предыдущие</button>
        <span>Страница {cursors.length + 1} · найдено {data.total}</span>
        <button type="button" className="button secondary compact" disabled={!data.next_before} onClick={() => { if (data.next_before) setCursors(values => [...values, data.next_before!]); }}>Следующие</button>
      </nav>}
    </>}
  </section>;
}
