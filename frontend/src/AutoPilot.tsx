import { pilotDomainFilter } from "./pilotFilterNavigation";
import React from "react";
import { pilotTextError, needsTextRetry } from "./pilotTextError";
import { TemplateCombobox } from "./TemplateCombobox";
import { titleRewriteOptions, titleRewriteLabel, type TitleRewriteMode } from "./titleRewriteModes";
import { MaintenanceReport } from "./MaintenanceReport";
import { maintenanceReportFallback } from "./pilotReportRoute";
import { PilotDistribution, type Distribution } from "./PilotDistribution";
import { PilotInternalPages, type InternalPages } from "./PilotInternalPages";
import { PilotMultiSelect } from "./PilotMultiSelect";
import { PilotTaskSearch, pilotTaskListPath } from "./PilotTaskSearch";
import { PilotVersionTabs, pilotPreparePath, type PilotVersion } from "./PilotVersionTabs";
import { PilotDropsLink } from "./ReglueReserves";
import { consumeDraftReturn, pilotDraftPath, reserveVisitHref, restoredDraftFromDrops, saveDraftForDrops } from "./pilotDropsNavigation";
import { savedSelection, sameSelection, scopeFacets, scopeError, inPilotScope, type PilotSelection, type PilotGroup, type PilotScopeMode } from "./pilotScope";
import "./styles/template-generator.css";
import { wordDiff } from "./wordDiff.mjs";
import { alternateDiff } from "./alternateDiff.mjs";
import { TransferConfirmation, type Confirmation } from "./TransferConfirmation";
import { ArrowLeft, Bot, Play, RefreshCw, ScrollText, X, AlertTriangle, Trash2 } from "lucide-react";
import "./styles/auto-pilot.css";

type DomainFilter = "reserve_drops" | "newregs" | "drops" | "other" | "internal_pages";
type ProjectRenderer = (ids: string[], label: string) => React.ReactNode;
const domainLabels: Record<DomainFilter, string> = {reserve_drops:"Из резерва дропов",newregs:"На новореги",drops:"На дропы",other:"Другие",internal_pages:"Добавлены страницы"};
type Api = <T>(path:string,options?:RequestInit)=>Promise<T>;
type Row = {monitor?:{state:string;message:string;attempts:number;checked_at?:string;next_check_at?:string;deadline_at?:string};reglue_status?:string;internal_pages?:InternalPages;versions?:PilotVersion[];selected_version?:number;title_rewrite_mode?:TitleRewriteMode;rewrite_paragraphs?:boolean;paragraphs_preview?:{draft_id:string;count:number;samples?:{before:string;after:string}[]};paragraphs_error?:string;brand?:string;emergency_subdomain?:boolean;updated_fields?:{title:boolean;h1:boolean;alternates:boolean;paragraphs?:boolean};verification?:{status:string;checked_at?:string;server?:string;code?:string;message?:string;checks:{code:string;label:string;ok:boolean}[]};notes?:{domain:string;message:string;checked_at:string}[];performed_at?:string;new_fake_path?:string;title_h1_current?:{title:string;h1:string;h1_status?:string;h1_source?:string;h1_note?:string;headings?:{text:string;source:string}[]};title_h1_preview?:{mode?:TitleRewriteMode;headings?:{level:number;before:string;after:string}[];title_before:string;title_after:string;h1_before:string;h1_after:string};title_h1_error?:string;confirmation?:Confirmation & {checked_at?:string};site_id:string;project:string;geo:string;status:string;reason?:string;run_id?:string;old_main?:string;new_main?:string;source_project?:string;scheme?:string;alternate?:string;alternate_before?:string;canonical?:string;alternates_enabled?:boolean;progress:number;phase?:string};
type Percentages = {subdomains:number;without_alternates:number;redirects:number;title_h1:number;paragraphs:number;internal_pages:number};
const defaultPercentages:Percentages={subdomains:10,without_alternates:10,redirects:20,title_h1:20,paragraphs:0,internal_pages:0};
type TextProgress = {done:number;total:number;running?:number;failed?:number};
const textProgress=(p:TextProgress)=>`готово ${p.done-(p.failed||0)} из ${p.total}${p.running?` · Генерируется: ${p.running}`:""}${p.failed?` · Ошибок: ${p.failed}`:""}`;
type Pilot = {domain_projects?:Record<DomainFilter,string[]>;parallel_texts?:boolean;planning_mode?:"percentages"|"mixed";generation_id?:string;replanning_requested?:boolean;report_id?:number;title_rewrite_mode?:TitleRewriteMode;distribution?:Distribution;name?:string;percentages?:Percentages;planning_filter?:Partial<PilotSelection>&{brand?:string;geo?:string};launched_at?:string;finished_at?:string;planning_phase?:string;paragraphs_progress?:TextProgress;title_h1_progress?:TextProgress;title_h1_outdated?:boolean;domain_summary?:{reserve_drops:number;newregs:number;drops:number;other:number;internal_pages?:number};variation_summary?:{internal_pages?:number;internal_pages_requested?:number;internal_pages_eligible?:number;paragraphs?:number;paragraphs_requested?:number;without_alternates:number;without_alternates_requested:number;total:number;subdomains:number;subdomains_requested:number;subdomains_percent?:number;redirects:number;redirects_requested:number;title_h1:number;title_h1_requested?:number;title_h1_percent:number;canonical_self:number;canonical_internal:number;used_variants:number;warning?:string};plan_outdated?:boolean;launch_enabled?:boolean;can_launch_while_generating?:boolean;id:string;mode:"preview"|"execution";status:string;error?:string;created_at:string;ready:number;items:Row[];counts:Record<string,number>;progress:{percent:number;done:number;total:number};events:{id:string;run_id:string;action:string;status:string;message?:string;at:string}[]};
const labels:Record<string,string>={pending:"Подготовка",generating:"Генерация текстов",ready:"Готов к запуску",queued:"В очереди",running:"Выполняется",waiting:"Ждём подтверждения",completed:"Готово",skipped:"Пропущено",failed:"Ошибка",partial:"Частично",cancelled:"Остановлено"};
const actions:Record<string,string>={content_generation:"Генерация текстов",content_dependency:"Ждём связанный проект",content_failed:"Ошибка генерации",internal_pages:"Внутренние страницы",paragraphs:"Переписывание абзацев",title_h1:"Обновление Title/H1",delete_domain:"Извлечение домена",create_domains:"Добавление домена",create_subdomains:"Создание поддомена",create_fake_main:"Создание внутряка",reserve:"Назначение резерва",reglue:"Смена Main",alternates:"Сохранение альтернейтов",indexing:"Индексация"};
const flag=(geo:string)=>/^[A-Z]{2}$/.test(geo||"")?String.fromCodePoint(...[...geo].map(c=>127397+c.charCodeAt(0))):"🌐";
function AlternateCode({before,after}:{before?:string;after:string}) {
 const parts=React.useMemo(()=>alternateDiff(before||"",after),[before,after]);
 return <code className="pilotAlternateCode" aria-label="Альтернейт после переклея">{parts.map((part,i)=>part.changed?<span key={i} className="pilotAlternateChanged">{part.text}</span>:part.text)}</code>;
}
function CanonicalCode({row}:{row:Row}) {
 const code=row.canonical||"",path=row.new_fake_path;
 if(!path||!code.includes(path))return <code>{code}</code>;
 const parts=code.split(path);
 return <code>{parts.map((part,index)=><React.Fragment key={index}>{index>0&&<span className="pilotAlternateChanged">{path}</span>}{part}</React.Fragment>)}</code>;
}
function UpdatedLabel({field}:{field:string}) {
 return <small className="pilotUpdated" aria-label={`${field} обновлён`}>Обновлён</small>;
}
function Paragraphs({row}:{row:Row}) {
 const preview=row.paragraphs_preview;
 if(!row.rewrite_paragraphs&&!preview&&!row.paragraphs_error)return null;
 return <div className="pilotParagraphs">
  {preview?<><strong>Абзацы: {preview.count}</strong>{row.updated_fields?.paragraphs&&<UpdatedLabel field="Абзацы"/>}{!!preview.samples?.length&&<details><summary>Примеры изменений</summary>{preview.samples.map((sample,index)=><div key={index}><p><b>Было:</b> {sample.before}</p><p><b>{row.updated_fields?.paragraphs?"Стало:":"Будет:"}</b> {sample.after}</p></div>)}</details>}</>:<small>Абзацы: подготовка текста</small>}
  {row.paragraphs_error&&<small role="status" className="pilotRewrittenWord">{pilotTextError(row.paragraphs_error,"paragraphs",row.title_rewrite_mode)}</small>}
 </div>;
}
function TitleH1({row}:{row:Row}) {
 const p=row.title_h1_preview;
 const meta=row.title_h1_current;
 const missingH1=meta?.h1_status==="not_found"?"Не найден":meta?.h1_status==="unavailable"?"Не удалось проверить":meta?.h1_status==="unresolved"?"Требует проверки на сайте":"Не проверен";
 return <div className="pilotTitleH1">{(["title","h1"] as const).map(key=><div key={key} title={key==="h1"?[meta?.h1_source,meta?.h1_note,...(meta?.headings?.map(h=>h.text)||[])].filter(Boolean).join("\n"):undefined}><b>{key==="title"?"Title":"H1"}: </b>{p?wordDiff(p[`${key}_before`],p[`${key}_after`]).map((part,i)=><span key={i} className={part.changed?"pilotRewrittenWord":undefined}>{part.text}</span>):meta?.[key]||(key==="h1"?missingH1:"—")}{row.updated_fields?.[key]&&<UpdatedLabel field={key==="title"?"Title":"H1"}/>}</div>)}{!!p?.headings?.length&&<details><summary>Все изменения заголовков · {p.headings.length}</summary>{p.headings.map((heading,index)=><div className="pilotHeadingPreview" key={index}><b>H{heading.level}</b><p><b>Было:</b> {heading.before}</p><p><b>{row.updated_fields?.title?"Стало:":"Будет:"}</b> {heading.after}</p></div>)}</details>}{row.title_h1_error&&<small role="status" className="pilotRewrittenWord">{pilotTextError(row.title_h1_error,"title_h1",row.title_rewrite_mode)}</small>}</div>;
}
const date=(value:string)=>new Date(value).toLocaleString("ru-RU",{timeZone:"Europe/Moscow"});

