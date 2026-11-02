export type PageEditFields = {title:string;description:string;content:Record<string,unknown>};
export type PageEditPayload = PageEditFields & {request_id:string;revision:string};
export type SavedPageDraft = PageEditPayload & {saved_at:string;status:"draft"|"pending"|"unknown"|"failed"};
export type PageSaveReceipt<T=unknown> = {id:string;status:string;error?:string;page?:T};
type DraftStorage = Pick<Storage,"getItem"|"setItem"|"removeItem">;

export function editablePageFingerprint(value:PageEditFields):string {
  return JSON.stringify([value.title,value.description,value.content]);
}

export function pageDraftStorageKey(actorId:string,siteId:string,pageKey:string):string {
  return `pagepilot:page-editor-draft:v1:${[actorId,siteId,pageKey].map(encodeURIComponent).join(":")}`;
}

export function readPageDraft(storage:DraftStorage,key:string):SavedPageDraft|null {
  try {
    const value=JSON.parse(storage.getItem(key)||"null");
    if(!value||typeof value.request_id!=="string"||!/^[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$/i.test(value.request_id)||typeof value.revision!=="string"||!/^[0-9a-f]{64}$/.test(value.revision)||typeof value.title!=="string"||typeof value.description!=="string"||!value.content||!Array.isArray(value.content.blocks)||typeof value.saved_at!=="string"||!["draft","pending","unknown","failed"].includes(value.status))return null;
    return value;
  }catch{return null;}
}

export function writePageDraft(storage:DraftStorage,key:string,draft:SavedPageDraft):boolean {
  try {const value=JSON.stringify(draft);storage.setItem(key,value);return storage.getItem(key)===value;}catch{return false;}
}

export function clearPageDraft(storage:DraftStorage,key:string,requestId:string):void {
  try {if(readPageDraft(storage,key)?.request_id===requestId)storage.removeItem(key);}catch{/* Keep the server copy if browser storage is unavailable. */}
}

export function preparePageDraft(page:PageEditFields&{revision:string},previous:SavedPageDraft|null,newId:()=>string,now=()=>new Date().toISOString()):SavedPageDraft {
  const same=previous&&previous.status!=="failed"&&previous.revision===page.revision&&editablePageFingerprint(previous)===editablePageFingerprint(page);
  return {request_id:same?previous.request_id:newId(),revision:page.revision,title:page.title,description:page.description,content:page.content,saved_at:now(),status:"draft"};
}

export function newestPageDraft(local:SavedPageDraft|null,server:SavedPageDraft|null):SavedPageDraft|null {
  if(!local)return server;
  if(!server)return local;
  if(local.request_id===server.request_id)return {...server,status:server.status==="draft"?local.status:server.status};
  const localTime=Date.parse(local.saved_at),serverTime=Date.parse(server.saved_at);
  return Number.isFinite(localTime)&&(!Number.isFinite(serverTime)||localTime>serverTime)?local:server;
}

export async function persistPageDraft({draft,storage,key,saveServer,onLocalSaved}:{draft:SavedPageDraft;storage:DraftStorage|null;key:string|null;saveServer:(payload:PageEditPayload)=>Promise<unknown>;onLocalSaved?:()=>void}):Promise<{local:boolean;server:boolean;error?:unknown}> {
  const local=!!storage&&!!key&&writePageDraft(storage,key,draft);
  if(local)onLocalSaved?.();
  const {request_id,revision,title,description,content}=draft;
  try {await saveServer({request_id,revision,title,description,content});return {local,server:true};}
  catch(error){return {local,server:false,error};}
}

export async function recoverPageSave<T>(draft:SavedPageDraft,readReceipt:(requestId:string)=>Promise<PageSaveReceipt<T>>):Promise<{draft:SavedPageDraft;operation:PageSaveReceipt<T>|null;notFound:boolean;error?:unknown}> {
  try {
    const operation=await readReceipt(draft.request_id);
    return {draft:{...draft,status:operation.status==="failed"?"failed":["pending","unknown"].includes(operation.status)?operation.status as "pending"|"unknown":"draft"},operation,notFound:false};
  }catch(error){
    const notFound=(error as {statusCode?:number})?.statusCode===404;
    return {draft:{...draft,status:notFound?"draft":"unknown"},operation:notFound?null:{id:draft.request_id,status:"unknown"},notFound,error};
  }
}
