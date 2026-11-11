export type GroupedTask = {id:string;group?:string;launched_at?:string;created_at?:string};
const dayFormat=new Intl.DateTimeFormat('ru-RU',{timeZone:'Europe/Moscow',day:'2-digit',month:'2-digit',year:'numeric'});
export function pilotTaskTime(task:GroupedTask):number {
 const value=task.launched_at||task.created_at;
 if(!value)return NaN;
 // Database timestamps without an offset are UTC, regardless of the browser zone.
 return Date.parse(/[zZ]|[+-]\d{2}:?\d{2}$/.test(value)?value:`${value}Z`);
}
export function pilotTaskDays<T extends GroupedTask>(items:T[]) {
 const groups:{date:string;items:T[]}[]=[];
 for(const item of items){
  const time=pilotTaskTime(item),date=Number.isFinite(time)?dayFormat.format(time):'Дата не указана';
  const last=groups.at(-1);
  if(last?.date===date)last.items.push(item);else groups.push({date,items:[item]});
 }
 return groups;
}
export function pilotTaskCollectionPath(query:string):string {
 const params=new URLSearchParams();
 if(query.trim())params.set("q",query.trim());
 return `/auto-reglue/pilot/task-collection?${params}`;
}
export function pilotTaskView<T extends GroupedTask>(items:T[],group:string,offset=0,limit=50) {
 const filtered=(group==="all"?[...items]:items.filter(item=>(item.group??"other")===group))
  .sort((a,b)=>(Number.isFinite(pilotTaskTime(b))?pilotTaskTime(b):-Infinity)-(Number.isFinite(pilotTaskTime(a))?pilotTaskTime(a):-Infinity));
 const start=Math.min(Math.max(0,offset),Math.max(0,Math.floor((filtered.length-1)/limit)*limit));
 return {items:filtered.slice(start,start+limit),total:filtered.length,has_more:start+limit<filtered.length,offset:start};
}
