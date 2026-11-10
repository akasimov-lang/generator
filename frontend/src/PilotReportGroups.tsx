import React from "react";
import "./styles/pilot-report-groups.css";

export const reportGroups = [
 ["all", "Все"], ["layout", "Вёрстка"], ["showcases", "Витрины"],
 ["reglues", "Переклеи"], ["brands", "Бренды"], ["other", "Прочее"],
] as const;
export type ReportGroup = typeof reportGroups[number][0];
export type ReportGroupCounts = Record<ReportGroup, number>;
export function reportGroupFromSearch(search:string):ReportGroup {
 const group=new URLSearchParams(search).get("group");
 return reportGroups.find(([key])=>key===group)?.[0]??"all";
}
export function PilotReportGroups({value,counts,onChange}:{value:ReportGroup;counts?:ReportGroupCounts;onChange:(group:ReportGroup)=>void}) {
 return <div className="pilotReportGroups" role="group" aria-label="Группы отчётов">
  {reportGroups.map(([key,label])=><button key={key} type="button" aria-pressed={value===key} className={value===key?"active":""} onClick={()=>onChange(key)}>
   {label}<span className="pilotReportGroupCount" aria-label={counts?`${counts[key]} отчётов`:"Загрузка количества"}>{counts?.[key]??"…"}</span>
  </button>)}
 </div>;
}
