import React from "react";
import "./styles/pilot-versions.css";

export type PilotVersion = { number: number; created_at?: string };
export function PilotVersionTabs({ versions, selected, disabled, onSelect, project }: {
 versions: PilotVersion[]; selected: number; disabled?: boolean; onSelect: (version: number) => void; project: string;
}) {
 return <div className="pilotVersionTabs" role="group" aria-label={`Версия проекта ${project}`}>
  {versions.map(version=><button key={version.number} type="button" className="button secondary compact" aria-pressed={version.number===selected}
   disabled={disabled||version.number===selected} onClick={()=>onSelect(version.number)}
   title={`Выбрать весь вариант проекта${version.created_at?` · ${new Date(version.created_at).toLocaleString("ru-RU",{timeZone:"Europe/Moscow"})} МСК`:""}`}>Вер {version.number}</button>)}
 </div>;
}
export function pilotPreparePath(jobId?: string) {
 return jobId?`/auto-reglue/pilot/${encodeURIComponent(jobId)}/prepare`:"/auto-reglue/pilot";
}
