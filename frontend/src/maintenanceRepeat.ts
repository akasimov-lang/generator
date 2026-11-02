type Api = <T>(path:string,options?:RequestInit)=>Promise<T>;
type Store = Pick<Storage,"getItem"|"setItem"|"removeItem">;
type Request = {request_id:string;allow_reserve:boolean};
type Result = Record<string,unknown> & {id:string;entries:unknown[]};

export const maintenanceReportLink=(id:string)=>`/auto-reglue/pilot/report?maintenance=${encodeURIComponent(id)}`;
export const maintenanceReportActive=(status?:string)=>["queued","running","waiting"].includes(status||"");
export const maintenanceEntriesActive=(report?:{status:string;entries:{status:string}[]}|null)=>!!report&&(maintenanceReportActive(report.status)||report.entries.some(entry=>["pending","queued","running","waiting"].includes(entry.status)));
export const maintenanceCanRepeat=(report?:{status:string;entries:{status:string}[]}|null)=>!!report?.entries.length&&["completed","partial","failed"].includes(report.status)&&report.entries.every(entry=>["completed","partial","failed","skipped"].includes(entry.status));

/** One explicit click creates one durable request; uncertain responses reuse its UUID and settings. */
export function createMaintenanceRepeat(parentId:string,api:Api,store?:Store,makeId=()=>crypto.randomUUID()) {
 const key=`pagepilot:maintenance-repeat:${parentId}`;
 let pending:Request|null=null,flight:Promise<Result>|null=null,accepted:Result|null=null;
 try {
  const saved=JSON.parse(store?.getItem(key)||"null");
  if(saved&&typeof saved.request_id==="string"&&saved.request_id&&typeof saved.allow_reserve==="boolean")pending=saved;
 } catch { /* Session storage is optional; in-memory idempotency remains available. */ }
 const remember=()=>{try{if(pending)store?.setItem(key,JSON.stringify(pending));else store?.removeItem(key);}catch{/* Private-mode storage may be unavailable. */}};
 return {
  pending:()=>pending,
  submit(allowReserve:boolean):Promise<Result> {
   if(accepted)return Promise.resolve(accepted);
   if(flight)return flight;
   if(!pending){pending={request_id:makeId(),allow_reserve:allowReserve};remember();}
   flight=api<unknown>(`/auto-reglue/maintenance-reports/${encodeURIComponent(parentId)}/repeat`,{
    method:"POST",body:JSON.stringify(pending),
   }).then(raw=>{
    const result=raw as Partial<Result>|null;
    if(!result||typeof result.id!=="string"||!result.id||result.id===parentId||!Array.isArray(result.entries))throw new Error("Не удалось подтвердить новый отчёт. Повторите отправку той же заявки.");
    accepted=result as Result;pending=null;remember();return accepted;
   }).catch(error=>{
    // A rejected request cannot have started work. Timeouts/5xx/malformed responses remain uncertain.
    if([400,401,403,404,409,422].includes((error as {statusCode?:number}|null)?.statusCode||0)){pending=null;remember();}
    throw error;
   }).finally(()=>{flight=null;});
   return flight;
  },
 };
}
