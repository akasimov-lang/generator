import {BrandHealthReport,normalizeBrandHealth,type HealthReport} from './BrandHealthReport';
import {ReportGenerations,normalizeGenerations,type ReportGeneration} from './ReportGenerations';
import {ArticleImageReport, normalizeArticleImages, type ArticleImageReportData} from "./ArticleImageReport";
import { ShowcaseInventoryReport, normalizeInventory, type InventoryReportData } from "./ShowcaseInventoryReport";
import React from "react";
import { ArrowLeft, RefreshCw, ScrollText, Repeat2 } from "lucide-react";
import { createMaintenanceRepeat, maintenanceEntriesActive, maintenanceCanRepeat, maintenanceReportLink } from "./maintenanceRepeat";
import "./styles/maintenance-report.css";
import { StructuredDataChanges, normalizeStructuredData, type StructuredDataEvidence } from "./StructuredDataChanges";

type Api = <T>(path:string,options?:RequestInit)=>Promise<T>;
type Values = {words?:number;unique_words?:number;brand_mentions?:number;h1?:string;title?:string;description?:string;main?:string;alternates?:string;canonical?:string;fake_path?:string};
type Stage = {key:string;label:string;state:string};
type Operation = {id:string;kind?:string;action?:string;status:string;started_at?:string;finished_at?:string;before?:Values;after?:Values};
type Entry = {generations?:ReportGeneration[];work_summary?:{done:string[];checks:string[];issues:string[];plan:string[]};current_observation?:{values:Values;source:string;observed_at:string};planning_status?:string;facts?:{label:string;value:string}[];kind?:string;structured_data?:StructuredDataEvidence;started_at?:string;finished_at?:string;progress?:{done:number;total:number;percent:number;label:string;stages?:Stage[]};site_id:string;project:string;status:string;phase?:string;message?:string;before?:Values;after?:Values;planned?:Values;content_started_at?:string;content_finished_at?:string;words_scope?:string;operations?:Operation[];copy_changes?:{field:string;old:string;new:string}[];table_changes?:{block:number|string;rows_before:number;rows_after:number}[];table_emojis?:boolean;paragraphs?:{count?:number;status?:string};uniqueness_percent?:number;shortened_percent?:number;brand_count_term?:string;paragraphs_before?:number;paragraphs_after?:number;paragraphs_added?:number;paragraphs_removed?:number;edit_ids?:string[];network_operation_ids?:string[];run_id?:string;error?:string;pending_reason?:string;notes?:string[]};
export type MaintenanceReportData = {brand_health?:HealthReport;presentation?:string;article_images?:ArticleImageReportData;planning_only?:boolean;display_status?:string;can_exclude?:boolean;excluded_projects?:{site_id:string;project:string;destination_report_id?:string}[];inventory?:InventoryReportData;task_type?:string;source_reports?:{id:string;report_id:number}[];id?:string;report_id?:number;repeat?:boolean;parent_report_id?:string;allow_reserve?:boolean;phase?:string;message?:string;progress?:{done:number;total:number;percent:number;unit?:string};name:string;status:string;total:number;counts:Record<string,number>;launched_at:string;finished_at?:string;updated_at:string;entries:Entry[]};
const labels:Record<string,string>={queued:"В очереди",pending:"Ожидается",running:"Выполняется",waiting:"Ждём подтверждения",completed:"Выполнено",partial:"Частично",failed:"Ошибка",skipped:"Пропущено",confirmed:"Подтверждено",unconfirmed:"Не подтверждено",ready:"Текст подготовлен"};
const date=(value?:string)=>value&&!Number.isNaN(Date.parse(value))?new Date(value).toLocaleString("ru-RU",{timeZone:"Europe/Moscow"}):"Нет данных";
const object=(value:unknown):Record<string,unknown>=>value&&typeof value==="object"&&!Array.isArray(value)?value as Record<string,unknown>:{};
const text=(value:unknown,fallback="")=>typeof value==="string"?value:fallback;
const strings=(value:unknown)=>Array.isArray(value)?value.filter((item):item is string=>typeof item==="string"):[];
const count=(value:unknown)=>typeof value==="number"&&Number.isFinite(value)&&value>=0?value:undefined;
const values=(value:unknown):Values=>Object.fromEntries(Object.entries(object(value)).filter(([key,v])=>["words","unique_words","brand_mentions"].includes(key)?typeof v==="number"&&Number.isFinite(v)&&v>=0:["title","h1","description","main","alternates","canonical","fake_path"].includes(key)&&typeof v==="string"));

