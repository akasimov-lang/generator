import React from 'react';
import {schemeRequest,serialDraftWriter} from './redirectSaveProgress';
import {TemplateCombobox} from './TemplateCombobox';
import {readRedirectDraft,type RedirectDraftRow} from './redirectDraft';
export type BoardSnapshot={positions:Record<string,{x:number;y:number}>;placed:string[];zoom:number;min_height?:number;sizes?:Record<string,{width:number;height:number}>};
export type SchemeDocument={id:string;name:string;kind:'draft'|'scheme'|'backup';saved_at:string;rows:RedirectDraftRow[];board:BoardSnapshot};
export type SchemeApi=<T>(path:string,options?:RequestInit)=>Promise<T>;
type Payload=Pick<SchemeDocument,'kind'|'name'|'rows'|'board'>;
export function readBoard(scope:string):BoardSnapshot {try{return {positions:JSON.parse(localStorage.getItem(`redirect-layout:${scope}`)||'{}'),sizes:JSON.parse(localStorage.getItem(`redirect-sizes:${scope}`)||'{}'),placed:JSON.parse(localStorage.getItem(`redirect-placed:${scope}`)||'[]'),zoom:Number(localStorage.getItem(`redirect-zoom:${scope}`))||1,min_height:Number(localStorage.getItem(`redirect-board-height:${scope}`))||0};}catch{return {positions:{},placed:[],zoom:1};}}
export function RedirectSchemeLibrary({scope,api,rows,onLoad,onLocalSave,onDates,busy,onActivity,autoSave=false,boardVersion=0,getBoard,onServerDraft,onDraftSaved}:{scope:string;api?:SchemeApi;rows:RedirectDraftRow[];onLoad:(doc:SchemeDocument)=>void;onLocalSave:()=>void;onDates:(dates:Record<string,string>)=>void;busy:boolean;onActivity?:(message:string|null)=>void;autoSave?:boolean;boardVersion?:number;getBoard?:()=>BoardSnapshot;onServerDraft?:(doc:SchemeDocument)=>void;onDraftSaved?:(doc:SchemeDocument)=>void}) {
  const [items,setItems]=React.useState<SchemeDocument[]>([]),[selected,setSelected]=React.useState(''),[name,setName]=React.useState(''),[working,setWorking]=React.useState(false),[status,setStatus]=React.useState(''),[serverChecked,setServerChecked]=React.useState(false);
  const workingRef=React.useRef(false),apiRef=React.useRef(api);apiRef.current=api;
  const callbacks=React.useRef({onServerDraft,onDraftSaved});callbacks.current={onServerDraft,onDraftSaved};
  const lastSaved=React.useRef(''),latestSignature=React.useRef('');
  const writeDraft=React.useMemo(()=>serialDraftWriter<Payload,SchemeDocument>(payload=>schemeRequest<SchemeDocument>(apiRef.current!,`/sites/${scope}/network/schemes`,{method:'POST',body:JSON.stringify(payload)})),[scope]);
  function remember(doc:SchemeDocument){setItems(old=>[doc,...old.filter(d=>d.id!==doc.id)]);}
  const loadList=React.useCallback(async()=>{if(!api)return;try{const result=await schemeRequest<{items:SchemeDocument[];draft:SchemeDocument|null;redirect_dates:Record<string,string>}>(api,`/sites/${scope}/network/schemes`,{cache:'no-store'});setItems([...(result.draft?[result.draft]:[]),...result.items]);onDates(result.redirect_dates);if(result.draft)callbacks.current.onServerDraft?.(result.draft);setServerChecked(true);}catch{setStatus('Список схем недоступен. Локальный черновик сохраняется.');}},[api,scope,onDates]);
  React.useEffect(()=>{void loadList();},[loadList]);
  React.useEffect(()=>{
    if(!api||!autoSave||!serverChecked){latestSignature.current='';return;}
    const payload:Payload={kind:'draft',name:'Черновик',rows,board:getBoard?.()||readBoard(scope)},signature=JSON.stringify(payload);latestSignature.current=signature;
    if(lastSaved.current===signature)return;
    let cancelled=false,timer:ReturnType<typeof setTimeout>;
    async function flush(){if(cancelled||lastSaved.current===signature)return;if(workingRef.current){timer=setTimeout(()=>void flush(),300);return;}
      setStatus('Сохраняем черновик на сервере…');
      try{const doc=await writeDraft(payload);lastSaved.current=signature;remember(doc);if(!cancelled&&latestSignature.current===signature){setStatus('Черновик сохранён на сервере');callbacks.current.onDraftSaved?.(doc);}}
      catch(e){if(!cancelled&&latestSignature.current===signature)setStatus(`Автосохранение на сервер не подтверждено: ${e instanceof Error?e.message:String(e)}`);}
    }
    timer=setTimeout(()=>void flush(),1200);return()=>{cancelled=true;clearTimeout(timer);};
  },[api,autoSave,rows,boardVersion,getBoard,scope,writeDraft,serverChecked]);
  async function save(kind:SchemeDocument['kind']) {
    if(busy||workingRef.current)return;workingRef.current=true;setWorking(true);onActivity?.(kind==='draft'?'Сохраняем черновик':kind==='backup'?'Создаём резервную копию':'Сохраняем именованную схему');
    try{onLocalSave();if(!api){setStatus('Черновик сохранён только в этом браузере.');return;}
      const payload:Payload={kind,name:kind==='scheme'?name.trim():kind==='backup'?`Копия ${new Date().toLocaleString('ru-RU',{timeZone:'Europe/Moscow'})} МСК`:'Черновик',rows,board:getBoard?.()||readBoard(scope)};
      if(kind==='draft')latestSignature.current=JSON.stringify(payload);
      const doc=kind==='draft'?await writeDraft(payload):await schemeRequest<SchemeDocument>(api,`/sites/${scope}/network/schemes`,{method:'POST',body:JSON.stringify(payload)});
      remember(doc);setServerChecked(true);setSelected(doc.id);if(kind==='draft'){lastSaved.current=JSON.stringify(payload);callbacks.current.onDraftSaved?.(doc);}
      setStatus(kind==='draft'?'Черновик сохранён на сервере':kind==='backup'?'Резервная копия сохранена':'Схема сохранена');
    }catch(e){setStatus(`Сохранение на сервер не подтверждено: ${e instanceof Error?e.message:String(e)}`);}finally{workingRef.current=false;setWorking(false);onActivity?.(null);}
  }
  async function restore(){if(!api||!selected||busy||workingRef.current)return;workingRef.current=true;setWorking(true);onActivity?.('Открываем сохранённую схему');try{onLocalSave();const doc=await schemeRequest<SchemeDocument>(api,`/sites/${scope}/network/schemes/${selected}`,{cache:'no-store'});if(!readRedirectDraft(JSON.stringify({version:1,rows:doc.rows,saved_at:doc.saved_at})))throw new Error('Некорректная схема');onLoad(doc);setStatus('Схема открыта как черновик. Редиректы ещё не отправлены.');}catch(e){setStatus(String(e));}finally{workingRef.current=false;setWorking(false);onActivity?.(null);}}
  return <><button type="button" className="button secondary compact" disabled={busy||working} onClick={()=>void save('draft')}>Сохранить черновик</button><details className="redirectLibrary"><summary>Схемы и копии</summary><div className="redirectLibraryPanel"><label>Название схемы<input value={name} maxLength={120} placeholder="Например, основная сетка" onChange={e=>setName(e.target.value)}/></label><button className="button secondary compact" disabled={busy||working||!name.trim()} onClick={()=>void save('scheme')}>Сохранить с именем</button><button className="button secondary compact" disabled={busy||working} onClick={()=>void save('backup')}>Резервная копия на сейчас</button><TemplateCombobox label="Сохранённые схемы" value={selected} options={items.map(d=>({value:d.id,label:`${d.name} · ${new Date(d.saved_at).toLocaleString('ru-RU',{timeZone:'Europe/Moscow'})} МСК`}))} onChange={setSelected}/><button className="button secondary compact" disabled={busy||working||!selected} onClick={()=>void restore()}>Открыть как черновик</button><small>Черновик автоматически сохраняется на сервере. Для отдельной версии сохраните схему с именем.</small></div></details>{status&&<small className="redirectLibraryStatus" role="status">{status}</small>}</>;
}
