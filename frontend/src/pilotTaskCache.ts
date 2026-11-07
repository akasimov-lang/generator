// Small per-tab snapshots. The authenticated user and current permission scope must match.
const PREFIX = "pagepilot-plan-list-v1:";
const MAX_AGE = 15 * 60_000;
type Store = Pick<Storage, "getItem" | "setItem" | "removeItem" | "key" | "length">;
export function readPilotTasks<T>(scope:string,path:string,storage:Store=sessionStorage):T|null {
 try {
  const value=JSON.parse(storage.getItem(PREFIX+path)||"null");
  if(!value||value.scope!==scope||Date.now()-value.at>MAX_AGE)return null;
  return value.data as T;
 } catch {return null;}
}
export function savePilotTasks<T>(scope:string,path:string,data:T,storage:Store=sessionStorage):void {
 try {
  const keys=Array.from({length:storage.length},(_,i)=>storage.key(i)).filter((key):key is string=>!!key&&key.startsWith(PREFIX));
  if(keys.length>=30)storage.removeItem(keys[0]);
  storage.setItem(PREFIX+path,JSON.stringify({scope,path,data,at:Date.now()}));
 } catch { /* Storage can be unavailable; server-side cache still works. */ }
}
export function clearPilotTasks(storage:Store=sessionStorage):void {
 try {
  Array.from({length:storage.length},(_,i)=>storage.key(i)).forEach(key=>{if(key?.startsWith(PREFIX))storage.removeItem(key);});
 } catch { /* Logout and mutations must not depend on browser storage. */ }
}