function plannedValues(row:Record<string,unknown>):Values {
 const plan={...object(row.plan),...object(row.planned)},prepared=object(row.prepared_content);
 return values({...plan,...prepared,main:plan.main??plan.new_main,
  alternates:plan.alternates??plan.alternate_markup??plan.alternateMarkup,
  canonical:plan.canonical??plan.canonicalFakeMainMarkup,fake_path:plan.fake_path??plan.fake_main_path});
}

export function normalizeMaintenanceReport(raw:unknown):MaintenanceReportData {
 const report=object(raw),progress=object(report.progress);
 if(!Array.isArray(report.entries))throw new Error("Сервер вернул отчёт без списка проектов. Обновите страницу отчёта.");
 const entries=report.entries.map((item,index)=>{
  const row=object(item),paragraphs=object(row.paragraphs),progress=object(row.progress);
  const copy_changes=Array.isArray(row.copy_changes)?row.copy_changes.map(item=>{const change=object(item);return {field:text(change.field),old:text(change.old),new:text(change.new)};}):[];
  const table_changes=Array.isArray(row.table_changes)?row.table_changes.map(item=>{const change=object(item);return {block:typeof change.block==="number"?change.block:text(change.block),rows_before:typeof change.rows_before==="number"?change.rows_before:0,rows_after:typeof change.rows_after==="number"?change.rows_after:0};}):[];
  const operations=Array.isArray(row.operations)?row.operations.map((item,index)=>{const op=object(item);return {id:text(op.id,String(index)),kind:text(op.kind),action:text(op.action),status:text(op.status,"unconfirmed"),started_at:text(op.started_at),finished_at:text(op.finished_at),before:values(op.before),after:values(op.after)};}):[];
  return {generations:normalizeGenerations(row.generations),work_summary:row.work_summary?{done:strings(object(row.work_summary).done),checks:strings(object(row.work_summary).checks),issues:strings(object(row.work_summary).issues),plan:strings(object(row.work_summary).plan)}:undefined,current_observation:row.current_observation?{values:values(object(row.current_observation).values),source:text(object(row.current_observation).source),observed_at:text(object(row.current_observation).observed_at)}:undefined,planning_status:text(row.planning_status),facts:Array.isArray(row.facts)?row.facts.map(item=>{const fact=object(item);return {label:text(fact.label),value:text(fact.value)};}):undefined,kind:text(row.kind),structured_data:normalizeStructuredData(row.structured_data),started_at:text(row.started_at),finished_at:text(row.finished_at),progress:row.progress?{done:count(progress.done)||0,total:count(progress.total)||0,percent:Math.min(100,count(progress.percent)||0),label:text(progress.label),stages:Array.isArray(progress.stages)?progress.stages.map(item=>{const stage=object(item);return {key:text(stage.key),label:text(stage.label),state:text(stage.state,"pending")};}):[]}:undefined,site_id:text(row.site_id,String(index)),project:text(row.project,"Проект не указан"),status:text(row.status,"pending"),phase:text(row.phase),message:text(row.message),before:values(row.before),after:values(row.after),planned:plannedValues(row),
   content_started_at:text(row.content_started_at),content_finished_at:text(row.content_finished_at),words_scope:text(row.words_scope,text(report.words_scope)),operations,copy_changes,table_changes,table_emojis:row.table_emojis===true,
   paragraphs:row.paragraphs?{count:typeof paragraphs.count==="number"?paragraphs.count:undefined,status:text(paragraphs.status)}:undefined,
   uniqueness_percent:count(row.uniqueness_percent),shortened_percent:count(row.shortened_percent),brand_count_term:text(row.brand_count_term),
   paragraphs_before:count(row.paragraphs_before),paragraphs_after:count(row.paragraphs_after),paragraphs_added:count(row.paragraphs_added),paragraphs_removed:count(row.paragraphs_removed),
   edit_ids:strings(row.edit_ids),network_operation_ids:strings(row.network_operation_ids),run_id:text(row.run_id),error:text(row.error),pending_reason:text(row.pending_reason),notes:strings(row.notes)};
 });
 const counts=Object.fromEntries(Object.entries(object(report.counts)).filter(([,value])=>typeof value==="number"&&Number.isFinite(value))) as Record<string,number>;
 const number=(value:unknown)=>typeof value==="number"&&Number.isFinite(value)?Math.max(0,value):0;
 const steps=entries.length&&entries.every(entry=>entry.progress&&entry.progress.total>0)?entries.reduce((sum,entry)=>({done:sum.done+(entry.progress?.done||0),total:sum.total+(entry.progress?.total||0)}),{done:0,total:0}):undefined;
 return {brand_health:report.task_type==="brand_health_audit"?normalizeBrandHealth(raw):undefined,presentation:text(report.presentation),article_images:report.task_type==="article_image_localization"?normalizeArticleImages(raw):undefined,planning_only:report.planning_only===true,display_status:text(report.display_status),can_exclude:report.can_exclude===true,excluded_projects:Array.isArray(report.excluded_projects)?report.excluded_projects.map(item=>{const row=object(item);return {site_id:text(row.site_id),project:text(row.project),destination_report_id:text(row.destination_report_id)};}):[],inventory:["showcase_inventory","showcase_standardization"].includes(text(report.task_type))?normalizeInventory(raw):undefined,task_type:text(report.task_type),source_reports:(Array.isArray(report.source_reports)?report.source_reports:[]).flatMap(item=>{const source=object(item);return typeof source.id==="string"&&count(source.report_id)!==undefined?[{id:source.id,report_id:source.report_id as number}]:[];}),id:text(report.id),report_id:count(report.report_id),repeat:report.repeat===true,parent_report_id:text(report.parent_report_id),allow_reserve:report.allow_reserve===true,phase:text(report.phase),message:text(report.message),
  progress:steps?{...steps,percent:Math.min(entries.some(entry=>["pending","running","waiting","queued"].includes(entry.status))?99:100,Math.round(100*steps.done/steps.total)),unit:"steps"}:report.progress?{done:number(progress.done),total:number(progress.total),percent:Math.min(100,number(progress.percent)),unit:text(progress.unit)}:undefined,
  name:text(report.name,"Отчёт по задаче"),status:text(report.status,"pending"),total:typeof report.total==="number"?report.total:entries.length,counts,
  launched_at:text(report.launched_at),updated_at:text(report.updated_at),finished_at:text(report.finished_at),entries};
}

