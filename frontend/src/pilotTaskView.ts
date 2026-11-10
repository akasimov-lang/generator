export type GroupedTask = {id:string;group?:string};
export function pilotTaskCollectionPath(query:string):string {
 const params=new URLSearchParams();
 if(query.trim())params.set("q",query.trim());
 return `/auto-reglue/pilot/task-collection?${params}`;
}
export function pilotTaskView<T extends GroupedTask>(items:T[],group:string,offset=0,limit=50) {
 const filtered=group==="all"?items:items.filter(item=>(item.group??"other")===group);
 const start=Math.min(Math.max(0,offset),Math.max(0,Math.floor((filtered.length-1)/limit)*limit));
 return {items:filtered.slice(start,start+limit),total:filtered.length,has_more:start+limit<filtered.length,offset:start};
}