type Task={report_id?:number;report_url?:string;name:string;mode:"preview"|"execution"|"maintenance";id:string;status:string;launched_at:string;finished_at?:string;total:number;counts:Record<string,number>};
type Tasks={items:Task[];total:number;has_more:boolean};
export function PilotReportIdentity({task}:{task:Pick<Task,"id"|"report_id"|"report_url"|"name"|"mode">}) {
 const href=task.mode==="maintenance"?(task.report_url||`/auto-reglue/pilot/report?maintenance=${encodeURIComponent(task.id)}`):`/auto-reglue/pilot${task.mode==="execution"?"/logs":""}?id=${encodeURIComponent(task.id)}`;
 return <div className="pilotReportIdentity">{Number.isInteger(task.report_id)&&Number(task.report_id)>=3000&&<a className="pilotReportId" href={href}>ID {task.report_id}</a>}<strong className="pilotReportName"><a href={href} title={task.name}>{task.name}</a></strong></div>;
}

export function AutoPilotPage({api,logs=false,reports=false,renderProjects}:{api:Api;logs?:boolean;reports?:boolean;renderProjects?:ProjectRenderer}) {
 const maintenance=new URLSearchParams(window.location.search).get("maintenance");
 const direct=new URLSearchParams(window.location.search).has("id")||(!reports&&(logs||new URLSearchParams(window.location.search).has("new")));
 const [history,setHistory]=React.useState<Tasks|null>(null),[error,setError]=React.useState(""),[offset,setOffset]=React.useState(0);
 const [search,setSearch]=React.useState(""),[query,setQuery]=React.useState("");
 React.useEffect(()=>{const timer=setTimeout(()=>setQuery(search.trim()),250);return()=>clearTimeout(timer);},[search]);
 const changeSearch=(value:string)=>{setSearch(value);setOffset(0);setHistory(null);setError("");};
 const [deleting,setDeleting]=React.useState<string|null>(null);
 const deletingRef=React.useRef(false);
 async function deleteDraft(task:Task){
  if(deletingRef.current)return;
  deletingRef.current=true;setDeleting(task.id);setError("");
  try{
   await api(`/auto-reglue/pilot/${task.id}`,{method:"DELETE"});
   const total=Math.max(0,(history?.total||0)-1);
   setHistory(current=>current?{...current,total,items:current.items.filter(item=>item.id!==task.id),has_more:offset+current.items.length-1<total}:current);
   if(offset>=total&&offset>0)setOffset(Math.max(0,Math.floor((total-1)/50)*50));
  }catch(e){setError(e instanceof Error?e.message:"Не удалось удалить черновик");}
  finally{deletingRef.current=false;setDeleting(null);}
 }
 React.useEffect(()=>{if(direct||maintenance||deleting||search.trim()!==query)return;let active=true;const load=()=>void api<Tasks>(pilotTaskListPath(offset,query),{cache:"no-store"}).then(data=>{if(active&&!deletingRef.current){if(offset>0&&offset>=data.total){setOffset(Math.max(0,Math.floor((data.total-1)/50)*50));return;}setHistory(data);setError("");}}).catch(e=>{if(active)setError(e instanceof Error?e.message:"Не удалось загрузить задания");});load();const timer=setInterval(load,5000);return()=>{active=false;clearInterval(timer);};},[api,direct,maintenance,offset,deleting,search,query]);
 if(maintenance)return <MaintenanceReport api={api} id={maintenance}/>;
 if(direct||(!reports&&!search.trim()&&!query&&history&&history.total===0))return <AutoPilotDetail api={api} logs={logs} renderProjects={renderProjects}/>;
 return <section className="dataPanel pilotPanel"><header className="pilotTools"><a className="button secondary compact" href="/auto-reglue"><ArrowLeft size={16}/>Массовые действия</a><h2>{reports?<ScrollText size={20}/>:<Bot size={20}/>} {reports?"Автопилот Отчет":"Auto Pilot — массовые переклеи"}</h2><a className="button primary compact" href="/auto-reglue/pilot?new=1"><Play size={16}/>Новый черновик</a></header>
 <PilotTaskSearch value={search} onChange={changeSearch} total={history?.total}/>
 {error&&<p role="alert">{error}</p>}{!history&&!error&&<p role="status">Загружаем задания…</p>}
 {history?.total===0&&<p role="status">{query?"По этому запросу заданий не найдено.":"Черновиков и запусков пока нет. Нажмите «Новый черновик», чтобы перейти к планированию."}</p>}
 {history&&history.total>0&&<><table className="pilotTable pilotTasks"><thead><tr><th>Черновик / запуск · МСК</th><th>Проектов</th><th>Выполнено</th><th>Пропущено</th><th>Ошибок</th><th>Состояние</th><th>Завершено · МСК</th><th>Задание</th></tr></thead><tbody>{history.items.map(task=><tr key={task.id}><td><PilotReportIdentity task={task}/><small>{date(task.launched_at)}</small></td><td>{task.total}</td><td>{task.counts.completed||0}</td><td>{task.counts.skipped||0}</td><td>{(task.counts.failed||0)+(task.counts.partial||0)}</td><td>{task.mode==="preview"?`Черновик · ${task.status==="queued"?"Планирование":task.status==="completed"?"План готов":labels[task.status]||task.status}`:task.status==="queued"?"Выполняется":labels[task.status]||task.status}</td><td>{task.finished_at?date(task.finished_at):"—"}</td><td>{task.mode==="maintenance"?<a href={task.report_url}>Открыть отчёт</a>:task.mode==="preview"?<><a href={`/auto-reglue/pilot?id=${task.id}`}>Открыть черновик</a><button type="button" className="button secondary compact pilotDeleteDraft" aria-label={`Удалить черновик: ${task.name}`} disabled={deleting!==null} onClick={()=>void deleteDraft(task)}><Trash2 size={14}/>{deleting===task.id?"Удаляем…":"Удалить черновик"}</button></>:<><a href={`/auto-reglue/pilot/logs?id=${task.id}`}>Открыть таблицу</a><br/><a href={`/auto-reglue/pilot/logs?id=${task.id}&issues=1`}>Ошибки и примечания</a></>}</td></tr>)}</tbody></table><footer className="pilotTools"><button type="button" className="button secondary compact" disabled={!offset} onClick={()=>setOffset(Math.max(0,offset-50))}>Назад</button><span>{offset+1}–{offset+history.items.length} из {history.total}</span><button type="button" className="button secondary compact" disabled={!history.has_more} onClick={()=>setOffset(offset+50)}>Далее</button></footer></>}
 </section>;
}

