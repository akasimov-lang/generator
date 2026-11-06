import { QueueSaveIndicator } from "./SaveIndicator";
import { NetworkEditStatus } from "./NetworkEditStatus";
import { editActive, type NetworkEditQueueView } from "./networkEditQueue";
import React from "react";
import { ArrowRight, ExternalLink, Pencil, Plus, Save, X } from "lucide-react";
import "./styles/domain-redirects.css";

export type DomainRedirect = {url:string;value:string};
export type RedirectEdit = {expected?:{rows:DomainRedirect[]};redirect_source:string;redirect_target:string;redirect_original_source:string};

function redirectHost(value:string):string {
  try {
    const url=new URL(value.trim().includes("://")?value.trim():`https://${value.trim()}`);
    return ["http:","https:"].includes(url.protocol)?url.hostname.toLowerCase().replace(/\.$/,""):"";
  }catch{return "";}
}

export function domainRedirectTargets(redirects:DomainRedirect[],available:boolean):Map<string,string> {
  const targets=new Map<string,string>();
  if(available)for(const row of redirects){
    if(!row||typeof row.url!=="string"||typeof row.value!=="string")continue;
    const source=redirectHost(row.url),target=redirectHost(row.value);
    if(source&&target)targets.set(source,target);
  }
  return targets;
}

export function domainRedirectTarget(domain:string,targets:Map<string,string>):string|undefined {
  return targets.get(redirectHost(domain));
}

