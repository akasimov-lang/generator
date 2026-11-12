import React from 'react';
import {menuMove,keyboardMenuMove,type MenuMoveItem,type MenuMove} from './menuReorder';
import './styles/menu-reorder.css';

type Drag = {source:MenuMoveItem;x:number;y:number;pointer:number;active:boolean;target?:MenuMoveItem;position:'before'|'after';handle:HTMLButtonElement};
export function useMenuDrag(items:MenuMoveItem[],revision:unknown,disabled:boolean,onMove?:(move:MenuMove)=>Promise<void>) {
  const ref=React.useRef<Drag|null>(null);
  const [hint,setHint]=React.useState<{source:string;target?:string;position?:string}|null>(null);
  const [message,setMessage]=React.useState('');
  const cancel=React.useCallback(()=>{
    const drag=ref.current;ref.current=null;setHint(null);
    if(drag?.handle.hasPointerCapture(drag.pointer))drag.handle.releasePointerCapture(drag.pointer);
  },[]);
  React.useEffect(()=>{cancel();},[revision,disabled,cancel]);
  React.useEffect(()=>{
    const key=(event:KeyboardEvent)=>{if(event.key==='Escape'&&ref.current){event.preventDefault();cancel();setMessage('Перемещение отменено.');}};
    window.addEventListener('keydown',key);
    return()=>window.removeEventListener('keydown',key);
  },[cancel]);
  function locate(event:React.PointerEvent<HTMLButtonElement>) {
    const drag=ref.current;if(!drag)return;
    if(!drag.active&&Math.hypot(event.clientX-drag.x,event.clientY-drag.y)<5)return;
    drag.active=true;
    const row=document.elementFromPoint(event.clientX,event.clientY)?.closest<HTMLElement>('[data-menu-reorder-key]');
    const target=items.find(item=>item.key===row?.dataset.menuReorderKey);
    const own=drag.handle.closest('section');
    const position=row&&event.clientY>row.getBoundingClientRect().top+row.getBoundingClientRect().height/2?'after':'before';
    drag.target=target&&own?.contains(row!)&&menuMove(drag.source,target,position)?target:undefined;
    drag.position=position;
    setHint({source:drag.source.key,target:drag.target?.key,position});
    const viewport=own?.querySelector('.siteMenuTreeViewport');
    if(viewport){const rect=viewport.getBoundingClientRect();if(event.clientY<rect.top+30)viewport.scrollTop-=18;else if(event.clientY>rect.bottom-30)viewport.scrollTop+=18;}
  }
  function save(move:MenuMove|null,title:string) {
    if(!move||disabled||!onMove)return;
    setMessage(`Сохраняем порядок: ${title}.`);
    void onMove(move).then(()=>setMessage(`Порядок сохранён: ${title}.`)).catch(()=>setMessage('Не удалось сохранить порядок.'));
  }
  return {hint,message,handle:(item:MenuMoveItem)=>({
    disabled:disabled||!onMove||!item.address,
    title:'Перетащите для изменения порядка. С клавиатуры: Alt + ↑ / ↓.',
    'aria-label':`Изменить порядок: ${item.title}`,
    'aria-keyshortcuts':'Alt+ArrowUp Alt+ArrowDown',
    onPointerDown:(event:React.PointerEvent<HTMLButtonElement>)=>{
      if(event.button!==0||disabled||!onMove||!item.address)return;
      event.preventDefault();event.currentTarget.focus();
      ref.current={source:item,x:event.clientX,y:event.clientY,pointer:event.pointerId,active:false,position:'before',handle:event.currentTarget};
      event.currentTarget.setPointerCapture(event.pointerId);
    },
    onPointerMove:locate,
    onPointerUp:(event:React.PointerEvent<HTMLButtonElement>)=>{
      if(ref.current)locate(event);
      const drag=ref.current;const move=drag?.active&&drag.target?menuMove(drag.source,drag.target,drag.position):null;
      cancel();if(drag)save(move,drag.source.title);
    },
    onPointerCancel:cancel,onLostPointerCapture:cancel,
    onKeyDown:(event:React.KeyboardEvent<HTMLButtonElement>)=>{
      if(event.altKey&&['ArrowUp','ArrowDown'].includes(event.key)){
        event.preventDefault();save(keyboardMenuMove(items,item.key,event.key==='ArrowUp'?-1:1),item.title);
      }
    },
  })};
}
