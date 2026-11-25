import React from 'react';
import {Trash2} from 'lucide-react';
import {TemplateCombobox} from './TemplateCombobox';
import {NetworkEditStatus} from './NetworkEditStatus';
import {RedirectSectionSaveStatus,type RedirectSaveFeedback} from './RedirectSectionSaveStatus';
import {editActive,type NetworkEditQueueView} from './networkEditQueue';
import {pageRedirectDraftKey,readPageRedirectDraft,type PageRedirectRow as Row} from './pageRedirectDraft';
import {redirectTableColumns} from './redirectTableColumns';
import type {PageRedirectEdit,PageRedirectGroup} from './PageRedirects';
import './styles/domain-redirects.css';
export function PageRedirectWorkspace({groups,domains,canon,revision,available,disabled,onSave,queue,scope='network',draftOwner=''}:{scope?:string;draftOwner?:string;queue?:NetworkEditQueueView;groups:PageRedirectGroup[];domains:string[];canon:string;revision:string;available:boolean;disabled:boolean;onSave:(edit:PageRedirectEdit,revision:string)=>Promise<boolean>}) {
  const storageKey=pageRedirectDraftKey(scope,draftOwner);
  const [draft,setDraft]=React.useState<Row[]|null>(()=>{try{return readPageRedirectDraft(localStorage.getItem(storageKey));}catch{return null;}});
  const [saving,setSaving]=React.useState(false),[error,setError]=React.useState(''),[persisted,setPersisted]=React.useState(false),[storageError,setStorageError]=React.useState('');
  const lock=React.useRef(false);
  const saved=React.useMemo<Row[]>(()=>groups.flatMap(g=>g.redirects.map(r=>({...r,domain:g.domain,id:crypto.randomUUID(),original:{...r,domain:g.domain}}))),[groups]);
  const rows:Row[]=draft||saved;
  const items=(queue?.items||[]).filter(i=>i.request.action==='page_redirect');
  const pending=items.some(editActive);
  const blocked=disabled||saving||pending||!available;
  const changes=rows.filter(r=>r.removed||!r.original||r.domain!==r.original.domain||r.url!==r.original.url||r.value!==r.original.value);
  React.useEffect(()=>{try{if(draft)localStorage.setItem(storageKey,JSON.stringify({version:1,rows:draft}));else localStorage.removeItem(storageKey);setPersisted(true);setStorageError('');}catch{setPersisted(false);setStorageError('Хранилище браузера недоступно. Не закрывайте вкладку до отправки изменений.');}},[draft,storageKey]);
  React.useEffect(()=>{if(!draft||persisted)return;const warn=(event:BeforeUnloadEvent)=>event.preventDefault();window.addEventListener('beforeunload',warn);return()=>window.removeEventListener('beforeunload',warn);},[draft,persisted]);
  const choices=[...new Set([...domains,...groups.map(g=>g.domain),...rows.map(r=>r.domain)].filter(Boolean))].sort();
  const paths=[...new Set(groups.flatMap(g=>g.redirects.map(r=>r.url)))].sort();
  const targets=[...new Set(groups.flatMap(g=>g.redirects.map(r=>r.value)))].sort();
  const options=(values:string[])=>values.map(value=>({value,label:value}));
  function update(id:string,patch:Partial<Row>){setDraft(rows.map(r=>r.id===id?{...r,...patch}:r));setPersisted(false);setError('');}
  async function submit(){
    if(lock.current||blocked||!changes.length)return;
    lock.current=true;setSaving(true);setError('');let rest=[...rows];
    try{
      const sources=new Set<string>();
      for(const r of rows.filter(r=>!r.removed)){
        const key=JSON.stringify([r.domain,r.url]);
        if(sources.has(key))throw new Error(`Повторяется источник ${r.domain}${r.url}`);
        sources.add(key);
        if(!r.domain||!r.url.startsWith('/')||r.url.startsWith('//')||!/^https?:\/\//i.test(r.value))throw new Error('Заполните домен, путь откуда и полный адрес назначения.');
        try{const target=new URL(r.value);if(!target.hostname)throw new Error();}catch{throw new Error(`Некорректный адрес назначения: ${r.value}`);}
      }
      for(const r of changes){
        const ok=await onSave({page_redirect_domain:r.domain,page_redirect_source:r.url,page_redirect_target:r.value,page_redirect_original_domain:r.original?.domain||'',page_redirect_original_source:r.original?.url||'',page_redirect_delete:!!r.removed,expected:{rows:r.original?[{url:r.original.url,value:r.original.value}]:[]}},revision);
        if(!ok)throw new Error('Неотправленные строки остались в редакторе. Проверьте очередь.');
        rest=r.removed?rest.filter(row=>row.id!==r.id):rest.map(row=>row.id===r.id?{...row,original:{domain:r.domain,url:r.url,value:r.value}}:row);
        setDraft(rest);
      }
      setDraft(null);
    }catch(e){setError(e instanceof Error?e.message:String(e));}finally{lock.current=false;setSaving(false);}
  }
  const failed=items.find(i=>i.status==='failed');
  const feedback:RedirectSaveFeedback=error||storageError?{state:'error',detail:error||storageError}:saving||pending?{state:'saving',detail:'Ожидаем подтверждение изменений от Webdev.'}:failed?{state:'error',detail:'Не все редиректы подтверждены. Проверьте статус строки.'}:changes.length?{state:persisted?'saved':'idle',detail:persisted?'Черновик сохранён в этом браузере. Изменения ещё не отправлены в Webdev.':'Черновик ещё не сохранён.'}:{state:'saved',detail:'Настройки получены из Webdev.'};
  return <section className="networkSection networkRedirects redirectCompactSection" aria-label="Постраничные редиректы">
    <div className="networkRedirectsHeading"><h3>Постраничные редиректы · {rows.filter(r=>!r.removed).length}</h3>{available&&<RedirectSectionSaveStatus {...feedback}/>}</div>
    <div className="redirectWorkspaceBody">
      {!available?<p role="status">Обновите данные, чтобы получить редиректы из Webdev.</p>:<>
        <div className="redirectSupportingBody"><div className="redirectTables redirectPageTables">{redirectTableColumns(rows).map((column,index)=><fieldset className="redirectTableField" disabled={blocked} key={index}>
          <table className="redirectEditTable" aria-label={`Постраничные редиректы · ${index+1}`}><thead><tr><th scope="col">Домен</th><th scope="col">Откуда</th><th scope="col">Куда · 301</th><th scope="col"><span className="redirectVisuallyHidden">Удаление</span></th></tr></thead><tbody>{column.map(r=><tr key={r.id} className={r.removed?'removed':''}>
            <td><TemplateCombobox portal label={`Домен редиректа: ${r.domain||'новая строка'}`} value={r.domain} options={options(choices)} onChange={domain=>update(r.id,{domain})}/></td>
            <td><TemplateCombobox portal label={`Откуда: ${r.domain}${r.url}`} value={r.url} options={options(paths)} allowCustom placeholder="/old-page/" onChange={url=>update(r.id,{url:url.replace(/\s/g,'')})}/></td>
            <td><TemplateCombobox portal label={`Куда: ${r.domain}${r.url}`} value={r.value} options={options(targets)} allowCustom placeholder={`https://${canon}/new-page/`} onChange={value=>update(r.id,{value:value.replace(/\s/g,'')})}/><NetworkEditStatus item={queue?.latest(`page:${r.original?.domain||r.domain}:${r.original?.url||r.url}`)} retry={id=>queue?.retry(id)}/></td>
            <td><button type="button" className="redirectTrashButton" aria-label={`${r.removed?'Отменить удаление':'Удалить редирект'} ${r.domain}${r.url}`} title={r.removed?'Отменить удаление':'Удалить редирект'} aria-pressed={!!r.removed} onClick={()=>{if(!r.original)setDraft(rows.filter(row=>row.id!==r.id));else update(r.id,{removed:!r.removed});}}><Trash2 size={15} aria-hidden="true"/></button></td>
          </tr>)}</tbody></table>
        </fieldset>)}</div></div>
        <div className="networkActions"><button type="button" className="button secondary compact" disabled={blocked} onClick={()=>{setPersisted(false);setDraft([...rows,{id:crypto.randomUUID(),domain:canon||choices[0]||'',url:'',value:''}]);}}>Добавить строку</button>{changes.length>0&&<button type="button" className="button secondary compact" disabled={saving} onClick={()=>{setDraft(null);setError('');}}>Отменить изменения</button>}<button type="button" className={`button compact redirectSubmitButton${changes.length?' hasChanges':''}`} disabled={blocked||!changes.length} onClick={()=>void submit()}>{saving?'Отправляем…':`Отправить изменения${changes.length?` (${changes.length})`:''}`}</button></div>
      </>}
      {error&&<p role="alert">{error}</p>}
      {items.filter(i=>editActive(i)||i.status==='failed').map(i=><div key={i.id}><small>{String(i.request.page_redirect_domain)}{String(i.request.page_redirect_source)}</small><NetworkEditStatus item={i} retry={id=>queue?.retry(id)}/></div>)}
    </div>
  </section>;
}
