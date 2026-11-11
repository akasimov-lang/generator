import React from 'react';

export type ReportGeneration = {id:string;topic:string;slug:string;status:string;percent:number;research_percent:number;ready:boolean};
const percent=(v:unknown)=>typeof v==='number'&&Number.isFinite(v)?Math.max(0,Math.min(100,Math.round(v))):0;
const text=(v:unknown)=>typeof v==='string'?v:'';
export function normalizeGenerations(value:unknown):ReportGeneration[]{
 return Array.isArray(value)?value.filter(v=>v&&typeof v==='object'&&typeof v.id==='string').map(v=>({id:v.id,topic:text(v.topic),slug:text(v.slug),status:text(v.status),ready:v.ready===true,percent:v.ready===true?100:Math.min(99,percent(v.percent)),research_percent:percent(v.research_percent)})):[];
}
const labels:Record<string,string>={draft:'Ожидается',generation_queued:'В очереди',generating:'Генерация',generation_failed:'Ошибка генерации',generated:'Текст готов',approved:'Проверен',scheduled:'Публикация запланирована',publishing:'Публикуется',publication_pending_confirmation:'Проверка публикации',published:'Опубликован',failed:'Ошибка'};
export function ReportGenerations({rows=[]}:{rows?:ReportGeneration[]}){
 if(!rows.length)return null;
 return <section className="reportGenerations" aria-label="Генерации текстов"><h4>Генерации текстов · готово {rows.filter(r=>r.ready).length} / {rows.length}</h4><p>Проценты отражают сохранённые этапы генерации. Готовый текст проходит отдельную проверку и публикацию.</p><ul>{rows.map(row=><li key={row.id}><div><strong>{row.topic}</strong><small>{row.slug}</small></div><span>{labels[row.status]||row.status}<small>Сбор источников: {row.research_percent}%</small></span><div className="reportGenerationProgress"><progress value={row.percent} max={100} aria-label={`Генерация: ${row.topic}`}/><b>{row.percent}%</b></div></li>)}</ul></section>;
}
