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

export function isMenuReorderRequest(path:string):boolean {
  return /^\/sites\/[^/?]+\/menu\/(header|footer)\/reorder(?:\?|$)/.test(path);
}

// Clone only the changed branch; keep URLs, IDs and all other fields intact.
export function applyMenuMove(items:unknown[],move:MenuMove):unknown[] {
  const {source,target,position}=move;
  if(!source.length||source.length!==target.length||source.slice(0,-1).join('.')!==target.slice(0,-1).join('.')||[...source,...target].some(index=>!Number.isInteger(index)||index<0))throw new Error('Перемещайте пункты внутри одного раздела меню.');
  const visit=(rows:unknown[],depth:number):unknown[]=>{
    const next=[...rows],index=source[depth];
    if(depth<source.length-1){
      const node=rows[index] as Record<string,unknown>|undefined;
      const key=node&&['children','items','submenu','subMenu'].find(key=>Array.isArray(node[key]));
      if(!node||!key)throw new Error('Меню изменилось. Повторите перемещение.');
      next[index]={...node,[key]:visit(node[key] as unknown[],depth+1)};
      return next;
    }
    const to=target[depth];
    if(!rows[index]||!rows[to]||rows.some(row=>typeof row!=='object'||row===null||Array.isArray(row)))throw new Error('Неподдерживаемый пункт меню.');
    const destination=to-Number(index<to)+Number(position==='after');
    if(index===to||destination===index)return rows;
    next.splice(destination,0,next.splice(index,1)[0]);
    return next.map((row,order)=>({...row as Record<string,unknown>,order}));
  };
  return visit(items,0);
}

export type MenuDragSlot={key:string;top:number;height:number};
// Stable layout coordinates avoid jitter when the displayed siblings move under the pointer.
export function menuDragPreview(slots:MenuDragSlot[],sourceKey:string,pointerY:number) {
  const from=slots.findIndex(slot=>slot.key===sourceKey);
  if(from<0)return null;
  const remaining=slots.filter(slot=>slot.key!==sourceKey);
  const to=remaining.filter(slot=>pointerY>slot.top+slot.height/2).length;
  const target=to<from?slots[to]:to>from?slots[to]:undefined;
  const order=[...slots];order.splice(to,0,order.splice(from,1)[0]);
  let top=slots[0].top;
  const offsets:Record<string,number>={};
  order.forEach((slot,index)=>{
    offsets[slot.key]=top-slot.top;
    const gap=index<slots.length-1?slots[index+1].top-slots[index].top-slots[index].height:0;
    top+=slot.height+gap;
  });
  return {target:target?.key,position:(to<from?'before':'after') as MenuMove['position'],offsets};
}

type MenuApi=<T>(path:string,options?:RequestInit)=>Promise<T>;
export async function persistMenuMove(api:MenuApi,siteId:string,menuType:'header'|'footer',items:unknown[],move:MenuMove,showItems:(items:unknown[])=>void) {
  showItems(applyMenuMove(items,move));
  try {
    const result=await api<{success:boolean;items:unknown[]}>(`/sites/${siteId}/menu/${menuType}/reorder`,{
      method:'POST',body:JSON.stringify({...move,expected_menu:items}),
    });
    if(!result.success||!Array.isArray(result.items))throw new Error('Сохранение порядка не подтверждено.');
    showItems(result.items);
  }catch(error){
    showItems(items);
    // A conflict may have loaded newer Webdev data into the project cache.
    // Fetch just that project; never reload the workspace or retry the write.
    try {
      const actual=await api<{default_menu:Record<string,unknown>}>(`/sites/lookup?site_id=${encodeURIComponent(siteId)}`,{cache:'no-store'});
      if(Array.isArray(actual.default_menu?.[menuType]))showItems(actual.default_menu[menuType] as unknown[]);
    }catch{/* Keep the previous order and the original save error. */}
    throw error;
  }
}
