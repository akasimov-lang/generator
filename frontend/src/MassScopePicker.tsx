import React from "react";
import { BrandIcon } from "./BrandIcon";
import { MASS_ACTION_GEOS } from "./massActionScope";

type Project = { id:string; brand:string; geo:string };
type Props = {loading?:boolean;children?:React.ReactNode;projects:Project[];geo:string;brand:string;onChange:(geo:string,brand:string)=>void;geoLabel:(geo:string)=>string};
export function MassScopePicker({projects,geo,brand,onChange,geoLabel,children,loading=false}:Props){
 const [search,setSearch]=React.useState("");
 const [sort,setSort]=React.useState<"desc"|"asc"|"name">("desc");
 // Keep familiar GEOs first, but never use them as an eligibility whitelist.
 const presentGeos=[...new Set(projects.map(project=>project.geo))];
 const geos=[...MASS_ACTION_GEOS.filter(code=>presentGeos.includes(code)),...presentGeos.filter(code=>!MASS_ACTION_GEOS.includes(code)).sort((a,b)=>a.localeCompare(b))];
 const groups=new Map<string,number>();
 for(const p of projects){if(!geo||p.geo===geo){const name=p.brand||"Бренд не указан";groups.set(name,(groups.get(name)||0)+1);}}
 const brands=[...groups].filter(([name])=>name.toLocaleLowerCase().includes(search.trim().toLocaleLowerCase())).sort((a,b)=>(sort==="name"?0:(sort==="desc"?b[1]-a[1]:a[1]-b[1]))||a[0].localeCompare(b[0],"ru"));
 function chooseGeo(next:string){onChange(next,projects.some(p=>(!next||p.geo===next)&&p.brand===brand)?brand:"");}
 return <section className="massScopePicker dataPanel" aria-busy={loading} aria-label="Бренды и GEO массовых действий">
  <div className="massGeoPanel" role="group" aria-label="GEO массовых действий"><span className="muted">GEO</span>{["",...geos].map(code=><button key={code} type="button" className="button secondary compact" aria-pressed={geo===code} onClick={()=>chooseGeo(code)}>{code?geoLabel(code):"Все GEO"}<span className="massGeoCount">{loading?"…":projects.filter(p=>!code||p.geo===code).length}</span></button>)}{children}</div>
  <div className="massBrandPanel"><div className="massBrandTools"><label className="massBrandSearch"><span className="muted">Бренды{geo?` · ${geo}`:""}</span><input type="search" value={search} onChange={e=>setSearch(e.target.value)} placeholder="Найти бренд" aria-label="Поиск бренда массовых действий"/></label><div className="massBrandSort" role="group" aria-label="Сортировка брендов">{([["desc","Больше проектов"],["asc","Меньше проектов"],["name","По названию"]] as const).map(([value,label])=><button type="button" className="button secondary compact" aria-pressed={sort===value} key={value} onClick={()=>setSort(value)}>{label}</button>)}</div></div>
   <div className="peerBrandTiles" role="group" aria-label={geo?`Бренды в GEO ${geo}`:"Бренды во всех GEO"}><button type="button" className="peerBrandTile" aria-pressed={!brand} onClick={()=>onChange(geo,"")}><span className="peerBrandName">Все бренды</span><span className="peerBrandCount">{loading?"…":projects.filter(p=>!geo||p.geo===geo).length}</span></button>{brands.map(([name,count])=><button key={name} type="button" className="peerBrandTile" aria-pressed={brand===name} aria-label={`${name}, проектов: ${count}`} onClick={()=>onChange(geo,name)}><BrandIcon brand={name}/><span className="peerBrandName" title={name}>{name}</span><span className="peerBrandCount" aria-hidden="true">{count}</span></button>)}</div>{loading?<p className="muted" role="status">Загружаем бренды и GEO…</p>:!brands.length&&<p className="muted">Бренды не найдены.</p>}
  </div>
 </section>;
}
