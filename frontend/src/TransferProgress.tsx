import React from "react";
import { TransferConfirmation, type Confirmation } from "./TransferConfirmation";
import { LoaderCircle, CircleCheck, CircleAlert } from "lucide-react";

type DomainError={domain:string;code:string;message:string;system_response?:unknown};
type DomainProgress={domain:string;domain_type?:string;stage:string;source_project?:string;target_project?:string;error?:DomainError};
export type TransferRun={confirmation?:Confirmation;id:string;status:string;phase?:string;message?:string;domain_progress?:DomainProgress[];plan:{domains?:{domain:string;domain_type?:string}[];source_project?:string;project:string;batch_id?:string;domain_errors?:DomainError[];replacement_error?:string;replacement_pending?:boolean}};
const labels:Record<string,string>={planned:"Подготовка",reserved:"Извлечение",extracted:"В очереди",adding:"Добавление",confirming:"Проверка Webdev",delivered:"Подтверждено",failed:"Пропущен",released:"Не извлечён"};
const values:Record<string,number>={planned:0,reserved:20,extracted:45,adding:75,confirming:90,delivered:100,failed:100,released:100};
export function TransferProgress({runs}:{runs:TransferRun[]}){
 if(!runs.length)return null;
 const rows=runs.flatMap(run=>run.domain_progress?.length?run.domain_progress:(run.plan.domains||[]).map(d=>({...d,stage:run.status==="completed"?"delivered":run.status==="failed"||run.status==="partial"?"failed":run.phase==="transfer_create"?"adding":run.phase==="transfer_delete"?"reserved":"planned",source_project:run.plan.source_project,target_project:run.plan.project,error:run.plan.domain_errors?.find(e=>e.domain===d.domain)})));
 const complete=rows.filter(r=>r.stage==="delivered").length,failed=rows.filter(r=>r.stage==="failed"||r.stage==="released").length;
 const progress=Math.round(rows.reduce((s,r)=>s+(values[r.stage]||0),0)/Math.max(rows.length,1));
 const busy=runs.some(r=>["planned","queued","running","waiting"].includes(r.status)||r.plan.replacement_pending);
 const errors=runs.flatMap(r=>r.plan.domain_errors?.length?r.plan.domain_errors:["failed","partial"].includes(r.status)?(r.plan.domains||[]).map(d=>({domain:d.domain,code:"TRANSFER_STOPPED",message:r.message||"Операция остановлена. Проверьте журнал.",system_response:r.message})):[]);
 return <section className="transferProgress" role="status" aria-label="Ход переноса доменов" aria-live="polite"><div className="transferProgressHeader">{busy?<LoaderCircle size={15} className="spin"/>:failed?<CircleAlert size={15}/>:<CircleCheck size={15}/>}<strong>{busy?"Перенос доменов":"Результат переноса"}</strong><span>Перенесено: {complete} · Ошибок: {failed}</span></div><div className="transferProgressTrack" role="progressbar" aria-label="Выполнение переноса" aria-valuemin={0} aria-valuemax={100} aria-valuenow={progress}><span style={{width:`${progress}%`}}/></div>
 <div className="transferConfirmationList">{runs.filter(r=>["queued","running","waiting"].includes(r.status)).map(r=><TransferConfirmation key={r.id} status={r.status} phase={r.phase} data={r.confirmation}/>)}</div><div className="transferProgressRows">{rows.map((row,i)=>{
  const error=row.error || errors.find(e=>e.domain===row.domain);
  const bad=row.stage==="failed"||row.stage==="released";
  const content=<><code>{row.domain}</code><span>{row.source_project} → {row.target_project}</span><small>{bad?"Ошибка · Подробнее":labels[row.stage]||row.stage}</small>{row.domain_type==="drop"&&<strong className="transferDropNotice">{row.stage==="delivered"?"Перенесён дроп вместо новорега":"Вместо новорега выбран дроп"}</strong>}</>;
  return bad?<details className="transferProgressErrorRow" key={`${row.domain}:${i}`}><summary>{content}</summary><div className="transferProgressErrorDetail"><span>{error?.code||"WEBDEV_CHECK_REQUIRED"} · {error?.message||"Нет подтверждения переноса. Обновите отчёт для проверки."}</span>{error?.system_response!=null&&<details><summary>Ответ системы</summary><pre>{JSON.stringify(error.system_response,null,2)}</pre></details>}</div></details>:<div key={`${row.domain}:${i}`}>{content}</div>;
 })}</div>
 {runs.map(r=>r.plan.replacement_error?<small key={r.id} className="transferWarning">{r.plan.replacement_error}</small>:null)}
 </section>;
}
