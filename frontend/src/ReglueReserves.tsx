import React from "react";
import { Plus, X, ArrowLeft, RefreshCw, Copy, Download, Database } from "lucide-react";
import { TemplateCombobox } from "./TemplateCombobox";
import { reserveReturnHref } from "./pilotDropsNavigation";
import "./styles/reglue-reserves.css";

type Api = <T>(path: string, options?: RequestInit) => Promise<T>;
type Entry = {id:string; domain:string; domain_type:"drop"|"newreg"; brand:string|null; status:string; created_at:string; assigned_at:string|null; project:string|null; project_restricted:boolean; fibery_name:string|null; error:string|null; run_status:string|null; membership_checked_at?:string|null};
export type ReserveRefresh = {id:string;status:string;progress:{done:number;total:number;percent:number};issues:{project:string|null;error:string}[];error:string|null;started_at:string|null;finished_at:string|null};
type Inventory = {items:Entry[]; total:number; available:number; brands:string[];refresh?:ReserveRefresh|null};
type ImportResult = {added:string[]; duplicates:string[]; errors:{domain:string;error:string}[]};
const statusLabels:Record<string,string> = {banned:"БАН", available:"В резерве", reserved:"Выделен запуску", assigned:"Добавлен в сетку", error:"Нужна проверка"};
const date = (value:string|null) => value ? new Date(value).toLocaleString("ru-RU") : "—";
const empty:Inventory = {items:[],total:0,available:0,brands:[]};

function useInventory(api:Api) {
 const [data,setData]=React.useState<Inventory>(empty),[error,setError]=React.useState(""),[loading,setLoading]=React.useState(true),[starting,setStarting]=React.useState(false);
 const refreshRequest=React.useRef<string|null>(null);
 const refreshing=starting||!!data.refresh&&["queued","running"].includes(data.refresh.status);
 const load=React.useCallback(async()=>{setLoading(true);setError("");try{setData(await api<Inventory>("/auto-reglue/reserves"));}catch(e){setError(e instanceof Error?e.message:"Не удалось загрузить резерв");}finally{setLoading(false);}},[api]);
 React.useEffect(()=>{void load();},[load]);
 React.useEffect(()=>{if(!data.refresh||!["queued","running"].includes(data.refresh.status))return;
  const timer=window.setInterval(()=>{void api<Inventory>("/auto-reglue/reserves").then(setData).catch(e=>setError(e instanceof Error?e.message:"Не удалось проверить обновление"));},2000);
  return()=>window.clearInterval(timer);
 },[api,data.refresh?.id,data.refresh?.status]);
 const refresh=React.useCallback(async()=>{if(refreshing)return;setStarting(true);setError("");refreshRequest.current??=crypto.randomUUID();try{
  const result=await api<ReserveRefresh>("/auto-reglue/reserves/refresh",{method:"POST",body:JSON.stringify({request_id:refreshRequest.current})});
  refreshRequest.current=null;setData(current=>({...current,refresh:result}));
 }catch(e){setError(e instanceof Error?e.message:"Не удалось обновить резерв");}finally{setStarting(false);}},[api,refreshing]);
 return {data,error,loading,load,refresh,refreshing};
}

