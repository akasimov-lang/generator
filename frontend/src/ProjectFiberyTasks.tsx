import React from "react";
import {ExternalLink, RefreshCw} from "lucide-react";
import {createVisiblePoll} from "./visiblePoll";

type Api=<T>(path:string,options?:RequestInit)=>Promise<T>;
type Task={id:string;title:string;url:string;at:string;created_at?:string|null};
type Feed={items:Task[];total:number;next_before:string|null};
const date=new Intl.DateTimeFormat("ru-RU",{timeZone:"Europe/Moscow",day:"2-digit",month:"2-digit",year:"numeric",hour:"2-digit",minute:"2-digit"});
export function ProjectFiberyTasks({api,siteId}:{api:Api;siteId:string}) {
 const [data,setData]=React.useState<Feed|null>(null),[error,setError]=React.useState("");
 const [cursor,setCursor]=React.useState<string[]>([]),[refresh,setRefresh]=React.useState(0);
 const before=cursor.at(-1)||"";
 React.useEffect(()=>{
  let active=true;setData(null);setError("");
  const stop=createVisiblePoll({intervalMs:60000,immediate:true,load:async()=>{
   const result=await api<Feed>(`/dashboard-activity/fibery-tasks?site_id=${encodeURIComponent(siteId)}&limit=8&before=${encodeURIComponent(before)}`);
   if(active){setData(result);setError("");}
  },onError:e=>{if(active)setError(e instanceof Error?e.message:"Не удалось загрузить задачи Fibery.");}});
  return()=>{active=false;stop();};
 },[api,siteId,before,refresh]);
 return <section className="dataPanel projectFiberyTasks" aria-labelledby="project-fibery-title">
  <header style={{display:"flex",justifyContent:"space-between",gap:12,alignItems:"center"}}><h2 id="project-fibery-title">Задачи Fibery{data?` · ${data.total}`:""}</h2>
   <button className="button secondary compact" type="button" aria-label="Обновить задачи Fibery проекта" onClick={()=>setRefresh(n=>n+1)}><RefreshCw size={15}/></button></header>
  {error&&<p role="alert">{error}</p>}
  {!data&&!error&&<p role="status">Загружаем задачи…</p>}
  {data&&!data.items.length&&<p className="fieldHint">Созданных задач Fibery у проекта пока нет.</p>}
  {!!data?.items.length&&<ul style={{listStyle:"none",margin:0,padding:0}}>{data.items.map(task=><li key={task.id} style={{padding:"12px 0",borderBottom:"1px solid var(--border-color, #dce4ef)"}}>
   <a href={task.url} target="_blank" rel="noopener noreferrer" style={{display:"flex",gap:8,alignItems:"baseline"}}><strong>{task.title}</strong><ExternalLink size={14}/></a>
   <small className="fieldHint" style={{display:"block",marginTop:5}}>{task.created_at?"Поставлена":"Первая запись"}: <time dateTime={task.created_at||task.at}>{date.format(new Date(task.created_at||task.at))}</time> · МСК</small>
  </li>)}</ul>}
  {data&&(cursor.length>0||data.next_before)&&<nav aria-label="Страницы задач проекта" style={{display:"flex",gap:12,marginTop:12}}>
   <button type="button" className="button secondary compact" disabled={!cursor.length} onClick={()=>setCursor(c=>c.slice(0,-1))}>Назад</button>
   <button type="button" className="button secondary compact" disabled={!data.next_before} onClick={()=>{if(data.next_before)setCursor(c=>[...c,data.next_before!]);}}>Далее</button>
  </nav>}
 </section>;
}
