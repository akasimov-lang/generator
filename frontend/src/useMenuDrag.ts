import React from 'react';
import {menuMove,keyboardMenuMove,menuDragPreview,type MenuMoveItem,type MenuMove,type MenuDragSlot} from './menuReorder';
import './styles/menu-reorder.css';

type Drag = {
  source:MenuMoveItem;startX:number;startY:number;x:number;y:number;pointer:number;active:boolean;
  move:MenuMove|null;handle:HTMLButtonElement;list:HTMLElement;viewport:HTMLElement;
  slots:(MenuDragSlot&{node:HTMLElement;item:MenuMoveItem})[];listTop:number;
  overlay?:HTMLElement;offsetX:number;offsetY:number;frame?:number;lastFrame?:number;
};
export function useMenuDrag(items:MenuMoveItem[],revision:unknown,disabled:boolean,onMove?:(move:MenuMove,title:string)=>Promise<void>) {
  const ref=React.useRef<Drag|null>(null);
  const [message,setMessage]=React.useState('');
  const cancel=React.useCallback(()=>{
    const drag=ref.current;ref.current=null;
    if(!drag)return;
    if(drag.frame!==undefined)cancelAnimationFrame(drag.frame);
    drag.overlay?.remove();
    drag.slots.forEach(({node})=>{node.style.removeProperty('transform');node.classList.remove('menuDragSibling','menuDragPlaceholder');});
    document.body.classList.remove('menuDragActive');
    if(drag.handle.hasPointerCapture(drag.pointer))drag.handle.releasePointerCapture(drag.pointer);
  },[]);
  React.useEffect(()=>{cancel();return cancel;},[revision,disabled,cancel]);
  React.useEffect(()=>{
    const key=(event:KeyboardEvent)=>{if(event.key==='Escape'&&ref.current){event.preventDefault();cancel();setMessage('Перемещение отменено.');}};
    window.addEventListener('keydown',key);window.addEventListener('resize',cancel);window.addEventListener('blur',cancel);
    return()=>{window.removeEventListener('keydown',key);window.removeEventListener('resize',cancel);window.removeEventListener('blur',cancel);};
  },[cancel]);

  function paint(drag:Drag) {
    if(!drag.overlay)return;
    drag.overlay.style.transform=`translate3d(${drag.x-drag.offsetX}px,${drag.y-drag.offsetY}px,0)`;
    const bounds=drag.viewport.getBoundingClientRect();
    const inside=drag.x>=bounds.left-24&&drag.x<=bounds.right+24&&drag.y>=bounds.top-32&&drag.y<=bounds.bottom+32;
    const delta=drag.list.getBoundingClientRect().top-drag.listTop;
    const preview=inside?menuDragPreview(drag.slots,drag.source.key,drag.y-delta):null;
    const target=drag.slots.find(slot=>slot.key===preview?.target)?.item;
    drag.move=target&&preview?menuMove(drag.source,target,preview.position):null;
    drag.slots.forEach(({key,node})=>{
      node.style.transform=`translateY(${drag.move?preview?.offsets[key]||0:0}px)`;
    });
  }
  function start(drag:Drag) {
    const row=drag.handle.closest<HTMLElement>('[data-menu-reorder-key]');
    if(!row)return;
    const bounds=row.getBoundingClientRect();
    const rows=Array.from(drag.list.children).filter((node):node is HTMLElement=>node instanceof HTMLElement);
    drag.listTop=drag.list.getBoundingClientRect().top;
    drag.slots=rows.flatMap(node=>{
      const key=node.querySelector<HTMLElement>('[data-menu-reorder-key]')?.dataset.menuReorderKey;
      const item=items.find(item=>item.key===key);
      if(!item)return [];
      const rect=node.getBoundingClientRect();
      return [{key:item.key,item,node,top:rect.top,height:rect.height}];
    });
    drag.offsetX=drag.startX-bounds.left;drag.offsetY=drag.startY-bounds.top;
    const overlay=row.cloneNode(true) as HTMLElement;
    overlay.classList.add('menuDragOverlay');overlay.setAttribute('aria-hidden','true');overlay.inert=true;
    overlay.querySelectorAll('[id]').forEach(node=>node.removeAttribute('id'));
    overlay.removeAttribute('data-menu-reorder-key');
    overlay.style.width=`${bounds.width}px`;
    document.body.appendChild(overlay);drag.overlay=overlay;drag.active=true;
    drag.slots.forEach(({key,node})=>{node.classList.add('menuDragSibling');if(key===drag.source.key)node.classList.add('menuDragPlaceholder');});
    document.body.classList.add('menuDragActive');
    setMessage(`Перемещение: ${drag.source.title}. Escape — отмена.`);
    const frame=(now:number)=>{
      if(ref.current!==drag)return;
      const rect=drag.viewport.getBoundingClientRect();
      const step=Math.min(32,now-(drag.lastFrame??now))/16;
      drag.lastFrame=now;
      if(drag.x>=rect.left-24&&drag.x<=rect.right+24){
        if(drag.y>=rect.top-32&&drag.y<rect.top+36)drag.viewport.scrollTop-=10*step;
        else if(drag.y<=rect.bottom+32&&drag.y>rect.bottom-36)drag.viewport.scrollTop+=10*step;
      }
      paint(drag);drag.frame=requestAnimationFrame(frame);
    };
    paint(drag);drag.frame=requestAnimationFrame(frame);
  }
  function locate(event:React.PointerEvent<HTMLButtonElement>) {
    const drag=ref.current;if(!drag||event.pointerId!==drag.pointer)return;
    drag.x=event.clientX;drag.y=event.clientY;
    if(!drag.active&&Math.hypot(drag.x-drag.startX,drag.y-drag.startY)>=5)start(drag);
  }
  function save(move:MenuMove|null,title:string) {
    if(!move||disabled||!onMove)return;
    setMessage(`Сохраняем порядок: ${title}.`);
    void onMove(move,title).then(()=>setMessage(`Новый порядок сохранён: ${title}.`)).catch(()=>setMessage('Не удалось сохранить порядок.'));
  }
  return {message,handle:(item:MenuMoveItem)=>({
    disabled:disabled||!onMove||!item.address,
    title:'Перетащите для изменения порядка. С клавиатуры: Alt + ↑ / ↓.',
    'aria-label':`Изменить порядок: ${item.title}`,
    'aria-keyshortcuts':'Alt+ArrowUp Alt+ArrowDown',
    onPointerDown:(event:React.PointerEvent<HTMLButtonElement>)=>{
      if(event.button!==0||disabled||!onMove||!item.address||ref.current)return;
      const list=event.currentTarget.closest('li')?.parentElement;
      const viewport=event.currentTarget.closest<HTMLElement>('.siteMenuTreeViewport');
      if(!list||!viewport)return;
      event.preventDefault();event.currentTarget.focus();
      ref.current={source:item,startX:event.clientX,startY:event.clientY,x:event.clientX,y:event.clientY,pointer:event.pointerId,active:false,move:null,handle:event.currentTarget,list,viewport,slots:[],listTop:0,offsetX:0,offsetY:0};
      event.currentTarget.setPointerCapture(event.pointerId);
    },
    onPointerMove:locate,
    onPointerUp:(event:React.PointerEvent<HTMLButtonElement>)=>{
      if(event.pointerId!==ref.current?.pointer)return;
      locate(event);const drag=ref.current;
      if(drag.active)paint(drag);
      const move=drag.move;cancel();save(move,drag.source.title);
    },
    onPointerCancel:cancel,onLostPointerCapture:cancel,
    onKeyDown:(event:React.KeyboardEvent<HTMLButtonElement>)=>{
      if(!ref.current&&event.altKey&&['ArrowUp','ArrowDown'].includes(event.key)){
        event.preventDefault();save(keyboardMenuMove(items,item.key,event.key==='ArrowUp'?-1:1),item.title);
      }
    },
  })};
}
