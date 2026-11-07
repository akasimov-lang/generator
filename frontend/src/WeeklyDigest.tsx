import React from 'react';
import {ArrowLeft, CalendarDays, Check, Copy, FileText, RefreshCw} from 'lucide-react';

type Api = <T>(path: string, init?: RequestInit) => Promise<T>;
export type DigestSummary = {
  id: string;
  week_start: string;
  week_end: string;
  title: string;
  status: 'open' | 'closed';
  updated_at?: string | null;
  period_end?: string | null;
  projects: number;
  manual_review_count: number;
};
type ReviewItem={key:string;site_id:string;project?:string;kind:string;field?:string;status?:string;reason?:string|null;updated_at?:string;report_url?:string};
export type Digest = DigestSummary & {text: string; saved_text?: string; saved_text_at?: string | null;review_items?:ReviewItem[]};
type DigestList = {reports: DigestSummary[]; current_week: string};

const dateTime = (value?: string | null) => value
  ? new Date(value).toLocaleString('ru-RU', {timeZone: 'Europe/Moscow', day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit'})
  : '';

export function currentMoscowWeek(now = new Date()) {
  const parts = new Intl.DateTimeFormat('en', {timeZone: 'Europe/Moscow', year: 'numeric', month: 'numeric', day: 'numeric'}).formatToParts(now);
  const part = (name: string) => Number(parts.find(p => p.type === name)?.value);
  const date = new Date(Date.UTC(part('year'), part('month') - 1, part('day')));
  date.setUTCDate(date.getUTCDate() - (date.getUTCDay() + 6) % 7);
  return date.toISOString().slice(0, 10);
}

export function validWeek(value: string) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const date = new Date(`${value}T00:00:00Z`);
  return !Number.isNaN(date.valueOf()) && date.toISOString().slice(0, 10) === value && date.getUTCDay() === 1;
}

function safeLink(value: string) {
  if (/^\/(?!\/)/.test(value) && !/[\\\u0000-\u001f]/.test(value)) return value;
  if (/^#[\w-]+$/.test(value)) return value;
  try {
    const url = new URL(value);
    return ['http:', 'https:'].includes(url.protocol) ? url.href : undefined;
  } catch { return undefined; }
}

function inline(text: string): React.ReactNode[] {
  const parts: React.ReactNode[] = [];
  const pattern = /\*\*([^*]+)\*\*|\[([^\]]+)\]\(([^)]+)\)|`([^`]+)`/g;
  let start = 0;
  for (const match of text.matchAll(pattern)) {
    const index = match.index ?? 0;
    if (index > start) parts.push(text.slice(start, index));
    if (match[1]) parts.push(<strong key={index}>{match[1]}</strong>);
    else if (match[2]) {
      const href = safeLink(match[3]);
      parts.push(href ? <a key={index} href={href} target="_blank" rel="noopener noreferrer">{match[2]}</a> : match[2]);
    } else parts.push(<code key={index}>{match[4]}</code>);
    start = index + match[0].length;
  }
  if (start < text.length) parts.push(text.slice(start));
  return parts;
}

/** The digest format is text, lists and emphasis. Remote HTML is always escaped. */
export function DigestText({text,issuesHref}: {text: string;issuesHref?:string}) {
  const lines = text.replace(/\r\n?/g, '\n').split('\n');
  const blocks: React.ReactNode[] = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i].trim();
    if (!line) { i++; continue; }
    const key = i;
    const heading = line.match(/^#{1,4}\s+(.+)$/) || line.match(/^\*\*(.+)\*\*$/);
    if (heading) {
      blocks.push(<h3 key={key}>{issuesHref&&/^Незавершённые задачи и задачи с ошибками:/.test(heading[1])?<a href={issuesHref}>{inline(heading[1])}</a>:inline(heading[1])}</h3>);
      i++;
      continue;
    }
    const list = line.match(/^(?:[-*]|\d+[.)])\s+/);
    if (list) {
      const ordered = /^\d/.test(line);
      const pattern = ordered ? /^\d+[.)]\s+(.+)$/ : /^[-*]\s+(.+)$/;
      const items: React.ReactNode[] = [];
      while (i < lines.length) {
        const item = lines[i].trim().match(pattern);
        if (!item) break;
        items.push(<li key={i}>{inline(item[1])}</li>);
        i++;
      }
      blocks.push(ordered ? <ol key={key}>{items}</ol> : <ul key={key}>{items}</ul>);
      continue;
    }
    const paragraph = [line];
    i++;
    while (i < lines.length && lines[i].trim() && !/^(?:#{1,4}\s|[-*]\s|\d+[.)]\s|\*\*.+\*\*$)/.test(lines[i].trim())) paragraph.push(lines[i++].trim());
    blocks.push(<p key={key}>{inline(paragraph.join(' '))}</p>);
  }
  return <div className="weeklyDigestText">{blocks}</div>;
}

export function WeeklyDigestLinks({reports, currentWeek}: {reports: DigestSummary[]; currentWeek: string}) {
  return <div className="weeklyDigestArchive" aria-label="Сводки по неделям">
    {reports.map(report => <a className="weeklyDigestArchiveItem" key={report.id} href={`/weekly-reports?week=${encodeURIComponent(report.week_start)}`} aria-current={report.week_start === currentWeek ? 'date' : undefined}>
      <FileText size={18}/><span><strong>{report.title}</strong><small>{report.status === 'open' ? 'Наполняется в течение недели' : 'Завершённая неделя'} · проектов: {report.projects}</small></span>
    </a>)}
  </div>;
}

export function WeeklyDigestList({api}: {api: Api}) {
  const [data, setData] = React.useState<DigestList | null>(null);
  const [error, setError] = React.useState('');
  const [loading, setLoading] = React.useState(false);
  const request = React.useRef(0);
  const load = React.useCallback(async (silent = false) => {
    const seq = ++request.current;
    if (!silent) setLoading(true);
    try {
      const result = await api<DigestList>('/weekly-digests', {cache: 'no-store'});
      if (seq === request.current) { setData(result); setError(''); }
    } catch (error) {
      if (seq === request.current) setError(error instanceof Error ? error.message : 'Не удалось загрузить сводки за неделю.');
    } finally { if (seq === request.current) setLoading(false); }
  }, [api]);
  React.useEffect(() => { void load(); return () => { ++request.current; }; }, [load]);
  React.useEffect(() => {
    const timer = setInterval(() => { if (!document.hidden) void load(true); }, 60000);
    return () => clearInterval(timer);
  }, [load]);
  const week = data?.current_week || currentMoscowWeek();
  return <section className="weeklyDigestOverview" aria-label="Текстовые сводки за неделю">
    <div className="weeklyDigestOverviewHeading"><div><h3><CalendarDays size={20}/>Еженедельная сводка</h3><p>Новый отчёт каждый понедельник по МСК. Подтверждённые работы добавляются в течение недели.</p></div><a className="button primary" href={`/weekly-reports?week=${encodeURIComponent(week)}`}><FileText size={17}/>Отчёт за эту неделю</a></div>
    {loading && !data && <p className="stateReportHint" role="status">Загружаем сводки…</p>}
    {error && <div className="weeklyDigestError"><span role="alert">{error}</span><button className="button secondary compact" onClick={() => void load()} disabled={loading}><RefreshCw size={14}/>Повторить</button></div>}
    {data && <WeeklyDigestLinks reports={data.reports} currentWeek={week}/>}
  </section>;
}

export function WeeklyDigest({api, week}: {api: Api; week: string}) {
  const [report, setReport] = React.useState<Digest | null>(null);
  const [error, setError] = React.useState('');
  const [loading, setLoading] = React.useState(false);
  const savedVersion=new URLSearchParams(window.location.search).get('text')==='saved';
  const issues=new URLSearchParams(window.location.search).get('issues')==='1';
  const [saved, setSaved] = React.useState(savedVersion);
  const [copyState, setCopyState] = React.useState('');
  const request = React.useRef(0);
  const load = React.useCallback(async (silent = false) => {
    if (!validWeek(week)) { setError('Неверная дата недели в ссылке на отчёт.'); return; }
    const seq = ++request.current;
    if (!silent) setLoading(true);
    try {
      const result = await api<Digest>(`/weekly-digests/${encodeURIComponent(week)}`, {cache: 'no-store'});
      if (seq === request.current) { setReport(result); setError(''); }
    } catch (error) {
      if (seq === request.current) setError(error instanceof Error ? error.message : 'Не удалось загрузить отчёт за неделю.');
    } finally { if (seq === request.current) setLoading(false); }
  }, [api, week]);
  React.useEffect(() => { setReport(null); setSaved(savedVersion); setCopyState(''); void load(); return () => { ++request.current; }; }, [load,savedVersion]);
  React.useEffect(() => {
    if (report?.status !== 'open') return;
    const timer = setInterval(() => { if (!document.hidden) void load(true); }, 60000);
    return () => clearInterval(timer);
  }, [load, report?.status]);
  const text = (saved ? report?.saved_text : report?.text) || '';
  const copy = async () => {
    try {
      if (!navigator.clipboard?.writeText) throw new Error('Clipboard unavailable');
      await navigator.clipboard.writeText(text);
      setCopyState('Скопировано');
    } catch { setCopyState('Не удалось скопировать автоматически. Выделите и скопируйте текст отчёта.'); }
  };
  return <section className="dataPanel stateReports weeklyDigestPage">
    <header className="stateReportTools"><a className="button secondary compact" href={issues?`/weekly-reports?week=${encodeURIComponent(week)}${saved?'&text=saved':''}`:'/weekly-reports'}><ArrowLeft size={15}/>{issues?'Назад к отчёту':'Все отчёты'}</a><h2><FileText size={20}/>{issues?'Незавершённые задачи и ошибки':report?.title || 'Отчёт за неделю'}</h2><button className="button secondary compact" disabled={loading} onClick={() => void load()}><RefreshCw size={15}/>Обновить</button></header>
    {error && <p role="alert">{error}</p>}
    {loading && !report && <p role="status">Загружаем отчёт…</p>}
    {report && !issues && <>
      <div className="weeklyDigestToolbar"><span className={`weeklyDigestStatus ${report.status}`}>{report.status === 'open' ? 'Наполняется в течение недели' : 'Завершённая неделя'}</span><span className="stateReportHint">{report.updated_at ? `Обновлён ${dateTime(report.updated_at)} МСК` : 'Сводка подготавливается'}</span><button className="button secondary compact" disabled={!text} onClick={() => void copy()}>{copyState === 'Скопировано' ? <Check size={15}/> : <Copy size={15}/>}Скопировать текст</button></div>
      {report.saved_text && <div className="weeklyDigestVersions" role="group" aria-label="Версия текстового отчёта"><button className="stateReportFilter" aria-pressed={!saved} onClick={() => { setSaved(false); setCopyState(''); }}>Актуальная сводка</button><button className="stateReportFilter" aria-pressed={saved} onClick={() => { setSaved(true); setCopyState(''); }}>Сводка из чата{report.saved_text_at ? ` · ${dateTime(report.saved_text_at)} МСК` : ''}</button></div>}
      {copyState && <p className="stateReportHint" role="status">{copyState}</p>}
      {saved && <p className="stateReportHint">Сохранённое текстовое описание из чата. Новые работы отображаются в актуальной сводке.</p>}
      {text ? <DigestText text={text} issuesHref={`/weekly-reports?week=${encodeURIComponent(week)}&issues=1${saved?'&text=saved':''}`}/> : <p className="weeklyDigestEmpty">Отчёт создан. Здесь появится сводка по мере подтверждения работ за эту неделю.</p>}
    </>}
    {report&&issues&&<WeeklyReviewItems items={report.review_items||[]} updatedAt={report.updated_at}/>}
  </section>;
}

export function WeeklyReviewItems({items,updatedAt}:{items:ReviewItem[];updatedAt?:string|null}) {
 const kinds:Record<string,string>={reglue:'Переклей',internal_pages:'Внутренние страницы',title_h1:'Title / H1',paragraphs:'Переписывание текста',text:'Генерация текста'};
 const statuses:Record<string,string>={queued:'В очереди',running:'Выполняется',waiting:'Ожидает подтверждения',failed:'Ошибка',partial:'Частично'};
 return <><p className="stateReportHint">Задач: {items.length}. Данные отчёта на {dateTime(updatedAt)} МСК.</p>{items.length?<div className="stateReportScroll"><table><thead><tr><th>Проект</th><th>Работа</th><th>Состояние / причина</th><th>Обновлено · МСК</th><th>Исходный план</th></tr></thead><tbody>{items.map(item=><tr key={item.key}><td>{item.project||item.site_id}</td><td>{kinds[item.field||item.kind]||item.kind}</td><td><strong>{statuses[item.status||'']||item.status||'Требует разбора'}</strong>{item.reason&&<p>{item.reason}</p>}</td><td>{dateTime(item.updated_at)||'—'}</td><td>{item.report_url&&safeLink(item.report_url)?<a href={item.report_url}>Открыть план</a>:'—'}</td></tr>)}</tbody></table></div>:<p>Незавершённых задач и ошибок в этой сводке нет.</p>}</>;
}