function ImportDialog({api,brands,onClose,onSaved}:{api:Api;brands:string[];onClose:()=>void;onSaved:()=>void}) {
 const dialog=React.useRef<HTMLDialogElement>(null);
 const [domains,setDomains]=React.useState(""),[brand,setBrand]=React.useState(""),[kind,setKind]=React.useState("drop"),[busy,setBusy]=React.useState(false),[error,setError]=React.useState("");
 const [result,setResult]=React.useState<ImportResult|null>(null);
 React.useEffect(()=>{dialog.current?.showModal();return()=>dialog.current?.close();},[]);
 async function submit(e:React.FormEvent){e.preventDefault();if(busy||!domains.trim())return;setBusy(true);setError("");try{const r=await api<ImportResult>("/auto-reglue/reserves",{method:"POST",body:JSON.stringify({domains,brand,domain_type:kind})});setResult(r);setDomains(r.errors.map(row=>row.domain).join("\n"));onSaved();}catch(e){setError(e instanceof Error?e.message:"Не удалось добавить домены");}finally{setBusy(false);}}
 return <dialog ref={dialog} className="reserveDialog" aria-labelledby="reserve-title" onCancel={e=>{e.preventDefault();if(!busy)onClose();}} onClick={e=>{if(e.target===e.currentTarget&&!busy){const r=e.currentTarget.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)onClose();}}}>
  <form onSubmit={submit}><header><h2 id="reserve-title">Добавить домены в резерв</h2><button type="button" className="button secondary compact" aria-label="Закрыть окно" disabled={busy} onClick={onClose}><X size={18}/></button></header>
   <p className="muted">Общая база для массового переклея. Укажите домены через пробел, запятую или с новой строки.</p>
   <fieldset disabled={busy} className="reserveFormFields"><div className="reserveImportOptions"><TemplateCombobox label="Тип доменов" value={kind} onChange={setKind} options={[{value:"drop",label:"Дропы"},{value:"newreg",label:"Новореги"}]}/><TemplateCombobox label="Бренд (необязательно)" value={brand} onChange={setBrand} options={[{value:"",label:"Для всех брендов"},...brands.map(b=>({value:b,label:b}))]}/></div>
   <label>Домены<textarea autoFocus rows={9} value={domains} onChange={e=>setDomains(e.target.value)} placeholder={"example.com\nexample.org, example.net"} maxLength={1500000}/></label></fieldset>
   <p className="muted">Бренд можно указать отдельно для каждого домена на странице резерва. Дропы из этой базы не используются для Азербайджана.</p>
   {error&&<p role="alert" className="reserveError">{error}</p>}
   {result&&<div role="status" className="reserveImportResult"><p>Добавлено: {result.added.length}. Уже в резерве: {result.duplicates.length}. Ошибок: {result.errors.length}.</p>{result.errors.length>0&&<ul>{result.errors.map((r,i)=><li key={i}>{r.domain}: {r.error}</li>)}</ul>}</div>}
   <footer><button className="button primary" disabled={busy||!domains.trim()} type="submit">{busy?"Отправляем…":"Отправить"}</button></footer>
  </form>
 </dialog>;
}

export function ReservePoolButton({api}:{api:Api}) {
 const {data,error,loading,load}=useInventory(api);const [open,setOpen]=React.useState(false);
 return <div className="reservePoolShortcut"><button type="button" className="button secondary compact" onClick={()=>setOpen(true)} title={error||`Добавлено: ${data.total}. Доступно для подбора: ${data.available}.`}><Plus size={16}/> drops <span className="reserveCount" aria-label={`Добавлено доменов: ${data.total}`}>{loading?"…":error?"!":data.total}</span></button><a href="/auto-reglue/reserves">показать</a>{error&&<small role="alert">{error}</small>}{open&&<ImportDialog api={api} brands={data.brands} onClose={()=>setOpen(false)} onSaved={()=>void load()}/>}</div>;
}

export function DropsReserveLink({href,available,loading=false,error="",disabled=false,onNavigate}:{href:string;available:number;loading?:boolean;error?:string;disabled?:boolean;onNavigate?:(event:React.MouseEvent<HTMLAnchorElement>)=>void}) {
 const label=loading?"Доступные резервы загружаются":error?"Не удалось загрузить количество резервов":`Доступных резервов: ${available}`;
 return <a className="button secondary compact" href={disabled?undefined:href} aria-disabled={disabled||undefined} title={error||label} onClick={onNavigate} onAuxClick={onNavigate} onContextMenu={onNavigate}><Database size={16}/>Drops <span className="reserveCount" aria-label={label}>{loading?"…":error?"!":available}</span></a>;
}

