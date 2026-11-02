import React from "react";
import { CircleAlert, RefreshCcw, ArrowLeft } from "lucide-react";
import { localProjectNotices, projectNotice, noticeSynced, NOTICE_EVENT, PROJECT_CHANGED_EVENT, setNotificationProject, type ProjectNotice } from "./projectNotificationEvents";

type Api = <T>(path: string, options?: RequestInit) => Promise<T>;
type Entry = {id:string; source:string; status:string; code:string; message:string; context:string; severity:string; active:boolean; created_at:string; occurrences:number; client_key?:string; resolved_at?:string};
type Feed = {active_count:number;total:number;items:Entry[];active_client_keys?:string[]};
const names:Record<string,string> = {interface:"Интерфейс",network:"Сетка",reglue:"Переклей",page_edit:"Редактирование страницы",page_generation:"Генерация страницы",auto_lb:"АвтоЛБ",image:"Изображения",menu:"Меню",generation:"Генерация",competitors:"Конкуренты",indexing:"Индексация",deletion:"Удаление",publication:"Публикация",job:"Фоновая задача"};
const states:Record<string,string> = {active:"Актуально",resolved:"Устранено",confirmed:"Подтверждено",completed:"Завершено",failed:"Ошибка",error:"Ошибка",warning:"Предупреждение",unknown:"Проверяется",pending:"Проверяется",queued:"В очереди",running:"Выполняется",waiting:"Ожидание",ready:"Готово",index_submitted:"Отправлено в индексатор"};
const date = (value:string) => value ? new Date(value).toLocaleString("ru-RU",{timeZone:"Europe/Moscow"}) : "Дата не сохранена";
function localEntry(notice:ProjectNotice):Entry { return {id:"local:"+notice.key,source:"interface",status:notice.active?"active":"resolved", code:notice.code,message:notice.message,context:notice.context||"",severity:notice.severity,active:notice.active,created_at:notice.created_at||new Date().toISOString(),occurrences:1,client_key:notice.key}; }
function useNotices(siteId:string) {
  const [local,setLocal] = React.useState(()=>localProjectNotices(siteId));
  React.useEffect(()=>{
    setLocal(localProjectNotices(siteId));
    const receive=()=>setLocal(localProjectNotices(siteId));
    window.addEventListener(NOTICE_EVENT,receive);return()=>window.removeEventListener(NOTICE_EVENT,receive);
  },[siteId]);
  return local;
}

export function ProjectNotificationCenter({siteId,project,username,api,href,onOpen}:{siteId:string;project:string;username:string;api:Api;href:string;onOpen:()=>void}) {
  const [feed,setFeed]=React.useState<Feed>({active_count:0,total:0,items:[]});
  const [loadError,setLoadError]=React.useState("");
  const local=useNotices(siteId);
  const storageKey=`project-notice-outbox:${username}:${siteId}`;
  const queue=React.useRef<ProjectNotice[]>([]);
  const running=React.useRef(false);
  const reload=React.useCallback(async()=>{
    try {const next=await api<Feed>(`/sites/${siteId}/notifications?limit=100&active_only=true`);if(Array.isArray(next.items)) {setFeed(next);setLoadError("");}}
    catch {setLoadError("Не удалось загрузить журнал проекта. Откройте его и повторите загрузку.");}
  },[api,siteId]);
  React.useEffect(()=>{
    let alive=true;
    setNotificationProject(siteId);setFeed({active_count:0,total:0,items:[]});
    try {const saved=JSON.parse(sessionStorage.getItem(storageKey)||"[]");queue.current=Array.isArray(saved)?saved.filter(n=>n?.siteId===siteId&&typeof n.key==="string"&&typeof n.message==="string"):[];}catch{queue.current=[];}
    for(const notice of queue.current)projectNotice(notice);
    for(const notice of localProjectNotices(siteId).filter(n=>n.persist&&!n.synced))if(!queue.current.some(n=>n.key===notice.key))queue.current.push(notice);
    const saveQueue=()=>{try{sessionStorage.setItem(storageKey,JSON.stringify(queue.current));}catch{/* Keep the in-memory outbox. */}};
    const flush=async()=>{
      if(running.current)return;running.current=true;
      try{
        while(alive&&queue.current.length){
          const notice=queue.current[0];
          await api(`/sites/${siteId}/notifications`,{method:"POST",body:JSON.stringify({key:notice.key,code:notice.code,message:notice.message,context:notice.context||"",severity:notice.severity,active:notice.active})});
          if(!alive)return;
          noticeSynced(siteId,notice.key);
          queue.current.shift();saveQueue();
        }
        if(alive)await reload();
      }catch{if(alive)setLoadError("Часть уведомлений ещё не записана в журнал. Повторная отправка — при восстановлении связи или открытии проекта.");}
      finally{running.current=false;}
    };
    const receive=(event:Event)=>{
      const notice=(event as CustomEvent<ProjectNotice>).detail;
      if(notice.siteId!==siteId||!notice.persist)return;
      queue.current.push(notice);saveQueue();void flush();
    };
    const changed=(event:Event)=>{if((event as CustomEvent).detail?.siteId===siteId)void reload();};
    const online=()=>void flush();
    window.addEventListener(NOTICE_EVENT,receive);window.addEventListener(PROJECT_CHANGED_EVENT,changed);window.addEventListener("online",online);
    void (queue.current.length?flush():reload());
    return()=>{alive=false;setNotificationProject("");window.removeEventListener(NOTICE_EVENT,receive);window.removeEventListener(PROJECT_CHANGED_EVENT,changed);window.removeEventListener("online",online);};
  },[siteId,storageKey,api,reload]);
  const extra=local.filter(n=>n.active&&!feed.active_client_keys?.includes(n.key)&&!feed.items.some(item=>item.active&&(item.client_key===n.key||item.message===n.message||(item.message.length>10&&n.message.includes(item.message)))));
  const count=feed.active_count+extra.length+(loadError?1:0);
  const summary=[...extra.map(n=>`${n.code}: ${n.message}`),...feed.items.slice(0,5).map(n=>`${n.code}: ${n.message}`),...(loadError?[loadError]:[])];
  const title=count?`${project} · Уведомлений: ${count}\n${summary.map(s=>s.slice(0,180)).join("\n")}`:`${project}: актуальных уведомлений нет. Открыть журнал проекта.`;
  return <a href={href} className={`projectNotificationButton ${count?"hasNotices":""}`} title={title} aria-label={`Уведомления проекта: ${count}`} onClick={event=>{if(event.metaKey||event.ctrlKey||event.shiftKey||event.altKey)return;event.preventDefault();onOpen();}}><CircleAlert size={19} aria-hidden="true"/><span className="projectNotificationCount">{count}</span></a>;
}

