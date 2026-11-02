import React from "react";
import { ExternalLink, Pencil, Plus, Trash2 } from "lucide-react";
import { TemplateCombobox } from "./TemplateCombobox";

export type PageRedirectGroup = {domain:string;redirects:{url:string;value:string}[]};
export type PageRedirectEdit = {page_redirect_domain:string;page_redirect_source:string;page_redirect_target:string;page_redirect_original_domain:string;page_redirect_original_source:string;page_redirect_delete:boolean};

export function PageRedirects({groups,domains,canon,revision,available,disabled,onSave}:{groups:PageRedirectGroup[];domains:string[];canon:string;revision:string;available:boolean;disabled:boolean;onSave:(edit:PageRedirectEdit,revision:string)=>Promise<boolean>}) {
  const [edit,setEdit]=React.useState<PageRedirectEdit|null>(null);
  const [saving,setSaving]=React.useState(false);
  const editRevision=React.useRef(revision);
  const sourceInput=React.useRef<HTMLInputElement>(null);
  const valid=groups.filter(g=>g&&typeof g.domain==="string"&&Array.isArray(g.redirects));
  const rows=valid.flatMap(g=>g.redirects.filter(r=>r&&typeof r.url==="string"&&typeof r.value==="string").map(r=>({...r,domain:g.domain})));
  const choices=[...new Set([...domains,...valid.map(g=>g.domain)])].sort((a,b)=>a.localeCompare(b));
  function start(next:PageRedirectEdit){editRevision.current=revision;setEdit(next);}
  function rowEdit(row:typeof rows[number],remove=false){start({page_redirect_domain:row.domain,page_redirect_source:row.url,page_redirect_target:row.value,page_redirect_original_domain:row.domain,page_redirect_original_source:row.url,page_redirect_delete:remove});}
  React.useEffect(()=>{if(edit&&!edit.page_redirect_delete)sourceInput.current?.focus();},[edit?.page_redirect_original_source,edit===null]);
  async function save(event:React.FormEvent){event.preventDefault();if(!edit||saving||disabled)return;setSaving(true);try{if(await onSave(edit,editRevision.current))setEdit(null);}finally{setSaving(false);}}
  return <section className="networkSection networkRedirects networkPageRedirects" aria-label="Постраничные редиректы">
    <div className="networkRedirectsHeading"><h3 className="networkRedirectTitle">Постраничные редиректы<span className="networkRedirectCount" aria-label={`Постраничных редиректов: ${rows.length}`}>{rows.length}</span></h3></div>
    {!available?<p className="muted">Редиректы ещё не получены из Webdev. Нажмите «Обновить данные».</p>:rows.length?<div className="networkTableWrap"><table className="domainRedirectsTable" aria-label="Перенаправления отдельных страниц"><thead><tr><th>Домен</th><th>Откуда</th><th>Куда</th><th>Действия</th></tr></thead><tbody>{rows.map((row,i)=><tr key={`${row.domain}:${row.url}:${i}`}><td>{row.domain}</td><td><code>{row.url}</code></td><td>{/^https?:\/\//i.test(row.value)?<a href={row.value} target="_blank" rel="noopener noreferrer">{row.value}<ExternalLink size={13} aria-hidden="true"/></a>:row.value}</td><td><div className="networkActions"><button type="button" className="button secondary compact" disabled={disabled||!!edit} aria-label={`Изменить постраничный редирект ${row.domain}${row.url}`} onClick={()=>rowEdit(row)}><Pencil size={13}/>Изменить</button><button type="button" className="button secondary compact" disabled={disabled||!!edit} aria-label={`Удалить постраничный редирект ${row.domain}${row.url}`} onClick={()=>rowEdit(row,true)}><Trash2 size={13}/>Удалить</button></div></td></tr>)}</tbody></table></div>:<p className="muted">Постраничных редиректов нет.</p>}
    <div className="networkActions"><button type="button" className="button secondary compact" disabled={disabled||!available||!!edit||!choices.length} onClick={()=>start({page_redirect_domain:choices.includes(canon)?canon:choices[0],page_redirect_source:"",page_redirect_target:"",page_redirect_original_domain:"",page_redirect_original_source:"",page_redirect_delete:false})}><Plus size={14}/>Добавить постраничный редирект</button></div>
    {edit&&<form aria-label={edit.page_redirect_delete?"Удаление постраничного редиректа":edit.page_redirect_original_source?"Редактирование постраничного редиректа":"Новый постраничный редирект"} onSubmit={event=>void save(event)}><fieldset className="networkRedirectForm" style={{border:0,padding:0,margin:0,minWidth:0}} disabled={disabled||saving}>
      {edit.page_redirect_delete?<p>Удалить редирект {edit.page_redirect_domain}{edit.page_redirect_source} → {edit.page_redirect_target}?</p>:<>
        <TemplateCombobox label="Домен редиректа" value={edit.page_redirect_domain} options={choices.map(value=>({value,label:value}))} onChange={value=>setEdit({...edit,page_redirect_domain:value})} placeholder="Найти домен"/>
        <label>Откуда<input ref={sourceInput} aria-label="Постраничный редирект: откуда" value={edit.page_redirect_source} maxLength={2048} autoComplete="off" spellCheck={false} placeholder="/play/" required onChange={e=>setEdit({...edit,page_redirect_source:e.target.value})}/></label>
        <label>Куда<input aria-label="Постраничный редирект: куда" type="url" value={edit.page_redirect_target} maxLength={4096} autoComplete="off" spellCheck={false} placeholder={`https://${canon}/`} required onChange={e=>setEdit({...edit,page_redirect_target:e.target.value})}/></label>
      </>}
      <div className="networkActions"><button type="submit" className="button compact" disabled={!edit.page_redirect_delete&&(!edit.page_redirect_domain||!edit.page_redirect_source.trim()||!edit.page_redirect_target.trim())}>{saving?"Сохраняем…":edit.page_redirect_delete?"Удалить редирект":"Сохранить постраничный редирект"}</button><button type="button" className="button secondary compact" onClick={()=>setEdit(null)}>Отмена</button></div>
      <small className="muted">Изменения сохраняются в Webdev после подтверждения его настройками.</small>
    </fieldset></form>}
  </section>;
}
