import React from 'react';
import {RefreshCw} from 'lucide-react';
import {reportCountry} from './reportGeo';
import './SitemapReport.css';
type Check={status?:number;valid?:boolean;count?:number;missing?:number;extra?:number;duplicates?:number;error?:string;location?:string;checked_at?:string};
type Row={site_id:string;project:string;main?:string;geo?:string;fibery_name?:string;fibery_url?:string;status:string;error?:string;finished_at?:string;recheck?:{id:string;requested_at?:string};fibery_task?:{url?:string};sitemap?:{before?:Check;after?:Check;action?:string;expected_count?:number;internal_pages?:number;sitemap_url?:string;webdev_verified?:boolean}};
export type SitemapReportData={entries:Row[]};
const obj=(v:unknown):Record<string,unknown>=>v&&typeof v==='object'&&!Array.isArray(v)?v as Record<string,unknown>:{};
export function normalizeSitemaps(raw:unknown):SitemapReportData {
 const rows=obj(raw).entries;
 return {entries:Array.isArray(rows)?rows.filter(v=>typeof obj(v).site_id==='string'&&typeof obj(v).project==='string') as Row[]:[]};
}
const safe=(url?:string)=>{try{const u=new URL(url||'');return ['https:','http:'].includes(u.protocol)&&!u.username&&!u.password?u.href:undefined;}catch{return undefined;}};
const fibery=(url?:string)=>{const u=safe(url);return u&&new URL(u).hostname==='hzhz.fibery.io'?u:undefined;};
const date=(v?:string)=>v&&!Number.isNaN(Date.parse(v))?new Date(v).toLocaleString('ru-RU',{timeZone:'Europe/Moscow'}):'—';
const labels:Record<string,string>={completed:'Готово',failed:'Ошибка',partial:'Частично',running:'Выполняется',pending:'Ожидает',skipped:'Пропущено'};
const actions:Record<string,string>={check_error:'Ошибка перепроверки',checking:'Проверяется',updated:'Обновлён и проверен',verified:'Актуален, проверен',saved_unconfirmed:'Сохранён в Webdev; публично не подтверждён',hosting_error:'Ошибка публичного sitemap',write_error:'Запись не подтверждена'};
const checking=(r:Row)=>!!r.recheck&&['running','pending'].includes(r.status);
const problem=(r:Row)=>['failed','partial'].includes(r.status)||checking(r);
type Api=<T>(path:string,options?:RequestInit)=>Promise<T>;
export function createSitemapRecheck(api:Api,reportId:string,newId=()=>crypto.randomUUID()) {
 const pending=new Set<string>(),ids=new Map<string,string>();
 return async (siteId:string)=>{
  if(pending.has(siteId))return;
  pending.add(siteId);
  try{
   const id=ids.get(siteId)||newId();ids.set(siteId,id);
   const result=await api<unknown>(`/auto-reglue/maintenance-reports/${encodeURIComponent(reportId)}/projects/${encodeURIComponent(siteId)}/sitemap-recheck`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({request_id:id})});
   ids.delete(siteId);return result;
  }finally{pending.delete(siteId);}
 };
}
export function sitemapRows(rows:Row[],filter='all') {
 return rows.filter(r=>filter==='all'||filter==='errors'&&problem(r)||filter==='updated'&&r.sitemap?.action==='updated')
  .slice().sort((a,b)=>Number(problem(b))-Number(problem(a))||a.project.localeCompare(b.project));
}
export function SitemapReport({report,reportId,api,onReportChange}:{report:SitemapReportData;reportId?:string;api?:Api;onReportChange?:(raw:unknown)=>void}) {
 const [filter,setFilter]=React.useState('all');
 const [pending,setPending]=React.useState<Record<string,boolean>>({}),[errorsBySite,setErrorsBySite]=React.useState<Record<string,string>>({});
 const submit=React.useMemo(()=>api&&reportId?createSitemapRecheck(api,reportId):undefined,[api,reportId]);
 const lifetime=React.useRef(0);
 React.useEffect(()=>{lifetime.current++;setPending({});setErrorsBySite({});return()=>{lifetime.current++;};},[submit]);
 async function recheck(siteId:string){
  if(!submit||pending[siteId])return;
  const version=lifetime.current;
  setPending(old=>({...old,[siteId]:true}));setErrorsBySite(old=>({...old,[siteId]:''}));
  try{const raw=await submit(siteId);if(version===lifetime.current&&raw)onReportChange?.(raw);}
  catch(e){if(version===lifetime.current)setErrorsBySite(old=>({...old,[siteId]:e instanceof Error?e.message:'Не удалось запустить проверку. Повторите обновление.'}));}
  finally{if(version===lifetime.current)setPending(old=>({...old,[siteId]:false}));}
 }
 const rows=sitemapRows(report.entries,filter),done=report.entries.filter(r=>r.status==='completed').length,updated=report.entries.filter(r=>r.sitemap?.action==='updated').length,errors=report.entries.filter(problem).length;
 return <div className="sitemapReport">
  <p>Готово: <b>{done} / {report.entries.length}</b> · Обновлено: <b>{updated}</b> · Требуют внимания: <b>{errors}</b></p>
  <details className="sitemapPlan"><summary>План проверки и восстановления</summary><ul><li>Получить текущий Main и опубликованные внутренние страницы каждого проекта со статусом «Массовые действия».</li><li>Проверить sitemap.xml; сохранить исходный файл перед исправлением.</li><li>Добавить или обновить sitemap, проверить запись в Webdev и публичный XML: только текущий Main, все опубликованные страницы, без дублей.</li></ul></details>
  <div className="sitemapFilters">{[['all',`Все ${report.entries.length}`],['errors',`Ошибки ${errors}`],['updated',`Обновлены ${updated}`]].map(([key,label])=><button type="button" key={key} aria-pressed={filter===key} onClick={()=>setFilter(key)}>{label}</button>)}</div>
  <div className="sitemapScroll"><table><thead><tr><th>Проект</th><th>Main / sitemap</th><th>Внутренних страниц</th><th>URL в XML<br/>До → после / нужно</th><th>Результат</th><th>Статус · МСК</th></tr></thead><tbody>
   {rows.map(r=>{const s=r.sitemap||{},country=reportCountry(r.geo,r.fibery_name),flag=country?String.fromCodePoint(...[...country].map(c=>127397+c.charCodeAt(0))):'🌐',main=safe(r.main?'https://'+r.main+'/':undefined),xml=safe(s.sitemap_url),f=fibery(r.fibery_url),task=fibery(r.fibery_task?.url),busy=!!pending[r.site_id]||checking(r);
    return <tr key={r.site_id}><th scope="row"><a href={'/project-menu/'+encodeURIComponent(r.project)+'/'}>{r.project}</a>{f&&<small><a href={f} target="_blank" rel="noopener noreferrer">{r.fibery_name||'Fibery'}</a></small>}</th>
     <td>{main?<a href={main} target="_blank" rel="noopener noreferrer">{flag} {r.main}</a>:'—'}{xml&&<small><a href={xml} target="_blank" rel="noopener noreferrer">sitemap.xml</a></small>}</td>
     <td>{s.internal_pages??'—'}</td><td>{s.before?.count??'—'} → {s.after?.count??'—'} / {s.expected_count??'—'}</td>
     <td>{checking(r)?'Получаем данные проекта и проверяем sitemap…':actions[s.action||'']||'Проверяется'}{r.error&&<small className="sitemapError">{r.error}</small>}<details><summary>Проверки</summary><small>Исходное состояние: HTTP {s.before?.status??'—'}, отсутствующих URL: {s.before?.missing??'—'}, лишних: {s.before?.extra??'—'}, дублей: {s.before?.duplicates??'—'}. {s.before?.error}</small><small>После: HTTP {s.after?.status??'—'}, публичный XML {s.after?.valid?'подтверждён':'не подтверждён'}; Webdev {s.webdev_verified?'подтверждён':'не подтверждён'}.</small></details>{task&&<small><a href={task} target="_blank" rel="noopener noreferrer">SEO-задача Fibery</a></small>}</td>
     <td><strong className={problem(r)?'sitemapError':''}>{labels[r.status]||r.status}</strong><small>{date(checking(r)?r.recheck?.requested_at:r.finished_at||s.after?.checked_at)}</small>{api&&reportId&&problem(r)&&<button type="button" className="sitemapRecheck" disabled={busy} aria-label={`Обновить sitemap: ${r.project}`} onClick={()=>void recheck(r.site_id)}><RefreshCw size={13} className={busy?'sitemapSpin':undefined}/>{busy?'Проверяем…':'Обновить'}</button>}{errorsBySite[r.site_id]&&<small className="sitemapError" role="status">{errorsBySite[r.site_id]}</small>}</td></tr>;
   })}{!rows.length&&<tr><td colSpan={6}>Нет проектов по выбранному фильтру.</td></tr>}
  </tbody></table></div>
 </div>;
}