export function ProjectLogs({siteId,project,api,onBack}:{siteId:string;project:string;api:Api;onBack:()=>void}) {
  const [feed,setFeed]=React.useState<Feed|null>(null);
  const [loading,setLoading]=React.useState(false);
  const [error,setError]=React.useState("");
  const [offset,setOffset]=React.useState(0);
  const [activeOnly,setActiveOnly]=React.useState(false);
  const [query,setQuery]=React.useState("");
  const [search,setSearch]=React.useState("");
  const local=useNotices(siteId);
  const load=React.useCallback(async()=>{setLoading(true);setError("");try{const next=await api<Feed>(`/sites/${siteId}/notifications?limit=50&offset=${offset}&active_only=${activeOnly}&q=${encodeURIComponent(search)}`);if(!Array.isArray(next.items))throw new Error("Журнал вернул неполный ответ.");setFeed(next);}catch(e){setError(e instanceof Error?e.message:String(e));}finally{setLoading(false);}},[api,siteId,offset,activeOnly,search]);
  React.useEffect(()=>{void load();},[load]);
  const extra=local.filter(n=>n.active&&!feed?.items.some(item=>item.client_key===n.key)).map(localEntry);
  return <section className="dataPanel projectLogs"><div className="panelHeader"><h2>Логи проекта · {project}</h2><div className="networkActions"><button type="button" className="button secondary compact" onClick={onBack}><ArrowLeft size={14}/>К проекту</button><button type="button" className="button secondary compact" disabled={loading} onClick={()=>void load()}><RefreshCcw size={14}/>Обновить журнал</button></div></div>
    <div className="projectLogsFilters"><button type="button" className={`button compact ${!activeOnly?"primary":"secondary"}`} onClick={()=>{setActiveOnly(false);setOffset(0);}}>Весь журнал</button><button type="button" className={`button compact ${activeOnly?"primary":"secondary"}`} onClick={()=>{setActiveOnly(true);setOffset(0);}}>Актуальные · {feed?.active_count??0}</button><form onSubmit={e=>{e.preventDefault();setSearch(query);setOffset(0);}}><input type="search" maxLength={200} aria-label="Поиск по логам" placeholder="Код или текст ошибки" value={query} onChange={e=>setQuery(e.target.value)}/><button type="submit" className="button secondary compact">Найти</button></form></div>
    {error&&<p role="alert">{error}</p>}{loading&&<p role="status">Загружаем журнал…</p>}
    {extra.length>0&&<div className="projectLocalNotices"><h3>Уведомления открытой формы</h3>{extra.map(item=><LogEntry key={item.id} item={item}/>)}</div>}
    {feed&&<><p className="muted">Всего записей: {feed.total}. Время — Москва. Устранённые ошибки остаются в истории.</p><div className="projectLogEntries">{feed.items.map(item=><LogEntry key={item.id} item={item}/>)}{!feed.items.length&&!extra.length&&<p>Записей по этому фильтру нет.</p>}</div><div className="projectLogsPagination"><button type="button" className="button secondary compact" disabled={!offset||loading} onClick={()=>setOffset(Math.max(0,offset-50))}>Предыдущие</button><span>{feed.total?offset+1:0}–{Math.min(offset+50,feed.total)} из {feed.total}</span><button type="button" className="button secondary compact" disabled={offset+50>=feed.total||loading} onClick={()=>setOffset(offset+50)}>Следующие</button></div></>}
  </section>;
}

function LogEntry({item}:{item:Entry}) {
  return <details className={`projectLogEntry ${item.active?item.severity:"resolved"}`}><summary><span>{date(item.created_at)}</span><b>{item.code||names[item.source]||item.source}</b><span className="projectLogSummary">{item.message.slice(0,200)}</span><small>{item.active?states[item.status]||"Актуально":item.status==="failed"?"Ошибка в истории":states[item.status]||item.status}</small></summary><div><p>{names[item.source]||item.source} · {states[item.status]||item.status} · {item.active?"Требует внимания":"История"}</p><pre>{item.message}</pre>{item.context&&<pre>{item.context}</pre>}<small>Запись: {item.id}{item.occurrences>1?` · Повторений: ${item.occurrences}`:""}{item.resolved_at?` · Устранено: ${date(item.resolved_at)}`:""}</small></div></details>;
}