function Changes({before,after,planned,contentOnly=false,brandTerm}:{before?:Values;after?:Values;planned?:Values;contentOnly?:boolean;brandTerm?:string}) {
 const fields=contentOnly?[["words","Words"],["unique_words","Уникальных слов"],["brand_mentions",brandTerm?`Вхождений бренда «${brandTerm}»`:"Вхождений бренда"],["title","Title"],["h1","H1"],["description","Description"]] as const:[["words","Words"],["unique_words","Уникальных слов"],["brand_mentions",brandTerm?`Вхождений бренда «${brandTerm}»`:"Вхождений бренда"],["title","Title"],["h1","H1"],["description","Description"],["main","Main"],["alternates","Альтернейты"],["canonical","Canonical"],["fake_path","Внутренняя страница"]] as const;
 const hasPlan=!!planned&&Object.keys(planned).length>0;
 const value=(data:Values|undefined,key:keyof Values,fallback:string)=>data?.[key]===undefined?fallback:data[key]===""?"Не задано":data[key];
 return <table className="maintenanceChanges"><thead><tr><th>Настройка</th><th>До</th>{hasPlan&&<th>План</th>}<th>После</th></tr></thead><tbody>
  {fields.filter(([key])=>!["unique_words","brand_mentions","canonical","fake_path"].includes(key)||before?.[key]!==undefined||after?.[key]!==undefined||planned?.[key]!==undefined).map(([key,label])=><tr key={key}><th scope="row">{label}</th><td>{value(before,key,"Нет данных")}</td>{hasPlan&&<td className="maintenancePlannedValue">{value(planned,key,"Ещё не подготовлено")}</td>}<td>{value(after,key,"Пока не подтверждено")}</td></tr>)}
 </tbody></table>;
}