export function PilotDropsLink({api,href,onNavigate,disabled}:{api:Api;href:string;onNavigate:(event:React.MouseEvent<HTMLAnchorElement>)=>void;disabled?:boolean}) {
 const {data,error,loading}=useInventory(api);
 return <DropsReserveLink href={href} available={data.available} error={error} loading={loading} disabled={disabled} onNavigate={onNavigate}/>;
}

export function ReserveBackLink({search}:{search:string}) {
 const href=reserveReturnHref(search);
 return <a className="button secondary compact" href={href||"/auto-reglue"}><ArrowLeft size={16}/>{href?"Назад в черновик":"Массовые действия"}</a>;
}

function BrandEditor({entry,brands,api,onSaved}:{entry:Entry;brands:string[];api:Api;onSaved:()=>void}) {
 const [draft,setDraft]=React.useState(entry.brand||""),[busy,setBusy]=React.useState(false),[error,setError]=React.useState("");
 React.useEffect(()=>setDraft(entry.brand||""),[entry.brand]);
 async function save(){if(busy||draft===(entry.brand||""))return;setBusy(true);setError("");try{await api(`/auto-reglue/reserves/${entry.id}`,{method:"PATCH",body:JSON.stringify({brand:draft})});onSaved();}catch(e){setError(e instanceof Error?e.message:"Бренд не сохранён");}finally{setBusy(false);}}
 if(entry.status!=="available")return <>{entry.brand||"Для всех брендов"}</>;
 return <fieldset disabled={busy} className="reserveFormFields reserveBrandEditor"><TemplateCombobox label={`Бренд: ${entry.domain}`} value={draft} onChange={setDraft} options={[{value:"",label:"Для всех брендов"},...Array.from(new Set([...brands,...(entry.brand?[entry.brand]:[])])).map(b=>({value:b,label:b}))]}/>{draft!==(entry.brand||"")&&<button type="button" className="button secondary compact" onClick={()=>void save()}>Сохранить</button>}{error&&<small role="alert" className="reserveError">{error}</small>}</fieldset>;
}

