type EventSource = Pick<EventTarget, "addEventListener" | "removeEventListener">;
type VisibilitySource = EventSource & {readonly hidden:boolean};
type TimerId = ReturnType<typeof setTimeout>;
type Timers = {setTimeout:(callback:()=>void,delay:number)=>TimerId;clearTimeout:(id:TimerId)=>void};

/** Refresh visible screens without overlapping slow requests or polling hidden tabs. */
export function createVisiblePoll({load,intervalMs,onError,immediate=false,page=document,focusTarget=window,timers=globalThis}:{
 load:()=>Promise<unknown>;intervalMs:number|(()=>number);onError?:(error:unknown)=>void;immediate?:boolean;
 page?:VisibilitySource;focusTarget?:EventSource|null;timers?:Timers;
}):()=>void {
 let stopped=false,busy=false,timer:TimerId|undefined;
 const clear=()=>{if(timer!==undefined){timers.clearTimeout(timer);timer=undefined;}};
 const schedule=()=>{
  clear();
  if(!stopped&&!page.hidden)timer=timers.setTimeout(()=>{void refresh();},typeof intervalMs==="function"?intervalMs():intervalMs);
 };
 const refresh=async()=>{
  if(stopped||busy||page.hidden)return;
  clear();busy=true;
  try{await load();}catch(error){if(!stopped)onError?.(error);}
  finally{busy=false;schedule();}
 };
 const visibility=()=>{if(page.hidden)clear();else void refresh();};
 const focus=()=>{void refresh();};
 page.addEventListener("visibilitychange",visibility);
 focusTarget?.addEventListener("focus",focus);
 if(immediate)void refresh();else schedule();
 return ()=>{stopped=true;clear();page.removeEventListener("visibilitychange",visibility);focusTarget?.removeEventListener("focus",focus);};
}

/** Concurrent reads share a request; post-write refreshes wait for one fresh read. */
export function createCoalescedLoader(load:()=>Promise<void>):(fresh?:boolean)=>Promise<void> {
 let flight:Promise<void>|null=null,next:Promise<void>|null=null,queuedFor:Promise<void>|null=null;
 const request=(fresh=false):Promise<void>=>{
  if(flight){
   if(!fresh)return flight;
   if(queuedFor!==flight){
    const previous=flight;queuedFor=previous;
    next=previous.catch(()=>{}).then(()=>request()).finally(()=>{if(queuedFor===previous){next=null;queuedFor=null;}});
   }
   return next!;
  }
  flight=Promise.resolve().then(load).finally(()=>{flight=null;});
  return flight;
 };
 return request;
}
