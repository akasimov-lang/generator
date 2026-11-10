import * as React from "react";
import { History, RefreshCw } from "lucide-react";
import { DashboardFiberyTasks } from "./DashboardFiberyTasks";
import "./styles/dashboard-activity.css";

type Api = <T>(path: string, options?: RequestInit) => Promise<T>;
type Entry = {
  id: string; kind: string; at: string; title: string; active: boolean; status: string;
  project?: string; project_url?: string; before?: string | null; after?: string | null;
  report_url?: string; report_number?: number | null; progress?: number; stage?: string;
  total?: number; done?: number;
};
type Feed = { active: Entry[]; items: Entry[]; next_before: string | null };
const date = new Intl.DateTimeFormat("ru-RU", { timeZone: "Europe/Moscow", day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit", second: "2-digit" });
const value = (text: string | null | undefined) => text == null ? "Нет данных" : text || "Не назначена";

function ActivityRow({ entry }: { entry: Entry }) {
  return <li className={`dashboardActivityRow${entry.active ? " isActive" : ""}`}>
    <time dateTime={entry.at}>{date.format(new Date(entry.at))}</time>
    <div className="dashboardActivityDetails">
      <strong>{entry.title}</strong>
      {entry.project_url && <a href={entry.project_url}>{entry.project}</a>}
      {entry.after !== undefined && <span className="dashboardActivityChange"><span>{value(entry.before)}</span><span aria-label="стало"> → </span><b>{value(entry.after)}</b></span>}
      {entry.report_url && <a href={entry.report_url}>Открыть отчёт{entry.report_number ? ` №${entry.report_number}` : ""}{entry.total !== undefined ? ` · проектов: ${entry.total}` : ""}</a>}
    </div>
    <div className={`dashboardActivityProgress status-${entry.status}`}>
      {entry.stage && <span>{entry.stage}</span>}
      {entry.progress !== undefined && <div className="dashboardActivityMeter"><progress aria-label={`Ход выполнения: ${entry.title}`} max={100} value={entry.progress} /><b>{entry.progress}%</b></div>}
    </div>
  </li>;
}

function LiveActivity({ api }: { api: Api }) {
  const [data, setData] = React.useState<Feed | null>(null);
  const [older, setOlder] = React.useState<Entry[]>([]);
  const [cursor, setCursor] = React.useState<string | null>(null);
  const [error, setError] = React.useState("");
  const [moreBusy, setMoreBusy] = React.useState(false);
  const [reload, setReload] = React.useState(0);
  const generation = React.useRef(0);
  React.useEffect(() => {
    const current = ++generation.current;
    let timer: number | undefined;
    const load = async () => {
      try {
        const result = await api<Feed>("/dashboard-activity");
        if (generation.current === current) { setData(result); setError(""); }
      } catch (e) {
        if (generation.current === current) setError(e instanceof Error ? e.message : "Не удалось обновить историю. Повторяем автоматически.");
      } finally {
        // Schedule after completion: slow requests never overlap.
        if (generation.current === current) timer = window.setTimeout(() => void load(), 5000);
      }
    };
    void load();
    return () => { generation.current++; window.clearTimeout(timer); };
  }, [api, reload]);
  async function more() {
    const next = older.length ? cursor : data?.next_before;
    if (!next || moreBusy) return;
    const current = generation.current;
    setMoreBusy(true);
    try {
      const result = await api<Feed>(`/dashboard-activity?before=${encodeURIComponent(next)}`);
      if (generation.current === current) { setOlder(rows => [...rows, ...result.items]); setCursor(result.next_before); }
    } catch (e) { if (generation.current === current) setError(e instanceof Error ? e.message : "Не удалось загрузить историю."); }
    finally { setMoreBusy(false); }
  }
  const seen = new Set(data?.active.map(row => row.id));
  const history = [...(data?.items || []), ...older].filter(row => {
    if (seen.has(row.id)) return false;
    seen.add(row.id); return true;
  });
  return <section className="dataPanel dashboardActivity" aria-labelledby="dashboard-activity-title">
    <header><h2 id="dashboard-activity-title"><History size={20} /> Живая история действий</h2>
      <button type="button" className="button secondary compact" onClick={() => setReload(n => n + 1)}><RefreshCw size={16} /> Обновить</button></header>
    <p className="fieldHint">Автообновление каждые 5 секунд · время МСК · процент выполнения этапов, включая завершившиеся с ошибкой.</p>
    {error && <p className="formError" role="alert">{error} Показаны последние полученные данные.</p>}
    {!data && !error && <p role="status">Загружаем историю…</p>}
    {!!data?.active.length && <div className="dashboardActivityActive"><h3>Выполняется · {data.active.length}</h3><ul>{data.active.map(entry => <ActivityRow key={entry.id} entry={entry} />)}</ul></div>}
    {data && !history.length && !data.active.length && <p>Действий пока нет.</p>}
    {!!history.length && <ul>{history.map(entry => <ActivityRow key={entry.id} entry={entry} />)}</ul>}
    {(older.length ? cursor : data?.next_before) && <button type="button" className="button secondary compact" disabled={moreBusy} onClick={() => void more()}>{moreBusy ? "Загружаем…" : "Показать более ранние действия"}</button>}
  </section>;
}

type MassReport = {
  id: string; created_at: string; actor: string; filter: { brand: string; geo: string };
  entries: { site_id: string; run_id?: string; target_project?: string; source_project?: string;
    status?: string; phase?: string; error?: string; message?: string; old_main?: string; new_main?: string;
    old_fake_main_path?: string | null; new_fake_main_path?: string | null; domains?: string[] }[];
  skipped: { project: string; error: string }[];
};
const statusLabels: Record<string, string> = { completed: "Подтверждено", partial: "Выполнено частично", failed: "Ошибка", cancelled: "Отменено", queued: "В очереди", running: "Выполняется", waiting: "Ожидает подтверждения", skipped: "Пропущено" };
function MassReportView({ api, id }: { api: Api; id: string }) {
  const [report, setReport] = React.useState<MassReport | null>(null);
  const [error, setError] = React.useState("");
  React.useEffect(() => {
    let live = true;
    let timer: number | undefined;
    async function load() {
      try {
        const result = await api<MassReport>(`/dashboard-activity/reports/${encodeURIComponent(id)}`);
        if (live) { setReport(result); setError(""); }
      } catch (e) { if (live) setError(e instanceof Error ? e.message : "Не удалось загрузить отчёт."); }
      finally { if (live) timer = window.setTimeout(() => void load(), 5000); }
    }
    void load();
    return () => { live = false; window.clearTimeout(timer); };
  }, [api, id]);
  return <section className="dataPanel dashboardActivity">
    <a href="/dashboard">← Живая история действий</a>
    <h2>Отчёт о массовых действиях{report && <> · {report.filter.brand} · {report.filter.geo}</>}</h2>
    {error && <p role="alert">{error}</p>}
    {!report && !error && <p>Загружаем отчёт…</p>}
    {report && <><p className="fieldHint">{date.format(new Date(report.created_at))} · {report.actor} · время МСК</p>
      <div className="tableScroll"><table className="reglueJournalTable"><thead><tr><th>Проект</th><th>Домены</th><th>Main: было → стало</th><th>Внутряк: было → стало</th><th>Результат</th></tr></thead>
        <tbody>{report.entries.map((row, index) => <tr key={row.run_id || `${row.site_id}:${index}`}>
          <td>{row.target_project ? <a href={`/project-network/${encodeURIComponent(row.target_project)}/`}>{row.target_project}</a> : "Нет данных"}{row.source_project && row.source_project !== row.target_project && <small>Из сетки: {row.source_project}</small>}</td>
          <td>{row.domains?.join(", ") || "—"}</td>
          <td>{value(row.old_main)} → <b>{row.new_main || "Не подтверждено"}</b></td>
          <td>{value(row.old_fake_main_path)} → <b>{row.new_fake_main_path || "Не подтверждено"}</b></td>
          <td>{statusLabels[row.status || ""] || "Подготовка"}{(row.error || row.message) && <small>{row.error || row.message}</small>}</td>
        </tr>)}</tbody></table></div>
      {!!report.skipped?.length && <details><summary>Пропущено: {report.skipped.length}</summary>{report.skipped.map((row, i) => <p key={i}>{row.project}: {row.error}</p>)}</details>}
    </>}
  </section>;
}

export function DashboardActivity({ api }: { api: Api }) {
  const report = new URLSearchParams(window.location.search).get("mass_report");
  const [collection, setCollection] = React.useState(() => new URLSearchParams(window.location.search).get("collection") === "fibery" ? "fibery" : "activity");
  function choose(value: string) {
    setCollection(value);
    const url = new URL(window.location.href);
    if (value === "fibery") url.searchParams.set("collection", "fibery"); else url.searchParams.delete("collection");
    window.history.replaceState(window.history.state, "", url);
  }
  if (report) return <MassReportView api={api} id={report} />;
  return <div><div className="dashboardCollections" role="group" aria-label="Подборка на дашборде">
    <button className={`button compact ${collection === "activity" ? "primary" : "secondary"}`} type="button" aria-pressed={collection === "activity"} onClick={() => choose("activity")}>История действий</button>
    <button className={`button compact ${collection === "fibery" ? "primary" : "secondary"}`} type="button" aria-pressed={collection === "fibery"} onClick={() => choose("fibery")}>Задачи Fibery</button>
  </div>{collection === "fibery" ? <DashboardFiberyTasks api={api} /> : <LiveActivity api={api} />}</div>;
}
