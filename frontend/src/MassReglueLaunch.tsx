import React from "react";
import { Play, X } from "lucide-react";

type Api = <T>(path:string, options?:RequestInit)=>Promise<T>;
type Launch = {id:string;status:string;error:string|null;items:{site_id:string;project:string;status:string;reason:string|null;run_id:string|null}[];counts:Record<string,number>};
const labels:Record<string,string>={pending:"Подготовка",queued:"В очереди",running:"Выполняется",waiting:"Ожидает подтверждения",completed:"Готово",skipped:"Пропущено",failed:"Ошибка",partial:"Выполнено частично",cancelled:"Остановлено"};

export function MassReglueLaunch({api,siteIds,onChanged}:{api:Api;siteIds:string[];onChanged:()=>void}) {
 const [job,setJob]=React.useState<Launch|null>(null),[busy,setBusy]=React.useState(false),[error,setError]=React.useState(""),[open,setOpen]=React.useState(false);
 const request=React.useRef<{id:string;sites:string}|null>(null),dialog=React.useRef<HTMLDialogElement>(null);
 const signature=JSON.stringify([...siteIds].sort());
 const load=React.useCallback(async()=>{try{setJob(await api<Launch|null>("/auto-reglue/list-launch",{cache:"no-store"}));}catch(e){setError(e instanceof Error?e.message:"Не удалось прочитать запуск");}},[api]);
 React.useEffect(()=>{void load();},[load]);
 React.useEffect(()=>{if(job?.status!=="queued")return;const timer=setInterval(()=>void load(),3000);return()=>clearInterval(timer);},[load,job?.status]);
 const previousStatus=React.useRef<string | undefined>(undefined);
 React.useEffect(()=>{if(previousStatus.current==="queued"&&job?.status==="completed")void onChanged();previousStatus.current=job?.status;},[job?.status,onChanged]);
 React.useEffect(()=>{if(open)dialog.current?.showModal();},[open]);
 async function start(){
  if(busy||job?.status==="queued"||!siteIds.length)return;
  setBusy(true);setError("");
  if(!request.current||request.current.sites!==signature)request.current={id:crypto.randomUUID(),sites:signature};
  try{setJob(await api<Launch>("/auto-reglue/list-launch",{method:"POST",body:JSON.stringify({request_id:request.current.id,site_ids:siteIds})}));request.current=null;setOpen(true);}
  catch(e){setError(e instanceof Error?e.message:"Не удалось запустить переклей");}
  finally{setBusy(false);}
 }
 return <span className="massListLaunch">
  <button type="button" className="button primary compact" disabled={busy||job?.status==="queued"||!siteIds.length} onClick={()=>void start()} title="Весь отфильтрованный список. Пропускаются проекты с участием «Нет» и уже переклеенные на этой неделе по Москве."><Play size={15}/>{busy?"Запускаем…":job?.status==="queued"?"Переклей выполняется":"Переклеить список"} · {siteIds.length}</button>
  {job&&<button type="button" className="button secondary compact" onClick={()=>setOpen(true)}>Результаты · {job.counts.completed||0}/{job.items.length}</button>}
  {error&&<small role="alert">{error}</small>}
  {open&&<dialog ref={dialog} className="reserveDialog massLaunchDialog" aria-labelledby="mass-launch-title" onCancel={()=>setOpen(false)}>
   <header><h2 id="mass-launch-title">Переклей списка</h2><button type="button" className="button secondary compact" aria-label="Закрыть результаты" onClick={()=>{dialog.current?.close();setOpen(false);}}><X size={18}/></button></header>
   <p>Готово: {job?.counts.completed||0}. Пропущено: {job?.counts.skipped||0}. Ошибок: {(job?.counts.failed||0)+(job?.counts.partial||0)}. {job?.status==="queued"?"Обработка продолжается; страницу можно закрыть.":"Обработка списка завершена."}</p>
   {job?.error&&<p role="alert">{job.error}</p>}
   <div className="reserveTableScroll"><table><thead><tr><th>Проект</th><th>Состояние</th><th>Результат</th></tr></thead><tbody>{job?.items.map(item=><tr key={item.site_id}><td><a href={`/project-auto-reglue/${encodeURIComponent(item.project)}/`}>{item.project}</a></td><td>{labels[item.status]||item.status}</td><td>{item.reason||"—"}</td></tr>)}</tbody></table></div>
  </dialog>}
 </span>;
}
