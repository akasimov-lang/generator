import React from "react";
import { TransferConfirmation, type Confirmation } from "./TransferConfirmation";
import { LoaderCircle } from "lucide-react";
import type { MassActionFilter } from "./massActionScope";

type Api = <T>(path: string, options?: RequestInit) => Promise<T>;
type DomainResult = { domain: string; status: string; code: string; message: string; source_removed?:boolean; warning?: {code: string; message: string} };
type Entry = { phase?:string; confirmation?:Confirmation; use_selected_reserve?: boolean; site_id?: string; run_id?: string; status?: string; error?: string; message?: string; source_project?: string; target_project?: string; domains?: string[]; old_main?: string; new_main?: string; old_fake_main_path?: string | null; new_fake_main_path?: string | null; domain_errors?: {domain:string;code:string;message:string;system_response?:unknown}[]; replacement_error?:string; drop_domains?:string[]; verification?: {checked_at: string; domains: DomainResult[]} };
type Report = { id: string; created_at: string; actor: string; filter: MassActionFilter; entries: Entry[]; skipped: { project: string; error: string }[] };
type CheckJob = {id: string; status: string; error?: string};
type QueueRow = {domain: string; source_project: string; target_project: string; status: string; error_code?: string; error?: string};
const statuses: Record<string, string> = { completed: "Подтверждено", failed: "Ошибка", cancelled: "Остановлено", queued: "В очереди", planned: "Запланировано", running: "Выполняется", waiting: "Ожидает подтверждения", partial: "Нужна проверка" };
const queueStatuses: Record<string,string> = {reserved:"Извлечение",extracted:"Ожидает добавления",adding:"Добавление",failed:"Нужна проверка"};

