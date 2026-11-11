import React from 'react';
import {reportCountry} from './reportGeo';
import {projectFromPilotFilter} from './pilotFilterNavigation';

export type PortfolioEvidence = {
 domains_count:number|null; brands_count:number|null; brands?:string[]; brands_source?:string;
 internal_pages_count:number|null; checked_at?:string|null; notes?:string[];
 interlinking?:{present:boolean;complete:boolean;links_count:number;internal_count:number;linked_from_home:number;linked_to_home:number;between_internal:number}|null;
};
type Row={site_id:string;project:string;fibery_name?:string;main?:string;geo?:string;status:string;error?:string;portfolio?:PortfolioEvidence};
export type PortfolioSort={key:'geo'|'project'|'main'|'domains'|'brands'|'pages'|'links'|'status';direction:'asc'|'desc'};
const collator=new Intl.Collator('ru',{numeric:true,sensitivity:'base'});
const countries=new Intl.DisplayNames(['ru'],{type:'region'});
const countryCode=(row:Row)=>reportCountry(row.geo,row.fibery_name)||'';
const flagFor=(code:string)=>code?String.fromCodePoint(...[...code].map(c=>127397+c.charCodeAt(0))):'🌐';
const countryName=(code:string)=>code?countries.of(code)||code:'Без GEO';
const mainDomain=(row:Row)=>row.main?.replace(/^https?:\/\//,'').replace(/\/$/,'');
const rowStatus=(row:Row)=>row.status==='completed'?'Готово':['failed','partial'].includes(row.status)?'Ошибка проверки':'Выполняется';

export function portfolioGeoCounts(entries:Row[]){
 const counts=new Map<string,number>();
 for(const row of entries){const geo=countryCode(row);counts.set(geo,(counts.get(geo)||0)+1);}
 return [...counts].sort(([a],[b])=>a&&b?collator.compare(a,b):a?-1:b?1:0).map(([geo,count])=>({geo,count}));
}

export function portfolioRows(entries:Row[],geo:string|null=null,sort:PortfolioSort={key:'geo',direction:'asc'}):Row[]{
 const value=(row:Row,country:string):string|number|null=>{
  switch(sort.key){
   case 'geo':return country||null;
   case 'project':return row.project;
   case 'main':return mainDomain(row)||null;
   case 'domains':return row.portfolio?.domains_count??null;
   case 'brands':return row.portfolio?.brands_count??null;
   case 'pages':return row.portfolio?.internal_pages_count??null;
   case 'links':return row.portfolio?.interlinking?Number(row.portfolio.interlinking.present):null;
   case 'status':return rowStatus(row);
  }
 };
 return entries.map(row=>{const country=countryCode(row);return {row,country,value:value(row,country)};})
  .filter(item=>geo===null||item.country===geo).sort((a,b)=>{
   // Unchecked values stay below measured values in both directions.
   if(a.value===null&&b.value!==null)return 1;
   if(b.value===null&&a.value!==null)return -1;
   const diff=a.value===null||b.value===null?0:typeof a.value==='number'&&typeof b.value==='number'?a.value-b.value:collator.compare(String(a.value),String(b.value));
   return diff*(sort.direction==='asc'?1:-1)||collator.compare(a.row.project,b.row.project)||collator.compare(a.row.site_id,b.row.site_id);
  }).map(item=>item.row);
}

export function ShowcasePortfolioTable({entries}:{entries:Row[]}){
 const [geo,setGeo]=React.useState<string|null>(null);
 const [sort,setSort]=React.useState<PortfolioSort>({key:'geo',direction:'asc'});
 const geos=React.useMemo(()=>portfolioGeoCounts(entries),[entries]);
 const rows=React.useMemo(()=>portfolioRows(entries,geo,sort),[entries,geo,sort]);
 const groups=React.useMemo(()=>{
  if(sort.key!=='geo')return [{geo:null,rows}];
  const grouped=new Map<string,Row[]>();
  for(const row of rows){const code=countryCode(row);if(!grouped.has(code))grouped.set(code,[]);grouped.get(code)!.push(row);}
  return [...grouped].map(([geo,rows])=>({geo,rows}));
 },[rows,sort.key]);
 const chooseGeo=(value:string|null)=>{setGeo(value);setSort({key:'geo',direction:'asc'});};
 const columns:{key:PortfolioSort['key'];label:string}[]=[{key:'project',label:'Имя проекта'},{key:'main',label:'Главный домен'},{key:'domains',label:'Доменов в сетке'},{key:'brands',label:'Брендов на витрине'},{key:'pages',label:'Внутренних страниц'},{key:'links',label:'Перелинковка'},{key:'status',label:'Статус · проверено МСК'}];
 const checked=entries.filter(row=>row.portfolio?.checked_at).length;
 const source=typeof window==='undefined'?'/auto-reglue/pilot':window.location.pathname+window.location.search;
 const renderRow=(row:Row)=>{
   const data=row.portfolio,links=data?.interlinking,country=reportCountry(row.geo,row.fibery_name);
   const flag=country?flagFor(country):null,main=mainDomain(row),status=rowStatus(row);
   return <tr key={row.site_id} data-project={row.project} data-geo={country||''}>
    <th scope="row"><a href={projectFromPilotFilter(`/project-network/${encodeURIComponent(row.project)}/`,source)}>{row.project}</a><small>{row.fibery_name||'Имя Fibery не заполнено'}</small><small><a href={`https://webdev-alfasearch.ru/projects/${encodeURIComponent(row.project)}`} target="_blank" rel="noopener noreferrer">Webdev ↗</a></small></th>
    <td>{flag&&<span role="img" aria-label={`GEO ${country}`} title={country||undefined}>{flag} </span>}{main&&/^[a-z0-9.-]+(?::\d+)?$/i.test(main)?<a href={`https://${main}/`} target="_blank" rel="noopener noreferrer">{main}</a>:row.main||'Не определён'}</td>
    <td>{data?.domains_count??'—'}</td>
    <td>{data?.brands?.length?<details><summary>{data.brands_count??'—'}</summary><p>{data.brands.join(', ')}</p></details>:data?.brands_count??'—'}{data?.brands_source==='webdev'&&<small>По данным Webdev</small>}</td>
    <td>{data?.internal_pages_count??'—'}</td>
    <td>{links?<details><summary>{links.present?'Да':'Нет'}</summary><small>Из главной: {links.linked_from_home}/{links.internal_count}</small><small>На главную: {links.linked_to_home}/{links.internal_count}</small><small>Между внутренними: {links.between_internal}</small><small>{links.complete?'Все страницы связаны с главной в обе стороны':'Полное покрытие не подтверждено'}</small></details>:'Не проверено'}</td>
    <td><strong>{status}</strong>{row.error&&<small className="showcaseInventoryError">{row.error}</small>}{data?.checked_at&&<small>{new Date(data.checked_at).toLocaleString('ru-RU',{timeZone:'Europe/Moscow'})}</small>}</td>
   </tr>;
 };
 return <>
  <p>Общие ключи · Массовые действия. Проверено {checked} из {entries.length} проектов. Изменения сайтов не выполнялись.</p>
  <p className="maintenanceWordsScope">Бренды — уникальные казино на главной. Домены — основная сетка Webdev, без AMP. Перелинковка «Да» — найдены ссылки в текстах между существующими страницами; меню, хлебные крошки и витрины не учитываются. Покрытие можно раскрыть.</p>
  <div className="showcaseGeoTiles" role="group" aria-label="Фильтр проектов по GEO">
   <button type="button" className="showcaseGeoTile" aria-pressed={geo===null} onClick={()=>chooseGeo(null)}><span>Все GEO</span><span className="showcaseGeoCount">{entries.length}</span></button>
   {geos.map(item=><button key={item.geo} type="button" className="showcaseGeoTile" data-geo={item.geo} title={countryName(item.geo)} aria-label={`${countryName(item.geo)}${item.geo?` (${item.geo})`:''}: ${item.count} проектов`} aria-pressed={geo===item.geo} onClick={()=>chooseGeo(item.geo)}><span aria-hidden="true" className="showcaseGeoFlag">{flagFor(item.geo)}</span><span>{item.geo||'Без GEO'}</span><span className="showcaseGeoCount">{item.count}</span></button>)}
  </div>
  <div className="showcasePortfolioTools"><span aria-live="polite">Показано {rows.length} из {entries.length} проектов</span><button type="button" className="button secondary compact" aria-pressed={sort.key==='geo'} onClick={()=>setSort({key:'geo',direction:'asc'})}>Группировать по GEO</button></div>
  <div className="maintenanceChangesScroll"><table className="showcaseInventoryTable showcasePortfolioTable"><thead><tr>
   {columns.map(column=><th key={column.key} scope="col" aria-sort={sort.key===column.key?(sort.direction==='asc'?'ascending':'descending'):'none'}><button className="showcaseColumnSort" type="button" onClick={()=>setSort(current=>({key:column.key,direction:current.key===column.key&&current.direction==='asc'?'desc':'asc'}))} title={`Сортировать: ${column.label}`}><span>{column.label}</span><span aria-hidden="true">{sort.key===column.key?(sort.direction==='asc'?'↑':'↓'):'↕'}</span></button></th>)}
  </tr></thead>{groups.map(group=><tbody key={group.geo??'sorted'}>{group.geo!==null&&<tr className="showcaseGeoGroup"><th scope="rowgroup" colSpan={7}><span aria-hidden="true">{flagFor(group.geo)}</span> {group.geo?`${group.geo} · `:''}{countryName(group.geo)} <span className="showcaseGeoCount">{group.rows.length}</span></th></tr>}{group.rows.map(renderRow)}</tbody>)}{!rows.length&&<tbody><tr><td colSpan={7}>Проекты не найдены.</td></tr></tbody>}</table></div>
 </>;
}
