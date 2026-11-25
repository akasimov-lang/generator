import React from 'react';
import { TemplateCombobox } from './TemplateCombobox';
import { NetworkEditStatus } from './NetworkEditStatus';
import { QueueSaveIndicator } from './SaveIndicator';
import { editActive, type NetworkEditQueueView } from './networkEditQueue';
import type { DomainRedirect, RedirectEdit } from './DomainRedirects';
import { cleanAddress, host, completeDrops, schemeProblems, unlinkedDomains, sourceChoices, orderRedirectChanges } from './redirectScheme';
import { RedirectGraph } from './RedirectGraph';
import './styles/domain-redirects.css';
type Draft=DomainRedirect & {id:string; original:string; removed?:boolean; expected:DomainRedirect[]};
export function RedirectWorkspace({redirects,revision,available,disabled,onSave,canon,queue,domains=[],types={},schema=false,scope='network'}:{queue?:NetworkEditQueueView;canon:string;onRetargetMain:(revision:string)=>Promise<boolean>;redirects:DomainRedirect[];revision:string;available:boolean;disabled:boolean;onSave:(edit:RedirectEdit,revision:string)=>Promise<boolean>;domains?:string[];types?:Record<string,string>;schema?:boolean;scope?:string}) {
  const [draft,setDraft]=React.useState<Draft[]|null>(null), [saving,setSaving]=React.useState(false), [error,setError]=React.useState('');
  const lock=React.useRef(false);
  const savedRows=React.useMemo<Draft[]>(()=>redirects.map(r=>({...r,id:crypto.randomUUID(),original:r.url,expected:[{...r}]})),[redirects]);
  const snapshot=()=>savedRows.map(r=>({...r}));
  const rows=draft||snapshot();
  const planned=rows.filter(r=>!r.removed);
  const pending=(queue?.items||[]).some(i=>['domain_redirect','domain_redirects_main'].includes(i.request.action)&&editActive(i));
  const blocked=!available||saving||disabled||pending;
  const problems=draft?schemeProblems(planned,domains,types,canon):[];
  const changed=rows.filter(r=>r.removed||!r.original||r.value!==r.expected[0]?.value||r.url!==r.original);
  const ordered=[...domains].sort((a,b)=>(types[a]==='drop'?0:types[a]==='newreg'?1:2)-(types[b]==='drop'?0:types[b]==='newreg'?1:2)||a.localeCompare(b));
  const label=(d:string)=>`${d} · ${types[d]==='drop'?'Дроп':types[d]==='newreg'?'Новорег':'Тип не указан'}`;
  const assigned=new Set([...redirects.map(r=>host(r.url)),...planned.map(r=>host(r.url)),...(queue?.items||[]).filter(i=>i.request.action==='domain_redirect'&&editActive(i)&&!i.request.redirect_delete).map(i=>host(String(i.request.redirect_source)))]);
  function update(id:string,patch:Partial<Draft>){setDraft(rows.map(r=>r.id===id?{...r,...patch}:r));setError('');}
  function connect(from:string,to:string){const next=draft||snapshot(),row=next.find(r=>host(r.url)===host(from));if(row){row.value=to;row.removed=false;}else next.push({id:crypto.randomUUID(),url:from,value:to,original:'',expected:[]});setDraft([...next]);}
  async function submit(){if(lock.current||blocked||problems.length)return;lock.current=true;setSaving(true);setError('');let rest=[...rows];try{for(const row of orderRedirectChanges(changed)){const ok=await onSave({redirect_source:cleanAddress(row.url),redirect_target:cleanAddress(row.value),redirect_original_source:row.original,redirect_delete:!!row.removed,expected:{rows:row.expected}},revision);if(!ok)throw new Error('Не удалось добавить строку в очередь. Неотправленные изменения сохранены в редакторе.');rest=row.removed?rest.filter(r=>r.id!==row.id):rest.map(r=>r.id===row.id?{...r,original:r.url,expected:[{url:r.url,value:r.value}]}:r);setDraft(rest);}setDraft(null);}catch(e){setError(e instanceof Error?e.message:String(e));}finally{lock.current=false;setSaving(false);}}
  React.useEffect(()=>{if(!draft)return;const warn=(event:BeforeUnloadEvent)=>event.preventDefault();window.addEventListener('beforeunload',warn);return()=>window.removeEventListener('beforeunload',warn);},[draft]);
  const singles=unlinkedDomains(domains,planned);
  return <section className="networkSection networkRedirects" aria-label="Доменные редиректы"><div className="networkRedirectsHeading"><h3>{schema?'Схема редиректов':'Доменные редиректы'} · {planned.length}</h3><QueueSaveIndicator items={(queue?.items||[]).filter(i=>['domain_redirect','domain_redirects_main'].includes(i.request.action))} label="Доменные редиректы"/>
    {!schema&&<a className="button secondary compact" href={`${location.pathname}?redirect-schema=1`}>Открыть схему</a>}
  </div>
    {!available?<p role="status">Обновите данные: редиректы ещё не получены из Webdev.</p>:<>
    <div className="networkActions"><button className="button secondary compact" disabled={blocked} onClick={()=>setDraft([...rows,{id:crypto.randomUUID(),url:'',value:'',original:'',expected:[]}])}>Добавить строку</button><button className="button secondary compact" disabled={blocked} onClick={()=>{try{const next=completeDrops(planned,domains,types,canon);setDraft([...rows.filter(r=>r.removed),...next.map(r=>{const old=rows.find(d=>host(d.url)===host(r.url));return old?{...old,...r}:{...r,id:crypto.randomUUID(),original:'',expected:[]};})]);setError('');}catch(e){setError(String(e));}}}>Подготовить подклей всех дропов</button>
      <button className="button compact" disabled={blocked||!changed.length||!!problems.length} onClick={()=>void submit()}>{saving?'Отправляем…':`Отправить изменения${changed.length?` (${changed.length})`:''}`}</button>{draft&&<button className="button secondary compact" disabled={saving} onClick={()=>{setDraft(null);setError('');}}>Отменить изменения</button>}</div>
    <p className="muted">{draft?'План: изменения ещё не отправлены.':'Подтверждённые настройки Webdev.'} После отправки результат подтверждается отдельно для каждой строки.</p>
    {pending&&<p role="status">Дождитесь завершения очереди перед следующим изменением схемы.</p>}
    {error&&<p role="alert">{error}</p>}{problems.length>0&&<ul role="alert">{problems.map(p=><li key={p}>{p}</li>)}</ul>}
    {schema&&<fieldset disabled={blocked} style={{border:0,padding:0,minWidth:0}}><RedirectGraph domains={domains} types={types} rows={planned} scope={scope} onConnect={connect}/></fieldset>}
    <div className="redirectEditorColumns">{rows.map(row=><fieldset key={row.id} className={`redirectEditorRow${row.removed?' removed':''}`} disabled={blocked}>
      <TemplateCombobox label="Откуда" value={row.url} options={sourceChoices(domains,types,[...assigned],canon,row.url).map(d=>({value:d,label:label(d)}))} onChange={value=>update(row.id,{url:cleanAddress(value)})}/>
      <TemplateCombobox label="Куда · 301" value={row.value} allowCustom options={ordered.filter(d=>host(d)!==host(row.url) && (types[domains.find(n=>host(n)===host(row.url))||'']!=='drop'||types[d]==='newreg')).map(d=>({value:d,label:d}))} onChange={value=>update(row.id,{value:cleanAddress(value)})}/>
      <button type="button" className="button secondary compact" onClick={()=>{if(!row.original)setDraft(rows.filter(r=>r.id!==row.id));else update(row.id,{removed:!row.removed});}}>{row.removed?'Вернуть':'Удалить'}</button>
    </fieldset>)}</div>
    <div className="redirectSingles"><h4>Домены без связей · {singles.length}</h4><div className="redirectEditorColumns">{['drop','newreg'].map(type=><div key={type}><strong>{type==='drop'?'Дропы':'Новореги'}</strong><ul>{singles.filter(d=>types[d]===type).map(d=><li key={d}>{d}</li>)}</ul></div>)}</div>{singles.some(d=>!types[d])&&<p>Тип не указан: {singles.filter(d=>!types[d]).join(', ')}</p>}</div>
    {schema&&<div className="networkTableWrap"><table className="domainRedirectsTable"><thead><tr><th>Домен</th><th>Тип</th><th>Подтверждённый 301</th><th>План 301</th></tr></thead><tbody>{[...new Set([...domains,...redirects.map(r=>r.url)])].map(d=><tr key={d}><td>{d}</td><td>{types[d]==='drop'?'Дроп':types[d]==='newreg'?'Новорег':'—'}</td><td>{redirects.find(r=>host(r.url)===host(d))?.value||'Нет исходящего редиректа'}</td><td>{planned.find(r=>host(r.url)===host(d))?.value||'Нет исходящего редиректа'}</td></tr>)}</tbody></table></div>}
    {(queue?.items||[]).filter(i=>['domain_redirect','domain_redirects_main'].includes(i.request.action)).map(i=><div key={i.id}><small>{String(i.request.redirect_source||'Доменные редиректы')}</small><NetworkEditStatus item={i} retry={id=>queue?.retry(id)}/></div>)}
    </>}
  </section>;
}