export function MaintenanceReportBody({report,onExclude,excluding,api}:{report:MaintenanceReportData;api?:Api;onExclude?:(id:string)=>void;excluding?:string|null}) {
 if(report.brand_health)return <BrandHealthReport report={report.brand_health} api={api}/>;
 if(report.article_images)return <ArticleImageReport report={report.article_images}/>;
 if(report.presentation==="work_list")return <><p>Выполненные работы и проверки показаны отдельно от плана. Обновлено: {date(report.updated_at)} МСК.</p>{report.entries.map(entry=><article className="maintenanceEntry" key={entry.site_id}><header><h3><a href={`/project-network/${encodeURIComponent(entry.project)}/`}>{entry.project}</a></h3><strong>{labels[entry.status]||entry.status}</strong></header><ReportGenerations rows={entry.generations}/>{entry.work_summary?.done.length?<ul>{entry.work_summary.done.map((s,i)=><li key={i}>{s}</li>)}</ul>:<p>Подтверждённые выполненные работы пока не записаны.</p>}{!!entry.work_summary?.checks.length&&<><h4>Проверено</h4><ul>{entry.work_summary.checks.map((s,i)=><li key={i}>{s}</li>)}</ul></>}{!!entry.work_summary?.issues.length&&<><h4>Примечания и оставшиеся работы</h4><ul>{entry.work_summary.issues.map((s,i)=><li key={i}>{s}</li>)}</ul></>}{!!entry.work_summary?.plan.length&&<details><summary>Исходный план</summary><ul>{entry.work_summary.plan.map((s,i)=><li key={i}>{s}</li>)}</ul></details>}{entry.finished_at&&<small>Подтверждено: {date(entry.finished_at)} МСК</small>}</article>)}</>;
 if(report.inventory)return <ShowcaseInventoryReport report={report.inventory}/>;
 if(report.task_type==='system_recovery')return <><p>Проверка системных ошибок и зависаний · {report.total} проектов. История неудачных попыток сохранена.</p><div className="maintenanceChangesScroll"><table className="showcaseInventoryTable"><thead><tr><th>Проект</th><th>Результаты проверки и работ</th><th>Статус</th></tr></thead><tbody>{report.entries.map(entry=><tr key={entry.site_id}><th scope="row"><a href={`/project-network/${encodeURIComponent(entry.project)}/`}>{entry.project}</a></th><td>{entry.facts?.map((fact,index)=><p key={index}><strong>{fact.label}: </strong><span style={{whiteSpace:'pre-wrap'}}>{fact.value}</span></p>)}</td><td>{labels[entry.status]||entry.status}{entry.error&&<p>{entry.error}</p>}<small>{date(entry.finished_at)} МСК</small></td></tr>)}</tbody></table></div></>;

 if(["toc_repair","showcase_audit"].includes(report.task_type||""))return <><p>Показаны сохранённые результаты проверок и подтверждённых операций. План будущих работ указан отдельно.</p><p>Проектов: {report.total} · Обновлено: {date(report.updated_at)} МСК</p>{report.entries.map(entry=><article className="maintenanceEntry" key={entry.site_id}><header><h3><a href={`/project-network/${encodeURIComponent(entry.project)}/`}>{entry.project}</a></h3><strong>{report.planning_only?(entry.planning_status==="blocked"?"Требуется пересчитать план":entry.phase==="awaiting_domain"?"План готов · нужен домен":"План готов"):labels[entry.status]||entry.status}</strong>{onExclude&&report.can_exclude&&<button type="button" className="button secondary compact" disabled={!!excluding} onClick={()=>onExclude(entry.site_id)} aria-label={`Исключить ${entry.project} из отчёта`}>{excluding===entry.site_id?"Исключаем…":"Исключить из отчёта"}</button>}</header><div className="maintenanceChangesScroll"><table className="maintenanceChanges maintenanceFacts"><tbody>{entry.facts?.map((fact,index)=><tr key={index}><th>{fact.label}</th><td style={{whiteSpace:"pre-wrap"}}>{fact.value}</td></tr>)}</tbody></table></div>{entry.error&&<p role="alert">{entry.error}</p>}</article>)}</>;
 return <>
  {!!report.source_reports?.length&&<p>Исходные задания: {report.source_reports.map((source,index)=><React.Fragment key={source.id}>{index>0?" · ":""}<a href={maintenanceReportLink(source.id)}>ID {source.report_id}</a></React.Fragment>)}</p>}
  {report.parent_report_id&&<p><a href={maintenanceReportLink(report.parent_report_id)}>Исходный отчёт группы</a></p>}
  <div className="pilotProgress"><strong>{report.display_status||labels[report.status]||report.status}</strong>{report.message&&<p role="status">{report.message}</p>}{report.progress&&<><progress value={report.progress.percent} max={100} aria-label="Прогресс выполнения задачи"/><small>{report.progress.done} / {report.progress.total}{report.progress.unit==="steps"?" этапов":""} · {report.progress.percent}%</small></>}<p>Проектов: {report.total} · Выполнено: {report.counts.completed||0} · Частично: {report.counts.partial||0} · Ошибок: {report.counts.failed||0}</p><small>Начало: {date(report.launched_at)} · Обновлено: {date(report.updated_at)}{report.finished_at?` · Завершено: ${date(report.finished_at)}`:""} · МСК</small></div>
  {maintenanceEntriesActive(report)&&<p role="status" className="maintenanceBackground">Обработка выполняется в фоне. Страницу можно закрыть; состояние и результаты сохраняются в этом отчёте.</p>}
  <p>В колонке «План» показаны подготовленные изменения. В колонке «После» — сохранённые и подтверждённые результаты. Если операция не подтверждена, причина указана у проекта.</p>
  {!report.entries.length&&<p role="status">В отчёте пока нет проектов.</p>}
  {!!report.excluded_projects?.length&&<details><summary>Исключённые проекты · {report.excluded_projects.length}</summary>{report.excluded_projects.map(row=><p key={row.site_id}>{row.project}{row.destination_report_id&&<> · <a href={`/auto-reglue/pilot?id=${row.destination_report_id}`}>Отдельный план</a></>}</p>)}</details>}
  {report.entries.map((entry,index)=><article className="maintenanceEntry" key={entry.site_id}>
   <header><h3>{index+1}. <a href={`/project-network/${encodeURIComponent(entry.project)}/`}>{entry.project}</a></h3><strong>{report.planning_only?(entry.planning_status==="blocked"?"Требуется пересчитать план":entry.phase==="awaiting_domain"?"План готов · нужен домен":"План готов"):labels[entry.status]||entry.status}</strong>{onExclude&&report.can_exclude&&<button type="button" className="button secondary compact" disabled={!!excluding} onClick={()=>onExclude(entry.site_id)} aria-label={`Исключить ${entry.project} из отчёта`}>{excluding===entry.site_id?"Исключаем…":"Исключить из отчёта"}</button>}</header>
   {!report.planning_only&&entry.progress&&<div className="maintenanceEntryProgress" role="status" aria-live="polite"><span>{entry.progress.label}</span><small>{entry.progress.done} / {entry.progress.total} этапов · {entry.progress.percent}%</small><progress value={entry.progress.percent} max={100} aria-label={`Прогресс ${entry.project}`}/>{!!entry.progress.stages?.length&&<ul className="maintenanceStages" aria-label="Этапы проекта">{entry.progress.stages.map(stage=><li key={stage.key} data-state={stage.state}><strong>{stage.label}</strong><span>{({pending:"Ожидается",running:"В работе",completed:"Готово",failed:"Ошибка",waiting:"Ждём подтверждения"} as Record<string,string>)[stage.state]||stage.state}</span></li>)}</ul>}</div>}
   {!report.planning_only&&<p className="maintenanceTimes">{entry.kind==="structured_data"?"Микроразметка":"Изменение контента"} · начало: {date(entry.started_at||entry.content_started_at)} · завершение: {date(entry.finished_at||entry.content_finished_at)} · МСК</p>}
   {entry.paragraphs&&<p>Переписано абзацев: {entry.paragraphs.count??"—"} · {labels[entry.paragraphs.status||""]||entry.paragraphs.status||"Не подтверждено"}</p>}
   {[entry.paragraphs_before,entry.paragraphs_after,entry.paragraphs_added,entry.paragraphs_removed].some(value=>value!==undefined)&&<p className="maintenanceParagraphCounts">Количество абзацев: было — {entry.paragraphs_before??"—"} · стало — {entry.paragraphs_after??"—"} · добавлено — {entry.paragraphs_added??"—"} · удалено — {entry.paragraphs_removed??"—"}</p>}
   {entry.uniqueness_percent!==undefined&&<p>Уникальность относительно предыдущей версии: {entry.uniqueness_percent}%.</p>}
   {!!entry.shortened_percent&&<p>Текст обрезан на {entry.shortened_percent}%.</p>}
   {!report.planning_only&&entry.message&&<p role="status">{entry.message}</p>}{entry.error&&<p role="status">{entry.error}</p>}{(!report.planning_only||entry.planning_status==="blocked"||entry.planning_status==="conditional")&&entry.pending_reason&&<p role="status">{entry.pending_reason}</p>}
   {entry.kind==="structured_data"?<StructuredDataChanges value={entry.structured_data}/>:<div className="maintenanceChangesScroll"><Changes before={entry.before} after={entry.after} planned={entry.planned} brandTerm={entry.brand_count_term}/></div>}
   {entry.current_observation&&<details><summary>Текущее состояние · {entry.current_observation.source==="cache"?"кеш":"Webdev"} · {date(entry.current_observation.observed_at)} МСК</summary><table className="maintenanceChanges"><tbody>{Object.entries(entry.current_observation.values).map(([key,value])=><tr key={key}><th>{({main:"Main",title:"Title",h1:"H1",description:"Description",words:"Words",alternates:"Альтернейты",canonical:"Canonical",fake_path:"Внутренняя страница"} as Record<string,string>)[key]||key}</th><td>{value===""?"Не задано":value}</td></tr>)}</tbody></table></details>}
   {entry.words_scope==="content_blocks"&&<p className="maintenanceWordsScope">Words — слова в тексте страницы: абзацы, заголовки, списки, таблицы и баннеры. Мета, скрипты и общие шаблоны не учитываются.</p>}
   {!!(entry.copy_changes?.length||entry.table_changes?.length)&&<details className="maintenanceTaskChanges"><summary>Что изменено · текст: {entry.copy_changes?.length||0} · таблицы: {entry.table_changes?.length||0}{entry.table_emojis?" · добавлены эмодзи":""}</summary>
    {!!entry.table_changes?.length&&<ul>{entry.table_changes.map((change,index)=><li key={index}>Таблица {index+1}: строк до — {change.rows_before}, после — {change.rows_after}</li>)}</ul>}
    {entry.copy_changes?.map((change,index)=><div key={index} className="maintenanceCopyChange"><strong>{({banner_title:"Заголовок баннера",banner_subtitle:"Текст баннера",banner_button:"Кнопка баннера",table_button:"Кнопка после таблицы"} as Record<string,string>)[change.field]||"Текст"}</strong><p><b>До:</b> {change.old}</p><p><b>После:</b> {change.new}</p></div>)}
   </details>}
   {!!entry.operations?.length&&<div className="maintenanceOperations"><h4>Изменения по операциям</h4>{entry.operations.map(operation=><details key={operation.id}>
    <summary>{operation.kind==="page_edit"?"Сохранение страницы":operation.action==="structured_data"?"Сохранение микроразметки":operation.action||"Настройки сетки"} · {labels[operation.status]||operation.status} · {date(operation.finished_at||operation.started_at)} МСК</summary>
    <p>Начало: {date(operation.started_at)} · Завершение: {date(operation.finished_at)} · МСК</p>
    {operation.action!=="structured_data"&&<div className="maintenanceChangesScroll"><Changes before={operation.before} after={operation.after} contentOnly={operation.kind==="page_edit"}/></div>}
    <p className="maintenanceOperationId">Запись операции: <code>{operation.id}</code></p>
   </details>)}</div>}
   {!!(entry.edit_ids?.length||entry.network_operation_ids?.length||entry.run_id)&&<details><summary>Идентификаторы операций</summary>{entry.run_id&&<p>Переклей: <code>{entry.run_id}</code></p>}{entry.edit_ids?.map(edit=><p key={edit}>Сохранение страницы: <code>{edit}</code></p>)}{entry.network_operation_ids?.map(operation=><p key={operation}>Настройки сетки: <code>{operation}</code></p>)}</details>}
  </article>)}
 </>;
}