export function ReglueReservesPage({api}:{api:Api}) {
 const {data,error,loading,load,refresh,refreshing}=useInventory(api);const [open,setOpen]=React.useState(false),[search,setSearch]=React.useState("");
 const [exportMessage,setExportMessage]=React.useState(""),[exportError,setExportError]=React.useState("");
 const items=data.items.filter(r=>[r.domain,r.brand,r.project,r.fibery_name,r.error].join(" ").toLocaleLowerCase().includes(search.toLocaleLowerCase().trim()));
 async function copyDomains(){setExportMessage("");setExportError("");try{await navigator.clipboard.writeText(items.map(row=>row.domain).join("\n"));setExportMessage(`Скопировано доменов: ${items.length}`);}catch{setExportError("Не удалось скопировать список. Разрешите доступ к буферу обмена в браузере.");}}
 function downloadCsv(){
  const rows:unknown[][]=[["Домен","Тип","Бренд","Добавлен в резерв","Добавлен в сетку","Сетка","Имя Fibery","Проверено","Состояние","Ошибки"],...items.map(r=>[r.domain,r.domain_type==="drop"?"Дроп":"Новорег",r.brand||"Для всех брендов",date(r.created_at),date(r.assigned_at),r.project||(r.project_restricted?"Нет доступа":""),r.fibery_name||"",date(r.membership_checked_at||null),statusLabels[r.status]||r.status,r.error||""])];
  const cell=(value:unknown)=>{let text=String(value??"");if(/^[\s]*[=+@-]/.test(text)||/^[\t\r\n]/.test(text))text="'"+text;return '"'+text.replace(/"/g,'""')+'"';};
  const url=URL.createObjectURL(new Blob(["\uFEFF"+rows.map(row=>row.map(cell).join(";")).join("\r\n")],{type:"text/csv;charset=utf-8"}));
  const link=document.createElement("a");link.href=url;link.download=`reglue-reserves-${new Date().toISOString().slice(0,10)}.csv`;document.body.appendChild(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
 }
 return <section className="dataPanel reserveInventory"><header className="reservePageTools"><ReserveBackLink search={window.location.search}/><span>Добавлено: <b>{data.total}</b> · В резерве: <b>{data.available}</b></span><button type="button" className="button secondary compact" onClick={()=>setOpen(true)}><Plus size={16}/> drops</button><button type="button" className="button secondary compact" onClick={()=>void refresh()} disabled={loading||refreshing}><RefreshCw size={16}/> {refreshing?"Обновляем…":"Обновить"}</button><button type="button" className="button secondary compact" title="Скопировать домены текущей выборки, каждый с новой строки" disabled={loading||!items.length} onClick={()=>void copyDomains()}><Copy size={16}/> Скопировать список</button><button type="button" className="button secondary compact" title="Скачать текущую выборку со всеми столбцами в CSV" disabled={loading||!items.length} onClick={downloadCsv}><Download size={16}/> Скачать CSV</button></header>{exportMessage&&<p role="status">{exportMessage}</p>}{exportError&&<p role="alert" className="reserveError">{exportError}</p>}
 {data.refresh&&<ReserveRefreshStatus refresh={data.refresh}/>}
 <p className="muted">Без бренда домен доступен всем проектам. Бренд ограничивает подбор этим брендом. Дропы из резерва исключены для GEO Азербайджан. Домены, уже бывшие Main в принимающей сетке, не используются повторно.</p>
 <label>Поиск<input type="search" placeholder="Домен, бренд, сетка, Fibery или ошибка" value={search} onChange={e=>setSearch(e.target.value)}/></label>
 {error&&<p role="alert" className="reserveError">{error}</p>}
 <div className="reserveTableScroll"><table><thead><tr>{["Домен","Тип","Бренд","Добавлен в резерв","Добавлен в сетку","Сетка","Имя Fibery","Состояние","Ошибки"].map(h=><th key={h}>{h}</th>)}</tr></thead><tbody>{items.map(r=><tr key={r.id}><td><b>{r.domain}</b></td><td>{r.domain_type==="drop"?"Дроп":"Новорег"}</td><td><BrandEditor entry={r} brands={data.brands} api={api} onSaved={()=>void load()}/></td><td>{date(r.created_at)}</td><td>{date(r.assigned_at)}</td><td>{r.project?<a href={`/project-network/${encodeURIComponent(r.project)}/`}>{r.project}</a>:r.project_restricted?"Нет доступа":"—"}</td><td>{r.fibery_name||"—"}{r.membership_checked_at&&<small className="reserveChecked">Проверено: {date(r.membership_checked_at)}</small>}</td><td>{statusLabels[r.status]||r.status}{r.run_status==="completed"&&<small> · Main назначен</small>}</td><td className="reserveError">{r.error||"—"}</td></tr>)}{!items.length&&<tr><td colSpan={9}>{loading?"Загрузка…":search?"Домены не найдены.":"В резерве пока нет доменов. Добавьте список через «+ drops»."}</td></tr>}</tbody></table></div>
 {open&&<ImportDialog api={api} brands={data.brands} onClose={()=>setOpen(false)} onSaved={()=>void load()}/>}
 </section>;
}

export function ReserveRefreshStatus({refresh}:{refresh:ReserveRefresh}) {
 const active=["queued","running"].includes(refresh.status);
 return <div role="status" className="reserveRefreshStatus"><p>{active?`Проверяем сетки в Webdev: ${refresh.progress.done} / ${refresh.progress.total||"…"}`:refresh.status==="completed"?`Резерв обновлён: ${date(refresh.finished_at)}`:"Обновление завершено не полностью. Недоступные сетки сохранили предыдущие данные."}</p>{active&&<progress max={100} value={refresh.progress.percent} aria-label="Обновление резервов"/>}{refresh.error&&<p className="reserveError">{refresh.error}</p>}{refresh.issues.length>0&&<details><summary>Не удалось проверить: {refresh.issues.length}</summary><ul>{refresh.issues.map((issue,i)=><li key={i}>{issue.project?`${issue.project}: `:""}{issue.error}</li>)}</ul></details>}</div>;
}
