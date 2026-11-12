import React from 'react';
import {ProjectGscField} from './ProjectGscField';
import {reportCountry} from './reportGeo';
import './BrandHealthReport.css';

type Api = <T>(path:string, options?:RequestInit)=>Promise<T>;
type Check = {outcome:string; reason?:string; title?:string; excerpt?:string; checked_at?:string; attempts?:number;
  chain?:{url:string;status:number;location?:string}[]; final_url?:string};
export type HealthRow = {site_id:string;project:string;brand:string;geo?:string;status:string;main_url?:string;
  inner_url?:string;fibery_url?:string;fibery_name?:string;domains_count?:number;error?:string;
  health?:{main?:Check;inner?:Check;configuration_error?:string;checked_at?:string}};
export type HealthReport = {entries:HealthRow[]; status:string; updated_at?:string};
const obj = (v:unknown):Record<string,unknown> => v && typeof v==='object' ? v as Record<string,unknown> : {};
const text = (v:unknown) => typeof v==='string' ? v : '';
export function normalizeBrandHealth(raw:unknown):HealthReport {
  const report=obj(raw);
  return {status:text(report.status),updated_at:text(report.updated_at),entries:(Array.isArray(report.entries)?report.entries:[]).map(item=>{
    const row=obj(item);
    return {...row,site_id:text(row.site_id),project:text(row.project),brand:text(row.brand),status:text(row.status)} as HealthRow;
  })};
}
const labels:Record<string,string> = {healthy:'Работает',placeholder:'Заглушка',redirect:'Редирект',redirect_loop:'Цикл редиректов',
  http_error:'Ошибка HTTP',blocked:'Проверка посетителя',review:'Проверить контент',unreachable:'Недоступен',not_configured:'Не задан'};
const safe = (url?:string) => {try {const u=new URL(url||'');return ['https:','http:'].includes(u.protocol)&&!u.username&&!u.password?u.href:undefined;} catch {return undefined;}};
const date = (v?:string) => v ? new Date(v).toLocaleString('ru-RU',{timeZone:'Europe/Moscow'}) : '—';
const problem = (row:HealthRow) => row.health && (row.health.configuration_error || row.health.main?.outcome!=='healthy' || !['healthy','not_configured'].includes(row.health.inner?.outcome||'')) || row.status==='failed';
export function healthRows(entries:HealthRow[],brand='',filter='all') {
  return entries.filter(row=>(!brand||row.brand===brand)&&(filter==='all'||filter==='placeholder'&&row.health?.main?.outcome==='placeholder'||filter==='problems'&&problem(row)))
    .sort((a,b)=>Number(b.health?.main?.outcome==='placeholder')-Number(a.health?.main?.outcome==='placeholder')||Number(!!problem(b))-Number(!!problem(a))||a.brand.localeCompare(b.brand)||a.project.localeCompare(b.project));
}
function CheckCell({check}:{check?:Check}) {
  if(!check)return <span className="brandHealthMuted">Ожидает проверки</span>;
  return <><span className={`brandHealthStatus is-${check.outcome}`}>{labels[check.outcome]||check.outcome}</span>
    <small>{check.chain?.map(h=>h.status).join(' → ')||'—'}</small>
    <details><summary>Подробнее</summary><p>{check.reason}</p>{check.title&&<p>Title: {check.title}</p>}
      {check.excerpt&&<p>{check.excerpt}</p>}{check.chain?.map((hop,i)=><p key={i}>{hop.status} · {hop.url}{hop.location&&<> → {hop.location}</>}</p>)}
      <small>{date(check.checked_at)} МСК · Проверок: {check.attempts||1}</small></details></>;
}
export function BrandHealthReport({report,api}:{report:HealthReport;api?:Api}) {
  const [brand,setBrand]=React.useState(''),[filter,setFilter]=React.useState('all');
  const rows=healthRows(report.entries,brand,filter);
  const checked=report.entries.filter(r=>r.health).length;
  const placeholders=report.entries.filter(r=>r.health?.main?.outcome==='placeholder').length;
  const problems=report.entries.filter(problem).length;
  const brands=[...new Set(report.entries.map(r=>r.brand))].sort();
  return <div className="brandHealthReport">
    <p>Проверено {checked} / {report.entries.length} · Заглушки Main: <b>{placeholders}</b> · Требуют внимания: <b>{problems}</b> · {date(report.updated_at)} МСК</p>
    <small>Проверяем HTTPS, редиректы и содержимое Main и выбранного внутряка. Изменения на сайтах не выполняются.</small>
    <div className="brandHealthFilters" aria-label="Фильтры проверки">
      {[['all',`Все ${report.entries.length}`],['placeholder',`Заглушки Main ${placeholders}`],['problems',`Требуют внимания ${problems}`]].map(([value,label])=><button key={value} type="button" aria-pressed={filter===value} onClick={()=>setFilter(value)}>{label}</button>)}
      <span/>{['',...brands].map(value=><button key={value} type="button" aria-pressed={brand===value} onClick={()=>setBrand(value)}>{value||'Все бренды'}{value&&` ${report.entries.filter(r=>r.brand===value).length}`}</button>)}
    </div>
    <div className="brandHealthScroll"><table><thead><tr><th>Проект / бренд</th><th>Fibery</th><th>Main</th><th>Основной внутряк</th><th>Main: проверка</th><th>Внутряк: проверка</th><th>GSC</th></tr></thead><tbody>
      {rows.map(row=>{const country=reportCountry(row.geo,row.fibery_name),flag=country?String.fromCodePoint(...[...country].map(c=>127397+c.charCodeAt(0))):'🌐';
        const main=safe(row.main_url),inner=safe(row.inner_url),fibery=/^https:\/\/hzhz\.fibery\.io\/favorites\/Alfasearch_Config\/SEO_Projects\/\d+$/.test(row.fibery_url||'')?row.fibery_url:undefined;
        return <tr key={row.site_id}><th scope="row"><a href={`/project-network/${encodeURIComponent(row.project)}/`}>{row.project}</a><small>{row.brand} · Доменов: {row.domains_count??'—'}</small></th>
          <td>{fibery?<a href={fibery} target="_blank" rel="noopener noreferrer" title={row.fibery_name}>{row.fibery_name||'Проект Fibery'}</a>:<small>Нет привязки</small>}</td>
          <td>{main?<a href={main} target="_blank" rel="noopener noreferrer">{flag} {new URL(main).host}</a>:'Не задан'}</td>
          <td>{inner?<a href={inner} target="_blank" rel="noopener noreferrer" title={inner}>{new URL(inner).pathname}</a>:'Не задан'}</td>
          <td><CheckCell check={row.health?.main}/>{row.error&&<small>{row.error}</small>}{row.health?.configuration_error&&<small>{row.health.configuration_error} Использованы сохранённые адреса.</small>}</td>
          <td><CheckCell check={row.health?.inner}/></td>
          <td>{api?<ProjectGscField siteId={row.site_id} api={api}/>:<small>Откройте отчёт для заполнения</small>}</td>
        </tr>;
      })}
      {!rows.length&&<tr><td colSpan={7}>Нет проектов по выбранному фильтру.</td></tr>}
    </tbody></table></div>
    <small>GSC сохраняется автоматически в карточке проекта, только в PagePilot. «Работает» означает, что получена содержательная страница нужного бренда; игровые и платёжные операции не проверяются.</small>
  </div>;
}
