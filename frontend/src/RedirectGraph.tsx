import React from 'react';
import { host, type RedirectRow } from './redirectScheme';
export function RedirectGraph({domains,rows,types,scope,onConnect}:{domains:string[];rows:RedirectRow[];types:Record<string,string>;scope:string;onConnect:(from:string,to:string)=>void}) {
  const nodes=[...new Set([...domains,...rows.flatMap(r=>[r.url,host(r.value)])])].filter((d,i,a)=>a.findIndex(v=>host(v)===host(d))===i);
  const [positions,setPositions]=React.useState<Record<string,{x:number;y:number}>>(()=>{try{return JSON.parse(localStorage.getItem(`redirect-layout:${scope}`)||'{}');}catch{return {};}});
  const [source,setSource]=React.useState('');
  const drag=React.useRef<{domain:string;x:number;y:number;left:number;top:number}|null>(null);
  const point=(domain:string)=>positions[host(domain)]||{x:types[domain]==='drop'?30:460,y:30+nodes.filter(n=>(types[n]==='drop')===(types[domain]==='drop')).indexOf(domain)*100};
  const persist=(next:typeof positions)=>{try{localStorage.setItem(`redirect-layout:${scope}`,JSON.stringify(next));}catch{ /* layout is optional */ }};
  const height=Math.max(450,...nodes.map(d=>point(d).y+100));
  return <><p>Перетаскивайте карточки за название. Для связи нажмите «Связать» у источника, затем «Выбрать целью» у назначения. С клавиатуры карточки перемещаются стрелками.</p>
    {source&&<p role="status">Источник: {source} <button type="button" onClick={()=>setSource('')}>Отменить связь</button></p>}
    <div className="redirectGraphScroll"><div className="redirectGraph" style={{height,width:Math.max(820,...nodes.map(d=>point(d).x+310))}}>
      <svg width="100%" height="100%" aria-label="Связи 301"><defs><marker id="redirect-tip" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8" fill="#6477cb"/></marker></defs>{rows.map((r,i)=>{const from=nodes.find(d=>host(d)===host(r.url)),to=nodes.find(d=>host(d)===host(r.value));if(!from||!to)return null;const a=point(from),b=point(to);return <g key={i}><line x1={a.x+135} y1={a.y+38} x2={b.x+135} y2={b.y+38} stroke="#6477cb" strokeWidth="2" markerEnd="url(#redirect-tip)"/><text x={(a.x+b.x)/2+135} y={(a.y+b.y)/2+30}>301</text></g>;})}</svg>
      {nodes.map(domain=>{const p=point(domain);return <div className={`redirectNode ${types[domain]||''}`} key={domain} style={{left:p.x,top:p.y}} onDragOver={e=>e.preventDefault()} onDrop={e=>{e.preventDefault();const from=e.dataTransfer.getData("text/redirect-source");if(from&&from!==domain)onConnect(from,domain);}}>
        <div className="redirectNodeHandle" role="button" tabIndex={0} aria-label={`Переместить ${domain}`} onPointerDown={e=>{e.currentTarget.setPointerCapture(e.pointerId);drag.current={domain,x:e.clientX,y:e.clientY,left:p.x,top:p.y};}} onPointerMove={e=>{const d=drag.current;if(d?.domain===domain)setPositions(old=>({...old,[host(domain)]:{x:Math.max(0,d.left+e.clientX-d.x),y:Math.max(0,d.top+e.clientY-d.y)}}));}} onPointerUp={()=>{drag.current=null;persist(positions);}} onPointerCancel={()=>{drag.current=null;}} onKeyDown={e=>{if(!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key))return;e.preventDefault();const next={...positions,[host(domain)]:{x:Math.max(0,p.x+(e.key==='ArrowRight'?20:e.key==='ArrowLeft'?-20:0)),y:Math.max(0,p.y+(e.key==='ArrowDown'?20:e.key==='ArrowUp'?-20:0))}};setPositions(next);persist(next);}}>{domain}</div>
        <small>{types[domain]==='drop'?'Дроп':types[domain]==='newreg'?'Новорег':'Тип не указан'}</small>
        <button type="button" draggable onDragStart={e=>{e.dataTransfer.setData("text/redirect-source",domain);e.dataTransfer.effectAllowed="link";}} title="Нажмите или перетащите на домен назначения" disabled={source===domain} onClick={()=>{if(source){onConnect(source,domain);setSource('');}else setSource(domain);}}>{source?'Выбрать целью':'Связать'}</button>
      </div>;})}
    </div></div></>;
}
