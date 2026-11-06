import { QueueSaveIndicator } from "./SaveIndicator";
import { NetworkEditStatus } from "./NetworkEditStatus";
import { editActive, type NetworkEditQueueView } from "./networkEditQueue";
import React from "react";
import { ExternalLink, Pencil, Plus, Trash2 } from "lucide-react";
import { TemplateCombobox } from "./TemplateCombobox";

export type PageRedirectGroup = {domain:string;redirects:{url:string;value:string}[]};
export type PageRedirectEdit = {expected?:{rows:{url:string;value:string}[]};page_redirect_domain:string;page_redirect_source:string;page_redirect_target:string;page_redirect_original_domain:string;page_redirect_original_source:string;page_redirect_delete:boolean};

export function PageRedirects({groups,domains,canon,revision,available,disabled,onSave,queue}:{queue?:NetworkEditQueueView;groups:PageRedirectGroup[];domains:string[];canon:string;revision:string;available:boolean;disabled:boolean;onSave:(edit:PageRedirectEdit,revision:string)=>Promise<boolean>}) {
  const blocked = queue ? false : disabled;
  const [edit,setEdit]=React.useState<PageRedirectEdit|null>(null);
  const [saving,setSaving]=React.useState(false);
  const editRevision=React.useRef(revision);
  const sourceInput=React.useRef<HTMLInputElement>(null);
  const valid=groups.filter(g=>g&&typeof g.domain==="string"&&Array.isArray(g.redirects));
  const rows=valid.flatMap(g=>g.redirects.filter(r=>r&&typeof r.url==="string"&&typeof r.value==="string").map(r=>({...r,domain:g.domain})));
  for (const item of queue?.items || []) {
    if(item.request.action!=="page_redirect"||item.status==="completed")continue;
    if(queue?.latest(`page:${item.request.page_redirect_original_domain||item.request.page_redirect_domain}:${item.request.page_redirect_original_source||item.request.page_redirect_source}`)?.id!==item.id)continue;
    const domain=String(item.request.page_redirect_original_domain||item.request.page_redirect_domain);
    const url=String(item.request.page_redirect_original_source||item.request.page_redirect_source);
    if(!rows.some(row=>row.domain===domain&&row.url===url)) rows.push({domain,url,value:String(item.request.page_redirect_target)});
  }
  const choices=[...new Set([...domains,...valid.map(g=>g.domain)])].sort((a,b)=>a.localeCompare(b));
  function start(next:PageRedirectEdit){editRevision.current=revision;setEdit({...next,expected:{rows:structuredClone(valid.filter(g=>g.domain===(next.page_redirect_original_domain||next.page_redirect_domain)).flatMap(g=>g.redirects.filter(r=>r.url===(next.page_redirect_original_source||next.page_redirect_source))))}});}
  function rowEdit(row:typeof rows[number],remove=false){start({page_redirect_domain:row.domain,page_redirect_source:row.url,page_redirect_target:row.value,page_redirect_original_domain:valid.some(g=>g.domain===row.domain&&g.redirects.some(r=>r.url===row.url))?row.domain:"",page_redirect_original_source:valid.some(g=>g.domain===row.domain&&g.redirects.some(r=>r.url===row.url))?row.url:"",page_redirect_delete:remove});}
  React.useEffect(()=>{if(edit&&!edit.page_redirect_delete)sourceInput.current?.focus();},[edit?.page_redirect_original_source,edit===null]);
  async function save(event:React.FormEvent){event.preventDefault();if(!edit||saving||blocked)return;setSaving(true);try{if(await onSave(edit,editRevision.current))setEdit(null);}finally{setSaving(false);}}
  return <section className="networkSection networkRedirects networkPageRedirects" aria-label="Постраничные редиректы">
    <div className="networkRedirectsHeading"><h3 className="networkRedirectTitle">Постраничные редиректы<span className="networkRedirectCount" aria-label={`Постраничных редиректов: ${rows.length}`}>{rows.length}</span><QueueSaveIndicator items={(queue?.items || []).filter(item=>item.request.action === "page_redirect")} label="Постраничные редиректы" /></h3></div>
    {!available?<p className="muted">Редиректы ещё не получены из Webdev. Нажмите «Обновить данные».</p>:rows.length?<div className="networkTableWrap"><table className="domainRedirectsTable" aria-label="Перенаправления отдельных страниц"><thead><tr><th>Домен</th><th>Откуда</th><th>Куда</th><th>Действия</th></tr></thead><tbody>{rows.map((row,i)=>{
      const queued=queue?.latest(`page:${row.domain}:${row.url}`);
      const pending=!!queued&&editActive(queued);
      const shown=queued&&queued.status!=="completed"?{...row,value:String(queued.request.page_redirect_target)}:row;
      return <tr key={`${row.domain}:${row.url}:${i}`}><td>{row.domain}</td><td><code>{row.url}</code></td><td>{/^https?:\/\//i.test(shown.value)?<a href={shown.value} target="_blank" rel="noopener noreferrer">{shown.value}<ExternalLink size={13} aria-hidden="true"/></a>:shown.value}</td><td>{pending?<NetworkEditStatus item={queued} retry={id=>queue?.retry(id)}/>:<><div className="networkActions"><button type="button" className="button secondary compact" disabled={saving||!!edit} aria-label={`Изменить постраничный редирект ${row.domain}${row.url}`} onClick={()=>rowEdit(shown)}><Pencil size={13}/>Изменить</button><button type="button" className="button secondary compact" disabled={saving||!!edit} aria-label={`Удалить постраничный редирект ${row.domain}${row.url}`} onClick={()=>rowEdit(shown,true)}><Trash2 size={13}/>Удалить</button></div><NetworkEditStatus item={queued} retry={id=>queue?.retry(id)}/></>}</td></tr>;})}</tbody></table></div>:<p className="muted">Постраничных редиректов нет.</p>}
    <div className="networkActions"><button type="button" className="button secondary compact" disabled={saving||!available||!!edit||!choices.length} onClick={()=>start({page_redirect_domain:choices.includes(canon)?canon:choices[0],page_redirect_source:"",page_redirect_target:"",page_redirect_original_domain:"",page_redirect_original_source:"",page_redirect_delete:false})}><Plus size={14}/>Добавить постраничный редирект</button></div>
    {edit&&<form aria-label={edit.page_redirect_delete?"Удаление постраничного редиректа":edit.page_redirect_original_source?"Редактирование постраничного редиректа":"Новый постраничный редирект"} onSubmit={event=>void save(event)}><fieldset className="networkRedirectForm" style={{border:0,padding:0,margin:0,minWidth:0}} disabled={saving}>
      {edit.page_redirect_delete?<p>Удалить редирект {edit.page_redirect_domain}{edit.page_redirect_source} → {edit.page_redirect_target}?</p>:<>
        <TemplateCombobox label="Домен редиректа" value={edit.page_redirect_domain} options={choices.map(value=>({value,label:value}))} onChange={value=>setEdit({...edit,page_redirect_domain:value})} placeholder="Найти домен"/>
        <label>Откуда<input ref={sourceInput} aria-label="Постраничный редирект: откуда" value={edit.page_redirect_source} maxLength={2048} autoComplete="off" spellCheck={false} placeholder="/play/" required onChange={e=>setEdit({...edit,page_redirect_source:e.target.value})}/></label>
        <label>Куда<input aria-label="Постраничный редирект: куда" type="url" value={edit.page_redirect_target} maxLength={4096} autoComplete="off" spellCheck={false} placeholder={`https://${canon}/`} required onChange={e=>setEdit({...edit,page_redirect_target:e.target.value})}/></label>
      </>}
      <div className="networkActions"><button type="submit" className="button compact" disabled={blocked||!edit.page_redirect_delete&&(!edit.page_redirect_domain||!edit.page_redirect_source.trim()||!edit.page_redirect_target.trim())}>{saving?"Сохраняем…":edit.page_redirect_delete?"Удалить редирект":"Сохранить постраничный редирект"}</button><button type="button" className="button secondary compact" onClick={()=>setEdit(null)}>Отмена</button></div>
      <small className="muted">Изменения сохраняются в Webdev после подтверждения его настройками.</small>
    </fieldset></form>}
  </section>;
}
