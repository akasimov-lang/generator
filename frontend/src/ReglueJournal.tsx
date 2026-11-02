import * as React from "react";
import { ArrowLeft, ArrowRight, History, RefreshCw } from "lucide-react";
import "./styles/reglue-journal.css";

type Api = <T>(path: string, options?: RequestInit) => Promise<T>;
type Entry = {
  id: string; project: string; project_url: string; brand: string; geo: string | null;
  at: string; old_main: string | null; new_main: string;
  old_path: string | null; new_path: string | null;
  path_changes: { before: string | null; after: string; at: string }[]; mode: string;
};
type Journal = {
  today: string; today_count: number; total: number;
  days: { date: string; items: Entry[] }[]; next_before: string | null;
};
const time = (value: string) => new Intl.DateTimeFormat("ru-RU", { timeZone: "Europe/Moscow", hour: "2-digit", minute: "2-digit", second: "2-digit" }).format(new Date(value));
const date = (value: string) => new Intl.DateTimeFormat("ru-RU", { timeZone: "Europe/Moscow", day: "numeric", month: "long", year: "numeric" }).format(new Date(`${value}T12:00:00+03:00`));
const pathText = (value: string | null) => value === null ? "Нет данных" : value || "Не задан";

export function ReglueJournalCard({ api, refreshKey }: { api: Api; refreshKey: unknown }) {
  const [count, setCount] = React.useState<number | null>(null);
  const [error, setError] = React.useState(false);
  React.useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const result = await api<{ today_count: number }>("/reglue-journal/summary");
        if (!cancelled) { setCount(result.today_count); setError(false); }
      } catch { if (!cancelled) setError(true); }
    };
    void load();
    const timer = window.setInterval(() => { if (!document.hidden) void load(); }, 30000);
    return () => { cancelled = true; window.clearInterval(timer); };
  }, [api, refreshKey]);
  return <a className="kpiCard interactive reglueJournalCard" href="/reglue-journal" title="Открыть журнал переклеев по датам">
    <div className="kpiIcon"><History /></div><span>Журнал переклеев</span>
    <strong>{error ? "—" : count ?? "…"}</strong><small>{error ? "Не удалось загрузить" : "Сегодня · МСК"}</small>
  </a>;
}

export function ReglueJournalPage({ api, refreshKey }: { api: Api; refreshKey: number }) {
  const [data, setData] = React.useState<Journal | null>(null);
  const [error, setError] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [reload, setReload] = React.useState(0);
  const generation = React.useRef(0);
  React.useEffect(() => {
    const current = ++generation.current;
    setBusy(true); setError("");
    api<Journal>("/reglue-journal").then(result => {
      if (current === generation.current) setData(result);
    }).catch(e => { if (current === generation.current) setError(e instanceof Error ? e.message : "Не удалось загрузить журнал."); })
      .finally(() => { if (current === generation.current) setBusy(false); });
    return () => { generation.current++; };
  }, [api, refreshKey, reload]);
  async function more() {
    if (!data?.next_before || busy) return;
    const current = generation.current;
    setBusy(true); setError("");
    try {
      const next = await api<Journal>(`/reglue-journal?before=${data.next_before}`);
      if (current === generation.current) setData({ ...next, days: [...data.days, ...next.days] });
    } catch (e) { if (current === generation.current) setError(e instanceof Error ? e.message : "Не удалось загрузить журнал."); }
    finally { if (current === generation.current) setBusy(false); }
  }
  return <section className="viewStack reglueJournal">
    <div className="dataPanel">
      <header className="reglueJournalToolbar">
        <a className="button secondary compact" href="/dashboard"><ArrowLeft size={16} /> Dashboard</a>
        <span>Мои переклеи{data && <> · Сегодня: <b>{data.today_count}</b> · Всего: <b>{data.total}</b></>}</span>
        <button type="button" className="button secondary compact" disabled={busy} onClick={() => setReload(n => n + 1)}><RefreshCw size={16} />{busy ? "Загружаем…" : "Обновить"}</button>
      </header>
      <p className="fieldHint">Выполненные через PagePilot переклеи. Даты и время — МСК.</p>
      {error && <p role="alert" className="formError">{error}</p>}
      {!data && busy && <p role="status">Загружаем журнал…</p>}
      {data && data.today_count === 0 && <p>Сегодня переклеев пока нет.</p>}
      {data && data.total === 0 && <p>Подтверждённых переклеев пока нет.</p>}
    </div>
    {data?.days.map(group => <section key={group.date} className="dataPanel">
      <h2>{group.date === data.today ? "Сегодня · " : ""}{date(group.date)} <span className="fieldHint">· {group.items.length}</span></h2>
      <div className="reglueJournalTableWrap"><table className="reglueJournalTable">
        <thead><tr><th>Время · МСК</th><th>Проект</th><th>Main: было → стало</th><th>Внутряк: было → стало</th></tr></thead>
        <tbody>{group.items.map(entry => <tr key={entry.id}>
          <td><time dateTime={entry.at}>{time(entry.at)}</time><small>{entry.mode}</small></td>
          <td><a href={entry.project_url}>{entry.project}</a><small>{[entry.brand, entry.geo].filter(Boolean).join(" · ")}</small></td>
          <td><div className="reglueJournalChange"><span>{entry.old_main || "Нет данных"}</span><ArrowRight size={15} aria-label="на" /><strong>{entry.new_main}</strong></div></td>
          <td><div className="reglueJournalChange"><span>{pathText(entry.old_path)}</span><ArrowRight size={15} aria-label="на" /><strong>{pathText(entry.new_path)}</strong></div>
            {entry.old_path !== null && entry.old_path === entry.new_path && <small>Без изменений</small>}
            {!!entry.path_changes.length && <small>Замена внутренней страницы · {time(entry.path_changes[entry.path_changes.length - 1].at)}</small>}
          </td>
        </tr>)}</tbody>
      </table></div>
    </section>)}
    {data?.next_before && <button type="button" className="button secondary" disabled={busy} onClick={() => void more()}>{busy ? "Загружаем…" : "Показать более ранние даты"}</button>}
  </section>;
}
