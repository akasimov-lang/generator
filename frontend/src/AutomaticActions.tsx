import React from "react";
type Row={id:string;title:string;status:string;created_at:string;actor:string;message:string;confirmed:boolean;url:string|null;changes:{field:string;before:unknown;after:unknown}[]};
type Api=<T>(path:string,options?:RequestInit)=>Promise<T>;
const labels:Record<string,string>={completed:"Выполнено",confirmed:"Подтверждено",running:"Выполняется",queued:"В очереди",pending:"Ожидание",waiting:"Ожидание подтверждения",failed:"Ошибка",partial:"Выполнено частично",skipped:"Пропущено",cancelled:"Остановлено"};
function text(value:unknown){return value==null?"Не сохранено":typeof value==="string"?value:JSON.stringify(value,null,2);}
export function AutomaticActions({siteId,api}:{siteId:string;api:Api}){
 const [rows,setRows]=React.useState<Row[]>([]),[error,setError]=React.useState(""),[loading,setLoading]=React.useState(true);
 React.useEffect(()=>{let current=true;setLoading(true);setRows([]);setError("");void api<{items:Row[]}>(`/auto-reglue/projects/${siteId}/history`,{cache:"no-store"}).then(data=>{if(current)setRows(data.items);}).catch(e=>{if(current)setError(e instanceof Error?e.message:"Не удалось загрузить историю");}).finally(()=>{if(current)setLoading(false);});return()=>{current=false;};},[api,siteId]);
 return <section className="networkSection"><h3>История массовых и автоматических действий</h3>{loading?<p role="status">Загружаем историю…</p>:error?<p role="alert">{error}</p>:!rows.length?<p className="muted">Записанных действий пока нет.</p>:rows.map(row=><article className="networkSection" key={row.id}>
 <strong>{row.title}</strong> — {labels[row.status]||row.status}<p className="muted">{new Date(row.created_at).toLocaleString("ru-RU",{timeZone:"Europe/Moscow"})} МСК · {row.actor}</p>{row.message&&<p>{row.message}</p>}
 {row.changes.length?<details><summary>Было / {row.confirmed?"стало":"запланировано"} · {row.changes.length}</summary>{row.changes.map((change,i)=><div key={i}><strong>{change.field}</strong><div className="networkAlternatesComparison"><div><small>Было</small><pre style={{whiteSpace:"pre-wrap",overflowWrap:"anywhere",maxHeight:240,overflow:"auto"}}>{text(change.before)}</pre></div><div><small>{row.confirmed?"Стало":"Запланировано"}</small><pre style={{whiteSpace:"pre-wrap",overflowWrap:"anywhere",maxHeight:240,overflow:"auto"}}>{text(change.after)}</pre></div></div></div>)}</details>:<p className="muted">Сравнение до/после в этой записи не сохранено.</p>}
 {row.url&&<a href={row.url}>Открыть отчёт</a>}</article>)}</section>;
}
