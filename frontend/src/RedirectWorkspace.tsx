import {RedirectSectionSaveStatus,type RedirectSaveFeedback} from "./RedirectSectionSaveStatus";
import {redirectTableColumns} from "./redirectTableColumns";
import {RedirectSchemeHeader} from "./RedirectSchemeHeader";
import {redirectSaveProgress,shouldRestoreServerDraft,type RedirectSaveBatch} from './redirectSaveProgress';
import {RedirectSaveProgress} from './RedirectSaveStatus';
import {RedirectSchemeLibrary,type SchemeApi,type SchemeDocument,type BoardSnapshot,readBoard} from "./RedirectSchemeLibrary";
import {readRedirectDraft,recoveryDraft,redirectDraftKey,removeDraftConnection,pruneConfirmedRedirectDeletes,settledRedirectDeleteFailures,type RedirectDraftRow} from "./redirectDraft";
import type {DomainMetricsMap} from "./domainMetrics";
import React from 'react';
import { Trash2 } from 'lucide-react';
import { TemplateCombobox } from './TemplateCombobox';
import { NetworkEditStatus } from './NetworkEditStatus';
import { QueueSaveIndicator } from './SaveIndicator';
import { editActive, type NetworkEditQueueView } from './networkEditQueue';
import type { DomainRedirect, RedirectEdit } from './DomainRedirects';
import { cleanAddress, host, completeDrops, schemeProblems, prepareRedirectDomainOptions, orderRedirectChanges, redirectDomainScope } from './redirectScheme';
import { RedirectGraph } from './RedirectGraph';
import './styles/domain-redirects.css';
type Draft=RedirectDraftRow;
export function RedirectWorkspace({redirects:allRedirects,revision,available,disabled,onSave,canon,queue,domains:allDomains=[],types={},schema=false,scope='network',excludedDomains=[],metrics={},draftOwner="",api,fiberyName}:{fiberyName?:string|null;api?:SchemeApi;draftOwner?:string;excludedDomains?:string[];metrics?:DomainMetricsMap;queue?:NetworkEditQueueView;canon:string;onRetargetMain:(revision:string)=>Promise<boolean>;redirects:DomainRedirect[];revision:string;available:boolean;disabled:boolean;onSave:(edit:RedirectEdit,revision:string)=>Promise<boolean>;domains?:string[];types?:Record<string,string>;schema?:boolean;scope?:string}) {
  const excludedKey=JSON.stringify(excludedDomains);
  const redirectScope=React.useMemo(()=>redirectDomainScope(allDomains,allRedirects,types,excludedDomains),[allDomains,allRedirects,types,excludedKey]);
  const {domains,redirects}=redirectScope;
  const storageKey=redirectDraftKey(scope,draftOwner);
  const recoveryKey=`redirect-draft-recovery:${location.pathname}`;
  const [initialDraft]=React.useState(()=>{try{const local=readRedirectDraft(localStorage.getItem(storageKey)),recovered=recoveryDraft(localStorage.getItem(recoveryKey),location.pathname,redirects,()=>crypto.randomUUID());return recovered&&(!local||recovered.saved_at>local.saved_at)?recovered:local;}catch{return null;}});
  const [draft,setDraftState]=React.useState<Draft[]|null>(initialDraft?.rows||null), [saving,setSaving]=React.useState(false), [error,setError]=React.useState('');
  const touchedDraft=React.useRef(false);
  const setDraft=React.useCallback<React.Dispatch<React.SetStateAction<Draft[]|null>>>(value=>{touchedDraft.current=true;setDraftState(value);},[]);
  const boardRef=React.useRef<BoardSnapshot|null>(null);
  const [loadedBoard,setLoadedBoard]=React.useState<BoardSnapshot|undefined>();
  const [boardVersion,setBoardVersion]=React.useState(0);
  const onBoardChange=React.useCallback((snapshot:BoardSnapshot,dirty:boolean)=>{boardRef.current=snapshot;if(dirty){touchedDraft.current=true;setBoardVersion(v=>v+1);}},[]);
  const getBoard=React.useCallback(()=>boardRef.current||readBoard(scope),[scope]);
  const [draftFeedback,setDraftFeedback]=React.useState<RedirectSaveFeedback|null>(null);
  const [libraryPhase,setLibraryPhase]=React.useState<string|null>(null);
  const [saveBatch,setSaveBatch]=React.useState<RedirectSaveBatch|null>(null);
  const [draftStatus,setDraftStatus]=React.useState(initialDraft?'Черновик восстановлен':'');
  const [draftPersisted,setDraftPersisted]=React.useState(!!initialDraft);
  const hadDraft=React.useRef(!!initialDraft);
  function saveDraft(next:Draft[]|null=draft){if(!next)return;try{const saved_at=new Date().toISOString();localStorage.setItem(storageKey,JSON.stringify({version:1,rows:next,saved_at}));localStorage.removeItem(recoveryKey);hadDraft.current=true;setDraftPersisted(true);setDraftStatus(`Черновик сохранён в этом браузере · ${new Date(saved_at).toLocaleTimeString('ru-RU',{timeZone:'Europe/Moscow',hour:'2-digit',minute:'2-digit'})} МСК`);}catch{setDraftPersisted(false);const detail='Не удалось сохранить черновик: хранилище браузера недоступно. Не закрывайте вкладку.';setDraftStatus(detail);setDraftFeedback({state:'error',detail});}}
  React.useEffect(()=>{if(draft)saveDraft(draft);else if(hadDraft.current){try{localStorage.removeItem(storageKey);localStorage.removeItem(recoveryKey);hadDraft.current=false;setDraftStatus('');setDraftPersisted(false);}catch{}}},[draft,storageKey]);
  const [redirectDates,setRedirectDates]=React.useState<Record<string,string>>({});
  const [graphVersion,setGraphVersion]=React.useState(0);
  function loadScheme(doc:SchemeDocument){setDraft(doc.rows);setLoadedBoard(doc.board);boardRef.current=doc.board;try{localStorage.setItem(`redirect-layout:${scope}`,JSON.stringify(doc.board.positions));localStorage.setItem(`redirect-sizes:${scope}`,JSON.stringify(doc.board.sizes||{}));localStorage.setItem(`redirect-placed:${scope}`,JSON.stringify(doc.board.placed));localStorage.setItem(`redirect-zoom:${scope}`,String(doc.board.zoom));localStorage.setItem(`redirect-board-height:${scope}`,String(doc.board.min_height||0));}catch{setError("Расположение открыто из сохранённой схемы; кеш браузера недоступен.");}setGraphVersion(v=>v+1);}
  const acceptServerDraft=React.useCallback((doc:SchemeDocument)=>{if(!shouldRestoreServerDraft(doc.saved_at,initialDraft?.saved_at,touchedDraft.current))return;touchedDraft.current=true;setDraftState(doc.rows);setLoadedBoard(doc.board);boardRef.current=doc.board;setGraphVersion(v=>v+1);setDraftStatus('Черновик восстановлен с сервера');},[]);
  const serverDraftSaved=React.useCallback((doc:SchemeDocument)=>{setDraftPersisted(true);setDraftStatus(`Черновик сохранён на сервере · ${new Date(doc.saved_at).toLocaleTimeString('ru-RU',{timeZone:'Europe/Moscow',hour:'2-digit',minute:'2-digit'})} МСК`);},[]);
  const TableSection=schema?'details':'div';
  const [tableOpen,setTableOpen]=React.useState(!schema);
  React.useEffect(()=>{if(!schema)return;const body=document.body.style.overflow,root=document.documentElement.style.overflow;document.body.style.overflow='hidden';document.documentElement.style.overflow='hidden';return()=>{document.body.style.overflow=body;document.documentElement.style.overflow=root;};},[schema]);
  const lock=React.useRef(false);
  const savedRows=React.useMemo<Draft[]>(()=>redirects.map(r=>({...r,id:crypto.randomUUID(),original:r.url,expected:{rows:[{...r}]}})),[redirects]);
  const snapshot=()=>savedRows.map(r=>({...r}));
  const pending=(queue?.items||[]).some(i=>['domain_redirect','domain_redirects_main'].includes(i.request.action)&&editActive(i));
  const reconciledDraft=React.useMemo(()=>draft&&available&&!saving&&!pending?pruneConfirmedRedirectDeletes(draft,redirects):draft,[draft,redirects,available,saving,pending]);
  React.useEffect(()=>{if(reconciledDraft!==draft)setDraftState(reconciledDraft);},[reconciledDraft,draft]);
  const rows=React.useMemo(()=>(reconciledDraft||savedRows).filter(row=>!redirectScope.isAmp(row.url)&&!redirectScope.isAmp(row.value)),[reconciledDraft,savedRows,redirectScope]);
  const planned=React.useMemo(()=>rows.filter(r=>!r.removed),[rows]);
  const settledFailures=settledRedirectDeleteFailures(queue?.items||[],redirects),settledFailureKey=JSON.stringify(settledFailures.map(i=>i.id));
  const dismissedFailures=React.useRef(new Set<string>());
  React.useEffect(()=>{if(!available||saving||pending||!queue)return;for(const item of settledFailures){if(dismissedFailures.current.has(item.id))continue;dismissedFailures.current.add(item.id);void queue.dismiss(item.id).catch(()=>{});}},[available,saving,pending,queue,settledFailureKey]);
  const blocked=!available||saving||disabled||pending||!!libraryPhase;
  const saveProgress=redirectSaveProgress(queue?.items||[],saveBatch,saving,libraryPhase);
  const problems=draft?schemeProblems(planned,domains,types,canon):[];
  const changed=rows.filter(r=>r.removed||!r.original||r.value!==r.expected.rows[0]?.value||r.url!==r.original);
  const domainChoices=React.useMemo(()=>prepareRedirectDomainOptions(domains,types,canon),[domains,types,canon]);
  const assigned=new Set([...redirects.map(r=>host(r.url)),...planned.map(r=>host(r.url)),...(queue?.items||[]).filter(i=>i.request.action==='domain_redirect'&&editActive(i)&&!i.request.redirect_delete).map(i=>host(String(i.request.redirect_source)))]);
  function update(id:string,patch:Partial<Draft>){if((patch.value&&redirectScope.isAmp(patch.value))||(patch.url&&redirectScope.isAmp(patch.url))){setError("AMP-домены не участвуют в доменных редиректах.");return;}setDraft(rows.map(r=>r.id===id?{...r,...patch}:r));setError('');}
  const connect=React.useCallback((from:string,to:string)=>{setDraft(current=>{const next=current||savedRows,index=next.findIndex(r=>host(r.url)===host(from));return index>=0?next.map((r,i)=>i===index?{...r,value:to,removed:false}:r):[...next,{id:crypto.randomUUID(),url:from,value:to,original:'',expected:{rows:[]}}];});},[savedRows]);
  const disconnect=React.useCallback((from:string,to:string)=>{if(blocked)return false;const next=removeDraftConnection(rows,from,to);if(next===rows){setError('Связь уже изменилась. Выберите её заново.');return false;}setDraft(next);setError('');return true;},[blocked,rows]);
  async function submit(){if(lock.current||blocked||problems.length)return;lock.current=true;setSaving(true);setError('');const batch:RedirectSaveBatch={ids:[],total:changed.length,sent:0};setSaveBatch({...batch});const previousIds=new Set((queue?.items||[]).map(i=>i.id));let rest=[...rows];try{for(const row of orderRedirectChanges(changed)){const ok=await onSave({redirect_source:cleanAddress(row.url),redirect_target:cleanAddress(row.value),redirect_original_source:row.original,redirect_delete:!!row.removed,expected:row.expected},revision);if(!ok)throw new Error('Не удалось добавить строку в очередь. Неотправленные изменения сохранены в редакторе.');batch.sent++;const receipt=queue?.latest(`domain:${row.original||row.url}`);if(receipt&&!previousIds.has(receipt.id)){batch.ids.push(receipt.id);previousIds.add(receipt.id);}setSaveBatch({...batch,ids:[...batch.ids]});rest=row.removed?rest.filter(r=>r.id!==row.id):rest.map(r=>r.id===row.id?{...r,original:r.url,expected:{rows:[{url:r.url,value:r.value}]}}:r);setDraft(rest);}setDraft(null);}catch(e){setError(e instanceof Error?e.message:String(e));}finally{lock.current=false;setSaving(false);}}
  React.useEffect(()=>{if(!draft||draftPersisted)return;const warn=(event:BeforeUnloadEvent)=>event.preventDefault();window.addEventListener('beforeunload',warn);return()=>window.removeEventListener('beforeunload',warn);},[draft,draftPersisted]);
  const queueFailure=(queue?.items||[]).find(i=>['domain_redirect','domain_redirects_main'].includes(i.request.action)&&i.status==='failed');
  const headerFeedback:RedirectSaveFeedback=error?{state:'error',detail:error}
    :saveProgress?.busy?{state:'saving',detail:`${saveProgress.label}. ${saveProgress.detail}`}
    :saveProgress?.failed||queueFailure?{state:'error',detail:saveProgress?.detail||queueFailure?.message||'Изменения не подтверждены Webdev.'}
    :draftFeedback?.state==='error'?draftFeedback
    :changed.length?(draftFeedback||{state:draftPersisted?'saved':'idle',detail:draftStatus||'Изменения ещё не отправлены в Webdev.'})
    :{state:'saved',detail:saveProgress?.detail||'Настройки получены из Webdev.'};
  return <section className={`networkSection networkRedirects${schema?" redirectSchemaWorkspace":" redirectCompactSection"}`} aria-label="Доменные редиректы">{schema&&<RedirectSchemeHeader fiberyName={fiberyName} canon={canon} domains={domains} types={types} redirectCount={planned.length} backHref={location.pathname}/>}<div className="networkRedirectsHeading"><h3>{schema?'Схема редиректов':'Доменные редиректы'} · {planned.length}</h3>{schema?<QueueSaveIndicator items={(queue?.items||[]).filter(i=>['domain_redirect','domain_redirects_main'].includes(i.request.action))} label="Доменные редиректы"/>:available&&<RedirectSectionSaveStatus {...headerFeedback}/>}
    {!schema&&<a className="button secondary compact" href={`${location.pathname}?redirect-schema=1`}>Открыть схему</a>}
  </div>
    <div className="redirectWorkspaceBody">
    {!available?<p role="status">Обновите данные: редиректы ещё не получены из Webdev.</p>:<>
    <TableSection className={schema?"redirectSupportingDetails":"redirectTableSection"} open={schema?tableOpen:undefined} onToggle={schema?e=>setTableOpen((e.currentTarget as HTMLDetailsElement).open):undefined}>{schema&&<summary>Редиректы · {planned.length}{schema&&problems.length>0&&<span className="redirectValidationCount" role="status">Проверить связи: {problems.length}</span>}</summary>}<div className="redirectSupportingBody">
    <div className="redirectTables">{redirectTableColumns(rows).map((column,index)=><fieldset className="redirectTableField" disabled={blocked} key={index}><table className="redirectEditTable" aria-label={`Доменные редиректы · ${index+1}`}><thead><tr><th scope="col">Откуда</th><th scope="col">Куда · 301</th><th scope="col"><span className="redirectVisuallyHidden">Удаление</span></th></tr></thead><tbody>{column.map(row=><tr key={row.id} className={row.removed?'removed':''} title={problems.filter(message=>message.includes(row.url)).join('\n')}>
      <td><TemplateCombobox portal label={`Откуда: ${row.url||'новый редирект'}`} value={row.url} tone={domainChoices.tone(row.url)} options={domainChoices.sources(row.url,assigned)} onChange={value=>update(row.id,{url:cleanAddress(value)})}/></td>
      <td><TemplateCombobox portal label={`Куда: ${row.url||'новый редирект'}`} value={row.value} tone={domainChoices.tone(row.value)} allowCustom options={domainChoices.targets(row.url)} onChange={value=>update(row.id,{value:cleanAddress(value)})}/>{schema&&problems.some(message=>message.includes(row.url))&&<small className="redirectRowIssue">Проверьте назначение</small>}<NetworkEditStatus item={queue?.latest(`domain:${row.original||row.url}`)} retry={id=>queue?.retry(id)}/></td>
      <td><button type="button" className="redirectTrashButton" aria-label={`${row.removed?'Отменить удаление':'Удалить редирект'} ${row.url||'новую строку'}`} title={row.removed?'Отменить удаление':'Удалить редирект'} aria-pressed={!!row.removed} onClick={()=>{if(!row.original)setDraft(rows.filter(r=>r.id!==row.id));else update(row.id,{removed:!row.removed});}}><Trash2 size={15} aria-hidden="true"/></button></td>
    </tr>)}</tbody></table></fieldset>)}</div>
    </div></TableSection>
    <div className="networkActions"><button className="button secondary compact" disabled={blocked} onClick={()=>{setTableOpen(true);setDraft([...rows,{id:crypto.randomUUID(),url:'',value:'',original:'',expected:{rows:[]}}]);}}>Добавить строку</button>{schema&&<button className="button secondary compact" disabled={blocked} onClick={()=>{try{const next=completeDrops(planned,domains,types,canon);setDraft([...rows.filter(r=>r.removed),...next.map(r=>{const old=rows.find(d=>host(d.url)===host(r.url));return old?{...old,...r}:{...r,id:crypto.randomUUID(),original:'',expected:{rows:[]}};})]);setError('');}catch(e){setError(String(e));}}}>Подклеить дропы</button>}
      <RedirectSchemeLibrary controls={schema} onStatusChange={setDraftFeedback} autoSave={!saving&&!pending&&(draft!==null||boardVersion>0)} boardVersion={boardVersion} getBoard={getBoard} onServerDraft={acceptServerDraft} onDraftSaved={serverDraftSaved} onActivity={setLibraryPhase} scope={scope} api={api} rows={rows} busy={saving} onDates={setRedirectDates} onLoad={loadScheme} onLocalSave={()=>{touchedDraft.current=true;saveDraft(rows);}}/>{changed.length>0&&<button className="button secondary compact" disabled={saving||!!libraryPhase} onClick={()=>{setDraft(null);setBoardVersion(v=>v+1);setError('');}}>Отменить изменения</button>}{schema&&draftStatus&&<small className={`redirectDraftStatus${draftPersisted?"":" error"}`} role="status">{draftStatus}</small>}<button className={`button compact redirectSubmitButton${changed.length?' hasChanges':''}`} disabled={blocked||!changed.length||!!problems.length} onClick={()=>void submit()}>{saving?'Отправляем…':`Отправить изменения${changed.length?` (${changed.length})`:''}`}</button></div>
    {saveProgress&&schema&&!saveProgress.busy&&<RedirectSaveProgress state={saveProgress}/>}
    {schema&&<p className="muted redirectSaveHint">{changed.length?'План: изменения ещё не отправлены.':'Подтверждённые настройки Webdev.'} После отправки результат подтверждается отдельно для каждой строки.</p>}
    {pending&&<p role="status">Дождитесь завершения очереди перед следующим изменением схемы.</p>}
    {error&&<p role="alert">{error}</p>}{!schema&&problems.length>0&&<ul role="alert">{problems.map(p=><li key={p}>{p}</li>)}</ul>}
    {schema&&<fieldset className="redirectGraphField" disabled={blocked} aria-busy={saveProgress?.busy||undefined} style={{border:0,padding:0,minWidth:0,margin:0}}><div className="redirectBoardContent" inert={!!saveProgress?.busy}><RedirectGraph initialBoard={loadedBoard} onBoardChange={onBoardChange} key={graphVersion} confirmedRows={redirects} redirectDates={redirectDates} metrics={metrics} canon={redirectScope.ampKeys.has(host(canon))?"":canon} disabled={blocked} domains={domains} types={types} rows={planned} scope={scope} onConnect={connect} onDisconnect={disconnect}/></div>{saveProgress?.busy&&<div className="redirectBusyOverlay"><RedirectSaveProgress state={saveProgress}/></div>}</fieldset>}

    </>}
    </div>
  </section>;
}
