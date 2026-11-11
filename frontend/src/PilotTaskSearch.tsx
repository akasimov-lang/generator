import React from "react";
import {Search,X} from "lucide-react";

export function pilotTaskListPath(offset:number,query:string,group="all"):string {
 const params=new URLSearchParams({offset:String(Math.max(0,offset))});
 if(query.trim())params.set("q",query.trim());
 if(group!=="all")params.set("group",group);
 return `/auto-reglue/pilot/tasks?${params}`;
}

export function PilotTaskSearch({value,onChange,total}:{value:string;onChange:(value:string)=>void;total?:number}) {
 return <div className="pilotTaskSearch">
  <label><Search size={18}/><input type="search" aria-label="Поиск заданий" placeholder="Бренд, GEO, домен или название задания" maxLength={200} value={value} onChange={event=>onChange(event.target.value)}/></label>
  {value&&<button type="button" className="button secondary compact" aria-label="Очистить поиск заданий" onClick={()=>onChange("")}><X size={16}/></button>}
  <small role="status">{value.trim()?`Найдено: ${total??"…"}. `:""}По дате плана / запуска · новые сверху · МСК</small>
 </div>;
}
