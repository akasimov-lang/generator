import React from 'react';
import { TemplateCombobox } from './TemplateCombobox';
import { NetworkEditStatus } from './NetworkEditStatus';
import { editActive, type NetworkEditQueueView } from './networkEditQueue';
import type { PageRedirectEdit,PageRedirectGroup } from './PageRedirects';
type Row={id:string;domain:string;url:string;value:string;original?:{domain:string;url:string;value:string};removed?:boolean};
export function PageRedirectWorkspace({groups,domains,canon,revision,available,disabled,onSave,queue}:{queue?:NetworkEditQueueView;groups:PageRedirectGroup[];domains:string[];canon:string;revision:string;available:boolean;disabled:boolean;onSave:(edit:PageRedirectEdit,revision:string)=>Promise<boolean>}) {
  const [draft,setDraft]=React.useState<Row[]|null>(null),[saving,setSaving]=React.useState(false),[error,setError]=React.useState('');
  const lock=React.useRef(false);
  const saved=React.useMemo<Row[]>(()=>groups.flatMap(g=>g.redirects.map(r=>({...r,domain:g.domain,id:crypto.randomUUID(),original:{...r,domain:g.domain}}))),[groups]);
  const rows:Row[]=draft||saved;
  const pending=(queue?.items||[]).some(i=>i.request.action==='page_redirect'&&editActive(i));
  const blocked=disabled||saving||pending||!available;
  const changes=rows.filter(r=>r.removed||!r.original||r.domain!==r.original.domain||r.url!==r.original.url||r.value!==r.original.value);
  React.useEffect(()=>{if(!draft)return;const warn=(event:BeforeUnloadEvent)=>event.preventDefault();window.addEventListener("beforeunload",warn);return()=>window.removeEventListener("beforeunload",warn);},[draft]);
  const choices=[...new Set([...domains,...groups.map(g=>g.domain)])].sort();
  function update(id:string,patch:Partial<Row>){setDraft(rows.map(r=>r.id===id?{...r,...patch}:r));}
  async function submit(){if(lock.current||blocked)return;lock.current=true;setSaving(true);setError('');let rest=[...rows];try{const sources=new Set();for(const r of rows.filter(r=>!r.removed)){const key=r.domain+r.url;if(sources.has(key))throw new Error(`Повторяется источник ${key}`);sources.add(key);if(!r.domain||!r.url.startsWith('/')||!/^https?:\/\//i.test(r.value))throw new Error('Заполните домен, путь откуда и полный адрес назначения.');}for(const r of changes){const ok=await onSave({page_redirect_domain:r.domain,page_redirect_source:r.url,page_redirect_target:r.value,page_redirect_original_domain:r.original?.domain||'',page_redirect_original_source:r.original?.url||'',page_redirect_delete:!!r.removed,expected:{rows:r.original?[{url:r.original.url,value:r.original.value}]:[]}},revision);if(!ok)throw new Error('Неотправленные строки остались в редакторе. Проверьте очередь.');rest=r.removed?rest.filter(row=>row.id!==r.id):rest.map(row=>row.id===r.id?{...row,original:{domain:r.domain,url:r.url,value:r.value}}:row);setDraft(rest);}setDraft(null);}catch(e){setError(String(e));}finally{lock.current=false;setSaving(false);}}
  return <section className="networkSection networkRedirects" aria-label="Постраничные редиректы"><h3>Постраничные редиректы · {rows.filter(r=>!r.removed).length}</h3><p className="muted">В том числе фейковые страницы: /page и /page/ — разные адреса. Подготовьте все строки и отправьте изменения вместе.</p>
    {!available&&<p>Обновите данные, чтобы получить редиректы из Webdev.</p>}{error&&<p role="alert">{error}</p>}
    <div className="networkActions"><button className="button secondary compact" disabled={blocked} onClick={()=>setDraft([...rows,{id:crypto.randomUUID(),domain:canon||choices[0]||'',url:'',value:''}])}>Добавить строку</button><button className="button compact" disabled={blocked||!changes.length} onClick={()=>void submit()}>{saving?'Отправляем…':'Отправить изменения'}</button>{draft&&<button className="button secondary compact" disabled={saving} onClick={()=>setDraft(null)}>Отменить изменения</button>}</div>
    <div className="redirectEditorColumns">{rows.map(r=><fieldset className={`redirectPageRow${r.removed?' removed':''}`} disabled={blocked} key={r.id}><TemplateCombobox label="Домен редиректа" value={r.domain} options={choices.map(d=>({value:d,label:d}))} onChange={domain=>update(r.id,{domain})}/><label>Откуда<input value={r.url} placeholder="/old-page/" onChange={e=>update(r.id,{url:e.target.value.replace(/\s/g,'')})}/></label><label>Куда · 301<input value={r.value} placeholder={`https://${canon}/new-page/`} onChange={e=>update(r.id,{value:e.target.value.replace(/\s/g,'')})}/></label><button className="button secondary compact" onClick={()=>{if(!r.original)setDraft(rows.filter(row=>row.id!==r.id));else update(r.id,{removed:!r.removed});}}>{r.removed?'Вернуть':'Удалить'}</button></fieldset>)}</div>
    {(queue?.items||[]).filter(i=>i.request.action==='page_redirect').map(i=><div key={i.id}><small>{String(i.request.page_redirect_domain)}{String(i.request.page_redirect_source)}</small><NetworkEditStatus item={i} retry={id=>queue?.retry(id)}/></div>)}
  </section>;
}
