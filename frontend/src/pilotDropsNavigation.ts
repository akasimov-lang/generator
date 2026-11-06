import type { PilotSelection } from "./pilotScope";
import type { TitleRewriteMode } from "./titleRewriteModes";

const PILOT="/auto-reglue/pilot";
const ORIGIN="https://pagepilot.invalid";
const UUID=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const SHARE_KEYS=["subdomains","without_alternates","redirects","title_h1","paragraphs"] as const;
const PREFIX="pagepilot:pilot-drops:";
type StorageLike=Pick<Storage,"getItem"|"setItem"|"removeItem">;
export type PilotDraftForm={allowStockDrops?:boolean;selection:PilotSelection;titleMode:TitleRewriteMode;planningMode?:"percentages"|"mixed";shares:Record<typeof SHARE_KEYS[number],string>&{internal_pages?:string}};

/** Only a planner or one exact saved draft can be a return destination. */
export function pilotDraftPath(value:string):string|null {
 if(!value.startsWith("/")||value.startsWith("//")||/[\\\u0000-\u0020]/.test(value))return null;
 try{
  const url=new URL(value,ORIGIN);
  if(url.origin!==ORIGIN||url.pathname!==PILOT||url.hash)return null;
  if([...url.searchParams.keys()].some(key=>key!=="id"&&key!=="new"))return null;
  if(url.searchParams.getAll("id").length>1||url.searchParams.getAll("new").length>1)return null;
  const id=url.searchParams.get("id"),fresh=url.searchParams.get("new");
  if(id!==null&&!UUID.test(id)||fresh!==null&&fresh!=="1")return null;
  return id?`${PILOT}?id=${encodeURIComponent(id)}`:`${PILOT}?new=1`;
 }catch{return null;}
}

export function reserveVisitHref(returnTo:string,token:string):string {
 const path=pilotDraftPath(returnTo);
 if(!path||!UUID.test(token))throw new Error("Некорректный адрес черновика.");
 const params=new URLSearchParams({returnTo:path,pilotState:token});
 return `/auto-reglue/reserves?${params}`;
}

export function reserveReturnHref(search:string):string|null {
 const params=new URLSearchParams(search),raw=params.get("returnTo");
 const path=raw&&pilotDraftPath(raw);
 if(!path||params.getAll("returnTo").length!==1)return null;
 const token=params.get("pilotState");
 return token&&UUID.test(token)?`${path}&resumeDrops=${encodeURIComponent(token)}`:path;
}

function isForm(value:unknown):value is PilotDraftForm {
 if(!value||typeof value!=="object")return false;
 const {selection,titleMode,shares,planningMode}=value as PilotDraftForm;
 const strings=(items:unknown,max:number)=>Array.isArray(items)&&items.length<=max&&items.every(item=>typeof item==="string"&&item.length<=160);
 return !!selection&&strings(selection.brands,5)&&strings(selection.geos,250)&&
  (selection.scope_mode===undefined||["include","exclude"].includes(selection.scope_mode))&&
  ["minimal","full_h1","full_all","mixed"].includes(titleMode)&&
  (planningMode===undefined||["percentages","mixed"].includes(planningMode))&&!!shares&&
  SHARE_KEYS.every(key=>typeof shares[key]==="string"&&shares[key].length<=16)&&
  (shares.internal_pages===undefined||typeof shares.internal_pages==="string"&&shares.internal_pages.length<=16);
}

export function saveDraftForDrops(storage:StorageLike,token:string,returnTo:string,form:PilotDraftForm):boolean {
 const path=pilotDraftPath(returnTo);
 if(!path||!UUID.test(token)||!isForm(form))return false;
 try{storage.setItem(PREFIX+token,JSON.stringify({version:1,returnTo:path,form}));return true;}catch{return false;}
}

/** Reading does not consume state: React may initialize twice in StrictMode. */
export function restoredDraftFromDrops(storage:StorageLike,currentPath:string):{token:string;returnTo:string;form:PilotDraftForm}|null {
 try{
  const url=new URL(currentPath,ORIGIN),token=url.searchParams.get("resumeDrops");
  if(!token||!UUID.test(token)||url.searchParams.getAll("resumeDrops").length!==1)return null;
  url.searchParams.delete("resumeDrops");
  const returnTo=pilotDraftPath(url.pathname+url.search);
  if(!returnTo)return null;
  const saved=JSON.parse(storage.getItem(PREFIX+token)||"null");
  return saved?.version===1&&saved.returnTo===returnTo&&isForm(saved.form)?{token,returnTo,form:saved.form}:null;
 }catch{return null;}
}

export function consumeDraftReturn(storage:StorageLike,token:string):void {
 try{if(UUID.test(token))storage.removeItem(PREFIX+token);}catch{/* A blocked store cannot trigger navigation or planning. */}
}
