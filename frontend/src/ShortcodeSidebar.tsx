import React from "react";

export type ShortcodeInfo = {name:string;uses_on_site:number;pages_count:number;defined:boolean|null};
export function shortcodeUses(content:unknown) {
  const uses=new Map<string,number[]>();
  const blocks=(content as {blocks?:unknown[]})?.blocks;
  if (!Array.isArray(blocks)) return uses;
  blocks.forEach((raw,index)=>{
    const block=raw as {type?:string;data?:unknown};
    if(block?.type!=="shortcode")return;
    const value=typeof block.data==="string"?block.data:(block.data as {shortcode?:unknown})?.shortcode;
    if(typeof value!=="string"||!value.trim())return;
    const name=value.trim().replace(/\.hbs$/,'');
    uses.set(name,[...(uses.get(name)||[]),index]);
  });
  return uses;
}

export function ShortcodeSidebar({content,catalog=[],onNavigate}:{content:unknown;catalog?:ShortcodeInfo[];onNavigate?:(index:number)=>void}) {
  const uses=shortcodeUses(content);
  const last=React.useRef(new Map<string,number>());
  const definitions=new Map(catalog.map(row=>[row.name,row]));
  const names=[...new Set([...definitions.keys(),...uses.keys()])].sort((a,b)=>Number(uses.has(b))-Number(uses.has(a))||a.localeCompare(b));
  return <aside className="pp-shortcode-sidebar" aria-label="Шорткоды сайта"><h3>Шорткоды <small>{names.length}</small></h3><p>На странице: {Array.from(uses.values()).reduce((n,indices)=>n+indices.length,0)}</p>
    {!names.length?<p>На странице нет шорткодов.</p>:<ul>{names.map(name=>{
      const info=definitions.get(name),indices=uses.get(name)||[];
      const jump=()=>{const previous=last.current.get(name);const index=indices.find(i=>previous===undefined||i>previous)??indices[0];last.current.set(name,index);onNavigate?.(index);};
      return <li key={name} className={indices.length?'used':''}>
        {onNavigate&&indices.length?<button type="button" onClick={jump} title="Перейти к следующему блоку" aria-label={`Перейти к шорткоду ${name}`}><code>{name}</code><strong>×{indices.length}</strong></button>:<span><code>{name}</code>{indices.length>0&&<strong>×{indices.length}</strong>}</span>}
        <small>{info?`В блоках сайта: ${info.uses_on_site} · Страниц: ${info.pages_count}`:'На открытой странице'}{info?.defined===false?' · Нет определения':''}</small>
      </li>;
    })}</ul>}
  </aside>;
}
