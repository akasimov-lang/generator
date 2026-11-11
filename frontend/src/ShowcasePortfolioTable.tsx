import React from 'react';
import {reportCountry} from './reportGeo';
import {projectFromPilotFilter} from './pilotFilterNavigation';

export type PortfolioEvidence = {
 domains_count:number|null; brands_count:number|null; brands?:string[]; brands_source?:string;
 internal_pages_count:number|null; checked_at?:string|null; notes?:string[];
 interlinking?:{present:boolean;complete:boolean;links_count:number;internal_count:number;linked_from_home:number;linked_to_home:number;between_internal:number}|null;
};
type Row={site_id:string;project:string;fibery_name?:string;main?:string;geo?:string;status:string;error?:string;portfolio?:PortfolioEvidence};

export function ShowcasePortfolioTable({entries}:{entries:Row[]}){
 const checked=entries.filter(row=>row.portfolio?.checked_at).length;
 const source=typeof window==='undefined'?'/auto-reglue/pilot':window.location.pathname+window.location.search;
 return <>
  <p>Общие ключи · Массовые действия. Проверено {checked} из {entries.length} проектов. Изменения сайтов не выполнялись.</p>
  <p className="maintenanceWordsScope">Бренды — уникальные казино на главной. Домены — основная сетка Webdev, без AMP. Перелинковка «Да» — найдены ссылки в текстах между существующими страницами; меню, хлебные крошки и витрины не учитываются. Покрытие можно раскрыть.</p>
  <div className="maintenanceChangesScroll"><table className="showcaseInventoryTable showcasePortfolioTable"><thead><tr>
   <th>Имя проекта</th><th>Главный домен</th><th>Доменов в сетке</th><th>Брендов на витрине</th><th>Внутренних страниц</th><th>Перелинковка</th><th>Статус · проверено МСК</th>
  </tr></thead><tbody>{entries.map(row=>{
   const data=row.portfolio,links=data?.interlinking,country=reportCountry(row.geo,row.fibery_name);
   const flag=country?String.fromCodePoint(...[...country].map(c=>127397+c.charCodeAt(0))):null;
   const main=row.main?.replace(/^https?:\/\//,'').replace(/\/$/,'');
   const status=row.status==='completed'?'Готово':['failed','partial'].includes(row.status)?'Ошибка проверки':'Выполняется';
   return <tr key={row.site_id}>
    <th scope="row"><a href={projectFromPilotFilter(`/project-network/${encodeURIComponent(row.project)}/`,source)}>{row.project}</a><small>{row.fibery_name||'Имя Fibery не заполнено'}</small><small><a href={`https://webdev-alfasearch.ru/projects/${encodeURIComponent(row.project)}`} target="_blank" rel="noopener noreferrer">Webdev ↗</a></small></th>
    <td>{flag&&<span role="img" aria-label={`GEO ${country}`} title={country||undefined}>{flag} </span>}{main&&/^[a-z0-9.-]+(?::\d+)?$/i.test(main)?<a href={`https://${main}/`} target="_blank" rel="noopener noreferrer">{main}</a>:row.main||'Не определён'}</td>
    <td>{data?.domains_count??'—'}</td>
    <td>{data?.brands?.length?<details><summary>{data.brands_count??'—'}</summary><p>{data.brands.join(', ')}</p></details>:data?.brands_count??'—'}{data?.brands_source==='webdev'&&<small>По данным Webdev</small>}</td>
    <td>{data?.internal_pages_count??'—'}</td>
    <td>{links?<details><summary>{links.present?'Да':'Нет'}</summary><small>Из главной: {links.linked_from_home}/{links.internal_count}</small><small>На главную: {links.linked_to_home}/{links.internal_count}</small><small>Между внутренними: {links.between_internal}</small><small>{links.complete?'Все страницы связаны с главной в обе стороны':'Полное покрытие не подтверждено'}</small></details>:'Не проверено'}</td>
    <td><strong>{status}</strong>{row.error&&<small className="showcaseInventoryError">{row.error}</small>}{data?.checked_at&&<small>{new Date(data.checked_at).toLocaleString('ru-RU',{timeZone:'Europe/Moscow'})}</small>}</td>
   </tr>;
  })}</tbody></table></div>
 </>;
}
