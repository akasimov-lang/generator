import React from 'react';
import { TemplateCombobox } from './TemplateCombobox';
import type { PageRedirectEdit,PageRedirectGroup } from './PageRedirects';
export function FakeRedirectControls({paths,current,canon,enabled,disabled,available,groups,onToggle,onSave}:{paths:string[];current:string;canon:string;enabled:boolean;disabled:boolean;available:boolean;groups:PageRedirectGroup[];onToggle:(value:boolean)=>Promise<boolean>;onSave:(edit:PageRedirectEdit)=>Promise<boolean>}) {
  const [source,setSource]=React.useState(''),[target,setTarget]=React.useState(''),[error,setError]=React.useState(''),[saving,setSaving]=React.useState(false);
  const options=[...new Set(paths.flatMap(p=>[p.replace(/\/$/,''),p.replace(/\/$/,'')+'/']))];
  async function perform(action:()=>Promise<boolean>){setSaving(true);setError('');try{if(!await action())throw new Error('Изменение не подтверждено. Проверьте статус операции.');}catch(e){setError(String(e));}finally{setSaving(false);}}
  return <div className="fakeRedirectControls"><label>301 со старых фейковых страниц на текущую <button type="button" role="switch" aria-checked={enabled} disabled={disabled||saving} onClick={()=>void perform(()=>onToggle(!enabled))}>{enabled?'Включено':'Выключено'}</button></label>
    <p className="muted">Текущий путь: {current||'не выбран'}. Выберите направление для варианта со слешем или без слеша.</p>
    <fieldset disabled={disabled||saving||!available} className="redirectEditorRow"><TemplateCombobox label="Фейковая страница: откуда" value={source} options={options.filter(p=>p!==current).map(p=>({value:p,label:p}))} onChange={setSource}/><TemplateCombobox label="Фейковая страница: куда" value={target} options={paths.filter(p=>p!==source).map(p=>({value:p,label:p}))} onChange={setTarget}/><button type="button" className="button secondary compact" disabled={!source||!target||source===target} onClick={()=>void perform(async()=>{const existing=groups.filter(g=>g.domain===canon).flatMap(g=>g.redirects.filter(r=>r.url===source));const ok=await onSave({page_redirect_domain:canon,page_redirect_source:source,page_redirect_target:`https://${canon}${target}`,page_redirect_original_domain:existing.length?canon:'',page_redirect_original_source:existing.length?source:'',page_redirect_delete:false,expected:{rows:existing}});if(ok){setSource('');setTarget('');}return ok;})}>Отправить 301</button></fieldset>
    <p className="muted">Чтобы изменить формат действующей страницы, сначала назначьте нужный путь текущим, затем направьте на него другой вариант.</p>{error&&<p role="alert">{error}</p>}
  </div>;
}
