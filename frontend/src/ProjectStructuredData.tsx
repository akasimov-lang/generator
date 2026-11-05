import React from "react";
import { Code2, Pencil, Save, X } from "lucide-react";
import "./styles/project-structured-data.css";

type Api = <T>(path: string, options?: RequestInit) => Promise<T>;
export type StructuredData = { revision?: string; enabled: boolean | null; markup: string; verified_at?: string | null; source: "webdev" };

export async function readStructuredData(api: Api, siteId: string): Promise<StructuredData> {
 const value=await api<StructuredData>(`/sites/${encodeURIComponent(siteId)}/structured-data`,{cache:"no-store"});
 if(!value||!(typeof value.enabled==="boolean"||value.enabled===null)||typeof value.markup!=="string"||value.source!=="webdev"){
  throw new Error("Webdev не вернул состояние и код микроразметки. Повторите обновление данных.");
 }
 return value;
}

export function StructuredDataView({data,loading=false,error=""}:{data:StructuredData|null;loading?:boolean;error?:string}) {
 const verified=data?.verified_at?new Date(data.verified_at):null;
 return <section className="networkSection projectStructuredData" aria-label="Микроразметка проекта">
  <div className="networkMarkupHeading"><h3><Code2 size={18}/>Микроразметка</h3>
   {data&&!loading&&!error&&<span className={`structuredDataState ${data.enabled===null?"unknown":data.enabled?"on":"off"}`}>{data.enabled===null?"Состояние не подтверждено":data.enabled?"Включена":"Выключена"}</span>}
  </div>
  {loading?<p role="status" className="muted">Загружаем микроразметку…</p>:error?<p role="alert">Не удалось получить микроразметку. {error}</p>:data?<>
   {data.markup.trim()?<pre tabIndex={0} aria-label="Код микроразметки"><code>{data.markup}</code></pre>:<p className="muted">{data.enabled?"Микроразметка включена, но Webdev не вернул её код.":"Код микроразметки не задан."}</p>}
   <small className="muted">Источник: Webdev{verified&&Number.isFinite(verified.getTime())?` · Проверено: ${verified.toLocaleString("ru-RU",{timeZone:"Europe/Moscow"})} МСК`:""}</small>
  </>:<p className="muted">Состояние микроразметки ещё не получено.</p>}
 </section>;
}

type SaveRequest = { request_id: string; revision: string; markup: string };
type SaveResult = { data: StructuredData | null; operation: { id: string; status: string; message: string } };

export function ProjectStructuredData({api,siteId,refreshKey,backgroundRefreshKey}:{api:Api;siteId:string;refreshKey?:string|number;backgroundRefreshKey?:string|number}) {
 const [data,setData]=React.useState<StructuredData|null>(null);
 const [loading,setLoading]=React.useState(true),[error,setError]=React.useState("");
 const [editing,setEditing]=React.useState(false),[draft,setDraft]=React.useState("");
 const [busy,setBusy]=React.useState(false),[waiting,setWaiting]=React.useState(false);
 const [message,setMessage]=React.useState("");
 const attempt=React.useRef<SaveRequest|null>(null);
 const editRevision=React.useRef("");
 const snapshot=React.useRef<StructuredData|null>(null); snapshot.current=data;
 const lastRead=React.useRef<{siteId:string;refreshKey?:string|number}|null>(null);
 React.useEffect(()=>{
  const previous=lastRead.current;
  if(previous?.siteId===siteId&&previous.refreshKey===refreshKey&&snapshot.current?.enabled===false&&!snapshot.current.markup.trim())return;
  lastRead.current={siteId,refreshKey};
  let current=true;setLoading(true);setError("");
  void readStructuredData(api,siteId).then(value=>{if(current)setData(value);}).catch(reason=>{
   if(current)setError(reason instanceof Error?reason.message:"Повторите обновление данных.");
  }).finally(()=>{if(current)setLoading(false);});
  return()=>{current=false;};
 },[api,siteId,refreshKey,backgroundRefreshKey]);
 function receive(value:SaveResult) {
  if(value.data)setData(value.data);
  setMessage(value.operation.message);
  setWaiting(value.operation.status!=="confirmed"&&value.operation.status!=="failed");
  if(value.operation.status==="confirmed") {
   setEditing(false);attempt.current=null;
  } else if(value.operation.status==="failed") {
   setError(value.operation.message);attempt.current=null;
  }
 }
 async function save() {
  const previous=attempt.current;
  const payload=previous&&previous.markup===draft&&previous.revision===editRevision.current?previous:
   {request_id:crypto.randomUUID(),revision:editRevision.current,markup:draft};
  attempt.current=payload;setBusy(true);setError("");setMessage("");
  try {
   receive(await api<SaveResult>(`/sites/${encodeURIComponent(siteId)}/structured-data`,{
    method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)}));
  } catch(reason) {
   setError(reason instanceof Error?reason.message:"Не удалось сохранить микроразметку.");
   // Keep both the text and request id: a retry cannot submit the same write twice.
  } finally {setBusy(false);}
 }
 async function check() {
  if(!attempt.current)return;
  setBusy(true);setError("");
  try {receive(await api<SaveResult>(`/sites/${encodeURIComponent(siteId)}/structured-data/operations/${attempt.current.request_id}`,{cache:"no-store"}));}
  catch(reason){setError(reason instanceof Error?reason.message:"Не удалось проверить сохранение.");}
  finally{setBusy(false);}
 }
 return <div className="structuredDataEditor">
  {editing?<section className="networkSection projectStructuredData" aria-label="Редактор микроразметки">
   <div className="networkMarkupHeading"><h3><Code2 size={18}/>Микроразметка</h3>
    <div className="structuredDataActions">
     <button type="button" className="button primary compact" disabled={busy||waiting||!draft.trim()} onClick={()=>void save()}><Save size={15}/>{busy?"Сохраняем…":"Сохранить"}</button>
     <button type="button" className="button secondary compact" disabled={busy||waiting} onClick={()=>{setEditing(false);setError("");attempt.current=null;}}><X size={15}/>Отмена</button>
    </div>
   </div>
   <textarea className="structuredDataCode" aria-label="Код микроразметки" spellCheck={false} rows={18} value={draft} disabled={busy||waiting} onChange={event=>setDraft(event.target.value)}/>
   <small className="muted">{data?.enabled?"Включена":"Выключена"} · Сохранение в Webdev</small>
  </section>:<>
   <StructuredDataView data={data} loading={loading} error={error}/>
   {data&&!loading&&!error&&<button type="button" className="button secondary compact structuredDataEdit" disabled={!data.revision||data.enabled===null} onClick={()=>{
    setDraft(data.markup);editRevision.current=data.revision||"";setEditing(true);setMessage("");setError("");attempt.current=null;
   }}><Pencil size={15}/>Редактировать</button>}
  </>}
  {editing&&error&&<p role="alert" className="error">{error}</p>}
  {message&&<p role="status" className="muted">{message}</p>}
  {editing&&attempt.current&&<button type="button" className="button secondary compact" disabled={busy} onClick={()=>void check()}>Проверить сохранение</button>}
 </div>;
}