export function DomainRedirects({redirects,revision,available,disabled,onSave,canon,onRetargetMain,queue}:{queue?:NetworkEditQueueView;canon:string;onRetargetMain:(revision:string)=>Promise<boolean>;redirects:DomainRedirect[];revision:string;available:boolean;disabled:boolean;onSave:(edit:RedirectEdit,revision:string)=>Promise<boolean>}) {
  const blocked = queue ? false : disabled;
  const [edit,setEdit]=React.useState<RedirectEdit|null>(null);
  const [saving,setSaving]=React.useState(false);
  const editRevision=React.useRef(revision);
  function startEdit(next:RedirectEdit){editRevision.current=revision;setEdit({...next,expected:{rows:structuredClone(redirects.filter(row=>row.url===(next.redirect_original_source||next.redirect_source)))}});}
  const sourceInput=React.useRef<HTMLInputElement>(null);
  const targetInput=React.useRef<HTMLInputElement>(null);
  const editFormId=React.useId();
  React.useEffect(()=>{if(edit){const input=edit.redirect_original_source?targetInput.current:sourceInput.current;input?.focus();input?.select();}},[edit?.redirect_original_source,edit===null]);
  async function save(event:React.FormEvent){
    event.preventDefault();
    if(!edit||saving||blocked)return;
    setSaving(true);
    try{if(await onSave(edit,editRevision.current))setEdit(null);}finally{setSaving(false);}
  }
  const valid=redirects.filter(row=>row&&typeof row.url==="string"&&typeof row.value==="string");
  for (const item of queue?.items || []) {
    if (item.request.action !== "domain_redirect" || item.status === "completed") continue;
    if (queue?.latest(`domain:${item.request.redirect_original_source || item.request.redirect_source}`)?.id !== item.id) continue;
    const source = String(item.request.redirect_original_source || item.request.redirect_source);
    if (!valid.some(row => row.url === source)) valid.push({url: source, value: String(item.request.redirect_target)});
  }
  const link=(domain:string)=>/^(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z0-9-]+$/i.test(domain)?<a href={`https://${domain}/`} target="_blank" rel="noopener noreferrer">{domain}<ExternalLink size={13} aria-hidden="true"/></a>:<span>{domain}</span>;
  return <section className="networkSection networkRedirects" aria-label="Доменные редиректы">
    <div className="networkRedirectsHeading"><h3 className="networkRedirectTitle">Доменные редиректы<span className="networkRedirectCount" aria-label={`Доменных редиректов: ${valid.length}`}>{valid.length}</span><QueueSaveIndicator items={(queue?.items || []).filter(item=>item.request.action === "domain_redirect" || item.request.action === "domain_redirects_main")} label="Доменные редиректы" /></h3><button type="button" className="button secondary compact" disabled={blocked||!!queue?.busy("domain_redirects_main")||saving||!!edit||!available||!canon||!valid.some(row=>row.value!==canon||row.url.replace(/^www\./,"")===canon.replace(/^www\./,""))} title={`Заменить назначения всех доменных редиректов на ${canon}`} onClick={()=>void (async()=>{setSaving(true);try{await onRetargetMain(revision);}finally{setSaving(false);}})()}><ArrowRight size={14}/>{saving&&!edit?"Сохраняем…":"301->main"}</button><NetworkEditStatus item={queue?.latest("domain_redirects_main")} retry={id=>queue?.retry(id)}/></div>
    {!available?<p className="muted">Редиректы ещё не получены из Webdev. Нажмите «Обновить данные».</p>:valid.length?<div className="networkTableWrap"><table className="domainRedirectsTable" aria-label="Откуда и куда перенаправляются домены"><thead><tr><th>Откуда</th><th aria-label="Направление"/><th>Куда</th><th>Действия</th></tr></thead><tbody>{valid.map((row,index)=>{
      const active=edit?.redirect_original_source===row.url;
      const queued=queue?.latest(`domain:${row.url}`);
      const pending=!!queued&&editActive(queued);
      const shownTarget=queued&&queued.status!=="completed" ? String(queued.request.redirect_target) : row.value;
      return <tr key={`${row.url}:${index}`}><td>{link(row.url)}</td><td><ArrowRight size={14} aria-hidden="true"/></td><td>{active&&edit?<span className="domainRedirectInlineField"><span aria-hidden="true">{row.value}<ExternalLink size={13}/></span><input ref={targetInput} form={editFormId} aria-label="Редирект: куда" value={edit.redirect_target} maxLength={253} autoComplete="off" spellCheck={false} required disabled={saving} onChange={e=>setEdit({...edit,redirect_target:e.target.value})} onKeyDown={e=>{if(e.key==="Escape"&&!saving){e.preventDefault();setEdit(null);}}}/></span>:<span className={pending?"networkEditPending":""}>{link(shownTarget)}</span>}</td><td>{pending?<NetworkEditStatus item={queued} retry={id=>queue?.retry(id)}/>:active?<form id={editFormId} className="domainRedirectInlineActions" aria-label="Редактирование редиректа" onSubmit={event=>void save(event)}><button type="submit" className="button secondary compact" disabled={blocked||saving||!edit?.redirect_target.trim()}><Save size={13}/>{saving?"Сохраняем…":"Сохранить"}</button><button type="button" className="button secondary compact" disabled={saving} onClick={()=>setEdit(null)}><X size={13}/>Отменить</button></form>:<button type="button" className="button secondary compact" aria-label={`Редактировать редирект ${row.url}`} disabled={saving||!!edit} onClick={()=>startEdit({redirect_source:row.url,redirect_target:shownTarget,redirect_original_source:redirects.some(saved=>saved.url===row.url)?row.url:""})}><Pencil size={13}/>Изменить</button>}{!pending&&<NetworkEditStatus item={queued} retry={id=>queue?.retry(id)}/>}</td></tr>;
    })}</tbody></table></div>:<p className="muted">Доменных редиректов нет.</p>}
    <div className="networkActions"><button type="button" className="button secondary compact" disabled={!available||saving||!!edit} onClick={()=>startEdit({redirect_source:"",redirect_target:"",redirect_original_source:""})}><Plus size={14}/>Добавить редирект</button></div>
    {edit&&!edit.redirect_original_source&&<form className="networkRedirectForm" aria-label="Новый редирект" onSubmit={event=>void save(event)}>
      <label>Откуда<input ref={sourceInput} aria-label="Редирект: откуда" value={edit.redirect_source} maxLength={253} autoComplete="off" spellCheck={false} disabled={saving} placeholder="old-domain.pl" required onChange={e=>setEdit({...edit,redirect_source:e.target.value})}/></label>
      <label>Куда<input aria-label="Редирект: куда" value={edit.redirect_target} maxLength={253} autoComplete="off" spellCheck={false} disabled={saving} placeholder="main-domain.pl" required onChange={e=>setEdit({...edit,redirect_target:e.target.value})}/></label>
      <div className="networkActions"><button type="submit" className="button compact" disabled={blocked||saving||!edit.redirect_source.trim()||!edit.redirect_target.trim()}>{saving?"Сохраняем…":"Сохранить редирект"}</button><button type="button" className="button secondary compact" disabled={saving} onClick={()=>setEdit(null)}>Отмена</button></div>
      <small className="muted">Укажите домены без https:// и пути. Изменения сохраняются в Webdev.</small>
    </form>}
  </section>;
}
