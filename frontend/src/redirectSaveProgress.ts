import type {NetworkEditItem} from './networkEditQueue';
export type RedirectSaveBatch={ids:string[];total:number;sent:number};
export type RedirectSaveState={busy:boolean;label:string;detail:string;value?:number;max?:number;failed?:number};
export function redirectSaveProgress(items:NetworkEditItem[],batch:RedirectSaveBatch|null,submitting:boolean,libraryPhase:string|null):RedirectSaveState|null {
  if(libraryPhase)return {busy:true,label:libraryPhase,detail:'Ожидаем подтверждение сохранения от сервера.'};
  const relevant=items.filter(i=>['domain_redirect','domain_redirects_main'].includes(i.request.action));
  const active=relevant.filter(i=>!['completed','failed'].includes(i.status));
  if(submitting)return {busy:true,label:'Отправляем изменения',detail:`Принято в очередь: ${batch?.sent||0} из ${batch?.total||0}`,value:batch?.sent||0,max:batch?.total||1};
  const known=batch?relevant.filter(i=>batch.ids.includes(i.id)):[];
  const completed=known.filter(i=>i.status==='completed').length,failed=known.filter(i=>i.status==='failed').length;
  if(active.length){const uncertain=active.some(i=>i.status==='unconfirmed');return {busy:true,label:uncertain?'Проверяем статус отправки':'Сохраняем редиректы в Webdev',detail:batch?`Подтверждено: ${completed} из ${batch.total}${failed?` · Ошибок: ${failed}`:''} · В очереди: ${active.length}`:`Ожидаем подтверждение · В очереди: ${active.length}`,value:batch?completed+failed:undefined,max:batch?.total,failed};}
  if(batch?.sent)return {busy:false,label:failed?'Сохранение завершено с ошибками':completed===batch.total?'Изменения подтверждены':'Отправка завершена',detail:`Подтверждено: ${completed} из ${batch.total}${failed?` · Ошибок: ${failed}`:''}`,value:completed+failed,max:batch.total,failed};
  return null;
}
export async function schemeRequest<T>(api:<R>(path:string,options?:RequestInit)=>Promise<R>,path:string,options?:RequestInit,timeoutMs=20000):Promise<T> {
  const controller=new AbortController();let timer:ReturnType<typeof setTimeout>|undefined;
  try{return await Promise.race([api<T>(path,{...options,signal:controller.signal}),new Promise<T>((_,reject)=>{timer=setTimeout(()=>{controller.abort();reject(new Error('Сервер не ответил вовремя. Сохранение на сервер не подтверждено; не закрывайте вкладку и проверьте список схем перед повтором.'));},timeoutMs);})]);}
  finally{if(timer!==undefined)clearTimeout(timer);}
}

/** Preserve write order so an older background save cannot overwrite a newer draft. */
export function serialDraftWriter<TPayload,TResult>(write:(payload:TPayload)=>Promise<TResult>) {
  let tail:Promise<unknown>=Promise.resolve();
  return (payload:TPayload)=>{const next=tail.catch(()=>undefined).then(()=>write(payload));tail=next;return next;};
}

export function shouldRestoreServerDraft(serverSavedAt:string,localSavedAt:string|undefined,userEdited:boolean) {
  return !userEdited&&(!localSavedAt||Date.parse(serverSavedAt)>Date.parse(localSavedAt));
}
