import React from 'react';

type Api = <T>(path:string,options?:RequestInit)=>Promise<T>;
type Page = {key:string;slug:string;title:string;description:string;content:Record<string,unknown>;revision:string};
type MenuItem = {title:string;path:string;externalId:string};
export function MenuPageIdentityEditor({api,siteId,menuType,item,sectionId,onSaved,onCancel}:{api:Api;siteId:string;menuType:'header'|'footer';item:MenuItem;sectionId?:string;onSaved:()=>void|Promise<void>;onCancel:()=>void}) {
 const [label,setLabel]=React.useState(item.title);
 const [menuUrl,setMenuUrl]=React.useState(item.path);
 const [pageUrl,setPageUrl]=React.useState(item.path);
 const [page,setPage]=React.useState<Page|null>(null);
 const [loading,setLoading]=React.useState(true);
 const [saving,setSaving]=React.useState(false);
 const [uncertain,setUncertain]=React.useState(false);
 const [error,setError]=React.useState('');
 React.useEffect(()=>{let active=true;(async()=>{
  try {
   const list=await api<{pages:{key:string;slug:string}[]}>(`/sites/${siteId}/pages?refresh=true`);
   const match=list.pages.find(p=>p.slug.replace(/\/$/,'')===item.path.replace(/\/$/,''));
   if(match){const detail=await api<Page>(`/sites/${siteId}/pages/${match.key}?refresh=true`);if(active){setPage(detail);setPageUrl(detail.slug);}}
  }catch(e){if(active)setError(e instanceof Error?e.message:'Не удалось загрузить страницу');}
  finally{if(active)setLoading(false);}
 })();return()=>{active=false;};},[api,siteId,item.path]);
 async function save(){
  setSaving(true);setError('');
  try{
   if(page && pageUrl.trim()!==page.slug){
    setUncertain(true);
    const result=await api<{status:string;error?:string;page?:Page}>(`/sites/${siteId}/pages/${page.key}`,{method:'PUT',body:JSON.stringify({request_id:crypto.randomUUID(),revision:page.revision,title:page.title,description:page.description,content:page.content,slug:pageUrl.trim()})});
    if(result.status==='failed')setUncertain(false);
    if(result.status!=='confirmed'||!result.page)throw new Error(result.error||'Изменение адреса страницы пока не подтверждено. Проверьте страницу перед повтором.');
    setPage(result.page);setUncertain(false);
   }
   let id=sectionId;
   if(!id){const adopted=await api<{section:{id:string}}>(`/sites/${siteId}/sections/adopt`,{method:'POST',body:JSON.stringify({external_id:item.externalId,name:item.title,path:item.path,menu_type:menuType,parent_id:null})});id=adopted.section.id;}
   await api(`/sites/${siteId}/sections/${id}`,{method:'PATCH',body:JSON.stringify({name:label.trim(),path:menuUrl.trim()})});
   const result=await api<{success:boolean;results:{success:boolean;error?:string}[]}>(`/sites/${siteId}/sections/${id}/sync`,{method:'POST'});
   if(!result.success)throw new Error(result.results.find(x=>!x.success)?.error||'Изменения меню пока не подтверждены');
   await onSaved();
  }catch(e){setError(e instanceof Error?e.message:'Не удалось сохранить изменения');}
  finally{setSaving(false);}
 }
 return <div className="menuPageIdentityForm">
  <label>Подпись пункта меню<input value={label} maxLength={160} disabled={saving} onChange={e=>setLabel(e.target.value)}/></label>
  <label>URL пункта меню<input value={menuUrl} maxLength={240} disabled={saving} onChange={e=>setMenuUrl(e.target.value)}/></label>
  <label>URL связанной страницы<input value={pageUrl} maxLength={240} disabled={loading||saving||!page} onChange={e=>{const next=e.target.value;if(menuUrl===pageUrl)setMenuUrl(next);setPageUrl(next);}}/></label>
  <small>{loading?'Загрузка актуальной страницы…':page?'При изменении адреса страницы совпадающая ссылка меню обновляется вместе с ним.':'По этому адресу опубликованная страница не найдена. Можно изменить подпись и ссылку меню.'}</small>
  {uncertain&&!saving&&<p role="status">Адрес страницы требует проверки. Закройте окно и загрузите актуальную страницу перед новой записью.</p>}
  {error&&<p className="formError" role="alert">{error}</p>}
  <div className="modalActions"><button type="button" className="button secondary" onClick={onCancel} disabled={saving}>Отменить</button><button type="button" className="button primary" onClick={()=>void save()} disabled={loading||saving||uncertain||!label.trim()||!menuUrl.trim()}>{saving?'Сохраняем…':'Сохранить'}</button></div>
 </div>;
}
