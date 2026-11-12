export type MenuMoveItem = {key:string; group:string; title:string; address?:number[]};
export type MenuMove = {source:number[]; target:number[]; position:'before'|'after'};
export function menuMove(source:MenuMoveItem, target:MenuMoveItem, position:MenuMove['position']):MenuMove|null {
  if(source.key===target.key||source.group!==target.group||!source.address||!target.address)return null;
  if(source.address.slice(0,-1).join('.')!==target.address.slice(0,-1).join('.'))return null;
  const from=source.address.at(-1)!,to=target.address.at(-1)!;
  if(position==='before'&&from===to-1||position==='after'&&from===to+1)return null;
  return {source:source.address,target:target.address,position};
}
export function keyboardMenuMove(items:MenuMoveItem[],key:string,direction:-1|1):MenuMove|null {
  const source=items.find(item=>item.key===key);
  if(!source)return null;
  const siblings=items.filter(item=>item.group===source.group);
  const target=siblings[siblings.findIndex(item=>item.key===key)+direction];
  return target?menuMove(source,target,direction<0?'before':'after'):null;
}
