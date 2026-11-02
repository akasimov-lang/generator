import React from "react";
import { X } from "lucide-react";
import { isExactNetworkDomainSearch, normalizeDomainQuery, normalizeProjectSearch, projectSearchKeywords } from "./projectSearch";
import { siteGeoFilterCode } from "./siteGeoFilter";
import "./styles/global-project-search.css";

export type GlobalSearchProject = {
 id:string;name:string;cache_canon?:string|null;base_url?:string;
 cache_domains?:string[];fibery_name?:string|null;brand?:string|null;
 cache_geo?:string|null;is_active?:boolean;
};
type IndexedProject<T extends GlobalSearchProject> = {site:T;values:string[];keywords:string};
const RESULTS_ID="mass-global-search-results";
const PAGE_SIZE=50;

function indexProjects<T extends GlobalSearchProject>(sites:readonly T[]):IndexedProject<T>[] {
 return sites.map(site=>{
  const values=[site.name,site.cache_canon||"",site.base_url||"",site.fibery_name||"",...(Array.isArray(site.cache_domains)?site.cache_domains:[])];
  return {site,values,keywords:projectSearchKeywords(values)};
 });
}

function matchIndex<T extends GlobalSearchProject>(index:IndexedProject<T>[],query:string):T[] {
 const normalized=normalizeDomainQuery(query);
 if(!normalized)return [];
 const decoded=normalizeProjectSearch(normalized);
 return index.filter(entry=>entry.keywords.includes(normalized)||entry.keywords.includes(decoded))
  .map(entry=>({...entry,exact:isExactNetworkDomainSearch(entry.values,normalized)}))
  .sort((left,right)=>Number(right.exact)-Number(left.exact))
  .map(entry=>entry.site);
}

/** The caller supplies the permitted snapshot; search never applies a mass-action scope. */
export function matchingGlobalProjects<T extends GlobalSearchProject>(sites:readonly T[],query:string):T[] {
 return matchIndex(indexProjects(sites),query);
}

export function GlobalProjectSearchInput({query,onChange,onSubmit,resultsId=RESULTS_ID}:{
 query:string;onChange:(query:string)=>void;onSubmit?:()=>void;resultsId?:string;
}) {
 const input=React.useRef<HTMLInputElement>(null);
 return <div className="globalProjectSearchInput">
  <input ref={input} className="workspaceHeadingSearch workspaceHeadingSearchCompact" type="search" value={query}
   aria-label="Поиск по всем сайтам" aria-controls={resultsId} placeholder="Домен проекта или домен в сетке"
   onChange={event=>onChange(event.target.value)} onKeyDown={event=>{
    if(event.nativeEvent.isComposing)return;
    if(event.key==="Escape"){event.preventDefault();onChange("");}
    if(event.key==="Enter"&&normalizeDomainQuery(query)&&onSubmit){event.preventDefault();onSubmit();}
   }}/>
  {query&&<button className="globalProjectSearchClear" type="button" aria-label="Очистить поиск по всем сайтам"
   onClick={()=>{onChange("");input.current?.focus();}}><X size={16}/></button>}
 </div>;
}

function Geo({value}:{value?:string|null}) {
 const code=siteGeoFilterCode(value);
 const flag=/^[A-Z]{2}$/.test(code)?String.fromCodePoint(...code.split("").map(letter=>127397+letter.charCodeAt(0))):"";
 return <span className="globalProjectSearchGeo">{flag&&<span aria-hidden="true">{flag}</span>}{code||"GEO не указано"}</span>;
}

export function GlobalProjectSearchResults({sites,query,onOpen,loading=false,id=RESULTS_ID}:{
 sites:readonly GlobalSearchProject[];query:string;onOpen:(name:string)=>void;loading?:boolean;id?:string;
}) {
 const normalized=normalizeDomainQuery(query);
 const index=React.useMemo(()=>indexProjects(sites),[sites]);
 const results=React.useMemo(()=>matchIndex(index,normalized),[index,normalized]);
 const [pageState,setPageState]=React.useState({query:"",page:0});
 const page=pageState.query===normalized?Math.min(pageState.page,Math.max(0,Math.ceil(results.length/PAGE_SIZE)-1)):0;
 const from=page*PAGE_SIZE;
 const visible=results.slice(from,from+PAGE_SIZE);
 if(!normalized)return null;
 return <section id={id} className="panel globalProjectSearchResults" aria-label="Результаты поиска по всем сайтам">
  <div className="globalProjectSearchSummary"><h2 aria-live="polite">Результаты поиска · {results.length}</h2>
   {loading&&<span className="muted" role="status">Обновляем список сайтов…</span>}
  </div>
  <p className="muted">Поиск по всем доступным проектам и доменам их сеток.</p>
  {results.length?<>
   <div className="tableScroll"><table><thead><tr><th>Проект</th><th>Бренд / GEO</th><th>Main</th><th>Имя Fibery</th></tr></thead>
    <tbody>{visible.map(site=><tr key={site.id}>
     <td><a href={`/project-network/${encodeURIComponent(site.name)}/`} onClick={event=>{
      if(event.button!==0||event.metaKey||event.ctrlKey||event.shiftKey||event.altKey)return;
      event.preventDefault();onOpen(site.name);
     }}>{site.name}</a></td>
     <td><span>{site.brand||"Общие ключи"}</span><Geo value={site.cache_geo}/></td>
     <td>{site.cache_canon||site.base_url||"—"}</td><td>{site.fibery_name||"—"}</td>
    </tr>)}</tbody>
   </table></div>
   {results.length>PAGE_SIZE&&<nav className="globalProjectSearchPagination" aria-label="Страницы результатов поиска">
    <button className="button secondary compact" type="button" disabled={page===0} onClick={()=>setPageState({query:normalized,page:page-1})}>Назад</button>
    <span>{from+1}–{Math.min(from+PAGE_SIZE,results.length)} из {results.length}</span>
    <button className="button secondary compact" type="button" disabled={from+PAGE_SIZE>=results.length} onClick={()=>setPageState({query:normalized,page:page+1})}>Далее</button>
   </nav>}
  </>:<p role="status">{loading?"Загружаем список сайтов…":"Проекты не найдены."}</p>}
 </section>;
}