export function MassReglueReports({ api, filter, revision, onChanged }: { api: Api; filter: MassActionFilter | null; revision: string; onChanged?:()=>void|Promise<void> }) {
  const [expanded,setExpanded]=React.useState<Record<string,boolean>>({});
  const [reports, setReports] = React.useState<Report[]>([]);
  const [error, setError] = React.useState("");
  const [refresh, setRefresh] = React.useState(0);
  const [job, setJob] = React.useState<CheckJob|null>(null);
  const [starting, setStarting] = React.useState(false);
  const [queue, setQueue] = React.useState<QueueRow[]>([]);
  const brand = filter?.brand, geo = filter?.geo;
  const scope=React.useRef("");scope.current=`${brand}:${geo}`;
  const busy=starting || job?.status==="queued" || job?.status==="running";
  React.useEffect(() => {setReports([]);setError("");setJob(null);setQueue([]);setStarting(false);setExpanded({});},[brand,geo]);
  React.useEffect(() => {
    let live = true;
    if (!brand || !geo) return;
    const query=new URLSearchParams({brand,geo});
    void Promise.all([
      api<{ reports: Report[] }>(`/auto-reglue/reports?${query}`, { cache: "no-store" }),
      api<CheckJob|null>(`/auto-reglue/reports/check?${query}`,{cache:"no-store"}),
      api<{entries:QueueRow[]}>(`/auto-reglue/transfer-queue?${query}`,{cache:"no-store"})
    ]).then(([data,check,outbox])=>{if(live){setReports(data.reports);setJob(check);setQueue(outbox.entries||[]);setError(check?.error||"");}})
      .catch(e=>{if(live)setError(e instanceof Error?e.message:"Не удалось загрузить отчёты");});
    return () => { live = false; };
  }, [api, brand, geo, revision, refresh]);
  React.useEffect(()=>{
    if(!brand || !geo)return;
    const timer=window.setInterval(()=>setRefresh(v=>v+1),2500);
    return ()=>window.clearInterval(timer);
  },[brand,geo]);
  const changedJob=React.useRef("");
  React.useEffect(()=>{if((job?.status==="completed"||job?.status==="failed")&&changedJob.current!==job.id){changedJob.current=job.id;setRefresh(v=>v+1);void onChanged?.();}},[job?.status,job?.id,onChanged]);
  async function checkReports(){
    if(!filter||busy)return;
    const requestedScope=scope.current;
    setStarting(true);setError("");
    try{
      const next=await api<CheckJob>("/auto-reglue/reports/check",{method:"POST",body:JSON.stringify({request_id:crypto.randomUUID(),filter})});
      if(scope.current===requestedScope){setJob(next);setRefresh(v=>v+1);}
    }catch(e){if(scope.current===requestedScope)setError(e instanceof Error?e.message:"Не удалось запустить проверку сеток");}
    finally{if(scope.current===requestedScope)setStarting(false);}
  }
  if (!brand || !geo) return null;
  return <section className="dataPanel massReglueReports"><div className="dataPanelHeader"><h2>Отчёты · {brand} · {geo}</h2><button type="button" className="button secondary compact" disabled={busy} onClick={()=>void checkReports()}>{busy&&<LoaderCircle size={14} className="spin"/>}{busy?"Проверяем сетки…":"Обновить отчёты"}</button></div><div className="dataPanelBody">
    {error && <p role="alert">{error}</p>}{!error && !reports.length && <p className="muted">Массовых запусков для этого бренда и GEO пока нет.</p>}
    <section className="transferOutbox" aria-label={`Очередь доменов ${brand} ${geo}`}><strong>Очередь извлечённых доменов <span>{queue.length} / 5</span></strong>
      {!queue.length?<small>Очередь пуста</small>:queue.map(row=>row.status==="failed"||row.error_code?<details className="transferProgressErrorRow" key={row.domain}><summary className="transferOutboxRow"><code>{row.domain}</code><span>{row.source_project} → {row.target_project}</span><small>Ошибка · Подробнее</small></summary><div className="transferProgressErrorDetail">{row.error_code} · {row.error||"Нужна проверка"}</div></details>:<div className="transferOutboxRow" key={row.domain}><code>{row.domain}</code><span>{row.source_project} → {row.target_project}</span><small>{queueStatuses[row.status]||row.status}</small></div>)}
    </section>
    {!!reports.length&&<div className="tableScroll"><table className="compactTransferReports" aria-label="Отчёт о переносе доменов"><thead><tr><th>Дата / автор</th><th>Из сетки</th><th>В сетку</th><th>Домен</th><th>Main</th><th>Внутряк</th><th>Результат</th></tr></thead><tbody>{reports.flatMap(report=>report.entries.flatMap((entry,index)=>(entry.domains?.filter(Boolean).length?entry.domains.filter(Boolean):[""]).map((domain,di)=>{
      const verified=entry.verification?.domains.find(row=>row.domain===domain);
      const ok=verified?.status==="confirmed" || (!verified && entry.status==="completed");
      const failure=entry.domain_errors?.find(row=>row.domain===domain);
      const drop=entry.drop_domains?.includes(domain);
      const status=ok ? (entry.use_selected_reserve?"Выбранный резерв стал Main своей сетки":verified?.source_removed===false?"В целевой сетке":"В целевой сетке, из исходной удалён") : failure ? `${failure.code} · ${failure.message}` : verified ? `${verified.code} · ${verified.message}` : entry.error || entry.message || statuses[entry.status||""] || "Ожидает подтверждения";
      const checked=entry.verification?.checked_at;
      const value=(before?:string|null,after?:string|null)=>!after || before===after?<strong>{after || before || "—"}</strong>:<>{before || "—"} → <strong>{after}</strong></>;
      const rowKey=`${report.id}:${entry.run_id||index}:${domain}:${di}`;
      const active=!ok&&!failure&&["queued","running","waiting","planned"].includes(entry.status||"");
      const bad=!ok && !active && Boolean(failure || verified?.status==="failed" || entry.status==="failed" || entry.status==="partial");
      const toggle=()=>setExpanded(old=>({...old,[rowKey]:!old[rowKey]}));
      return <React.Fragment key={rowKey}><tr className={bad?"transferReportErrorRow":undefined} data-domain={domain} tabIndex={bad?0:undefined} aria-expanded={bad?Boolean(expanded[rowKey]):undefined} onClick={bad?toggle:undefined} onKeyDown={bad?e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();toggle();}}:undefined}><td className="transferReportDate"><time dateTime={report.created_at}>{new Date(report.created_at).toLocaleString("ru-RU",{timeZone:"Europe/Moscow"})}</time><small>{report.actor}</small></td><td>{entry.source_project||"—"}</td><td>{entry.target_project||"—"}</td><td><code>{domain||"—"}</code>{drop&&<strong className="transferDropNotice">{ok?"Перенесён дроп вместо новорега":"Вместо новорега выбран дроп"}</strong>}</td><td>{value(entry.old_main,entry.new_main)}</td><td>{value(entry.old_fake_main_path,entry.new_fake_main_path)}</td><td className={ok?"transferResultOk":"transferResultPending"} title={checked?`Проверено: ${new Date(checked).toLocaleString("ru-RU",{timeZone:"Europe/Moscow"})}`:undefined}>{ok?<><strong>ОК · </strong>{status}</>:active?<TransferConfirmation status={entry.status} phase={entry.phase} data={entry.confirmation}/>:bad?<span>Ошибка · {expanded[rowKey]?"Скрыть":"Подробнее"}</span>:status}</td></tr>{bad&&expanded[rowKey]&&<tr className="transferReportErrorDetail"><td colSpan={7}><strong>{domain}</strong><p>{status}</p>{failure?.system_response!=null&&<details><summary>Ответ системы</summary><pre>{JSON.stringify(failure.system_response,null,2)}</pre></details>}{entry.replacement_error&&<small>{entry.replacement_error}</small>}</td></tr>}</React.Fragment>;
    })))}</tbody></table></div>}
    {reports.some(report=>report.skipped.length>0)&&<details className="transferSkipped"><summary>Пропущенные проекты</summary>{reports.flatMap(report=>report.skipped.map(row=><p key={`${report.id}:${row.project}`}>{row.project}: {row.error}</p>))}</details>}
  </div></section>;
}
