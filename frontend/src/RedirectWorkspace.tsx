import {RedirectSchemeLibrary,type SchemeApi,type SchemeDocument} from "./RedirectSchemeLibrary";
import {readRedirectDraft,recoveryDraft,redirectDraftKey,type RedirectDraftRow} from "./redirectDraft";
import type {DomainMetricsMap} from "./domainMetrics";
import React from 'react';
import { Trash2 } from 'lucide-react';
import { TemplateCombobox } from './TemplateCombobox';
import { NetworkEditStatus } from './NetworkEditStatus';
import { QueueSaveIndicator } from './SaveIndicator';
import { editActive, type NetworkEditQueueView } from './networkEditQueue';
import type { DomainRedirect, RedirectEdit } from './DomainRedirects';
import { cleanAddress, host, completeDrops, schemeProblems, sourceChoices, orderRedirectChanges, redirectDomainScope } from './redirectScheme';
import { RedirectGraph } from './RedirectGraph';
import './styles/domain-redirects.css';
type Draft=RedirectDraftRow;
export function RedirectWorkspace({redirects:allRedirects,revision,available,disabled,onSave,canon,queue,domains:allDomains=[],types={},schema=false,scope='network',excludedDomains=[],metrics={},draftOwner="",api}:{api?:SchemeApi;draftOwner?:string;excludedDomains?:string[];metrics?:DomainMetricsMap;queue?:NetworkEditQueueView;canon:string;onRetargetMain:(revision:string)=>Promise<boolean>;redirects:DomainRedirect[];revision:string;available:boolean;disabled:boolean;onSave:(edit:RedirectEdit,revision:string)=>Promise<boolean>;domains?:string[];types?:Record<string,string>;schema?:boolean;scope?:string}) {
  const redirectScope=React.useMemo(()=>redirectDomainScope(allDomains,allRedirects,types,excludedDomains),[allDomains,allRedirects,types,excludedDomains]);
  const {domains,redirects}=redirectScope;
  const storageKey=redirectDraftKey(scope,draftOwner);
  const recoveryKey=`redirect-draft-recovery:${location.pathname}`;
  const [initialDraft]=React.useState(()=>{try{const local=readRedirectDraft(localStorage.getItem(storageKey)),recovered=recoveryDraft(localStorage.getItem(recoveryKey),location.pathname,redirects,()=>crypto.randomUUID());return recovered&&(!local||recovered.saved_at>local.saved_at)?recovered:local;}catch{return null;}});
  const [draft,setDraft]=React.useState<Draft[]|null>(initialDraft?.rows||null), [saving,setSaving]=React.useState(false), [error,setError]=React.useState('');
  const [draftStatus,setDraftStatus]=React.useState(initialDraft?'Черновик восстановлен':'');
  const [draftPersisted,setDraftPersisted]=React.useState(!!initialDraft);
  const hadDraft=React.useRef(!!initialDraft);
  function saveDraft(next:Draft[]|null=draft){if(!next)return;try{const saved_at=new Date().toISOString();localStorage.setItem(storageKey,JSON.stringify({version:1,rows:next,saved_at}));localStorage.removeItem(recoveryKey);hadDraft.current=true;setDraftPersisted(true);setDraftStatus(`Черновик сохранён в этом браузере · ${new Date(saved_at).toLocaleTimeString('ru-RU',{timeZone:'Europe/Moscow',hour:'2-digit',minute:'2-digit'})} МСК`);}catch{setDraftPersisted(false);setDraftStatus('Не удалось сохранить черновик: хранилище браузера недоступно. Не закрывайте вкладку.');}}
  React.useEffect(()=>{if(draft)saveDraft(draft);else if(hadDraft.current){try{localStorage.removeItem(storageKey);localStorage.removeItem(recoveryKey);hadDraft.current=false;setDraftStatus('');setDraftPersisted(false);}catch{}}},[draft,storageKey]);
  const [redirectDates,setRedirectDates]=React.useState<Record<string,string>>({});
  const [graphVersion,setGraphVersion]=React.useState(0);
  function loadScheme(doc:SchemeDocument){setDraft(doc.rows);try{localStorage.setItem(`redirect-layout:${scope}`,JSON.stringify(doc.board.positions));localStorage.setItem(`redirect-placed:${scope}`,JSON.stringify(doc.board.placed));localStorage.setItem(`redirect-zoom:${scope}`,String(doc.board.zoom));}catch{setError("Не удалось восстановить расположение: хранилище браузера недоступно.");}setGraphVersion(v=>v+1);}
  const [expanded,setExpanded]=React.useState(false);
  const [tableOpen,setTableOpen]=React.useState(!schema);
  React.useEffect(()=>{if(!schema)return;const body=document.body.style.overflow,root=document.documentElement.style.overflow;document.body.style.overflow='hidden';document.documentElement.style.overflow='hidden';return()=>{document.body.style.overflow=body;document.documentElement.style.overflow=root;};},[schema]);
  const lock=React.useRef(false);
  const savedRows=React.useMemo<Draft[]>(()=>redirects.map(r=>({...r,id:crypto.randomUUID(),original:r.url,expected:{rows:[{...r}]}})),[redirects]);
  const snapshot=()=>savedRows.map(r=>({...r}));
  const rows=(draft||snapshot()).filter(row=>!redirectScope.isAmp(row.url)&&!redirectScope.isAmp(row.value));
  const planned=rows.filter(r=>!r.removed);
  const pending=(queue?.items||[]).some(i=>['domain_redirect','domain_redirects_main'].includes(i.request.action)&&editActive(i));
  const blocked=!available||saving||disabled||pending;
  const problems=draft?schemeProblems(planned,domains,types,canon):[];
  const changed=rows.filter(r=>r.removed||!r.original||r.value!==r.expected.rows[0]?.value||r.url!==r.original);
  const ordered=[...domains].sort((a,b)=>(types[a]==='drop'?0:types[a]==='newreg'?1:2)-(types[b]==='drop'?0:types[b]==='newreg'?1:2)||a.localeCompare(b));
  const label=(d:string)=>`${d} · ${types[d]==='drop'?'Дроп':types[d]==='newreg'?'Новорег':'Тип не указан'}`;
  const assigned=new Set([...redirects.map(r=>host(r.url)),...planned.map(r=>host(r.url)),...(queue?.items||[]).filter(i=>i.request.action==='domain_redirect'&&editActive(i)&&!i.request.redirect_delete).map(i=>host(String(i.request.redirect_source)))]);
  function update(id:string,patch:Partial<Draft>){if((patch.value&&redirectScope.isAmp(patch.value))||(patch.url&&redirectScope.isAmp(patch.url))){setError("AMP-домены не участвуют в доменных редиректах.");return;}setDraft(rows.map(r=>r.id===id?{...r,...patch}:r));setError('');}
  function connect(from:string,to:string){const next=draft||snapshot(),row=next.find(r=>host(r.url)===host(from));if(row){row.value=to;row.removed=false;}else next.push({id:crypto.randomUUID(),url:from,value:to,original:'',expected:{rows:[]}});setDraft([...next]);}
  async function submit(){if(lock.current||blocked||problems.length)return;lock.current=true;setSaving(true);setError('');let rest=[...rows];try{for(const row of orderRedirectChanges(changed)){const ok=await onSave({redirect_source:cleanAddress(row.url),redirect_target:cleanAddress(row.value),redirect_original_source:row.original,redirect_delete:!!row.removed,expected:row.expected},revision);if(!ok)throw new Error('Не удалось добавить строку в очередь. Неотправленные изменения сохранены в редакторе.');rest=row.removed?rest.filter(r=>r.id!==row.id):rest.map(r=>r.id===row.id?{...r,original:r.url,expected:{rows:[{url:r.url,value:r.value}]}}:r);setDraft(rest);}setDraft(null);}catch(e){setError(e instanceof Error?e.message:String(e));}finally{lock.current=false;setSaving(false);}}
  React.useEffect(()=>{if(!draft||draftPersisted)return;const warn=(event:BeforeUnloadEvent)=>event.preventDefault();window.addEventListener('beforeunload',warn);return()=>window.removeEventListener('beforeunload',warn);},[draft,draftPersisted]);
  return <section className={`networkSection networkRedirects${schema?" redirectSchemaWorkspace":" redirectCompactSection"}`} aria-label="Доменные редиректы"><div className="networkRedirectsHeading"><h3>{schema?'Схема редиректов':'Доменные редиректы'} · {planned.length}</h3><QueueSaveIndicator items={(queue?.items||[]).filter(i=>['domain_redirect','domain_redirects_main'].includes(i.request.action))} label="Доменные редиректы"/>
    {!schema&&<><a className="button secondary compact" href={`${location.pathname}?redirect-schema=1`}>Открыть схему</a><button type="button" className="button secondary compact" aria-expanded={expanded} onClick={()=>setExpanded(value=>!value)}>{expanded?'Свернуть':'Редактировать редиректы'}</button></>}
  </div>
    <div className="redirectWorkspaceBody" hidden={!schema&&!expanded}>
    {!available?<p role="status">Обновите данные: редиректы ещё не получены из Webdev.</p>:<>
    <details className="redirectSupportingDetails" open={tableOpen} onToggle={e=>setTableOpen(e.currentTarget.open)}><summary>Редиректы · {planned.length}{schema&&problems.length>0&&<span className="redirectValidationCount" role="status">Проверить связи: {problems.length}</span>}</summary><div className="redirectSupportingBody">
    <div className="redirectTables">{[rows.slice(0,Math.ceil(rows.length/2)),rows.slice(Math.ceil(rows.length/2))].filter(column=>column.length).map((column,index)=><fieldset className="redirectTableField" disabled={blocked} key={index}><table className="redirectEditTable" aria-label={`Доменные редиректы · ${index+1}`}><thead><tr><th scope="col">Откуда</th><th scope="col">Куда · 301</th><th scope="col"><span className="redirectVisuallyHidden">Удаление</span></th></tr></thead><tbody>{column.map(row=><tr key={row.id} className={row.removed?'removed':''} title={problems.filter(message=>message.includes(row.url)).join('\n')}>
      <td><TemplateCombobox label={`Откуда: ${row.url||'новый редирект'}`} value={row.url} options={sourceChoices(domains,types,[...assigned],canon,row.url).map(d=>({value:d,label:label(d)}))} onChange={value=>update(row.id,{url:cleanAddress(value)})}/></td>
      <td><TemplateCombobox label={`Куда: ${row.url||'новый редирект'}`} value={row.value} allowCustom options={ordered.filter(d=>host(d)!==host(row.url) && (types[domains.find(n=>host(n)===host(row.url))||'']!=='drop'||types[d]==='newreg')).map(d=>({value:d,label:d}))} onChange={value=>update(row.id,{value:cleanAddress(value)})}/>{schema&&problems.some(message=>message.includes(row.url))&&<small className="redirectRowIssue">Проверьте назначение</small>}<NetworkEditStatus item={queue?.latest(`domain:${row.original||row.url}`)} retry={id=>queue?.retry(id)}/></td>
      <td><button type="button" className="redirectTrashButton" aria-label={`${row.removed?'Отменить удаление':'Удалить редирект'} ${row.url||'новую строку'}`} title={row.removed?'Отменить удаление':'Удалить редирект'} aria-pressed={!!row.removed} onClick={()=>{if(!row.original)setDraft(rows.filter(r=>r.id!==row.id));else update(row.id,{removed:!row.removed});}}><Trash2 size={15} aria-hidden="true"/></button></td>
    </tr>)}</tbody></table></fieldset>)}</div>
    </div></details>
    <div className="networkActions"><button className="button secondary compact" disabled={blocked} onClick={()=>{setTableOpen(true);setDraft([...rows,{id:crypto.randomUUID(),url:'',value:'',original:'',expected:{rows:[]}}]);}}>Добавить строку</button><button className="button secondary compact" disabled={blocked} onClick={()=>{try{const next=completeDrops(planned,domains,types,canon);setDraft([...rows.filter(r=>r.removed),...next.map(r=>{const old=rows.find(d=>host(d.url)===host(r.url));return old?{...old,...r}:{...r,id:crypto.randomUUID(),original:'',expected:{rows:[]}};})]);setError('');}catch(e){setError(String(e));}}}>{schema?"Подклеить дропы":"Подготовить подклей всех дропов"}</button>
      <button className="button compact" disabled={blocked||!changed.length||!!problems.length} onClick={()=>void submit()}>{saving?'Отправляем…':`Отправить изменения${changed.length?` (${changed.length})`:''}`}</button><RedirectSchemeLibrary scope={scope} api={api} rows={rows} busy={saving} onDates={setRedirectDates} onLoad={loadScheme} onLocalSave={()=>saveDraft(rows)}/>{draft&&<button className="button secondary compact" disabled={saving} onClick={()=>{setDraft(null);setError('');}}>Отменить изменения</button>}{draftStatus&&<small className={`redirectDraftStatus${draftPersisted?"":" error"}`} role="status">{draftStatus}</small>}</div>
    <p className="muted redirectSaveHint">{draft?'План: изменения ещё не отправлены.':'Подтверждённые настройки Webdev.'} После отправки результат подтверждается отдельно для каждой строки.</p>
    {pending&&<p role="status">Дождитесь завершения очереди перед следующим изменением схемы.</p>}
    {error&&<p role="alert">{error}</p>}{!schema&&problems.length>0&&<ul role="alert">{problems.map(p=><li key={p}>{p}</li>)}</ul>}
    {schema&&<fieldset className="redirectGraphField" disabled={blocked} style={{border:0,padding:0,minWidth:0,margin:0}}><RedirectGraph key={graphVersion} confirmedRows={redirects} redirectDates={redirectDates} metrics={metrics} canon={redirectScope.ampKeys.has(host(canon))?"":canon} disabled={blocked} domains={domains} types={types} rows={planned} scope={scope} onConnect={connect}/></fieldset>}

    </>}
    </div>
  </section>;
}
