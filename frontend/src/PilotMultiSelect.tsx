import React from "react";
import { Check, ChevronDown } from "lucide-react";
import { toggleSelection, type PilotOption } from "./pilotScope";

export function PilotMultiSelect({label,allLabel,clearLabel,values,options,total,onChange,max}:{
 label:string;allLabel:string;clearLabel?:string;values:string[];options:PilotOption[];total:number;onChange:(values:string[])=>void;max?:number;
}){
 const id=React.useId(),input=React.useRef<HTMLInputElement>(null),list=React.useRef<HTMLDivElement>(null);
 const [open,setOpen]=React.useState(false),[query,setQuery]=React.useState<string|null>(null),[active,setActive]=React.useState(0);
 const selected=values.map(value=>options.find(option=>option.value===value)?.label||value).join(", ")||allLabel;
 const normalized=(query||"").trim().toLocaleLowerCase();
 const all:PilotOption={value:"",label:clearLabel||allLabel,count:total,pinned:true};
 const filtered=[all,...options].filter(option=>`${option.label} ${option.value}`.toLocaleLowerCase().includes(normalized));
 const pinned=filtered.filter(option=>option.pinned),ordinary=filtered.filter(option=>!option.pinned),ordered=[...pinned,...ordinary];
 const atLimit=max!==undefined&&values.length>=max;
 const blocked=(option:PilotOption)=>!!option.disabled||!!(option.value&&atLimit&&!values.includes(option.value));
 function show(){setQuery(null);setActive(0);setOpen(true);}
 function close(){setOpen(false);setQuery(null);}
 function choose(option:PilotOption){if(blocked(option))return;onChange(toggleSelection(values,option.value,max));setQuery(null);setActive(0);}
 React.useEffect(()=>{setActive(index=>Math.min(index,Math.max(0,ordered.length-1)));},[ordered.length]);
 React.useEffect(()=>{if(open)list.current?.querySelector(`[data-index="${active}"]`)?.scrollIntoView({block:"nearest"});},[open,active]);
 const optionRow=(option:PilotOption,index:number)=><div key={option.value} role="option" id={`${id}-option-${index}`} data-index={index}
  aria-selected={option.value?values.includes(option.value):!values.length} aria-disabled={blocked(option)}
  className={index===active?"active":""} onMouseDown={event=>event.preventDefault()} onClick={()=>choose(option)}>
  <span>{option.label}</span>{(option.value||!clearLabel)&&<span className="pilotOptionCount">{option.count}</span>}{(option.value?values.includes(option.value):!values.length)&&<Check size={16}/>}</div>;
 return <div className="tg-combobox pilotMultiSelect" onBlur={event=>{if(!event.currentTarget.contains(event.relatedTarget as Node))close();}}>
  <label htmlFor={id}>{label}{max&&<small> · до {max} брендов</small>}</label>
  <div className="tg-combobox-control"><input id={id} ref={input} role="combobox" aria-expanded={open} aria-autocomplete="list" aria-controls={`${id}-list`}
   aria-activedescendant={open&&ordered[active]?`${id}-option-${active}`:undefined} title={selected} value={query??selected}
   autoComplete="off" spellCheck={false} onFocus={event=>{show();event.target.select();}} onClick={()=>{if(!open)show();}}
   onChange={event=>{setQuery(event.target.value);setActive(0);setOpen(true);}}
   onKeyDown={event=>{
    if(event.key==="ArrowDown"||event.key==="ArrowUp"){event.preventDefault();if(!open)show();else setActive(index=>Math.max(0,Math.min(ordered.length-1,index+(event.key==="ArrowDown"?1:-1))));}
    else if(event.key==="Enter"&&open){event.preventDefault();if(ordered[active])choose(ordered[active]);}
    else if(event.key==="Escape"){event.preventDefault();close();}
    else if(event.key==="Tab")close();
   }}/><button type="button" tabIndex={-1} aria-label={`Открыть список: ${label}`} onMouseDown={event=>event.preventDefault()} onClick={()=>{if(open)close();else{input.current?.focus();show();}}}><ChevronDown size={18}/></button></div>
  {open&&<div ref={list} id={`${id}-list`} role="listbox" aria-label={label} aria-multiselectable="true" className="tg-combobox-list">
   {!!pinned.length&&<div role="presentation" className="pilotPinnedOptions">{pinned.map(optionRow)}</div>}
   {ordinary.map((option,index)=>optionRow(option,index+pinned.length))}
   {!ordered.length&&<p role="status">Ничего не найдено. Попробуйте название или код.</p>}
   {atLimit&&<p role="status">Выбрано {max} брендов. Снимите выбор, чтобы добавить другой.</p>}
  </div>}
 </div>;
}