export function MaintenanceRepeatControls({ready,pending,uncertain,allowReserve,createdUrl,onReserve,onRepeat}:{
 ready:boolean;pending:boolean;uncertain:boolean;allowReserve:boolean;createdUrl?:string;onReserve:(value:boolean)=>void;onRepeat:()=>void;
}) {
 return <div className="maintenanceRepeat">
  <div className="maintenanceRepeatActions"><button type="button" className="button primary compact" disabled={!ready||pending||!!createdUrl} onClick={onRepeat}><Repeat2 size={16}/>{pending?"Создаём новый отчёт…":"Повторить для этой группы"}</button>
   <label><input type="checkbox" checked={allowReserve} disabled={!ready||pending||uncertain||!!createdUrl} onChange={event=>onReserve(event.target.checked)}/>Разрешено использовать резерв</label></div>
  <p>Полностью переписать контент, мета и заголовки проектов группы и выполнить новый переклей. Результат появится в отдельном отчёте.</p>
  <small>Резерв используется только если в своей сетке нет неиспользованного новорега.</small>
  {uncertain&&!pending&&<p role="status">Ответ на заявку не подтверждён. Повторная отправка проверит тот же запуск с прежними настройками.</p>}
  {createdUrl&&<p role="status"><a href={createdUrl}>Открыть новый отчёт</a></p>}
 </div>;
}