function AutoPilotDetail({api,logs=false,renderProjects}:{api:Api;logs?:boolean;renderProjects?:ProjectRenderer}) {
 const [restored]=React.useState(()=>{try{return logs?null:restoredDraftFromDrops(window.sessionStorage,window.location.pathname+window.location.search);}catch{return null;}});
 const [reserveToken]=React.useState(()=>logs?"":crypto.randomUUID());
 const [loaded,setLoaded]=React.useState(false);
 const [job,setJob]=React.useState<Pilot|null>(null),[busy,setBusy]=React.useState(false),[error,setError]=React.useState("");
 const issuesOnly=new URLSearchParams(window.location.search).get("issues")==="1";
 const [domainFilter,setDomainFilterState]=React.useState<DomainFilter|null>(()=>pilotDomainFilter(window.location.search));
 function setDomainFilter(value: React.SetStateAction<DomainFilter|null>) {
  const next=typeof value==="function"?value(domainFilter):value;
  const url=new URL(window.location.href);
  if(next)url.searchParams.set("domainFilter",next);else url.searchParams.delete("domainFilter");
  window.history.replaceState(window.history.state,"",url.pathname+url.search+url.hash);
  setDomainFilterState(next);
 }
 const [issueTab,setIssueTab]=React.useState<"results"|"journal">("results");
 const initialId=React.useRef(new URLSearchParams(window.location.search).get("id"));
 const starting=React.useRef(false);
 const prepareReceipt=React.useRef<{id:string;signature:string}|null>(null);
 const [selection,setSelection]=React.useState<PilotSelection>(restored?.form.selection||{brands:[],geos:[],scope_mode:"include"});
 const [planningMode,setPlanningMode]=React.useState<"percentages"|"mixed">(restored?.form.planningMode||"percentages");
 const [titleMode,setTitleMode]=React.useState<TitleRewriteMode>(restored?.form.titleMode||"minimal");
 const [shares,setShares]=React.useState<Record<keyof Percentages,string>>({subdomains:"10",without_alternates:"10",redirects:"20",title_h1:"20",paragraphs:"0",internal_pages:"0",...restored?.form.shares});
 const applyShares=(values:Percentages)=>setShares(Object.fromEntries(Object.entries({...defaultPercentages,...values}).map(([key,value])=>[key,String(value)])) as Record<keyof Percentages,string>);
 const [options,setOptions]=React.useState<{brands:string[];geos:string[];groups:PilotGroup[];percentages:Percentages;title_rewrite_mode?:TitleRewriteMode}|null>(null);
 React.useEffect(()=>{if(!restored)return;consumeDraftReturn(window.sessionStorage,restored.token);window.history.replaceState(window.history.state,"",restored.returnTo);},[restored]);
 React.useEffect(()=>{if(logs)return;let active=true;void api<{brands:string[];geos:string[];groups:PilotGroup[];percentages:Percentages;title_rewrite_mode?:TitleRewriteMode}>("/auto-reglue/pilot/options").then(data=>{if(active){setOptions(data);if(!initialId.current&&!restored){applyShares(data.percentages);setTitleMode(data.title_rewrite_mode||"minimal");}}}).catch(e=>{if(active)setError(e instanceof Error?e.message:"Не удалось загрузить фильтры");});return()=>{active=false;};},[api,logs,restored]);
 const readEpoch=React.useRef(0);
 const accept=React.useCallback((next:Pilot)=>{readEpoch.current++;setJob(next);const url=new URL(window.location.href);url.searchParams.set("id",next.id);url.searchParams.delete("new");window.history.replaceState(null,"",url);},[]);
 React.useEffect(()=>{let active=true;void(async()=>{try{
  const next=initialId.current?await api<Pilot>(`/auto-reglue/pilot/${initialId.current}`,{cache:"no-store"}):logs?await api<Pilot|null>("/auto-reglue/pilot",{cache:"no-store"}):null;
  if(active&&next){accept(next);if(!restored){applyShares(next.percentages||defaultPercentages);setTitleMode(next.title_rewrite_mode||"minimal");setPlanningMode(next.planning_mode||"percentages");setSelection(savedSelection(next.planning_filter));}}
 }catch(e){const fallback=initialId.current?await maintenanceReportFallback(api,initialId.current,e):null;if(active&&fallback){window.location.replace(fallback);return;}if(active)setError(e instanceof Error?e.message:"Не удалось подготовить план");}finally{if(active)setLoaded(true);}})();return()=>{active=false;};},[api,logs,accept,restored]);
 React.useEffect(()=>{if(!job||(job.status!=="queued"&&job.mode!=="execution"&&!job.replanning_requested))return;let active=true;const epoch=readEpoch.current;
  const timer=setInterval(()=>void api<Pilot>(`/auto-reglue/pilot/${job.id}`,{cache:"no-store"}).then(next=>{if(active&&epoch===readEpoch.current){setJob(next);setError("");}}).catch(e=>{if(active)setError(e instanceof Error?e.message:"Не удалось обновить прогресс");}),3000);
  return()=>{active=false;clearInterval(timer);};},[api,job?.id,job?.status,job?.replanning_requested,job?.generation_id]);
 async function prepare(){
  if(starting.current||!canPrepare)return;
  starting.current=true;setBusy(true);setError("");
  const path=pilotPreparePath(job?.id);
  const payload={...selection,planning_mode:planningMode,title_rewrite_mode:titleMode,percentages:Object.fromEntries(Object.entries(shares).map(([key,value])=>[key,Number(value)]))};
  const signature=JSON.stringify([path,payload]);
  if(prepareReceipt.current?.signature!==signature)prepareReceipt.current={id:crypto.randomUUID(),signature};
  try{accept(await api<Pilot>(path,{method:"POST",body:JSON.stringify({request_id:prepareReceipt.current.id,...payload})}));prepareReceipt.current=null;}
  catch(e){setError(e instanceof Error?e.message:"Не удалось обновить план");}
  finally{starting.current=false;setBusy(false);}
 }
 async function selectVersion(row:Row,version:number){
  if(!job||starting.current||row.selected_version===version)return;
  starting.current=true;setBusy(true);setError("");
  try{accept(await api<Pilot>(`/auto-reglue/pilot/${job.id}/rows/${row.site_id}/version`,{method:"POST",body:JSON.stringify({version})}));}
  catch(e){setError(e instanceof Error?e.message:"Не удалось выбрать версию проекта");}
  finally{starting.current=false;setBusy(false);}
 }
 async function start(){if(!job||!canStart||starting.current)return;starting.current=true;setBusy(true);setError("");try{const next=await api<Pilot>(`/auto-reglue/pilot/${job.id}/start`,{method:"POST"});window.location.assign(`/auto-reglue/pilot/logs?id=${encodeURIComponent(next.id)}`);}catch(e){setError(e instanceof Error?e.message:"Не удалось запустить план");starting.current=false;setBusy(false);}}
 async function refreshRow(row:Row){if(!job||starting.current)return;starting.current=true;setBusy(true);setError("");try{accept(await api<Pilot>(`/auto-reglue/pilot/${job.id}/rows/${row.site_id}/refresh`,{method:"POST",body:JSON.stringify({request_id:crypto.randomUUID()})}));}catch(e){setError(e instanceof Error?e.message:"Не удалось обновить строку");}finally{starting.current=false;setBusy(false);}}
 async function cancelRow(row:Row){if(!job||!row.run_id||starting.current)return;starting.current=true;setBusy(true);setError("");try{await api(`/auto-reglue/runs/${row.run_id}/cancel`,{method:"POST"});accept(await api<Pilot>(`/auto-reglue/pilot/${job.id}`,{cache:"no-store"}));}catch(e){setError(e instanceof Error?e.message:"Не удалось отменить переклей");}finally{starting.current=false;setBusy(false);}}
 async function checkRow(row:Row){if(!job||!row.run_id||starting.current)return;starting.current=true;setBusy(true);setError("");try{await api(`/auto-reglue/runs/${row.run_id}/check`,{method:"POST"});accept(await api<Pilot>(`/auto-reglue/pilot/${job.id}`,{cache:"no-store"}));}catch(e){setError(e instanceof Error?e.message:"Не удалось проверить Webdev");}finally{starting.current=false;setBusy(false);}}
 const checkButton=(row:Row)=>row.run_id&&row.status!=="cancelled"?<button type="button" className="button secondary compact pilotCancelRow" aria-label={`Обновить результат ${row.project}`} title="Повторить загрузку Title/H1 из плана при необходимости и проверить свежие данные Webdev" disabled={busy||row.verification?.status==="queued"} onClick={()=>void checkRow(row)}><RefreshCw size={12}/>{row.verification?.status==="queued"?"Проверяем…":"Обновить"}</button>:null;
 const verification=(row:Row)=>row.verification&&row.verification.status!=="queued"?<details><summary>Проверка Webdev{row.verification.checked_at?` · ${date(row.verification.checked_at)}`:""}</summary><small>{row.verification.server}</small><small>{row.verification.code} {row.verification.message}</small>{row.verification.checks.map(item=><small key={item.code}>{item.ok?"✓":"×"} {item.label}</small>)}</details>:null;
 const monitoring=(row:Row)=>row.monitor?<small role="status">{row.monitor.message}{row.monitor.checked_at?` Проверено: ${date(row.monitor.checked_at)}.`:""}{row.monitor.state==="watching"&&row.monitor.deadline_at?` Автопроверка до ${date(row.monitor.deadline_at)}.`:""}</small>:null;
 const issueRows=job?.items.filter(row=>(row.monitor?.state==="manual"||["mismatch","failed"].includes(row.verification?.status||"")||["failed","partial","waiting"].includes(row.status)||!!row.notes?.length||row.internal_pages?.status==="failed"||row.internal_pages?.status==="partial"))||[];
 const preparing=job?.mode==="preview"&&(job.status==="queued"||job.replanning_requested);
 const sharesValid=Object.values(shares).every(value=>/^\d+$/.test(value)&&Number(value)<=100);
 const sharesChanged=!!job&&(Object.keys(shares) as (keyof Percentages)[]).some(key=>Number(shares[key])!==(job.percentages?.[key]??defaultPercentages[key]));
 const facets=React.useMemo(()=>scopeFacets(options?.groups||[],selection),[options,selection]);
 const selectionError=options?scopeError(options.groups,selection):"";
 const excluding=selection.scope_mode==="exclude";
 const scopeChanged=!!job&&!sameSelection(selection,savedSelection(job.planning_filter));
 const titleModeChanged=!!job&&(titleMode!==(job.title_rewrite_mode||"minimal")||planningMode!==(job.planning_mode||"percentages"));
 const visibleRows=logs?(job?.items||[]):(job?.items||[]).filter(row=>inPilotScope(row,selection));
 const canPrepare=!busy&&!job?.replanning_requested&&job?.mode!=="execution"&&loaded&&!!options&&sharesValid&&!selectionError&&facets.total>0;
 const canStart=!!options&&sharesValid&&!selectionError&&!sharesChanged&&!scopeChanged&&!titleModeChanged&&job?.mode==="preview"&&(job.status==="completed"||job.can_launch_while_generating===true)&&job.ready>0&&job.launch_enabled!==false&&(job.parallel_texts||!job.items.some(row=>row.status!=="skipped"&&(row.title_h1_error||row.paragraphs_error)))&&!busy;
 const rowVersionDisabled=busy||scopeChanged||sharesChanged||titleModeChanged||job?.status!=="completed"||!!job?.replanning_requested||!!job?.plan_outdated;
 const headingModeField=()=>logs?<span className="pilotHeadingModeSaved">{titleRewriteLabel(job?.title_rewrite_mode||"minimal")}</span>:<fieldset disabled={busy} className="pilotHeadingMode"><TemplateCombobox label="Режим Title/заголовков" value={titleMode} options={titleRewriteOptions} onChange={value=>setTitleMode(value as TitleRewriteMode)} placeholder="Найти режим"/></fieldset>;
 const percentageFields=(summary?:Pilot["variation_summary"])=> <div className="pilotShares">{([["subdomains","Поддомены"],["without_alternates","Без альтернейтов"],["redirects","301"],["title_h1","Title/H1"],["paragraphs","Абзацы"],["internal_pages","Внутренние страницы"]] as const).map(([key,label],index)=><React.Fragment key={key}>{index>0&&" · "}<label title="Количество в сохранённом плане / целевое количество. Новые проценты применяются после обновления плана.">{label}: {summary?`${job?.distribution?.counts[key]??summary[key]??0} / ${summary[`${key}_requested`]??0} `:""}({logs?shares[key]:<input type="number" min="0" max="100" step="1" aria-label={`${label}, процент`} value={shares[key]} disabled={busy||(planningMode==="mixed"&&["subdomains","without_alternates","redirects"].includes(key))} onChange={event=>setShares(current=>({...current,[key]:event.target.value}))} aria-invalid={!/^\d+$/.test(shares[key])||Number(shares[key])>100}/>}%)</label>{key==="title_h1"&&headingModeField()}</React.Fragment>)}</div>;
 const startButton=()=> <button className="button primary compact" type="button" disabled={!canStart} onClick={()=>void start()}><Play size={16}/>{busy?"Подождите…":"Запустить"}{job?` · ${job.ready}`:""}</button>;
 const returnTo=pilotDraftPath(`/auto-reglue/pilot${job?.id||initialId.current?`?id=${encodeURIComponent(job?.id||initialId.current!)}`:"?new=1"}`)||"/auto-reglue/pilot?new=1";
 function visitDrops(event:React.MouseEvent<HTMLAnchorElement>){
  if(busy||!loaded){event.preventDefault();return;}
  let saved=false;try{saved=saveDraftForDrops(window.sessionStorage,reserveToken,returnTo,{selection,titleMode,shares,planningMode});}catch{/* Storage access can be blocked by the browser. */}
  if(!saved){event.preventDefault();setError("Не удалось сохранить параметры для возврата. Разрешите хранение данных вкладки и повторите переход.");}
 }
 return <section className="dataPanel pilotPanel">
  <header className="pilotTools"><a className="button secondary compact" href="/auto-reglue"><ArrowLeft size={16}/>Массовые действия</a><a className="button secondary compact" href="/auto-reglue/pilot">Список заданий</a><h2><Bot size={20}/>{issuesOnly?"Auto Pilot — ошибки и примечания":logs?"Auto Pilot — отчёт":"Auto Pilot — план переклея"}</h2>
   {!logs&&<PilotDropsLink api={api} href={reserveVisitHref(returnTo,reserveToken)} onNavigate={visitDrops} disabled={busy||!loaded}/>}
   {!logs&&<button className="button secondary compact" type="button" disabled={!canPrepare} onClick={()=>void prepare()}><RefreshCw size={16}/>{job?.mode==="preview"&&job.status==="queued"?"Перезапустить планирование":job?"Обновить план":"Запланировать"}</button>}
   {!logs&&startButton()}
   {job?.mode==="execution"&&!logs&&<a className="button secondary compact" href={`/auto-reglue/pilot/logs?id=${job.id}`}><ScrollText size={16}/>Открыть отчёт</a>}
   {logs&&<a className="button secondary compact" href={`/auto-reglue/pilot${job?`?id=${job.id}`:""}`}>Показанный план</a>}
  </header>
  {job?.name&&<div className="pilotHint pilotReportHeading"><PilotReportIdentity task={{...job,name:`${job.mode==="preview"?"Черновик: ":"Задание: "}${job.name}`}}/></div>}
  {!logs&&<fieldset className="pilotFilters pilotPlanningFilters" disabled={busy||!loaded}>
   <div className="pilotScopeMode"><TemplateCombobox label="Режим переклея" value={planningMode} options={[{value:"percentages",label:"По заданным процентам"},{value:"mixed",label:"Смешанный",keywords:"все способы поровну"}]} onChange={value=>{setPlanningMode(value as "percentages"|"mixed");if(value==="mixed"){setShares(current=>({...current,subdomains:"50",without_alternates:"50",redirects:"50"}));}}} placeholder="Найти режим"/></div>
   <div className="pilotScopeMode"><TemplateCombobox label="Режим выборки" value={selection.scope_mode||"include"} options={[{value:"include",label:"Выбрать"},{value:"exclude",label:"Исключить"}]} onChange={value=>setSelection(current=>({...current,scope_mode:value as PilotScopeMode}))} placeholder="Найти режим"/></div>
   <PilotMultiSelect label="Бренд" allLabel={excluding?"Выберите бренды":"Все бренды"} clearLabel={excluding?"Снять выбор":undefined} values={selection.brands} options={facets.brands} total={facets.brandTotal} max={5} onChange={brands=>setSelection(current=>({...current,brands}))}/>
   <PilotMultiSelect label="ГЕО" allLabel={excluding?"Выберите ГЕО":"Все ГЕО"} clearLabel={excluding?"Снять выбор":undefined} values={selection.geos} options={facets.geos} total={facets.geoTotal} onChange={geos=>setSelection(current=>({...current,geos}))}/>
  </fieldset>}
  {!logs&&<p className="pilotHint">Уже переклеенные на текущей календарной неделе проекты исключаются. Неделя: понедельник–воскресенье, МСК.</p>}
  {!logs&&planningMode==="mixed"&&<p className="pilotHint">Смешанный переклей: доступные типы Main и схемы распределяются поровну; 301 — цель 50%. Без альтернейтов — половина совместимых корневых новорегов. Режим Title/заголовков, доли рерайта и новых страниц задаются независимо.</p>}
  {!logs&&job?.can_launch_while_generating&&<p className="pilotHint">Домены и схемы готовы — можно запускать. Тексты генерируются параллельно. Каждый проект сначала публикует готовый контент, затем выполняет переклей.</p>}
  {!logs&&excluding&&<p className="pilotHint">Исключаются выбранные бренды только в выбранных ГЕО. Проекты других брендов и ГЕО остаются в планировании.</p>}
  {!logs&&options&&<p className="pilotHint" role="status">{excluding?`Останется проектов: ${facets.total} · Исключено: ${facets.excluded}`:`Проектов в выборке: ${facets.total}`}{!facets.total?". Измените выбранные бренды или ГЕО.":""}{job&&scopeChanged?` · В текущем плане показано: ${visibleRows.length}. Полный состав появится после обновления плана.`:""}</p>}
  {!logs&&selectionError&&<p role="alert">{selectionError}</p>}
  {!logs&&(scopeChanged||sharesChanged||titleModeChanged)&&<p role="status">Параметры изменены. Нажмите «Обновить план», чтобы применить их.</p>}
  {job?.mode==="execution"&&<nav className="pilotTools" aria-label="Результаты переклея"><a className="button secondary compact" href={`/auto-reglue/pilot/logs?id=${job.id}`}>Все проекты · {job.items.length}</a><a className="button secondary compact" aria-current={issuesOnly?"page":undefined} href={`/auto-reglue/pilot/logs?id=${job.id}&issues=1`}><AlertTriangle size={16}/>Ошибки и примечания · {issueRows.length}</a></nav>}
  {error&&<p role="alert">{error}</p>}{job?.error&&<p role="alert">{job.error}</p>}
  {!job&&!error&&<p role="status">{loaded&&logs?"Запусков Auto Pilot пока нет.":loaded?"Выберите бренд и ГЕО и нажмите «Запланировать». Планирование начнётся только по кнопке.":"Загружаем план…"}</p>}
  {!logs&&!job?.variation_summary&&<div className="pilotProgress"><strong>Распределение планируемых переклеев</strong>{percentageFields()}<small>Проценты применяются при планировании. Доли округляются по математическим правилам.</small><PilotDistribution entered={shares} planningMode={planningMode} titleMode={titleMode}/></div>}
  {!logs&&!sharesValid&&<p role="alert">Укажите целые проценты от 0 до 100.</p>}
  {job&&<><div className="pilotProgress"><div><strong>{preparing?(job.replanning_requested?"Перезапускаем подготовку этого черновика":job.planning_phase||"Подготовка плана"):job.mode==="preview"?"План подготовлен":job.status==="completed"?"Обработка завершена":"Выполнение переклея"}</strong><span>{job.progress.percent}%</span></div><progress aria-label={job.mode==="preview"?"Подготовка плана":"Выполнение переклея"} value={job.progress.percent} max={100}/>
   {(preparing||job.mode==="execution")&&!!job.title_h1_progress?.total&&<small role="status">Title/H1: {textProgress(job.title_h1_progress)}.</small>}{(preparing||job.mode==="execution")&&!!job.paragraphs_progress?.total&&<small role="status">Абзацы: {textProgress(job.paragraphs_progress)}.</small>}<small>{job.mode==="preview"?`Схемы готовы: ${job.ready} · Всего проектов: ${job.progress.total}`:`Обработано: ${job.progress.done} из ${job.progress.total} · Успешно: ${job.counts.completed||0}`} · Пропущено: {job.counts.skipped||0} · Ошибок: {(job.counts.failed||0)+(job.counts.partial||0)} · План от {date(job.created_at)} МСК</small></div>
   {!logs&&<p className="pilotHint">«Запустить» выполняет только этот план вручную. Расписание и общий переключатель автоматики не меняются.</p>}
   {!logs&&job.title_h1_outdated&&<p role="status" className="pilotHint">Правило H1 обновлено: обновите строки с длинными H1 или весь план. Для выбранных проектов H1 будет сокращён до 3–5 слов.</p>}
   {!logs&&job.plan_outdated&&<p role="status" className="pilotHint">Порядок подбора доменов обновлён. Нажмите «Обновить план» перед запуском.</p>}
   {!logs&&<p className="muted pilotHint">Показаны конкретные домены и разметка по сохранённым настройкам. При изменении сетки запуск остановится с причиной; другой домен автоматически не подставляется. <span className="pilotAlternateChanged">Зелёным</span> выделены изменения альтернейта и новый внутряк в Canonical.</p>}
   {job.domain_summary&&<div className="pilotDomainSummary" aria-label="Фильтр по типу домена"><strong>{job.mode==="execution"?"Результаты выполнения":"Домены и страницы в плане"}</strong>{(Object.keys(domainLabels) as DomainFilter[]).map(kind=><button type="button" key={kind} className="button secondary compact" aria-pressed={domainFilter===kind} disabled={!job.domain_projects||!renderProjects} onClick={()=>setDomainFilter(current=>current===kind?null:kind)}>{kind==="internal_pages"&&job.mode==="preview"?"Добавление страниц":domainLabels[kind]}: <b>{job.domain_projects?.[kind]?.length??job.domain_summary?.[kind]??0}</b></button>)}{domainFilter&&<button type="button" className="button secondary compact" onClick={()=>setDomainFilter(null)}>Сбросить фильтр</button>}<small>Поддомены учтены по типу родительского домена; резерв входит в число дропов.{job.mode==="execution"?(domainFilter==="internal_pages"?" Показаны проекты с опубликованными внутренними страницами, включая частично выполненные задания.":" Фильтры доменов показывают подтверждённую смену Main."):""}</small></div>}
   {domainFilter&&job.domain_projects&&renderProjects&&<section aria-label={`Проекты: ${domainLabels[domainFilter]}`}>{renderProjects(job.domain_projects[domainFilter],domainLabels[domainFilter])}{!job.domain_projects[domainFilter].length&&<p role="status">В этой категории проектов нет.</p>}</section>}
   {job.variation_summary&&<div className="pilotProgress"><strong>Распределение среди {job.variation_summary.total} планируемых переклеев</strong>{percentageFields(job.variation_summary)}<small>Каноникал на себя: {job.variation_summary.canonical_self} · На внутряк: {job.variation_summary.canonical_internal} · Разновидностей в плане: {job.variation_summary.used_variants}. Доли округлены по математическим правилам.</small>{job.variation_summary.warning&&<p role="status">{job.variation_summary.warning}</p>}<PilotDistribution entered={shares} saved={job.percentages} data={job.distribution} planningMode={planningMode} changed={sharesChanged||scopeChanged||titleModeChanged} titleMode={titleMode} savedTitleMode={job.title_rewrite_mode||"minimal"}/></div>}

   {!domainFilter&&<>
   {issuesOnly&&<div className="pilotTools" role="tablist" aria-label="Ошибки и примечания"><button type="button" role="tab" aria-selected={issueTab==="results"} className="button secondary compact" onClick={()=>setIssueTab("results")}>Ошибки и примечания</button><button type="button" role="tab" aria-selected={issueTab==="journal"} className="button secondary compact" onClick={()=>setIssueTab("journal")}>Журнал операций</button></div>}
   {issuesOnly?(issueTab==="results"?<><table className="pilotTable pilotIssues"><colgroup><col style={{width:"19%"}}/><col style={{width:"19%"}}/><col style={{width:"15%"}}/><col style={{width:"32%"}}/><col style={{width:"15%"}}/></colgroup><thead><tr><th>Проект</th><th>Новый Main</th><th>Этап / состояние</th><th>Причина</th><th>Проверки / действия</th></tr></thead><tbody>{issueRows.map(row=><tr key={row.site_id}><td><a href={`/project-network/${encodeURIComponent(row.project)}/`}>{flag(row.geo)} {row.project}</a></td><td>{row.new_main||"—"}</td><td><strong>{labels[row.status]}</strong><small>{actions[row.phase||""]||row.phase}</small></td><td>{row.reason||(!row.internal_pages?.reason&&"Ожидается подтверждение Webdev.")}<PilotInternalPages data={row.internal_pages} project={row.project}/>{row.notes?.map((note,i)=><small key={i} className="pilotNote">Примечание: {note.domain} — {note.message}</small>)}{row.confirmation?.exhausted&&row.monitor?.state!=="watching"&&<small>Автопроверки завершены. Требуется проверка результата.</small>}</td><td>{checkButton(row)}{verification(row)}{monitoring(row)}<small>Повторных проверок: {row.confirmation?.attempt??0}{row.confirmation?.limit?` / ${row.confirmation.limit}`:""}</small>{row.confirmation?.checked_at&&<small>{date(row.confirmation.checked_at)}</small>}{row.run_id&&["waiting","partial"].includes(row.status)&&<button type="button" className="button secondary compact pilotCancelRow" aria-label={`Отменить переклей ${row.project}`} disabled={busy} onClick={()=>void cancelRow(row)}><X size={12}/>Отменить переклей</button>}</td></tr>)}</tbody></table>{!issueRows.length&&<p role="status">Ошибок, ожиданий и примечаний нет.</p>}</>:null):<table className="pilotTable"><colgroup><col style={{width:"3%"}}/><col style={{width:logs?"13%":"16%"}}/><col style={{width:"13%"}}/><col style={{width:"18%"}}/><col style={{width:"22%"}}/><col style={{width:logs?"14%":"17%"}}/><col style={{width:logs?"9%":"11%"}}/>{logs&&<col style={{width:"8%"}}/>}</colgroup><thead><tr><th>№</th><th>Проект Webdev</th><th>Новый Main</th><th>Схема переклея</th><th>Альтернейт после переклея</th><th>Title / H1</th><th>Состояние</th>{logs&&<th>Дата переклея · МСК</th>}</tr></thead><tbody>{visibleRows.map((row,i)=><tr key={row.site_id} className={`pilotRow ${row.status}`}><td>{i+1}</td><td><a href={`/project-network/${encodeURIComponent(row.project)}/`}><span title={row.geo} aria-label={`GEO ${row.geo}`}>{flag(row.geo)}</span> {row.project}</a>{row.emergency_subdomain&&<span title="Нет резервов: используется поддомен вне процентной квоты. Добавьте новореги в сетку." aria-label="Нужно добавить новореги" style={{color:"var(--warning, #b7791f)",marginLeft:6}}>⚠</span>}{row.old_main&&<small>Сейчас: {row.old_main}</small>}<small>Бренд: {row.brand||"Общие ключи"}</small>{!logs&&job.mode==="preview"&&!!row.versions?.length&&<PilotVersionTabs project={row.project} versions={row.versions} selected={row.selected_version||1} disabled={rowVersionDisabled} onSelect={version=>void selectVersion(row,version)}/>}</td><td><strong>{row.new_main||"—"}</strong>{row.source_project&&<small>Из: {row.source_project}</small>}</td><td>{row.scheme||row.reason||"Подготавливается…"}<PilotInternalPages data={row.internal_pages} project={row.project}/>{row.canonical&&<details><summary>Canonical</summary><CanonicalCode row={row}/></details>}</td><td>{row.alternate?<AlternateCode before={row.alternate_before} after={row.alternate}/>:row.new_main?(row.alternates_enabled?"Не заданы":"Выключены"):"—"}{row.updated_fields?.alternates&&<UpdatedLabel field="Альтернейт"/>}</td><td><TitleH1 row={row}/><Paragraphs row={row}/></td><td>{!logs&&job.mode==="preview"&&<button className="button secondary compact pilotRefreshRow" type="button" aria-label={`Обновить план ${row.project}`} title="Создать следующую версию всего проекта. После пяти версий список очищается и начинается с первой." disabled={rowVersionDisabled} onClick={()=>void refreshRow(row)}><RefreshCw size={14}/></button>}{job.mode==="execution"&&checkButton(row)}<strong>{job.mode==="preview"&&needsTextRetry(row)?"Нужна новая генерация":labels[row.status]||row.status}</strong>{row.reglue_status&&<small>Переклей: {labels[row.reglue_status]||row.reglue_status}</small>}{verification(row)}{monitoring(row)}<div className="pilotRowProgress"><progress aria-label={`Прогресс ${row.project}`} value={job.mode==="preview"||row.status==="skipped"?0:row.progress} max={100}/><small>{job.mode==="preview"?"0% · Переклей не запущен":row.status==="skipped"?"Не участвует":`${row.progress}% · ${actions[row.phase||""]||row.phase||""}`}</small></div>{logs&&row.status==="waiting"&&<TransferConfirmation status={row.status} phase={row.phase} data={row.confirmation}/>} {row.reason&&<small>{row.reason}</small>}{row.notes?.map(note=><small key={note.domain} className="pilotNote" title={date(note.checked_at)}>Примечание: {note.domain} — {note.message}</small>)}{job.mode==="execution"&&row.run_id&&["planned","queued","running","waiting","partial"].includes(row.status)&&<button type="button" className="button secondary compact pilotCancelRow" aria-label={`Отменить переклей ${row.project}`} title="Остановить дальнейшие операции этого проекта" disabled={busy} onClick={()=>void cancelRow(row)}><X size={12}/>Отменить переклей</button>}</td>{logs&&<td>{row.performed_at?date(row.performed_at):"—"}</td>}</tr>)}</tbody></table>}
   {!visibleRows.length&&<p>{scopeChanged?"В текущем плане нет проектов, подходящих под выбранные фильтры. Нажмите «Обновить план».":"Нет доступных проектов со статусом «Массовые действия»."}</p>}
   </>}
   {!logs&&<footer className="pilotTools">{startButton()}</footer>}
   {!domainFilter&&issuesOnly&&issueTab==="journal"&&<div className="pilotEvents" role="tabpanel"><h3>Журнал операций</h3>{!job.events.length&&<p className="muted">Операции появятся после начала выполнения. Страницу можно закрыть — журнал сохранится.</p>}{job.events.map(event=><article key={event.id}><time>{date(event.at)}</time><strong>{job.items.find(r=>r.run_id===event.run_id)?.project}</strong><span>{actions[event.action]||event.action} · {event.status==="confirmed"?"Подтверждено":labels[event.status]||event.status}</span>{event.message&&<p>{event.message}</p>}</article>)}</div>}
  </>}
 </section>;
}