export function MaintenanceReport({api,id}:{api:Api;id:string}) {
 const [report,setReport]=React.useState<MaintenanceReportData|null>(null),[error,setError]=React.useState(""),[loading,setLoading]=React.useState(false);
 const [allowReserve,setAllowReserve]=React.useState(false),[repeating,setRepeating]=React.useState(false),[uncertain,setUncertain]=React.useState(false),[repeatError,setRepeatError]=React.useState(""),[createdUrl,setCreatedUrl]=React.useState("");
 const repeat=React.useMemo(()=>{let store:Storage|undefined;try{if(typeof window!=="undefined")store=window.sessionStorage;}catch{/* Storage is optional. */}return createMaintenanceRepeat(id,api,store);},[id,api]);
 React.useEffect(()=>{const pending=repeat.pending();setAllowReserve(pending?.allow_reserve??false);setUncertain(!!pending);setRepeating(false);setRepeatError("");setCreatedUrl("");},[repeat]);
 const [excluding,setExcluding]=React.useState<string|null>(null);
 const excludingRef=React.useRef(false);
 async function excludeProject(siteId:string){if(excludingRef.current)return;excludingRef.current=true;setExcluding(siteId);setError("");try{++request.current;setReport(normalizeMaintenanceReport(await api(`/auto-reglue/reports/${encodeURIComponent(id)}/projects/${encodeURIComponent(siteId)}/exclude`,{method:"POST"})));}catch(e){setError(e instanceof Error?e.message:"Не удалось исключить проект");}finally{excludingRef.current=false;setExcluding(null);}}
 const request=React.useRef(0);
 const load=React.useCallback(async()=>{
  const sequence=++request.current;setLoading(true);
  try{const archive=new URLSearchParams(window.location.search).get("archive")==="1";const raw=await api<unknown>(`/auto-reglue/maintenance-reports/${encodeURIComponent(id)}${archive?"?archive=true":""}`,{cache:"no-store"});if(sequence!==request.current)return;if(object(raw).pilot_report_url===`/auto-reglue/pilot?id=${id}`){window.location.replace(`/auto-reglue/pilot?id=${id}`);return;}const value=normalizeMaintenanceReport(raw);setReport(value);setError("");}
  catch(e){if(sequence===request.current)setError(e instanceof Error?e.message:"Не удалось загрузить отчёт");}
  finally{if(sequence===request.current)setLoading(false);}
 },[api,id]);
 React.useEffect(()=>{setReport(null);void load();return()=>{request.current++;};},[load]);
 React.useEffect(()=>{if(!maintenanceEntriesActive(report))return;const timer=setInterval(()=>void load(),5000);return()=>clearInterval(timer);},[load,report]);
 const ready=report?.presentation!=="work_list"&&!["brand_health_audit","structured_data","toc_repair","showcase_audit","showcase_inventory","showcase_standardization","article_image_localization","site_maintenance"].includes(report?.task_type||"")&&maintenanceCanRepeat(report);
 async function repeatGroup(){
  if(!ready||repeating||createdUrl)return;
  setRepeating(true);setRepeatError("");
  try{const result=await repeat.submit(allowReserve);const url=maintenanceReportLink(result.id);setCreatedUrl(url);setUncertain(false);window.location.assign(url);}
  catch(error){setUncertain(!!repeat.pending());setRepeatError(error instanceof Error?error.message:"Не удалось создать повторный процесс. Повторите отправку.");}
  finally{setRepeating(false);}
 }
 return <section className="dataPanel pilotPanel maintenanceReport">
  <header className="pilotTools"><a className="button secondary compact" href="/auto-reglue/pilot/report"><ArrowLeft size={16}/>Планы и отчёты</a><h2><ScrollText size={20}/><span>{report?.report_id!==undefined&&<a className="maintenanceReportId" href={maintenanceReportLink(id)}>{!report.planning_only?"Отчёт по плану":"План"} №{report.report_id}</a>}{report?.name||"Отчёт по задаче"}</span></h2><button type="button" className="button secondary compact" disabled={loading} onClick={()=>void load()}><RefreshCw size={16}/>{loading?"Обновляем…":"Обновить"}</button></header>
  {error&&<p role="alert">{error}</p>}{!report&&!error&&<p role="status">Загружаем отчёт…</p>}
  {report&&!report.planning_only&&report.presentation!=="work_list"&&!["brand_health_audit","structured_data","toc_repair","showcase_audit","showcase_inventory","showcase_standardization","article_image_localization","site_maintenance"].includes(report.task_type||"")&&<MaintenanceRepeatControls ready={ready} pending={repeating} uncertain={uncertain} allowReserve={allowReserve} createdUrl={createdUrl} onReserve={setAllowReserve} onRepeat={()=>void repeatGroup()}/>}
  {repeatError&&<p role="alert">{repeatError}</p>}
  {report&&<MaintenanceReportBody report={report} api={api} onExclude={siteId=>void excludeProject(siteId)} excluding={excluding}/>}
 </section>;
}
